import json
import subprocess
import sys
from pathlib import Path

from checks.base import Check
from domain.model import NIO, Protocol
from domain.result import CheckResult, CheckStatus
from engine.context import CheckContext
from engine.runner import Runner
from run import write_results_incrementally


def make_result(target_id, status=CheckStatus.PASS):
    return CheckResult(
        check_id="TEST.execution",
        implementation="test",
        target_id=target_id,
        status=status,
        message="Synthetic result.",
    )


class FakeProgress:
    def __init__(self):
        self.completed = 0

    def update(self, amount):
        self.completed += amount


def test_results_are_flushed_before_the_next_execution(tmp_path):
    output_path = tmp_path / "results.jsonl"
    progress = FakeProgress()

    def result_batches():
        yield [make_result("NIO-1")]
        persisted = output_path.read_text(encoding="utf-8")
        assert json.loads(persisted)["target_id"] == "NIO-1"
        yield [make_result("NIO-2")]

    with output_path.open("x", encoding="utf-8") as output_file:
        count = write_results_incrementally(
            result_batches(),
            output_file,
            progress,
        )

    assert count == 2
    assert progress.completed == 2


class MultipleResultsCheck(Check):
    check_id = "TEST.multiple"
    implementation = "test"

    def run(self, target, context):
        return [
            make_result(f"{target.id}-A"),
            make_result(f"{target.id}-B"),
        ]


class RaisingCheck(Check):
    check_id = "TEST.raises_for_persistence"
    implementation = "test"

    def run(self, target, context):
        raise RuntimeError("synthetic failure")


def test_progress_counts_executions_and_all_results_are_written(tmp_path):
    nios = [
        NIO(
            id=f"NIO-{index}",
            specification="Synthetic requirement.",
            type="requirement",
            req="Yes",
        )
        for index in (1, 2)
    ]
    protocol = Protocol(
        document_id="test",
        title="Test",
        nios=nios,
    )
    runner = Runner(CheckContext(protocol=protocol))
    checks = [MultipleResultsCheck()]
    progress = FakeProgress()
    output_path = tmp_path / "multiple.jsonl"

    assert runner.count_work_units(checks) == 2
    with output_path.open("x", encoding="utf-8") as output_file:
        count = write_results_incrementally(
            runner.iter_run(checks),
            output_file,
            progress,
        )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert count == 4
    assert len(lines) == 4
    assert progress.completed == 2


def test_error_result_is_written_incrementally(tmp_path):
    nio = NIO(
        id="NIO-1",
        specification="Synthetic requirement.",
        type="requirement",
        req="Yes",
    )
    protocol = Protocol(
        document_id="test",
        title="Test",
        nios=[nio],
    )
    runner = Runner(CheckContext(protocol=protocol))
    output_path = tmp_path / "error.jsonl"

    with output_path.open("x", encoding="utf-8") as output_file:
        write_results_incrementally(
            runner.iter_run([RaisingCheck()]),
            output_file,
            FakeProgress(),
        )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "ERROR"
    assert "RuntimeError: synthetic failure" in persisted["message"]


def test_cli_refuses_existing_output_unless_overwrite_is_set(tmp_path):
    repository_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "nios.jsonl"
    output_path = tmp_path / "results.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "id": "NIO-1",
                "type": "requirement",
                "section_number": "4.3",
                "specification": "The unit shall respond.",
                "rationale": None,
                "req": "Yes",
                "source": {
                    "file": "fixture.docx",
                    "table": 1,
                    "word_row": 12,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    original = "existing output must remain unchanged\n"
    output_path.write_text(original, encoding="utf-8")
    command = [
        sys.executable,
        "run.py",
        "--input",
        str(input_path),
        "--check",
        "COR-02.01.single_shall",
        "--output",
        str(output_path),
    ]

    refused = subprocess.run(
        command,
        cwd=str(repository_root),
        check=False,
        capture_output=True,
        text=True,
    )

    assert refused.returncode != 0
    assert "Output file already exists" in refused.stderr
    assert output_path.read_text(encoding="utf-8") == original

    overwritten = subprocess.run(
        command + ["--overwrite"],
        cwd=str(repository_root),
        check=False,
        capture_output=True,
        text=True,
    )

    assert overwritten.returncode == 0, overwritten.stderr
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "PASS"
