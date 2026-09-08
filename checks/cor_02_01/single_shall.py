from checks.base import Check
from domain.model import NIO
from domain.result import CheckResult, CheckStatus


class SingleShallCheck(Check):
    check_id = "COR-02.01.single_shall"
    implementation = "v0_exact_string"

    requires = ()

    def run(
        self,
        target: NIO,
        context,
    ) -> list[CheckResult]:

        if target.type == "section_header":
            return [
                CheckResult(
                    check_id=self.check_id,
                    implementation=self.implementation,
                    target_id=target.id,
                    status=CheckStatus.NOT_APPLICABLE,
                    message="Record is a section header.",
                )
            ]

        count = target.specification.count("shall")

        if count <= 1:
            status = CheckStatus.PASS
            message = (
                f'Found {count} occurrence(s) of "shall".'
            )
        else:
            status = CheckStatus.FAIL
            message = (
                f'Found {count} occurrences of "shall".'
            )

        return [
            CheckResult(
                check_id=self.check_id,
                implementation=self.implementation,
                target_id=target.id,
                status=status,
                message=message,
                metadata={
                    "shall_count": count,
                },
            )
        ]
