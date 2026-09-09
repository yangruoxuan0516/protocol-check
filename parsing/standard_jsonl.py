import json
from pathlib import Path
from typing import List

from domain.standard import StandardChunk


CONTENT_TYPES = {
    "text",
    "table",
    "figure_caption",
}


def load_standard_jsonl(path: str) -> List[StandardChunk]:
    chunks = []
    with Path(path).open("r", encoding="utf-8") as source_file:
        for line_number, line in enumerate(source_file, start=1):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            chunks.append(_parse_chunk(data, line_number))
    return chunks


def _parse_chunk(data, line_number: int) -> StandardChunk:
    chunk_id = data["chunk_id"]
    document = data["document"]
    content_type = data["content_type"]
    section_number = data["section_number"]
    section_title = data["section_title"]
    page_start = data["page_start"]
    page_end = data["page_end"]
    text = data["text"]

    if not isinstance(chunk_id, str) or not chunk_id:
        raise ValueError(f"Invalid chunk_id at line {line_number}.")
    if not isinstance(document, str) or not document:
        raise ValueError(f"Invalid document at line {line_number}.")
    if content_type not in CONTENT_TYPES:
        raise ValueError(
            f"Invalid content_type at line {line_number}: {content_type!r}"
        )
    if section_number is not None and not isinstance(section_number, str):
        raise ValueError(f"Invalid section_number at line {line_number}.")
    if section_title is not None and not isinstance(section_title, str):
        raise ValueError(f"Invalid section_title at line {line_number}.")
    if not isinstance(page_start, int) or isinstance(page_start, bool):
        raise ValueError(f"Invalid page_start at line {line_number}.")
    if not isinstance(page_end, int) or isinstance(page_end, bool):
        raise ValueError(f"Invalid page_end at line {line_number}.")
    if page_end < page_start:
        raise ValueError(f"page_end precedes page_start at line {line_number}.")
    if not isinstance(text, str):
        raise ValueError(f"Invalid text at line {line_number}.")

    return StandardChunk(
        chunk_id=chunk_id,
        document=document,
        content_type=content_type,
        section_number=section_number,
        section_title=section_title,
        page_start=page_start,
        page_end=page_end,
        text=text,
    )
