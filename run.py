import argparse
import json
from pathlib import Path
from typing import Any, Iterable, List, TextIO

from tqdm import tqdm

from config import load_config
from domain.result import CheckResult
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
from parsing.standard_jsonl import load_standard_jsonl
from services.bge import BGEEmbeddingService
from services.embedding_store import EmbeddingStore
from services.nio_retriever import NIORetriever
from services.qwen import QwenService
from services.standard_retriever import StandardRetriever


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        default=None,
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

    group.add_argument(
        "--inspect-standard-retrieval",
        action="store_true",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "-o",
        "--output",
        default=None,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing output file.",
    )

    parser.add_argument(
        "--rebuild-embeddings",
        action="store_true",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--target-id",
        action="append",
        default=None,
    )

    return parser.parse_args()


def resolve_protocol_input(
    cli_input: Any,
    configured_input: Any,
) -> Path:
    selected = cli_input or configured_input
    if not selected:
        raise SystemExit(
            "Protocol input is required. Use --input or configure "
            "[data].protocol."
        )
    return Path(selected)


def get_inspection_targets(protocol, limit, target_ids=None):
    if target_ids:
        if len(set(target_ids)) != len(target_ids):
            raise SystemExit("Duplicate --target-id values are not allowed.")

        records_by_id = {nio.id: nio for nio in protocol.nios}
        selected = []
        for target_id in target_ids:
            target = records_by_id.get(target_id)
            if target is None:
                raise SystemExit(f"Requested target ID does not exist: {target_id}")
            if target.type != "requirement":
                raise SystemExit(
                    f"Requested target ID is not a requirement: {target_id}"
                )
            selected.append(target)
        return selected

    targets = [nio for nio in protocol.nios if nio.type == "requirement"]
    if limit is not None:
        targets = targets[:limit]
    return targets


def open_output_file(
    output_path: Path,
    overwrite: bool,
) -> TextIO:
    mode = "w" if overwrite else "x"
    try:
        return output_path.open(
            mode,
            encoding="utf-8",
        )
    except FileExistsError:
        raise SystemExit(
            f"Output file already exists: {output_path}. "
            "Use --overwrite to replace it."
        ) from None


def write_results_incrementally(
    result_batches: Iterable[List[CheckResult]],
    output_file: TextIO,
    progress: Any,
) -> int:
    result_count = 0

    for check_results in result_batches:
        for result in check_results:
            json.dump(
                result.to_dict(),
                output_file,
                ensure_ascii=False,
            )
            output_file.write("\n")
            output_file.flush()
            result_count += 1

        progress.update(1)

    return result_count


def write_inspection_incrementally(
    targets,
    nio_retriever,
    standard_retriever,
    top_k: int,
    output_file: TextIO,
    progress: Any,
) -> int:
    record_count = 0

    for target in targets:
        query_embedding = nio_retriever.get_embedding(target.id)
        matches = standard_retriever.search_by_vector(
            query_embedding,
            top_k=top_k,
        )
        record = {
            "target_id": target.id,
            "target_section_number": target.section_number,
            "query": target.specification,
            "matches": [
                {
                    "rank": rank,
                    "chunk_id": match.chunk.chunk_id,
                    "document": match.chunk.document,
                    "content_type": match.chunk.content_type,
                    "section_number": match.chunk.section_number,
                    "section_title": match.chunk.section_title,
                    "page_start": match.chunk.page_start,
                    "page_end": match.chunk.page_end,
                    "similarity": match.similarity,
                    "text": match.chunk.text,
                }
                for rank, match in enumerate(matches, start=1)
            ],
        }
        json.dump(record, output_file, ensure_ascii=False)
        output_file.write("\n")
        output_file.flush()
        progress.update(1)
        record_count += 1

    return record_count


def create_embedding_store(config, rebuild: bool):
    if not all(
        (
            config.bge.api_key,
            config.bge.base_url,
            config.bge.model,
        )
    ):
        return None
    return EmbeddingStore(
        cache_dir=Path(config.embeddings.cache_dir),
        embedding_service=BGEEmbeddingService(
            api_key=config.bge.api_key,
            base_url=config.bge.base_url,
            model=config.bge.model,
        ),
        rebuild=rebuild,
    )


def run_standard_inspection(
    args,
    config,
    protocol,
    protocol_path: Path,
) -> None:
    embedding_store = create_embedding_store(
        config,
        args.rebuild_embeddings,
    )
    if embedding_store is None:
        raise SystemExit(
            "BGE configuration is required for standard retrieval inspection."
        )
    if not config.standards.arinc664p2 or not config.standards.arinc664p7:
        raise SystemExit(
            "Both [standards].arinc664p2 and arinc664p7 must be configured."
        )

    p2_path = Path(config.standards.arinc664p2)
    p7_path = Path(config.standards.arinc664p7)
    nio_retriever = NIORetriever(
        protocol=protocol,
        embedding_store=embedding_store,
        source_path=protocol_path,
        top_k=config.retrieval.nio.top_k,
    )
    standard_retriever = StandardRetriever(
        p2_chunks=load_standard_jsonl(str(p2_path)),
        p2_source_path=p2_path,
        p7_chunks=load_standard_jsonl(str(p7_path)),
        p7_source_path=p7_path,
        embedding_store=embedding_store,
        top_k=config.retrieval.standard.top_k,
    )
    targets = get_inspection_targets(
        protocol,
        args.limit,
        args.target_id,
    )
    top_k = (
        args.top_k
        if args.top_k is not None
        else config.retrieval.standard.top_k
    )
    output_path = (
        Path(args.output)
        if args.output is not None
        else Path("retrieval_outputs/arinc_retrieval.jsonl")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open_output_file(output_path, args.overwrite) as output_file:
        with tqdm(
            total=len(targets),
            desc="Inspecting retrieval",
            unit="requirement",
        ) as progress:
            record_count = write_inspection_incrementally(
                targets,
                nio_retriever,
                standard_retriever,
                top_k,
                output_file,
                progress,
            )
    print(f"Wrote {record_count} retrieval records to {output_path}")


def main():
    args = parse_args()

    config = load_config()

    protocol_path = resolve_protocol_input(
        args.input,
        config.data.protocol,
    )
    protocol = load_protocol_jsonl(str(protocol_path))

    if args.inspect_standard_retrieval:
        run_standard_inspection(
            args,
            config,
            protocol,
            protocol_path,
        )
        return

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
    needs_standard_retriever = any(
        "standard_retriever" in check.requires
        for check in checks
    )
    embedding_store = None
    if needs_nio_retriever or needs_standard_retriever:
        embedding_store = create_embedding_store(
            config,
            args.rebuild_embeddings,
        )
    if embedding_store is not None:
        nio_retriever = NIORetriever(
            protocol=protocol,
            embedding_store=embedding_store,
            source_path=protocol_path,
            top_k=config.retrieval.nio.top_k,
        )

    standard_retriever = None
    if (
        needs_standard_retriever
        and embedding_store is not None
        and config.standards.arinc664p2
        and config.standards.arinc664p7
    ):
        p2_path = Path(config.standards.arinc664p2)
        p7_path = Path(config.standards.arinc664p7)
        standard_retriever = StandardRetriever(
            p2_chunks=load_standard_jsonl(str(p2_path)),
            p2_source_path=p2_path,
            p7_chunks=load_standard_jsonl(str(p7_path)),
            p7_source_path=p7_path,
            embedding_store=embedding_store,
            top_k=config.retrieval.standard.top_k,
        )

    context = CheckContext(
        protocol=protocol,
        llm=llm,
        nio_retriever=nio_retriever,
        standard_retriever=standard_retriever,
    )

    runner = Runner(context)

    output_path = (
        Path(args.output)
        if args.output is not None
        else Path(config.runner.output_dir) / "results.jsonl"
    )
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    total_work = runner.count_work_units(
        checks=checks,
        limit=args.limit,
    )
    with open_output_file(
        output_path,
        overwrite=args.overwrite,
    ) as output_file:
        with tqdm(
            total=total_work,
            desc="Checking",
            unit="check-target",
        ) as progress:
            result_count = write_results_incrementally(
                runner.iter_run(
                    checks=checks,
                    limit=args.limit,
                ),
                output_file,
                progress,
            )

    print(
        f"Wrote {result_count} results "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()
