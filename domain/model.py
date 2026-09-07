from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Source:
    file: Optional[str] = None
    table: Optional[str] = None
    word_row: Optional[int] = None


@dataclass
class NIO:
    id: str
    specification: str

    rationale: Optional[str] = None
    req: Optional[str] = None
    source: Optional[Source] = None

    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Protocol:
    document_id: str
    title: str
    nios: list[NIO]

    acronyms: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
