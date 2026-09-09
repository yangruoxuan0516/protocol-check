from pathlib import Path

import pytest

from run import resolve_protocol_input


def test_explicit_protocol_input_overrides_configured_path():
    resolved = resolve_protocol_input(
        "explicit.jsonl",
        "configured.jsonl",
    )

    assert resolved == Path("explicit.jsonl")


def test_configured_protocol_input_is_used_without_cli_input():
    resolved = resolve_protocol_input(None, "configured.jsonl")

    assert resolved == Path("configured.jsonl")


def test_missing_protocol_input_has_clear_error():
    with pytest.raises(SystemExit, match="Protocol input is required"):
        resolve_protocol_input(None, "")
