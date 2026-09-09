from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StandardChunk:
    chunk_id: str
    document: str
    content_type: str
    section_number: Optional[str]
    section_title: Optional[str]
    page_start: int
    page_end: int
    text: str
