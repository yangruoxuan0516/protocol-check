import argparse
import json
from pathlib import Path

from config import load_config
from engine.context import CheckContext
from engine.registry import (
    CHECKS,
    get_check,
    get_checks_by_prefix,
)
from engine.runner import Runner
from parsing.nio_jsonl import (
    load_protocol_jsonl,
)
from services.bge import BGEEmbeddingService
from services.nio_retriever import NIORetriever
from services.qwen import QwenService


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
    )

    group = parser.add_mutually_exclusive_group(
        required=True
    )

    group.add_argument(
        "--check",
        help=(
            "Exact check ID, e.g. "
            "COR-02.01.factual_correct"
        ),
    )

    group.add_argument(
        "--requirement",
        help=(
            "Run all checks under a checklist "
            "item, e.g. COR-02.01"
        ),
    )

    group.add_argument(
        "--all",
        action="store_true",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--output",
        default=None,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    config = load_config()

    if args.check:
        checks = [
            get_check(args.check)
        ]

    elif args.requirement:
        checks = get_checks_by_prefix(
            args.requirement
        )

        if not checks:
            raise ValueError(
                "No checks found for "
                f"{args.requirement}"
            )

    else:
        checks = list(
            CHECKS.values()
        )

    protocol = load_protocol_jsonl(
        args.input
    )

    llm = None
    needs_llm = any(
        "llm" in check.requires
        for check in checks
    )
    if needs_llm and all(
        (
            config.qwen.api_key,
            config.qwen.base_url,
            config.qwen.model,
        )
    ):
        llm = QwenService(
            api_key=config.qwen.api_key,
            base_url=config.qwen.base_url,
            model=config.qwen.model,
            temperature=config.qwen.temperature,
        )

    nio_retriever = None
    needs_nio_retriever = any(
        "nio_retriever" in check.requires
        for check in checks
    )
    if needs_nio_retriever and all(
        (
            config.bge.api_key,
            config.bge.base_url,
            config.bge.model,
        )
    ):
        embedding_service = BGEEmbeddingService(
            api_key=config.bge.api_key,
            base_url=config.bge.base_url,
            model=config.bge.model,
        )
        nio_retriever = NIORetriever(
            protocol=protocol,
            embedding_service=embedding_service,
            top_k=config.retrieval.nio.top_k,
        )

    context = CheckContext(
        protocol=protocol,
        llm=llm,
        nio_retriever=nio_retriever,
    )

    runner = Runner(context)

    results = runner.run(
        checks=checks,
        limit=args.limit,
    )

    output_path = (
        Path(args.output)
        if args.output is not None
        else Path(config.runner.output_dir) / "results.jsonl"
    )
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        for result in results:
            json.dump(
                result.to_dict(),
                f,
                ensure_ascii=False,
            )
            f.write("\n")

    print(
        f"Wrote {len(results)} results "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()
