from typing import Iterator, Optional

from checks.base import CheckScope
from domain.result import CheckResult, CheckStatus


class Runner:
    def __init__(self, context):
        self.context = context

    def run(
        self,
        checks,
        limit: Optional[int] = None,
    ) -> list[CheckResult]:
        results: list[CheckResult] = []
        for check_results in self.iter_run(checks, limit):
            results.extend(check_results)
        return results

    def iter_run(
        self,
        checks,
        limit: Optional[int] = None,
    ) -> Iterator[list[CheckResult]]:

        for check in checks:

            dependency_error = (
                self._check_dependencies(check)
            )

            if dependency_error:
                yield [
                    CheckResult(
                        check_id=check.check_id,
                        implementation=(
                            check.implementation
                        ),
                        target_id="__CHECK__",
                        status=CheckStatus.BLOCKED,
                        message=dependency_error,
                    )
                ]
                continue

            if check.scope == CheckScope.NIO:
                targets = self.context.protocol.nios

                if limit is not None:
                    targets = targets[:limit]

                for target in targets:
                    yield self._safe_run(
                        check,
                        target,
                    )

            elif check.scope == CheckScope.DOCUMENT:
                yield self._safe_run(
                    check,
                    self.context.protocol,
                )

            elif (
                check.scope
                == CheckScope.REQUIREMENT_SET
            ):
                nios = self.context.protocol.nios

                if limit is not None:
                    nios = nios[:limit]

                yield self._safe_run(
                    check,
                    nios,
                )

            else:
                raise ValueError(
                    f"Unsupported scope: "
                    f"{check.scope}"
                )

    def count_work_units(
        self,
        checks,
        limit: Optional[int] = None,
    ) -> int:
        total = 0

        for check in checks:
            if self._check_dependencies(check):
                total += 1
            elif check.scope == CheckScope.NIO:
                targets = self.context.protocol.nios
                if limit is not None:
                    targets = targets[:limit]
                total += len(targets)
            elif check.scope in {
                CheckScope.DOCUMENT,
                CheckScope.REQUIREMENT_SET,
            }:
                total += 1
            else:
                raise ValueError(
                    f"Unsupported scope: "
                    f"{check.scope}"
                )

        return total

    def _safe_run(self, check, target):
        try:
            check_results = check.run(
                target,
                self.context,
            )

            if not isinstance(check_results, list):
                raise TypeError(
                    "Check.run() must return list[CheckResult]."
                )

            if not all(
                isinstance(result, CheckResult)
                for result in check_results
            ):
                raise TypeError(
                    "Check.run() returned a non-CheckResult item."
                )

            return check_results

        except Exception as exc:
            target_id = getattr(
                target,
                "id",
                "__UNKNOWN__",
            )

            return [
                CheckResult(
                    check_id=check.check_id,
                    implementation=(
                        check.implementation
                    ),
                    target_id=target_id,
                    status=CheckStatus.ERROR,
                    message=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )
            ]

    def _check_dependencies(
        self,
        check,
    ) -> Optional[str]:

        for dependency in check.requires:
            value = getattr(
                self.context,
                dependency,
                None,
            )

            if value is None:
                return (
                    f"Required service "
                    f"'{dependency}' "
                    f"is unavailable."
                )

        return None
