import asyncio
import threading
from collections import OrderedDict
from hashlib import sha256
from pathlib import Path

from qdrant_client import QdrantClient, models

from app.config import Settings
from app.rag.embeddings import EmbeddingModel
from app.rag.ingestion import load_documents


COLLECTION = "dishcare_knowledge"


class KnowledgeBase:

    def __init__(
        self,
        settings: Settings,
    ):

        self.settings = settings

        self.embedding = EmbeddingModel(
            settings.embedding_model
        )

        settings.qdrant_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = QdrantClient(
            path=str(settings.qdrant_path),
            force_disable_check_same_thread=True,
        )

        self.lock = threading.Lock()
        self.query_cache = OrderedDict()

    def initialize(self):

        documents = load_documents(
            Path(__file__).resolve().parents[2]
            / "knowledge_base"
        )

        if not documents:
            raise RuntimeError(
                "Knowledge base has no documents"
            )

        with self.lock:
            self.query_cache.clear()

            if self.client.collection_exists(
                COLLECTION
            ):

                self.client.delete_collection(
                    COLLECTION
                )

            self.client.create_collection(
                collection_name=COLLECTION,
                vectors_config=models.VectorParams(
                    size=self.embedding.dimension,
                    distance=models.Distance.COSINE,
                ),
            )

            vectors = self.embedding.embed([
                doc["text"]
                for doc in documents
            ])

            points = [
                models.PointStruct(
                    id=doc["id"],
                    vector=vector,
                    payload={
                        "source": doc["source"],
                        "title": doc["title"],
                        "text": doc["text"],
                    },
                )
                for doc, vector in zip(
                    documents,
                    vectors,
                )
            ]

            self.client.upsert(
                collection_name=COLLECTION,
                points=points,
            )

        print(
            f"Indexed {len(documents)} document chunks"
        )

    def _retrieve(
        self,
        query: str,
    ) -> list[dict]:

        cache_key = sha256(query.encode()).digest()
        with self.lock:
            cached = self.query_cache.get(cache_key)
            if cached is not None:
                self.query_cache.move_to_end(cache_key)
                return [item.copy() for item in cached]
            vector = self.embedding.embed([query])[0]

            response = self.client.query_points(
                collection_name=COLLECTION,
                query=vector,
                limit=self.settings.rag_top_k,
                score_threshold=0.25,
                with_payload=True,
            )

            documents = [
                {
                    "source": point.payload["source"],
                    "text": point.payload["text"],
                    "score": round(point.score, 4),
                }
                for point in response.points
            ]
            self.query_cache[cache_key] = documents
            if len(self.query_cache) > 128:
                self.query_cache.popitem(last=False)
            return [item.copy() for item in documents]

    async def retrieve(
        self,
        query: str,
    ) -> list[dict]:

        return await asyncio.to_thread(
            self._retrieve,
            query,
        )

    def close(self):

        self.client.close()