from checks.base import Check
from domain.model import NIO
from domain.result import CheckResult, CheckStatus, Evidence


class FactualCorrectArincCheck(Check):
    check_id = "COR-02.01.factual_correct_arinc"
    implementation = "v1_arinc_topk"
    requires = ("llm", "nio_retriever", "standard_retriever")

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

        query_embedding = context.nio_retriever.get_embedding(target.id)
        matches = context.standard_retriever.search_by_vector(
            query_embedding,
            top_k=context.standard_retriever.top_k,
        )
        prompt = self._build_prompt(target, matches)
        answer = context.llm.ask_json(prompt)

        try:
            status = CheckStatus(answer["status"])
        except (KeyError, ValueError):
            raise ValueError(f"Invalid LLM status: {answer}")
        if status not in {
            CheckStatus.PASS,
            CheckStatus.FAIL,
            CheckStatus.REVIEW,
        }:
            raise ValueError(f"Invalid LLM status: {answer}")

        supporting_chunk_ids = answer.get("supporting_chunk_ids")
        if not isinstance(supporting_chunk_ids, list) or not all(
            isinstance(chunk_id, str)
            for chunk_id in supporting_chunk_ids
        ):
            raise ValueError(
                "LLM supporting_chunk_ids must be a list of strings."
            )

        matches_by_id = {
            match.chunk.chunk_id: match
            for match in matches
        }
        unknown_ids = [
            chunk_id
            for chunk_id in supporting_chunk_ids
            if chunk_id not in matches_by_id
        ]
        if unknown_ids:
            raise ValueError(
                "LLM cited unknown ARINC chunk IDs: "
                + ", ".join(unknown_ids)
            )

        messages = {
            CheckStatus.PASS: (
                "The supplied ARINC evidence was judged sufficient to "
                "support the material factual or technical assertion."
            ),
            CheckStatus.FAIL: (
                "The supplied ARINC evidence was judged to directly "
                "contradict a material factual or technical assertion."
            ),
            CheckStatus.REVIEW: (
                "The supplied ARINC evidence was insufficient or too "
                "general for a reliable factual or technical judgment."
            ),
        }
        evidence = [
            self._to_evidence(matches_by_id[chunk_id])
            for chunk_id in supporting_chunk_ids
        ]

        return [
            CheckResult(
                check_id=self.check_id,
                implementation=self.implementation,
                target_id=target.id,
                status=status,
                message=messages[status],
                evidence=evidence,
                metadata={
                    "target_requirement": {
                        "id": target.id,
                        "section_number": target.section_number,
                        "specification": target.specification,
                    },
                    "retrieved_chunks": [
                        self._match_metadata(rank, match)
                        for rank, match in enumerate(matches, start=1)
                    ],
                    "supporting_chunk_ids": supporting_chunk_ids,
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

    @staticmethod
    def _build_prompt(target: NIO, matches) -> str:
        evidence_blocks = []
        for rank, match in enumerate(matches, start=1):
            chunk = match.chunk
            evidence_blocks.append(
                f"""[Evidence {rank}]
Chunk ID: {chunk.chunk_id}
Document: {chunk.document}
Section: {chunk.section_number or "N/A"}
Title: {chunk.section_title or "N/A"}
Pages: {chunk.page_start}-{chunk.page_end}
Content type: {chunk.content_type}
Similarity: {match.similarity:.6f} (retrieval ranking only)

{chunk.text}"""
            )
        evidence_text = "\n\n".join(evidence_blocks) or "No evidence retrieved."

        return f"""
Judge factual and technical correctness only from the supplied target
requirement and supplied ARINC evidence. Do not use unstated knowledge of
ARINC 664.

Target requirement ({target.id}):
{target.specification}

ARINC evidence:
{evidence_text}

Related evidence is not necessarily sufficient evidence. Do not assume the
requirement is correct merely because it is compatible with or related to the
retrieved material. Absence of contradiction is not support. Similarity only
explains retrieval ranking and is not evidence strength.

ARINC may be more general than the inspected protocol. If the protocol adds a
project-specific value, actor, condition, responsibility, feature, or
constraint not established by the supplied evidence, use REVIEW unless the
evidence directly contradicts it. Use PASS only when the evidence sufficiently
supports the material assertion. Use FAIL only for a direct material
contradiction. Prefer REVIEW over unsupported confidence.

Do not judge writing quality, grammar, single-shall structure, naming
consistency, duplication, implementation freedom, or other checklist criteria.

Return ONLY a JSON object in this exact form:
{{
  "status": "PASS" | "FAIL" | "REVIEW",
  "reason": "brief explanation",
  "supporting_chunk_ids": ["retrieved chunk IDs actually relied upon"]
}}
""".strip()

    @staticmethod
    def _match_metadata(rank, match):
        chunk = match.chunk
        return {
            "rank": rank,
            "chunk_id": chunk.chunk_id,
            "document": chunk.document,
            "content_type": chunk.content_type,
            "section_number": chunk.section_number,
            "section_title": chunk.section_title,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "similarity": match.similarity,
            "text": chunk.text,
        }

    @classmethod
    def _to_evidence(cls, match):
        chunk = match.chunk
        return Evidence(
            source_type=chunk.document,
            source_id=chunk.chunk_id,
            text=chunk.text,
            metadata={
                "content_type": chunk.content_type,
                "section_number": chunk.section_number,
                "section_title": chunk.section_title,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "similarity": match.similarity,
            },
        )
