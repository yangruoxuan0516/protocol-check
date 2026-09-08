import json

from checks.cor_02_12.not_duplicate import NotDuplicateCheck
from domain.model import NIO, Protocol
from domain.result import CheckStatus
from engine.context import CheckContext
from services.nio_retriever import RetrievedNIO


def make_protocol(*nios):
    return Protocol(
        document_id="test",
        title="Test",
        nios=list(nios),
    )


class FakeRetriever:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = 0

    def retrieve(self, target):
        self.calls += 1
        return self.candidates


class FakeLLM:
    model = "fake-qwen"

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.last_raw_response = None

    def ask_json(self, prompt):
        self.calls.append(prompt)
        answer = self.answers.pop(0)
        self.last_raw_response = json.dumps(answer)
        return answer


class MustNotCall:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected service call: {name}")


def requirement(nio_id, specification):
    return NIO(
        id=nio_id,
        specification=specification,
        type="requirement",
    )


def run_check(judgments, similarities=None):
    target = requirement("NIO-1", "The unit shall respond.")
    similarities = similarities or [0.9] * len(judgments)
    candidates = [
        requirement(
            f"NIO-{index + 2}",
            f"Candidate requirement {index + 1}",
        )
        for index in range(len(judgments))
    ]
    retrieved = [
        RetrievedNIO(nio=candidate, similarity=similarity)
        for candidate, similarity in zip(candidates, similarities)
    ]
    retriever = FakeRetriever(retrieved)
    llm = FakeLLM(
        [
            {
                "status": judgment,
                "reason": f"Reason for {judgment}",
            }
            for judgment in judgments
        ]
    )
    context = CheckContext(
        protocol=make_protocol(target, *candidates),
        llm=llm,
        nio_retriever=retriever,
    )
    result = NotDuplicateCheck().run(target, context)[0]
    return result, retriever, llm


def test_section_header_is_not_applicable_without_service_calls():
    header = NIO(
        id="NIO-1",
        specification="Section heading",
        type="section_header",
    )
    context = CheckContext(
        protocol=make_protocol(header),
        llm=MustNotCall(),
        nio_retriever=MustNotCall(),
    )

    result = NotDuplicateCheck().run(header, context)[0]

    assert result.status is CheckStatus.NOT_APPLICABLE
    assert result.message == "Record is a section header."


def test_duplicate_candidate_fails_and_retains_traceability():
    result, retriever, llm = run_check(
        ["DUPLICATE"],
        similarities=[0.87],
    )

    assert result.status is CheckStatus.FAIL
    assert result.related_ids == ["NIO-2"]
    assert retriever.calls == 1
    assert len(llm.calls) == 1
    assert result.metadata["model"] == "fake-qwen"
    diagnostic = result.metadata["candidates"][0]
    assert diagnostic["id"] == "NIO-2"
    assert diagnostic["similarity"] == 0.87
    assert diagnostic["judgment"] == "DUPLICATE"
    assert diagnostic["reason"] == "Reason for DUPLICATE"
    assert "Requirement A:" in diagnostic["prompt"]
    assert diagnostic["raw_response"] is not None
    assert diagnostic["parsed_response"]["status"] == "DUPLICATE"


def test_high_similarity_does_not_fail_without_duplicate_judgment():
    result, _, _ = run_check(
        ["NOT_DUPLICATE", "NOT_DUPLICATE"],
        similarities=[0.999, 0.998],
    )

    assert result.status is CheckStatus.PASS
    assert result.related_ids == []


def test_review_without_duplicate_returns_review():
    result, _, _ = run_check(
        ["NOT_DUPLICATE", "REVIEW"],
    )

    assert result.status is CheckStatus.REVIEW
    assert result.related_ids == []


def test_duplicate_takes_precedence_over_review():
    result, _, _ = run_check(
        ["REVIEW", "DUPLICATE"],
    )

    assert result.status is CheckStatus.FAIL
    assert result.related_ids == ["NIO-3"]
