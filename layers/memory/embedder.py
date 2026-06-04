"""Sentence-transformer embedding wrapper with disk cache."""
import hashlib
import json
import os
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class Embedder:
    """Wraps sentence-transformers with a simple disk cache."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: str = "./data/embedding_cache",
    ) -> None:
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._model = None  # Lazy-load

    def _get_model(self):
        if self._model is None:
            import time
            from sentence_transformers import SentenceTransformer

            t0 = time.monotonic()
            self._model = SentenceTransformer(self.model_name)
            logger.info(
                "embedder.model_loaded",
                model=self.model_name,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
        return self._model

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model_name}:{text}".encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def embed(self, text: str) -> list[float]:
        """Embed a single text string (cached)."""
        key = self._cache_key(text)
        cache_file = self._cache_path(key)
        if cache_file.exists():
            logger.debug("embedder.cache_hit", key=key[:8])
            return json.loads(cache_file.read_text())
        vec = self._get_model().encode(text, normalize_embeddings=True).tolist()
        cache_file.write_text(json.dumps(vec))
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, using cache where available."""
        import time

        uncached: list[tuple[int, str]] = []
        result: list[list[float] | None] = [None] * len(texts)

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            cache_file = self._cache_path(key)
            if cache_file.exists():
                result[i] = json.loads(cache_file.read_text())
            else:
                uncached.append((i, text))

        if uncached:
            t0 = time.monotonic()
            vecs = self._get_model().encode(
                [t for _, t in uncached], normalize_embeddings=True, show_progress_bar=False
            ).tolist()
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.info("embedder.batch_encoded", count=len(uncached), latency_ms=elapsed)
            for (i, text), vec in zip(uncached, vecs):
                result[i] = vec
                key = self._cache_key(text)
                self._cache_path(key).write_text(json.dumps(vec))

        return result  # type: ignore[return-value]
