import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


CATALOG_PATH = Path(__file__).with_name("checklist_catalog.json")
ACTIONABLE_STATUSES = {"CHECK", "TRY"}
MATURITY_VALUES = {"implemented", "experimental", "not_implemented"}


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    selected_path = path or CATALOG_PATH
    try:
        with selected_path.open("r", encoding="utf-8") as handle:
            catalog = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load checklist catalog {selected_path}: {exc}")

    _validate_catalog(catalog, selected_path)
    return catalog


def _validate_catalog(catalog: Any, path: Path) -> None:
    if not isinstance(catalog, dict) or not isinstance(
        catalog.get("categories"), list
    ):
        raise ValueError(f"Invalid checklist catalog structure: {path}")

    item_ids: Set[str] = set()
    concept_ids: Set[str] = set()
    for category in catalog["categories"]:
        if not isinstance(category, dict) or not isinstance(
            category.get("items"), list
        ):
            raise ValueError(f"Invalid checklist category in {path}")
        for item in category["items"]:
            item_id = item.get("item_id")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"Invalid checklist item in {path}")
            if item_id in item_ids:
                raise ValueError(f"Duplicate checklist item {item_id} in {path}")
            item_ids.add(item_id)
            concepts = item.get("concepts", [])
            if not isinstance(concepts, list):
                raise ValueError(f"Invalid concepts for {item_id} in {path}")
            for concept in concepts:
                concept_id = concept.get("concept_id")
                if not isinstance(concept_id, str) or not concept_id:
                    raise ValueError(f"Invalid concept under {item_id} in {path}")
                if concept_id in concept_ids:
                    raise ValueError(f"Duplicate concept {concept_id} in {path}")
                concept_ids.add(concept_id)
                if concept.get("interpretation_status") not in {
                    "CHECK",
                    "TRY",
                    "NOT_CHECK",
                }:
                    raise ValueError(
                        f"Invalid interpretation status for {concept_id} in {path}"
                    )
                if concept.get("maturity") not in MATURITY_VALUES:
                    raise ValueError(
                        f"Invalid maturity for {concept_id} in {path}"
                    )
                checker_ids = concept.get("checker_ids")
                if not isinstance(checker_ids, list) or not all(
                    isinstance(checker_id, str) for checker_id in checker_ids
                ):
                    raise ValueError(
                        f"Invalid checker_ids for {concept_id} in {path}"
                    )
                default = concept.get("default_checker_id")
                if default is not None and default not in checker_ids:
                    raise ValueError(
                        f"Default checker for {concept_id} is not mapped in {path}"
                    )


def iter_items(catalog: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for category in catalog["categories"]:
        for item in category["items"]:
            yield item


def iter_concepts(catalog: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in iter_items(catalog):
        for concept in item.get("concepts", []):
            yield concept


def checker_to_concept(catalog: Dict[str, Any]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for concept in iter_concepts(catalog):
        for checker_id in concept["checker_ids"]:
            mapping[checker_id] = concept["concept_id"]
    return mapping


def calculate_coverage(
    catalog: Dict[str, Any],
    registry_checker_ids: Iterable[str],
) -> Dict[str, Any]:
    registry = set(registry_checker_ids)
    totals = _empty_totals()
    category_summaries: List[Dict[str, Any]] = []
    item_details: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for category in catalog["categories"]:
        category_totals = _empty_totals()
        for item in category["items"]:
            actionable = [
                concept
                for concept in item.get("concepts", [])
                if concept["interpretation_status"] in ACTIONABLE_STATUSES
            ]
            covered = []
            for concept in actionable:
                registered = sorted(set(concept["checker_ids"]) & registry)
                is_covered = (
                    concept["maturity"] == "implemented" and bool(registered)
                )
                if concept["maturity"] == "implemented" and not registered:
                    warnings.append(
                        f"{concept['concept_id']} is marked implemented but none "
                        "of its mapped checkers exist in the registry."
                    )
                covered.append(is_covered)

            if not actionable:
                classification = "not_checkable"
            elif all(covered):
                classification = "fully_covered"
            elif any(covered):
                classification = "partially_covered"
            else:
                classification = "not_implemented"

            item_detail = {
                "item_id": item["item_id"],
                "category_id": category["category_id"],
                "classification": classification,
                "actionable_concepts": len(actionable),
                "implemented_concepts": sum(covered),
            }
            item_details.append(item_detail)
            _add_item(category_totals, classification, len(actionable), sum(covered))
            _add_item(totals, classification, len(actionable), sum(covered))

        category_summaries.append(
            {
                "category_id": category["category_id"],
                "title": category["title"],
                **category_totals,
            }
        )

    return {
        **totals,
        "categories": category_summaries,
        "items": item_details,
        "warnings": warnings,
    }


def _empty_totals() -> Dict[str, int]:
    return {
        "item_count": 0,
        "fully_covered": 0,
        "partially_covered": 0,
        "not_implemented": 0,
        "not_checkable": 0,
        "actionable_concepts": 0,
        "implemented_concepts": 0,
    }


def _add_item(
    totals: Dict[str, int],
    classification: str,
    actionable: int,
    implemented: int,
) -> None:
    totals["item_count"] += 1
    totals[classification] += 1
    totals["actionable_concepts"] += actionable
    totals["implemented_concepts"] += implemented
