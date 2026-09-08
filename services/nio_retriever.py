from dataclasses import dataclass
from math import sqrt
from typing import Any, Dict, List, Optional

from domain.model import NIO, Protocol


@dataclass(frozen=True)
class RetrievedNIO:
    nio: NIO
    similarity: float


class NIORetriever:
    def __init__(
        self,
        protocol: Protocol,
        embedding_service: Any,
        top_k: int = 5,
    ):
        self.protocol = protocol
        self.embedding_service = embedding_service
        self.top_k = top_k
        self._requirements = [
            nio
            for nio in protocol.nios
            if nio.type == "requirement"
        ]
        self._embeddings: Optional[Dict[str, List[float]]] = None

    def retrieve(self, target: NIO) -> List[RetrievedNIO]:
        self._ensure_index()
        assert self._embeddings is not None

        try:
            target_embedding = self._embeddings[target.id]
        except KeyError:
            raise ValueError(
                f"Target requirement is not indexed: {target.id}"
            )

        results = [
            RetrievedNIO(
                nio=candidate,
                similarity=self._cosine_similarity(
                    target_embedding,
                    self._embeddings[candidate.id],
                ),
            )
            for candidate in self._requirements
            if candidate.id != target.id
        ]
        results.sort(
            key=lambda item: item.similarity,
            reverse=True,
        )
        return results[:self.top_k]

    def _ensure_index(self) -> None:
        if self._embeddings is not None:
            return

        vectors = self.embedding_service.embed(
            [nio.specification for nio in self._requirements]
        )
        if len(vectors) != len(self._requirements):
            raise ValueError(
                "Embedding service returned an unexpected vector count."
            )

        self._embeddings = {
            nio.id: vector
            for nio, vector in zip(self._requirements, vectors)
        }

    @staticmethod
    def _cosine_similarity(
        left: List[float],
        right: List[float],
    ) -> float:
        if len(left) != len(right):
            raise ValueError("Embedding dimensions do not match.")

        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0

        dot_product = sum(
            left_value * right_value
            for left_value, right_value in zip(left, right)
        )
        return dot_product / (left_norm * right_norm)
