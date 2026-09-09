import json

import pytest

from checks.cor_02_01.factual_correct_arinc import FactualCorrectArincCheck
from domain.model import NIO, Protocol
from domain.result import CheckStatus
from domain.standard import StandardChunk
from engine.context import CheckContext
from engine.runner import Runner
from services.standard_retriever import StandardMatch


def requirement(nio_id="NIO-1", nio_type="requirement"):
    return NIO(
        id=nio_id,
        specification="The hosted function shall transmit the frame.",
        type=nio_type,
        section_number="4.3.2",
        req="Yes",
    )


def standard_match(
    chunk_id="ARINC664P7-3.4.2-TEXT-001",
    similarity=0.8421,
):
    return StandardMatch(
        chunk=StandardChunk(
            chunk_id=chunk_id,
            document="ARINC664P7",
            content_type="text",
            section_number="3.4.2",
            section_title="Virtual Links",
            page_start=42,
            page_end=43,
            text="ARINC evidence text.",
        ),
        similarity=similarity,
    )


class FakeNIORetriever:
    def __init__(self, embedding):
        self.embedding = embedding
        self.calls = []

    def get_embedding(self, nio_id):
        self.calls.append(nio_id)
        return self.embedding


class FakeStandardRetriever:
    def __init__(self, matches, top_k=3):
        self.matches = matches
        self.top_k = top_k
        self.calls = []

    def search_by_vector(self, query_embedding, top_k):
        self.calls.append((query_embedding, top_k))
        return self.matches[:top_k]


class FakeLLM:
    model = "fake-qwen"

    def __init__(self, answer):
        self.answer = answer
        self.calls = []
        self.last_raw_response = json.dumps(answer)

    def ask_json(self, prompt):
        self.calls.append(prompt)
        return self.answer


class MustNotCall:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected service access: {name}")


def make_context(answer, matches=None, top_k=3, embedding=None):
    target = requirement()
    query_embedding = embedding if embedding is not None else [1.0, 0.0]
    nio_retriever = FakeNIORetriever(query_embedding)
    standard_retriever = FakeStandardRetriever(
        matches if matches is not None else [standard_match()],
        top_k=top_k,
    )
    llm = FakeLLM(answer)
    context = CheckContext(
        protocol=Protocol("test", "Test", [target]),
        llm=llm,
        nio_retriever=nio_retriever,
        standard_retriever=standard_retriever,
    )
    return target, context, nio_retriever, standard_retriever, llm


def test_section_header_is_not_applicable_without_service_calls():
    target = requirement(nio_type="section_header")
    context = CheckContext(
        protocol=Protocol("test", "Test", [target]),
        llm=MustNotCall(),
        nio_retriever=MustNotCall(),
        standard_retriever=MustNotCall(),
    )

    result = FactualCorrectArincCheck().run(target, context)[0]

    assert result.status is CheckStatus.NOT_APPLICABLE
    assert result.message == "Record is a section header."


@pytest.mark.parametrize(
    ("llm_status", "expected_status"),
    [
        ("PASS", CheckStatus.PASS),
        ("FAIL", CheckStatus.FAIL),
        ("REVIEW", CheckStatus.REVIEW),
    ],
)
def test_llm_status_maps_directly(llm_status, expected_status):
    target, context, _, _, _ = make_context(
        {
            "status": llm_status,
            "reason": "Evidence-based judgment.",
            "supporting_chunk_ids": ["ARINC664P7-3.4.2-TEXT-001"],
        }
    )

    result = FactualCorrectArincCheck().run(target, context)[0]

    assert result.status is expected_status


def test_cached_vector_top_k_provenance_and_traceability_are_preserved():
    cached_vector = object()
    matches = [
        standard_match(),
        standard_match("ARINC664P2-1.4.2-TABLE-001", similarity=0.71),
    ]
    target, context, nio_retriever, standard_retriever, llm = make_context(
        {
            "status": "PASS",
            "reason": "The cited chunk directly supports the assertion.",
            "supporting_chunk_ids": ["ARINC664P7-3.4.2-TEXT-001"],
        },
        matches=matches,
        top_k=2,
        embedding=cached_vector,
    )

    result = FactualCorrectArincCheck().run(target, context)[0]

    assert nio_retriever.calls == ["NIO-1"]
    assert standard_retriever.calls == [(cached_vector, 2)]
    assert len(llm.calls) == 1
    assert result.metadata["target_requirement"]["specification"] == target.specification
    assert [item["rank"] for item in result.metadata["retrieved_chunks"]] == [1, 2]
    retrieved = result.metadata["retrieved_chunks"][0]
    assert retrieved["chunk_id"] == "ARINC664P7-3.4.2-TEXT-001"
    assert retrieved["document"] == "ARINC664P7"
    assert retrieved["content_type"] == "text"
    assert retrieved["section_number"] == "3.4.2"
    assert retrieved["section_title"] == "Virtual Links"
    assert retrieved["page_start"] == 42
    assert retrieved["page_end"] == 43
    assert retrieved["similarity"] == 0.8421
    assert retrieved["text"] == "ARINC evidence text."
    assert result.metadata["supporting_chunk_ids"] == [
        "ARINC664P7-3.4.2-TEXT-001"
    ]
    assert result.evidence[0].source_id == "ARINC664P7-3.4.2-TEXT-001"
    assert result.metadata["prompt"] == llm.calls[0]
    assert "Absence of contradiction is not support" in llm.calls[0]
    assert "Similarity: 0.842100 (retrieval ranking only)" in llm.calls[0]
    assert result.metadata["raw_model_response"] == llm.last_raw_response
    assert result.metadata["parsed_model_response"]["status"] == "PASS"
    assert result.metadata["model"] == "fake-qwen"


def test_high_similarity_cannot_override_review_judgment():
    target, context, _, _, _ = make_context(
        {
            "status": "REVIEW",
            "reason": "The related evidence is too general.",
            "supporting_chunk_ids": [],
        },
        matches=[standard_match(similarity=0.9999)],
    )

    result = FactualCorrectArincCheck().run(target, context)[0]

    assert result.status is CheckStatus.REVIEW
    assert "insufficient or too general" in result.message


def test_unknown_supporting_chunk_id_becomes_runner_error():
    target, context, _, _, _ = make_context(
        {
            "status": "PASS",
            "reason": "Invalid citation.",
            "supporting_chunk_ids": ["ARINC664P7-UNKNOWN"],
        }
    )

    result = Runner(context).run([FactualCorrectArincCheck()])[0]

    assert result.status is CheckStatus.ERROR
    assert "unknown ARINC chunk IDs" in result.message
