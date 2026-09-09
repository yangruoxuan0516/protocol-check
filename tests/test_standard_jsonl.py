import json

import pytest

from parsing.standard_jsonl import load_standard_jsonl


def record(content_type="text", **overrides):
    value = {
        "chunk_id": "ARINC664P2-1.1-TEXT-001",
        "document": "ARINC664P2",
        "content_type": content_type,
        "section_number": "1.1",
        "section_title": "Introduction",
        "page_start": 10,
        "page_end": 11,
        "text": "Example chunk text.",
    }
    value.update(overrides)
    return value


def write_records(path, records):
    path.write_text(
        "".join(json.dumps(item) + "\n" for item in records),
        encoding="utf-8",
    )


def test_valid_content_types_and_nullable_section_fields_parse(tmp_path):
    path = tmp_path / "arinc.jsonl"
    write_records(
        path,
        [
            record("text"),
            record(
                "table",
                chunk_id="ARINC664P2-1.1-TABLE-001",
                section_number=None,
            ),
            record(
                "figure_caption",
                chunk_id="ARINC664P2-1.1-FIGURE-001",
                section_title=None,
            ),
        ],
    )

    chunks = load_standard_jsonl(str(path))

    assert [chunk.content_type for chunk in chunks] == [
        "text",
        "table",
        "figure_caption",
    ]
    assert chunks[1].section_number is None
    assert chunks[2].section_title is None
    assert chunks[0].page_start == 10
    assert isinstance(chunks[0].page_start, int)
    assert chunks[0].page_end == 11


def test_invalid_content_type_is_rejected(tmp_path):
    path = tmp_path / "invalid.jsonl"
    write_records(path, [record("unknown")])

    with pytest.raises(ValueError, match="Invalid content_type"):
        load_standard_jsonl(str(path))


def test_page_end_before_page_start_is_rejected(tmp_path):
    path = tmp_path / "invalid-pages.jsonl"
    write_records(path, [record(page_start=12, page_end=11)])

    with pytest.raises(ValueError, match="page_end precedes page_start"):
        load_standard_jsonl(str(path))
