from math import sqrt

import pytest

from domain.model import NIO, Protocol
from services.embedding_store import EmbeddingStore
from services.nio_retriever import NIORetriever


class FakeEmbeddingService:
    model = "fake-bge"

    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [self.vectors[text] for text in texts]


def test_retriever_preserves_semantics_and_reuses_protocol_cache(tmp_path):
    target = NIO(
        id="NIO-1",
        specification="target",
        type="requirement",
    )
    near = NIO(
        id="NIO-2",
        specification="near",
        type="requirement",
    )
    middle = NIO(
        id="NIO-3",
        specification="middle",
        type="requirement",
    )
    far = NIO(
        id="NIO-4",
        specification="far",
        type="requirement",
    )
    header = NIO(
        id="NIO-5",
        specification="header is never embedded",
        type="section_header",
    )
    protocol = Protocol(
        document_id="test",
        title="Test",
        nios=[target, near, middle, far, header],
    )
    embedding_service = FakeEmbeddingService(
        {
            "target": [1.0, 0.0],
            "near": [0.8, 0.2],
            "middle": [1.0, 1.0],
            "far": [0.0, 1.0],
        }
    )
    source_path = tmp_path / "protocol.jsonl"
    source_path.write_text("synthetic protocol\n", encoding="utf-8")
    store = EmbeddingStore(tmp_path / "cache", embedding_service)
    retriever = NIORetriever(
        protocol=protocol,
        embedding_store=store,
        source_path=source_path,
        top_k=2,
    )

    results = retriever.retrieve(target)
    retriever.retrieve(near)

    assert embedding_service.calls == [
        ["target", "near", "middle", "far"]
    ]
    assert [result.nio.id for result in results] == [
        "NIO-2",
        "NIO-3",
    ]
    assert target.id not in [result.nio.id for result in results]
    assert len(results) == 2
    assert results[0].similarity > results[1].similarity
    assert results[0].similarity == pytest.approx(
        0.8 / sqrt(0.8 ** 2 + 0.2 ** 2)
    )
    assert retriever.get_embedding("NIO-1").tolist() == [1.0, 0.0]

    cached_service = FakeEmbeddingService({})
    cached_retriever = NIORetriever(
        protocol=protocol,
        embedding_store=EmbeddingStore(tmp_path / "cache", cached_service),
        source_path=source_path,
        top_k=2,
    )
    assert [item.nio.id for item in cached_retriever.retrieve(target)] == [
        "NIO-2",
        "NIO-3",
    ]
    assert cached_service.calls == []
