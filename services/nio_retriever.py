from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from domain.model import NIO, Protocol
from services.embedding_store import EmbeddingIndex, EmbeddingStore


@dataclass(frozen=True)
class RetrievedNIO:
    nio: NIO
    similarity: float


class NIORetriever:
    def __init__(
        self,
        protocol: Protocol,
        embedding_store: EmbeddingStore,
        source_path: Path,
        top_k: int = 5,
    ):
        self.protocol = protocol
        self.embedding_store = embedding_store
        self.source_path = Path(source_path)
        self.top_k = top_k
        self._requirements = [
            nio
            for nio in protocol.nios
            if nio.type == "requirement"
        ]
        self._index: Optional[EmbeddingIndex] = None

    def retrieve(self, target: NIO) -> List[RetrievedNIO]:
        index = self._get_index()
        target_embedding = index.get(target.id)
        scores = index.embeddings @ target_embedding
        rows = {
            item_id: row
            for row, item_id in enumerate(index.item_ids)
        }

        results = [
            RetrievedNIO(
                nio=candidate,
                similarity=float(scores[rows[candidate.id]]),
            )
            for candidate in self._requirements
            if candidate.id != target.id
        ]
        results.sort(
            key=lambda item: item.similarity,
            reverse=True,
        )
        return results[:self.top_k]

    def get_embedding(self, nio_id: str):
        return self._get_index().get(nio_id)

    def _get_index(self) -> EmbeddingIndex:
        if self._index is None:
            self._index = self.embedding_store.load_or_build(
                dataset_name="protocol",
                source_path=self.source_path,
                item_ids=[nio.id for nio in self._requirements],
                texts=[nio.specification for nio in self._requirements],
                embedding_input="nio.specification",
            )
        return self._index
