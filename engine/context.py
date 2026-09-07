from dataclasses import dataclass
from typing import Any, Optional

from domain.model import Protocol


@dataclass
class CheckContext:
    protocol: Protocol

    llm: Optional[Any] = None
