from app.config import Settings
from app.rag.embeddings import EmbeddingModel


def main():

    settings = Settings()

    model = EmbeddingModel(
        settings.embedding_model
    )

    vectors = model.embed([
        "My television has no signal",
        "मेरे टीवी में सिग्नल नहीं आ रहा है",
    ])

    print("Embedding model ready")
    print("Dimensions:", model.dimension)
    print("Vectors generated:", len(vectors))


if __name__ == "__main__":
    main()