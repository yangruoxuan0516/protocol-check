import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from domain.model import NIO, Protocol


VALID_STATUSES = {
    "PASS",
    "FAIL",
    "REVIEW",
    "NOT_APPLICABLE",
    "BLOCKED",
    "ERROR",
}
SENTINEL_TARGET_IDS = {"__CHECK__", "__UNKNOWN__"}
STATUS_SEVERITY = {
    "ERROR": 0,
    "BLOCKED": 1,
    "FAIL": 2,
    "REVIEW": 3,
    "PASS": 4,
    "NOT_APPLICABLE": 5,
}


@dataclass
class LoadedResult:
    data: Dict[str, Any]
    source_path: Path
    line_number: int

    @property
    def key(self) -> Tuple[str, str, str]:
        return (
            self.data["check_id"],
            self.data["implementation"],
            self.data["target_id"],
        )


def load_result_files(paths: Sequence[Path]) -> List[LoadedResult]:
    normalized = [Path(path).resolve() for path in paths]
    if len(set(normalized)) != len(normalized):
        raise ValueError("The same result JSONL file was supplied more than once.")

    loaded: List[LoadedResult] = []
    key_sources: Dict[Tuple[str, str, str], Path] = {}
    for path in normalized:
        if not path.is_file():
            raise ValueError(f"Result file does not exist: {path}")
        try:
            handle = path.open("r", encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Unable to read result file {path}: {exc}")
        with handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                try:
                    value = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Malformed JSON in {path} at line {line_number}: {exc.msg}"
                    )
                _validate_result(value, path, line_number)
                record = LoadedResult(value, path, line_number)
                previous_path = key_sources.get(record.key)
                if previous_path is not None and previous_path != path:
                    check_id, implementation, target_id = record.key
                    raise ValueError(
                        "Ambiguous result dataset: "
                        f"{check_id} / {implementation} / {target_id} appears in "
                        f"both {previous_path} and {path}."
                    )
                key_sources[record.key] = path
                loaded.append(record)
    return loaded


def _validate_result(value: Any, path: Path, line_number: int) -> None:
    location = f"{path} at line {line_number}"
    if not isinstance(value, dict):
        raise ValueError(f"Invalid CheckResult in {location}: expected an object.")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid CheckResult in {location}: value is not strict JSON: {exc}"
        ) from None

    required_string_fields = (
        "check_id",
        "implementation",
        "target_id",
        "status",
        "message",
    )
    for field in required_string_fields:
        if field not in value or not isinstance(value[field], str):
            raise ValueError(
                f"Invalid CheckResult in {location}: {field!r} must be a string."
            )
    if not value["check_id"] or not value["implementation"] or not value["target_id"]:
        raise ValueError(
            f"Invalid CheckResult in {location}: identifiers must not be empty."
        )
    if value["status"] not in VALID_STATUSES:
        raise ValueError(
            f"Invalid CheckResult in {location}: unsupported status "
            f"{value['status']!r}."
        )

    related_ids = value.get("related_ids")
    if not isinstance(related_ids, list) or not all(
        isinstance(item, str) for item in related_ids
    ):
        raise ValueError(
            f"Invalid CheckResult in {location}: 'related_ids' must be a list "
            "of strings."
        )
    evidence = value.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError(
            f"Invalid CheckResult in {location}: 'evidence' must be a list."
        )
    for index, entry in enumerate(evidence, start=1):
        _validate_evidence(entry, location, index)
    if not isinstance(value.get("metadata"), dict):
        raise ValueError(
            f"Invalid CheckResult in {location}: 'metadata' must be an object."
        )


def _validate_evidence(value: Any, location: str, index: int) -> None:
    prefix = f"Invalid evidence item {index} in CheckResult at {location}"
    if not isinstance(value, dict):
        raise ValueError(f"{prefix}: expected an object.")
    if not isinstance(value.get("source_type"), str):
        raise ValueError(f"{prefix}: 'source_type' must be a string.")
    for field in ("source_id", "text"):
        if field not in value or value[field] is not None and not isinstance(
            value[field], str
        ):
            raise ValueError(f"{prefix}: {field!r} must be a string or null.")
    if not isinstance(value.get("metadata"), dict):
        raise ValueError(f"{prefix}: 'metadata' must be an object.")


def build_report_dataset(
    protocol: Protocol,
    loaded_results: Sequence[LoadedResult],
    result_paths: Sequence[Path],
) -> Dict[str, Any]:
    protocol_by_id = {nio.id: nio for nio in protocol.nios}
    represented = set()
    framework_indexes: List[int] = []
    results: List[Dict[str, Any]] = []
    variant_keys = sorted(
        {
            (record.data["check_id"], record.data["implementation"])
            for record in loaded_results
        }
    )
    variant_ids = {key: f"variant-{index}" for index, key in enumerate(variant_keys)}
    variants = []
    for key in variant_keys:
        check_id, implementation = key
        source_files = sorted(
            {
                record.source_path.name
                for record in loaded_results
                if (record.data["check_id"], record.data["implementation"]) == key
            }
        )
        variants.append(
            {
                "variant_id": variant_ids[key],
                "check_id": check_id,
                "implementation": implementation,
                "source_files": source_files,
            }
        )

    cells: Dict[str, Dict[str, List[int]]] = {
        variant["variant_id"]: {} for variant in variants
    }
    for record in loaded_results:
        target_id = record.data["target_id"]
        result = dict(record.data)
        variant_id = variant_ids[(result["check_id"], result["implementation"])]
        result["_source_file"] = record.source_path.name
        result["_source_line"] = record.line_number
        result["_variant_id"] = variant_id
        result_index = len(results)
        results.append(result)
        if target_id in SENTINEL_TARGET_IDS:
            framework_indexes.append(result_index)
            continue
        if target_id not in protocol_by_id:
            raise ValueError(
                f"Result target {target_id!r} from {record.source_path} line "
                f"{record.line_number} does not exist in the protocol JSONL."
            )
        represented.add(target_id)
        cells[variant_id].setdefault(target_id, []).append(result_index)

    ordered_targets = [nio for nio in protocol.nios if nio.id in represented]
    protocol_records = [_serialize_nio(nio) for nio in ordered_targets]
    all_protocol_records = [_serialize_nio(nio) for nio in protocol.nios]
    return {
        "result_files": [Path(path).name for path in result_paths],
        "record_count": len(loaded_results),
        "target_count": len(ordered_targets),
        "checker_implementation_count": len(variants),
        "targets": protocol_records,
        "target_by_id": {
            record["id"]: record for record in all_protocol_records
        },
        "section_groups": build_section_groups(ordered_targets),
        "variants": variants,
        "results": results,
        "cells": cells,
        "framework_result_indexes": framework_indexes,
    }


def _serialize_nio(nio: NIO) -> Dict[str, Any]:
    source = None
    if nio.source is not None:
        source = {
            "file": nio.source.file,
            "table": nio.source.table,
            "word_row": nio.source.word_row,
        }
    return {
        "id": nio.id,
        "type": nio.type,
        "section_number": nio.section_number,
        "specification": nio.specification,
        "rationale": nio.rationale,
        "req": nio.req,
        "source": source,
    }


def build_section_groups(nios: Iterable[NIO]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    previous_section = object()
    for nio in nios:
        section = nio.section_number
        if section != previous_section:
            groups.append(
                {
                    "section_number": section,
                    "label": f"Section {section}" if section else "Unsectioned",
                    "target_ids": [],
                }
            )
            previous_section = section
        groups[-1]["target_ids"].append(nio.id)
    return groups


def aggregate_status(results: Sequence[Dict[str, Any]]) -> str:
    if not results:
        raise ValueError("Cannot aggregate an empty result collection.")
    return min(results, key=lambda item: STATUS_SEVERITY[item["status"]])["status"]
