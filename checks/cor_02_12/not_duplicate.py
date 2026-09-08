from checks.base import Check
from domain.model import NIO
from domain.result import CheckResult, CheckStatus


class NotDuplicateCheck(Check):
    check_id = "COR-02.12.not_duplicate"
    implementation = "v0_bge_topk_qwen"
    requires = ("llm", "nio_retriever")

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

        candidate_diagnostics = []
        duplicate_ids = []
        has_review = False

        for retrieved in context.nio_retriever.retrieve(target):
            candidate = retrieved.nio
            prompt = self._build_prompt(target, candidate)
            answer = context.llm.ask_json(prompt)
            judgment = answer.get("status")

            if judgment not in {
                "DUPLICATE",
                "NOT_DUPLICATE",
                "REVIEW",
            }:
                raise ValueError(
                    f"Invalid LLM duplicate status: {answer}"
                )

            reason = answer.get(
                "reason",
                "No reason supplied.",
            )
            candidate_diagnostics.append(
                {
                    "id": candidate.id,
                    "similarity": retrieved.similarity,
                    "judgment": judgment,
                    "reason": reason,
                    "prompt": prompt,
                    "raw_response": getattr(
                        context.llm,
                        "last_raw_response",
                        None,
                    ),
                    "parsed_response": answer,
                }
            )

            if judgment == "DUPLICATE":
                duplicate_ids.append(candidate.id)
            elif judgment == "REVIEW":
                has_review = True

        if duplicate_ids:
            status = CheckStatus.FAIL
            message = (
                "One or more likely duplicate requirements "
                "were detected among the retrieved candidates."
            )
        elif has_review:
            status = CheckStatus.REVIEW
            message = (
                "No duplicate was confirmed, but at least one "
                "retrieved candidate comparison was inconclusive."
            )
        else:
            status = CheckStatus.PASS
            message = (
                "No duplicate was detected among the retrieved "
                "candidates."
            )

        return [
            CheckResult(
                check_id=self.check_id,
                implementation=self.implementation,
                target_id=target.id,
                status=status,
                message=message,
                related_ids=duplicate_ids,
                metadata={
                    "model": context.llm.model,
                    "candidates": candidate_diagnostics,
                },
            )
        ]

    @staticmethod
    def _build_prompt(target: NIO, candidate: NIO) -> str:
        return f"""
Requirement A:
{target.specification}

Requirement B:
{candidate.specification}

Determine whether A and B express substantially the same requirement.

Treat them as duplicates only when they impose materially the same
obligation or constraint on the same behavior under materially the same
conditions, such that keeping both would be redundant.

Do NOT call requirements duplicates merely because:
- they discuss the same topic
- they share terminology
- one is related to the other
- one is more specific than the other
- they partially overlap

Return REVIEW if the available text is insufficient to make a reliable
judgment.

Return ONLY a JSON object in this exact form:
{{
  "status": "DUPLICATE" | "NOT_DUPLICATE" | "REVIEW",
  "reason": "brief explanation"
}}
""".strip()
