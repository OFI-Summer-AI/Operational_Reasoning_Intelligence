"""Tests for the memory layer."""
import pytest
from layers.ingestion.schema import UnifiedIncident
from layers.memory.embedder import Embedder
from layers.memory.vector_store import IncidentVectorStore


@pytest.fixture
def embedder(tmp_path):
    return Embedder(model_name="all-MiniLM-L6-v2", cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def vector_store(tmp_path):
    return IncidentVectorStore(
        persist_dir=str(tmp_path / "chromadb"),
        collection_name="test_incidents",
        embedding_model="all-MiniLM-L6-v2",
        embedding_cache_dir=str(tmp_path / "cache"),
    )


def test_embedder_single(embedder):
    vec = embedder.embed("database connection pool exhausted")
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(v, float) for v in vec)


def test_embedder_cache(embedder, tmp_path):
    text = "test text for caching"
    vec1 = embedder.embed(text)
    vec2 = embedder.embed(text)
    assert vec1 == vec2


def test_embedder_batch(embedder):
    texts = ["incident one", "incident two", "incident three"]
    vecs = embedder.embed_batch(texts)
    assert len(vecs) == 3
    assert all(isinstance(v, list) for v in vecs)


def test_vector_store_upsert_and_count(vector_store, sample_incident):
    assert vector_store.count() == 0
    vector_store.upsert([sample_incident])
    assert vector_store.count() == 1


def test_vector_store_similarity_search(vector_store, sample_incident):
    vector_store.upsert([sample_incident])
    results = vector_store.similarity_search("database connection pool exhausted", k=1)
    assert len(results) == 1
    assert results[0].incident_id == sample_incident.incident_id
    assert results[0].similarity_score > 0


def test_vector_store_reset(vector_store, sample_incident):
    vector_store.upsert([sample_incident])
    assert vector_store.count() == 1
    vector_store.reset()
    assert vector_store.count() == 0


def test_vector_store_idempotent_upsert(vector_store, sample_incident):
    vector_store.upsert([sample_incident])
    vector_store.upsert([sample_incident])  # same ID → update, not duplicate
    assert vector_store.count() == 1
