import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


EMBEDDING_FORMAT_VERSION = 1


@dataclass(frozen=True)
class EmbeddingIndex:
    item_ids: List[str]
    embeddings: np.ndarray
    _rows: Dict[str, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_rows",
            {item_id: index for index, item_id in enumerate(self.item_ids)},
        )

    def get(self, item_id: str) -> np.ndarray:
        try:
            row = self._rows[item_id]
        except KeyError:
            raise KeyError(f"Embedding not found for item: {item_id}") from None
        return self.embeddings[row]


class EmbeddingStore:
    def __init__(
        self,
        cache_dir: Path,
        embedding_service: Any,
        rebuild: bool = False,
    ):
        self.cache_dir = Path(cache_dir)
        self.embedding_service = embedding_service
        self.rebuild = rebuild

    def load_or_build(
        self,
        dataset_name: str,
        source_path: Path,
        item_ids: List[str],
        texts: List[str],
        embedding_input: str,
    ) -> EmbeddingIndex:
        if len(item_ids) != len(texts):
            raise ValueError("Item IDs and embedding texts must have equal length.")
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("Embedding item IDs must be unique.")

        source_path = Path(source_path)
        identity = self._identity(source_path, embedding_input, len(item_ids))
        npz_path, manifest_path = self._cache_paths(dataset_name)

        if not self.rebuild:
            cached = self._load_valid_cache(
                npz_path,
                manifest_path,
                identity,
                item_ids,
            )
            if cached is not None:
                return cached

        index = self._build(item_ids, texts)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        np.savez(
            npz_path,
            item_ids=np.asarray(item_ids, dtype=np.str_),
            embeddings=index.embeddings,
        )
        manifest = dict(identity)
        manifest["dimension"] = int(index.embeddings.shape[1])
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return index

    def _build(self, item_ids: List[str], texts: List[str]) -> EmbeddingIndex:
        if not texts:
            embeddings = np.empty((0, 0), dtype=np.float32)
        else:
            embeddings = np.asarray(
                self.embedding_service.embed(texts),
                dtype=np.float32,
            )
            if embeddings.ndim != 2 or embeddings.shape[0] != len(item_ids):
                raise ValueError(
                    "Embedding service returned an inconsistent vector matrix."
                )
            embeddings = self.normalize_rows(embeddings)
        return EmbeddingIndex(list(item_ids), embeddings)

    def _load_valid_cache(
        self,
        npz_path: Path,
        manifest_path: Path,
        identity: Dict[str, Any],
        expected_item_ids: List[str],
    ) -> Optional[EmbeddingIndex]:
        if not npz_path.exists() or not manifest_path.exists():
            return None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key, value in identity.items():
                if manifest.get(key) != value:
                    return None
            if manifest.get("normalized") is not True:
                return None

            with np.load(npz_path, allow_pickle=False) as cached:
                item_ids = cached["item_ids"].tolist()
                embeddings = cached["embeddings"]

            if item_ids != expected_item_ids:
                return None
            if embeddings.dtype != np.float32 or embeddings.ndim != 2:
                return None
            if embeddings.shape[0] != len(item_ids):
                return None
            if embeddings.shape[1] != manifest.get("dimension"):
                return None
            if not np.isfinite(embeddings).all():
                return None
            norms = np.linalg.norm(embeddings, axis=1)
            nonzero = norms > 0.0
            if nonzero.any() and not np.allclose(norms[nonzero], 1.0):
                return None
            return EmbeddingIndex(item_ids, embeddings)
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _identity(
        self,
        source_path: Path,
        embedding_input: str,
        item_count: int,
    ) -> Dict[str, Any]:
        return {
            "source_file": str(source_path.resolve()),
            "source_sha256": self.source_sha256(source_path),
            "model": self.embedding_service.model,
            "item_count": item_count,
            "normalized": True,
            "embedding_input": embedding_input,
            "embedding_format_version": EMBEDDING_FORMAT_VERSION,
        }

    def _cache_paths(self, dataset_name: str):
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", dataset_name)
        if not safe_name:
            raise ValueError("Embedding dataset name must not be empty.")
        return (
            self.cache_dir / f"{safe_name}.npz",
            self.cache_dir / f"{safe_name}.manifest.json",
        )

    @staticmethod
    def source_sha256(source_path: Path) -> str:
        digest = hashlib.sha256()
        with Path(source_path).open("rb") as source_file:
            for block in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def normalize_rows(embeddings: np.ndarray) -> np.ndarray:
        embeddings = np.asarray(embeddings, dtype=np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = np.zeros_like(embeddings, dtype=np.float32)
        np.divide(embeddings, norms, out=normalized, where=norms != 0.0)
        return normalized

    @staticmethod
    def normalize_vector(embedding: np.ndarray) -> np.ndarray:
        vector = np.asarray(embedding, dtype=np.float32)
        if vector.ndim != 1:
            raise ValueError("Query embedding must be one-dimensional.")
        norm = float(np.linalg.norm(vector))
        if norm == 0.0:
            return np.zeros_like(vector, dtype=np.float32)
        return vector / norm
