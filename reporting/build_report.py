import argparse
import sys
from pathlib import Path
from typing import List


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_config
from reporting.report import write_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a self-contained offline protocol-check report."
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--results-dir",
        type=Path,
        help="Directory containing the explicitly selected result JSONL files.",
    )
    inputs.add_argument(
        "--results",
        type=Path,
        nargs="+",
        help="Explicit result JSONL files to include.",
    )
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing report HTML file.",
    )
    return parser.parse_args()


def resolve_result_paths(args) -> List[Path]:
    if args.results is not None:
        return list(args.results)
    if not args.results_dir.is_dir():
        raise ValueError(f"Results directory does not exist: {args.results_dir}")
    paths = sorted(args.results_dir.glob("*.jsonl"))
    if not paths:
        raise ValueError(f"No result JSONL files found in {args.results_dir}")
    return paths


def main() -> None:
    args = parse_args()
    try:
        config = load_config()
        if not config.data.protocol:
            raise ValueError(
                "Protocol input is not configured. Set [data].protocol in "
                "config.toml."
            )
        result_paths = resolve_result_paths(args)
        write_report(
            protocol_path=Path(config.data.protocol),
            result_paths=result_paths,
            output_path=args.output,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
    print(f"Wrote offline report to {args.output}")


if __name__ == "__main__":
    main()
