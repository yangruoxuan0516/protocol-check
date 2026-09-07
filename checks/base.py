from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from domain.result import CheckResult


class CheckScope(str, Enum):
    NIO = "nio"
    DOCUMENT = "document"
    REQUIREMENT_SET = "requirement_set"


class Check(ABC):
    check_id: str
    implementation: str

    scope: CheckScope = CheckScope.NIO

    requires: tuple[str, ...] = ()

    @abstractmethod
    def run(
        self,
        target: Any,
        context: Any,
    ) -> list[CheckResult]:
        ...
