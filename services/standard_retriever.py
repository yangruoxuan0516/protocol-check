from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from domain.standard import StandardChunk
from services.embedding_store import EmbeddingIndex, EmbeddingStore


@dataclass(frozen=True)
class StandardMatch:
    chunk: StandardChunk
    similarity: float


class StandardRetriever:
    def __init__(
        self,
        p2_chunks: List[StandardChunk],
        p2_source_path: Path,
        p7_chunks: List[StandardChunk],
        p7_source_path: Path,
        embedding_store: EmbeddingStore,
        top_k: int = 5,
    ):
        self.p2_chunks = [chunk for chunk in p2_chunks if chunk.text]
        self.p7_chunks = [chunk for chunk in p7_chunks if chunk.text]
        self.p2_source_path = Path(p2_source_path)
        self.p7_source_path = Path(p7_source_path)
        self.embedding_store = embedding_store
        self.top_k = top_k
        self._indexes: Optional[List[Tuple[List[StandardChunk], EmbeddingIndex]]] = None

    def search_by_vector(
        self,
        query_embedding,
        top_k: Optional[int] = None,
    ) -> List[StandardMatch]:
        query = self.embedding_store.normalize_vector(query_embedding)
        matches = []

        for chunks, index in self._get_indexes():
            if not chunks:
                continue
            if index.embeddings.shape[1] != query.shape[0]:
                raise ValueError("Query and standard embedding dimensions do not match.")
            scores = index.embeddings @ query
            matches.extend(
                StandardMatch(chunk=chunk, similarity=float(score))
                for chunk, score in zip(chunks, scores)
            )

        matches.sort(
            key=lambda match: (
                -match.similarity,
                match.chunk.document,
                match.chunk.chunk_id,
            )
        )
        result_limit = self.top_k if top_k is None else top_k
        return matches[:result_limit]

    def _get_indexes(self):
        if self._indexes is None:
            self._indexes = [
                (
                    self.p2_chunks,
                    self.embedding_store.load_or_build(
                        dataset_name="ARINC664P2",
                        source_path=self.p2_source_path,
                        item_ids=[chunk.chunk_id for chunk in self.p2_chunks],
                        texts=[chunk.text for chunk in self.p2_chunks],
                        embedding_input="standard_chunk.text",
                    ),
                ),
                (
                    self.p7_chunks,
                    self.embedding_store.load_or_build(
                        dataset_name="ARINC664P7",
                        source_path=self.p7_source_path,
                        item_ids=[chunk.chunk_id for chunk in self.p7_chunks],
                        texts=[chunk.text for chunk in self.p7_chunks],
                        embedding_input="standard_chunk.text",
                    ),
                ),
            ]
        return self._indexes
