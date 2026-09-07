from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


@dataclass
class Evidence:
    source_type: str

    source_id: Optional[str] = None
    text: Optional[str] = None

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    check_id: str
    implementation: str

    target_id: str
    status: CheckStatus

    message: str

    related_ids: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "implementation": self.implementation,
            "target_id": self.target_id,
            "related_ids": self.related_ids,
            "status": self.status.value,
            "message": self.message,
            "evidence": [
                {
                    "source_type": e.source_type,
                    "source_id": e.source_id,
                    "text": e.text,
                    "metadata": e.metadata,
                }
                for e in self.evidence
            ],
            "metadata": self.metadata,
        }