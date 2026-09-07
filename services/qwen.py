import json
from typing import Any, Optional

from openai import OpenAI


class QwenService:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.0,
    ):
        self.model = model
        self.temperature = temperature
        self.last_raw_response: Optional[str] = None

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def ask(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=self.temperature,
        )

        return response.choices[0].message.content or ""
    
    def ask_json(self, prompt: str) -> dict[str, Any]:
        raw = self.ask(prompt)
        self.last_raw_response = raw

        parsed = self._parse_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON response must be an object.")
        return parsed

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = raw.strip()

        # 兼容 ```json ... ```
        if text.startswith("```"):
            lines = text.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 非严格 fallback：
        # 找第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                f"LLM did not return valid JSON:\n{raw}"
            )

        return json.loads(text[start : end + 1])
