import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from engine.registry import CHECKS
from parsing.nio_jsonl import load_protocol_jsonl
from reporting.catalog import (
    calculate_coverage,
    checker_to_concept,
    load_catalog,
)
from reporting.data import build_report_dataset, load_result_files
from reporting.html_report import render_html
from reporting.presentation import add_presentation_data


def registry_snapshot() -> Dict[str, Dict[str, Any]]:
    snapshot: Dict[str, Dict[str, Any]] = {}
    for check_id, check in CHECKS.items():
        scope = getattr(check.scope, "value", str(check.scope))
        snapshot[check_id] = {
            "check_id": check_id,
            "implementation": check.implementation,
            "scope": scope,
            "dependencies": list(check.requires),
            "module": check.__class__.__module__,
        }
    return snapshot


def build_report(
    protocol_path: Path,
    result_paths: Sequence[Path],
    catalog_path: Optional[Path] = None,
    generated_at: Optional[str] = None,
) -> str:
    protocol_path = Path(protocol_path)
    paths = [Path(path) for path in result_paths]
    protocol = load_protocol_jsonl(str(protocol_path))
    catalog = load_catalog(catalog_path)
    registry = registry_snapshot()
    loaded_results = load_result_files(paths)
    dataset = build_report_dataset(protocol, loaded_results, paths)
    add_presentation_data(dataset["results"])

    report_catalog = _prepare_catalog(catalog, dataset, registry)
    coverage = calculate_coverage(catalog, registry.keys())
    mapped = checker_to_concept(catalog)
    report_checker_ids = {
        variant["check_id"] for variant in dataset["variants"]
    }
    unmapped_checker_ids = sorted(report_checker_ids - set(mapped))
    warnings = list(coverage["warnings"])
    registry_unmapped = sorted(set(registry) - set(mapped))
    if registry_unmapped:
        warnings.append(
            "Registered checker(s) not mapped in the checklist catalog: "
            + ", ".join(registry_unmapped)
        )
    if unmapped_checker_ids:
        warnings.append(
            f"{len(unmapped_checker_ids)} checker(s) in this report are not "
            "mapped in checklist_catalog.json."
        )

    payload = {
        "catalog": report_catalog,
        "coverage": coverage,
        "registry": registry,
        "dataset": dataset,
        "unmapped_checker_ids": unmapped_checker_ids,
        "warnings": warnings,
        "provenance": {
            "protocol_source": protocol_path.name,
            "result_files": dataset["result_files"],
            "checker_ids": sorted(report_checker_ids),
            "implementations": sorted(
                {
                    variant["implementation"]
                    for variant in dataset["variants"]
                }
            ),
            "generated_at": generated_at
            or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }
    return render_html(payload)


def write_report(
    protocol_path: Path,
    result_paths: Sequence[Path],
    output_path: Path,
    catalog_path: Optional[Path] = None,
    overwrite: bool = False,
) -> None:
    output_path = Path(output_path)
    html = build_report(protocol_path, result_paths, catalog_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    try:
        with output_path.open(mode, encoding="utf-8") as handle:
            handle.write(html)
    except FileExistsError:
        raise ValueError(
            f"Report already exists: {output_path}. Use --overwrite to replace it."
        ) from None


def _prepare_catalog(
    catalog: Dict[str, Any],
    dataset: Dict[str, Any],
    registry: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    prepared = copy.deepcopy(catalog)
    variants_by_checker: Dict[str, list] = {}
    for variant in dataset["variants"]:
        variants_by_checker.setdefault(variant["check_id"], []).append(variant)

    for category in prepared["categories"]:
        for item in category["items"]:
            for concept in item.get("concepts", []):
                available = []
                for checker_id in concept["checker_ids"]:
                    available.extend(variants_by_checker.get(checker_id, []))
                available.sort(
                    key=lambda value: (
                        value["check_id"],
                        value["implementation"],
                    )
                )
                default_checker_id = concept.get("default_checker_id")
                preferred = [
                    variant
                    for variant in available
                    if variant["check_id"] == default_checker_id
                ]
                selected = preferred[0] if preferred else (available[0] if available else None)
                concept["available_variants"] = available
                concept["selected_variant_id"] = (
                    selected["variant_id"] if selected else None
                )
                concept["preferred_available"] = bool(preferred)
                concept["registered_checker_ids"] = sorted(
                    set(concept["checker_ids"]) & set(registry)
                )
    return prepared

