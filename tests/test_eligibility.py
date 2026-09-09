from checks.base import Check, CheckScope
from domain.model import NIO, Protocol
from domain.result import CheckResult, CheckStatus
from engine.context import CheckContext
from engine.registry import CHECKS
from engine.runner import Runner
from services.embedding_store import EmbeddingStore
from services.nio_retriever import NIORetriever


def mixed_protocol():
    return Protocol(
        document_id="test",
        title="Test",
        nios=[
            NIO("YES", "Yes requirement", "requirement", req="Yes"),
            NIO("NO", "No requirement", "requirement", req="No"),
            NIO("NULL", "Null requirement", "requirement", req=None),
            NIO("HEADER", "Section header", "section_header", req="Yes"),
        ],
    )


class RecordingCheck(Check):
    check_id = "TEST.recording"
    implementation = "test"

    def __init__(self):
        self.target_ids = []

    def run(self, target, context):
        self.target_ids.append(target.id)
        return [
            CheckResult(
                check_id=self.check_id,
                implementation=self.implementation,
                target_id=target.id,
                status=CheckStatus.PASS,
                message="recorded",
            )
        ]


def test_default_runner_checks_only_req_yes_requirements():
    check = RecordingCheck()
    runner = Runner(CheckContext(protocol=mixed_protocol()))

    results = runner.run([check])

    assert check.target_ids == ["YES"]
    assert [result.target_id for result in results] == ["YES"]
    assert runner.count_work_units([check]) == 1


def test_check_all_includes_all_requirements_but_not_headers():
    check = RecordingCheck()
    runner = Runner(
        CheckContext(protocol=mixed_protocol()),
        check_all_nios=True,
    )

    results = runner.run([check])

    assert check.target_ids == ["YES", "NO", "NULL"]
    assert [result.target_id for result in results] == ["YES", "NO", "NULL"]
    assert runner.count_work_units([check]) == 3


def test_check_all_nios_cli_flag_is_available(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run.py",
            "--check",
            "COR-02.01.single_shall",
            "--check-all-nios",
        ],
    )

    args = run_module.parse_args()

    assert args.check_all_nios is True


class RequirementSetCheck(Check):
    check_id = "TEST.requirement_set"
    implementation = "test"
    scope = CheckScope.REQUIREMENT_SET

    def __init__(self):
        self.received_ids = []

    def run(self, target, context):
        self.received_ids = [nio.id for nio in target]
        return []


def test_requirement_set_receives_the_same_active_population():
    default_check = RequirementSetCheck()
    all_check = RequirementSetCheck()

    Runner(CheckContext(protocol=mixed_protocol())).run([default_check])
    Runner(
        CheckContext(protocol=mixed_protocol()),
        check_all_nios=True,
    ).run([all_check])

    assert default_check.received_ids == ["YES"]
    assert all_check.received_ids == ["YES", "NO", "NULL"]


def test_all_registered_nio_checks_inherit_runner_filter(monkeypatch):
    for check in CHECKS.values():
        assert check.scope is CheckScope.NIO
        called_ids = []
        monkeypatch.setattr(check, "requires", ())
        monkeypatch.setattr(
            check,
            "run",
            lambda target, context, called_ids=called_ids: (
                called_ids.append(target.id) or []
            ),
        )

        Runner(CheckContext(protocol=mixed_protocol())).run([check])

        assert called_ids == ["YES"]


class FakeEmbeddingService:
    model = "fake-bge"

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vectors = {
            "Yes requirement": [1.0, 0.0],
            "No requirement": [0.8, 0.2],
            "Null requirement": [0.0, 1.0],
        }
        return [vectors[text] for text in texts]


def test_nio_retriever_population_and_cache_follow_check_all_mode(tmp_path):
    source_path = tmp_path / "protocol.jsonl"
    source_path.write_text("same source\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    protocol = mixed_protocol()

    default_service = FakeEmbeddingService()
    default_retriever = NIORetriever(
        protocol=protocol,
        embedding_store=EmbeddingStore(cache_dir, default_service),
        source_path=source_path,
    )
    default_retriever.get_embedding("YES")
    assert default_service.calls == [["Yes requirement"]]

    all_service = FakeEmbeddingService()
    all_retriever = NIORetriever(
        protocol=protocol,
        embedding_store=EmbeddingStore(cache_dir, all_service),
        source_path=source_path,
        check_all_nios=True,
    )
    all_retriever.get_embedding("NO")
    assert all_service.calls == [[
        "Yes requirement",
        "No requirement",
        "Null requirement",
    ]]
    assert [item.nio.id for item in all_retriever.retrieve(protocol.nios[0])] == [
        "NO",
        "NULL",
    ]
import sys

import run as run_module
