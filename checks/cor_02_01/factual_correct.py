from checks.base import Check
from domain.model import NIO
from domain.result import CheckResult, CheckStatus


class FactualCorrectCheck(Check):
    check_id = "COR-02.01.factual_correct"

    # 这个名字非常重要
    # 以后可以有 v1_arinc_rag
    implementation = "v0_llm_only"

    requires = ("llm",)

    def run(
        self,
        target: NIO,
        context,
    ) -> list[CheckResult]:

        prompt = f"""
You are reviewing a technical requirement from an
aircraft data network interoperability specification.

Requirement ID:
{target.id}

Requirement:
{target.specification}

Determine whether the requirement is factually correct.

For this experimental version, make the judgment based
on the information available to you.

Return ONLY a JSON object in this exact form:

{{
  "status": "PASS" | "FAIL" | "REVIEW",
  "reason": "brief explanation"
}}

Use REVIEW if you cannot reliably determine factual
correctness from the available information.
""".strip()

        answer = context.llm.ask_json(prompt)

        try:
            status = CheckStatus(answer["status"])
        except (KeyError, ValueError):
            raise ValueError(
                f"Invalid LLM status: {answer}"
            )

        if status not in {
            CheckStatus.PASS,
            CheckStatus.FAIL,
            CheckStatus.REVIEW,
        }:
            raise ValueError(
                f"Invalid LLM status: {answer}"
            )

        return [
            CheckResult(
                check_id=self.check_id,
                implementation=self.implementation,
                target_id=target.id,
                status=status,
                message=answer.get(
                    "reason",
                    "No reason supplied.",
                ),
                metadata={
                    "prompt": prompt,
                    "raw_model_response": getattr(
                        context.llm,
                        "last_raw_response",
                        None,
                    ),
                    "parsed_model_response": answer,
                    "model": context.llm.model,
                },
            )
        ]
