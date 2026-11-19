from sentence_transformers import SentenceTransformer


class EmbeddingModel:

    def __init__(self, model_name: str):

        self.model = SentenceTransformer(
            model_name,
            device="cpu",
        )

        self.dimension = (
            self.model.get_sentence_embedding_dimension()
        )

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return vectors.tolist()