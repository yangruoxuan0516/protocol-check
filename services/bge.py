from typing import List

from openai import OpenAI


class BGEEmbeddingService:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
    ):
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        ordered_data = sorted(
            response.data,
            key=lambda item: item.index,
        )
        return [item.embedding for item in ordered_data]
