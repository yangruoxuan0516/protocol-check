import json

import numpy as np

from services.embedding_store import EmbeddingStore


class FakeEmbeddingService:
    def __init__(self, model="fake-bge"):
        self.model = model
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[3.0, 4.0], [0.0, 2.0]][:len(texts)]


def build(store, source_path):
    return store.load_or_build(
        dataset_name="protocol",
        source_path=source_path,
        item_ids=["NIO-2", "NIO-1"],
        texts=["second", "first"],
        embedding_input="nio.specification",
    )


def test_first_build_writes_normalized_float32_cache_in_id_order(tmp_path):
    source_path = tmp_path / "protocol.jsonl"
    source_path.write_text("version one\n", encoding="utf-8")
    service = FakeEmbeddingService()
    cache_dir = tmp_path / "cache"

    index = build(EmbeddingStore(cache_dir, service), source_path)

    assert service.calls == [["second", "first"]]
    assert index.item_ids == ["NIO-2", "NIO-1"]
    assert index.embeddings.dtype == np.float32
    assert np.allclose(np.linalg.norm(index.embeddings, axis=1), 1.0)
    assert (cache_dir / "protocol.npz").exists()
    manifest = json.loads(
        (cache_dir / "protocol.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["normalized"] is True
    assert manifest["dimension"] == 2
    with np.load(cache_dir / "protocol.npz", allow_pickle=False) as cached:
        assert cached["item_ids"].tolist() == ["NIO-2", "NIO-1"]
        assert cached["embeddings"].dtype == np.float32


def test_valid_cache_avoids_embedding_call(tmp_path):
    source_path = tmp_path / "protocol.jsonl"
    source_path.write_text("unchanged\n", encoding="utf-8")
    build(EmbeddingStore(tmp_path / "cache", FakeEmbeddingService()), source_path)
    service = FakeEmbeddingService()

    index = build(EmbeddingStore(tmp_path / "cache", service), source_path)

    assert service.calls == []
    assert index.item_ids == ["NIO-2", "NIO-1"]


def test_source_model_and_explicit_rebuild_invalidate_cache(tmp_path):
    source_path = tmp_path / "protocol.jsonl"
    source_path.write_text("version one\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    build(EmbeddingStore(cache_dir, FakeEmbeddingService()), source_path)

    source_path.write_text("version two\n", encoding="utf-8")
    changed_source = FakeEmbeddingService()
    build(EmbeddingStore(cache_dir, changed_source), source_path)
    assert len(changed_source.calls) == 1

    changed_model = FakeEmbeddingService(model="different-model")
    build(EmbeddingStore(cache_dir, changed_model), source_path)
    assert len(changed_model.calls) == 1

    forced = FakeEmbeddingService(model="different-model")
    build(EmbeddingStore(cache_dir, forced, rebuild=True), source_path)
    assert len(forced.calls) == 1


def test_corrupt_or_inconsistent_cache_is_rebuilt(tmp_path):
    source_path = tmp_path / "protocol.jsonl"
    source_path.write_text("source\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    build(EmbeddingStore(cache_dir, FakeEmbeddingService()), source_path)

    (cache_dir / "protocol.npz").write_bytes(b"not an npz")
    corrupt_service = FakeEmbeddingService()
    build(EmbeddingStore(cache_dir, corrupt_service), source_path)
    assert len(corrupt_service.calls) == 1

    np.savez(
        cache_dir / "protocol.npz",
        item_ids=np.asarray(["wrong", "ids"], dtype=np.str_),
        embeddings=np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
    )
    inconsistent_service = FakeEmbeddingService()
    build(EmbeddingStore(cache_dir, inconsistent_service), source_path)
    assert len(inconsistent_service.calls) == 1

    np.savez(
        cache_dir / "protocol.npz",
        item_ids=np.asarray(["NIO-2", "NIO-1"], dtype=np.str_),
        embeddings=np.asarray(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype=np.float32,
        ),
    )
    dimension_service = FakeEmbeddingService()
    build(EmbeddingStore(cache_dir, dimension_service), source_path)
    assert len(dimension_service.calls) == 1


def test_embedding_input_identity_change_invalidates_cache(tmp_path):
    source_path = tmp_path / "protocol.jsonl"
    source_path.write_text("source\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    build(EmbeddingStore(cache_dir, FakeEmbeddingService()), source_path)
    service = FakeEmbeddingService()

    EmbeddingStore(cache_dir, service).load_or_build(
        dataset_name="protocol",
        source_path=source_path,
        item_ids=["NIO-2", "NIO-1"],
        texts=["second", "first"],
        embedding_input="nio.specification.v2",
    )

    assert len(service.calls) == 1
