import pytest
from regulaforge.graphrag.infrastructure.embedding_model import EmbeddingModel


class TestEmbeddingModel:
    def test_fallback_embedding(self):
        model = EmbeddingModel()
        vec = model.embed(["test"])
        assert len(vec) == 1
        assert len(vec[0]) == 384

    def test_embed_query(self):
        model = EmbeddingModel()
        vec = model.embed_query("test query")
        assert len(vec) == 384

    def test_embed_batch(self):
        model = EmbeddingModel()
        texts = ["first text", "second text", "third text"]
        model = EmbeddingModel()
        vectors = model.embed(texts)
        assert len(vectors) == 3
        assert all(len(v) == 384 for v in vectors)

    def test_embed_consistency(self):
        model = EmbeddingModel()
        v1 = model.embed_query("Reserve Bank of India")
        v2 = model.embed_query("Reserve Bank of India")
        # Fallback uses hash, so same input should produce same output
        assert v1 == v2

    def test_embed_different_inputs(self):
        model = EmbeddingModel()
        v1 = model.embed_query("RBI")
        v2 = model.embed_query("SEBI")
        assert v1 != v2

    def test_fallback_vectors_are_normalized(self):
        model = EmbeddingModel()
        vec = model.embed_query("test")
        norm = sum(v * v for v in vec) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_dimension_property(self):
        model = EmbeddingModel()
        assert model.dimension == 384

    def test_empty_text(self):
        model = EmbeddingModel()
        vec = model.embed_query("")
        assert len(vec) == 384

    def test_model_name_default(self):
        model = EmbeddingModel()
        assert model.model_name == "all-MiniLM-L6-v2"

    def test_device_default(self):
        model = EmbeddingModel()
        assert model.device == "cpu"
