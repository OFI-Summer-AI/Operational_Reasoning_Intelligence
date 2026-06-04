"""ChromaDB vector store for incident similarity search."""
import time
from typing import Any

import chromadb
import structlog

from layers.ingestion.schema import SimilarIncident, UnifiedIncident
from layers.ingestion.text_utils import normalize_unicode_text
from layers.memory.embedder import Embedder

logger = structlog.get_logger(__name__)


class IncidentVectorStore:
    """Manages incident embeddings in ChromaDB."""

    def __init__(
        self,
        persist_dir: str = "./data/chromadb",
        collection_name: str = "ori_incidents",
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_cache_dir: str = "./data/embedding_cache",
    ) -> None:
        self.embedder = Embedder(model_name=embedding_model, cache_dir=embedding_cache_dir)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "vector_store.ready",
            collection=collection_name,
            existing_count=self._collection.count(),
        )

    def _incident_to_text(self, incident: UnifiedIncident) -> str:
        parts = [incident.title, incident.description]
        parts.extend(incident.signals[:10])
        if incident.deployment_notes:
            parts.append(incident.deployment_notes)
        return " ".join(filter(None, parts))

    def upsert(self, incidents: list[UnifiedIncident]) -> None:
        """Add or update incidents in the vector store."""
        if not incidents:
            return

        texts = [self._incident_to_text(inc) for inc in incidents]
        t0 = time.monotonic()
        embeddings = self.embedder.embed_batch(texts)
        embed_ms = int((time.monotonic() - t0) * 1000)

        self._collection.upsert(
            ids=[inc.incident_id for inc in incidents],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "title": normalize_unicode_text(inc.title)[:200],
                    "severity": inc.severity,
                    "affected_system": inc.affected_system,
                    "source_dataset": inc.source_dataset,
                    "true_root_cause": inc.true_root_cause or "",
                    "description": normalize_unicode_text(inc.description)[:500],
                }
                for inc in incidents
            ],
        )
        logger.info(
            "vector_store.upserted",
            count=len(incidents),
            embed_latency_ms=embed_ms,
            total_count=self._collection.count(),
        )

    def similarity_search(self, query: str, k: int = 3) -> list[SimilarIncident]:
        """Return top-k most similar incidents to the query string."""
        t0 = time.monotonic()
        query_vec = self.embedder.embed(query)
        results = self._collection.query(
            query_embeddings=[query_vec],
            n_results=min(k, max(self._collection.count(), 1)),
            include=["metadatas", "distances", "documents"],
        )
        latency = int((time.monotonic() - t0) * 1000)

        similar: list[SimilarIncident] = []
        ids = results["ids"][0] if results["ids"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        for inc_id, meta, dist in zip(ids, metadatas, distances):
            score = 1.0 - float(dist)  # cosine distance → similarity
            similar.append(
                SimilarIncident(
                    incident_id=inc_id,
                    title=normalize_unicode_text(meta.get("title", "")),
                    description=normalize_unicode_text(meta.get("description", "")),
                    root_cause=meta.get("true_root_cause") or None,
                    similarity_score=round(score, 4),
                    source_dataset=meta.get("source_dataset", "unknown"),
                )
            )

        top_score = similar[0].similarity_score if similar else 0.0
        logger.info(
            "chromadb.retrieved",
            k=len(similar),
            top_score=top_score,
            latency_ms=latency,
        )
        return similar

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        """Delete all vectors — for debugging/testing only."""
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection.name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.warning("vector_store.reset", collection=self._collection.name)
