from pathlib import Path

from domain.standard import StandardChunk
from services.embedding_store import EmbeddingStore
from services.standard_retriever import StandardRetriever


class FakeEmbeddingService:
    model = "fake-bge"

    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [self.vectors[text] for text in texts]


def chunk(chunk_id, document, content_type, text, page):
    return StandardChunk(
        chunk_id=chunk_id,
        document=document,
        content_type=content_type,
        section_number=f"{page}.1",
        section_title=f"Section {page}",
        page_start=page,
        page_end=page,
        text=text,
    )


def make_retriever(tmp_path, service):
    p2_path = tmp_path / "p2.jsonl"
    p7_path = tmp_path / "p7.jsonl"
    if not p2_path.exists():
        p2_path.write_text("p2 source\n", encoding="utf-8")
        p7_path.write_text("p7 source\n", encoding="utf-8")
    p2_chunks = [
        chunk("P2-TEXT", "ARINC664P2", "text", "p2 text", 10),
        chunk("P2-TABLE", "ARINC664P2", "table", "p2 table", 11),
        chunk("P2-EMPTY", "ARINC664P2", "text", "", 12),
    ]
    p7_chunks = [
        chunk("P7-FIGURE", "ARINC664P7", "figure_caption", "p7 figure", 20),
        chunk("P7-TEXT", "ARINC664P7", "text", "p7 text", 21),
    ]
    return StandardRetriever(
        p2_chunks=p2_chunks,
        p2_source_path=p2_path,
        p7_chunks=p7_chunks,
        p7_source_path=p7_path,
        embedding_store=EmbeddingStore(tmp_path / "cache", service),
        top_k=3,
    )


def test_global_ranking_preserves_provenance_without_filtering_or_threshold(tmp_path):
    vectors = {
        "p2 text": [0.8, 0.6],
        "p2 table": [0.95, 0.05],
        "p7 figure": [1.0, 0.0],
        "p7 text": [-1.0, 0.0],
    }
    service = FakeEmbeddingService(vectors)
    retriever = make_retriever(tmp_path, service)

    matches = retriever.search_by_vector([1.0, 0.0], top_k=3)

    assert [match.chunk.chunk_id for match in matches] == [
        "P7-FIGURE",
        "P2-TABLE",
        "P2-TEXT",
    ]
    assert [match.similarity for match in matches] == sorted(
        [match.similarity for match in matches],
        reverse=True,
    )
    assert {match.chunk.document for match in matches} == {
        "ARINC664P2",
        "ARINC664P7",
    }
    assert matches[0].chunk.content_type == "figure_caption"
    assert matches[1].chunk.section_number == "11.1"
    assert matches[1].chunk.section_title == "Section 11"
    assert matches[1].chunk.page_start == 11
    assert matches[1].chunk.page_end == 11
    assert matches[1].chunk.text == "p2 table"
    assert "P2-EMPTY" not in [match.chunk.chunk_id for match in matches]

    all_matches = retriever.search_by_vector([1.0, 0.0], top_k=10)
    assert all_matches[-1].chunk.chunk_id == "P7-TEXT"
    assert all_matches[-1].similarity < 0.0


def test_standard_caches_avoid_repeated_embedding_calls(tmp_path):
    vectors = {
        "p2 text": [0.8, 0.6],
        "p2 table": [0.95, 0.05],
        "p7 figure": [1.0, 0.0],
        "p7 text": [-1.0, 0.0],
    }
    first_service = FakeEmbeddingService(vectors)
    make_retriever(tmp_path, first_service).search_by_vector([1.0, 0.0])
    assert len(first_service.calls) == 2

    cached_service = FakeEmbeddingService({})
    matches = make_retriever(tmp_path, cached_service).search_by_vector(
        [1.0, 0.0]
    )

    assert cached_service.calls == []
    assert len(matches) == 3
