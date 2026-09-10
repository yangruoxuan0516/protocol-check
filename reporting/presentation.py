from typing import Any, Dict, Iterable, List


def tokenize_prompt_evidence(
    prompt: str,
    retrieved_chunks: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    chunks = sorted(
        list(retrieved_chunks),
        key=lambda item: item.get("rank", 0),
    )
    if not chunks:
        return {"available": False, "text": prompt}

    tokenized = prompt
    for index, chunk in enumerate(chunks, start=1):
        text = chunk.get("text")
        if not isinstance(text, str) or not text or text not in tokenized:
            return {"available": False, "text": prompt}
        tokenized = tokenized.replace(text, f"<E{index}>", 1)
    return {"available": True, "text": tokenized}


def add_presentation_data(results: List[Dict[str, Any]]) -> None:
    for result in results:
        metadata = result.get("metadata", {})
        prompt = metadata.get("prompt")
        chunks = metadata.get("retrieved_chunks")
        if isinstance(chunks, list):
            presentation = result.setdefault("_presentation", {})
            presentation["retrieved_chunks"] = prepare_retrieved_chunks(
                chunks,
                metadata.get("supporting_chunk_ids", []),
            )
            if isinstance(prompt, str):
                presentation["tokenized_prompt"] = tokenize_prompt_evidence(
                    prompt,
                    chunks,
                )


def prepare_retrieved_chunks(
    retrieved_chunks: Iterable[Dict[str, Any]],
    supporting_chunk_ids: Iterable[str],
) -> List[Dict[str, Any]]:
    cited_ids = set(supporting_chunk_ids)
    prepared = []
    for chunk in sorted(
        retrieved_chunks,
        key=lambda item: item.get("rank", 0),
    ):
        display_chunk = dict(chunk)
        display_chunk["cited"] = chunk.get("chunk_id") in cited_ids
        prepared.append(display_chunk)
    return prepared
