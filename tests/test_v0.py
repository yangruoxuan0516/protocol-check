import json
import subprocess
import sys
from pathlib import Path

from checks.base import Check
from checks.cor_02_01.factual_correct import FactualCorrectCheck
from checks.cor_02_01.single_shall import SingleShallCheck
from domain.model import NIO, Protocol
from domain.result import CheckResult, CheckStatus
from engine.context import CheckContext
from engine.runner import Runner
from parsing.nio_jsonl import load_protocol_jsonl


def make_protocol(*nios: NIO) -> Protocol:
    return Protocol(
        document_id="synthetic",
        title="Synthetic protocol",
        nios=list(nios),
    )


def test_parse_actual_jsonl_fields_req_mapping_and_source(tmp_path):
    input_path = tmp_path / "nios.jsonl"
    record = {
        "id": "NIO-1",
        "specification": "The unit shall respond.",
        "rationale": None,
        "Req": "Yes",
        "source": {
            "file": "protocol.docx",
            "table": "Table 1",
            "word_row": 123,
        },
    }
    input_path.write_text(
        json.dumps(record) + "\n",
        encoding="utf-8",
    )

    protocol = load_protocol_jsonl(str(input_path))

    nio = protocol.nios[0]
    assert nio.id == "NIO-1"
    assert nio.specification == record["specification"]
    assert nio.rationale is None
    assert nio.req == "Yes"
    assert nio.source is not None
    assert nio.source.file == "protocol.docx"
    assert nio.source.table == "Table 1"
    assert nio.source.word_row == 123
    assert isinstance(nio.source.word_row, int)


def test_single_shall_uses_exact_lowercase_occurrences():
    nio = NIO(
        id="NIO-2",
        specification="The unit shall start and shall report. SHALL is ignored.",
    )
    context = CheckContext(protocol=make_protocol(nio))

    result = SingleShallCheck().run(nio, context)[0]

    assert result.status is CheckStatus.FAIL
    assert result.metadata["shall_count"] == 2


class RaisingCheck(Check):
    check_id = "TEST.raises"
    implementation = "test"

    def run(self, target, context):
        raise RuntimeError("synthetic failure")


class NeedsServiceCheck(Check):
    check_id = "TEST.needs_service"
    implementation = "test"
    requires = ("llm",)

    def run(self, target, context):
        raise AssertionError("dependency blocking should prevent execution")


def test_runner_converts_checker_exception_to_error():
    nio = NIO(id="NIO-3", specification="Example")
    runner = Runner(CheckContext(protocol=make_protocol(nio)))

    result = runner.run([RaisingCheck()])[0]

    assert result.status is CheckStatus.ERROR
    assert result.target_id == "NIO-3"
    assert "RuntimeError: synthetic failure" in result.message


def test_runner_blocks_missing_dependency():
    nio = NIO(id="NIO-4", specification="Example")
    runner = Runner(CheckContext(protocol=make_protocol(nio)))

    result = runner.run([NeedsServiceCheck()])[0]

    assert result.status is CheckStatus.BLOCKED
    assert result.target_id == "__CHECK__"
    assert "'llm'" in result.message


class FakeLLM:
    model = "fake-qwen"
    last_raw_response = '{"status":"REVIEW","reason":"Insufficient evidence."}'

    def ask_json(self, prompt):
        assert "The component shall use the specified encoding." in prompt
        return {
            "status": "REVIEW",
            "reason": "Insufficient evidence.",
        }


def test_factual_correct_with_fake_llm_preserves_traceability():
    nio = NIO(
        id="NIO-5",
        specification="The component shall use the specified encoding.",
    )
    llm = FakeLLM()
    context = CheckContext(
        protocol=make_protocol(nio),
        llm=llm,
    )

    result = FactualCorrectCheck().run(nio, context)[0]

    assert result.status is CheckStatus.REVIEW
    assert result.metadata["model"] == "fake-qwen"
    assert result.metadata["raw_model_response"] == llm.last_raw_response
    assert result.metadata["parsed_model_response"]["status"] == "REVIEW"
    assert nio.specification in result.metadata["prompt"]


def test_cli_runs_single_shall_with_synthetic_jsonl(tmp_path):
    repository_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "nios.jsonl"
    output_path = tmp_path / "nested" / "results.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "id": "NIO-6",
                "specification": "The unit shall respond.",
                "rationale": "Synthetic fixture",
                "Req": "Yes",
                "source": {
                    "file": "fixture.docx",
                    "table": "Table A",
                    "word_row": 1,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "run.py",
            "--input",
            str(input_path),
            "--check",
            "COR-02.01.single_shall",
            "--output",
            str(output_path),
        ],
        cwd=str(repository_root),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["status"] == "PASS"
    assert result["metadata"]["shall_count"] == 1
