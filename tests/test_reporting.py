import json
import re
from pathlib import Path

import pytest

from engine.registry import CHECKS
from reporting.catalog import (
    calculate_coverage,
    iter_concepts,
    iter_items,
    load_catalog,
)
from reporting.data import (
    aggregate_status,
    build_report_dataset,
    load_result_files,
)
from reporting.html_report import render_html
from reporting.presentation import (
    prepare_retrieved_chunks,
    tokenize_prompt_evidence,
)
from reporting.report import _prepare_catalog, build_report
from parsing.nio_jsonl import load_protocol_jsonl


def protocol_record(
    nio_id,
    specification="Synthetic requirement.",
    section_number="4.3",
    nio_type="requirement",
):
    return {
        "id": nio_id,
        "type": nio_type,
        "section_number": section_number,
        "specification": specification,
        "rationale": None,
        "req": "Yes",
        "source": {"file": "fixture.docx", "table": 1, "word_row": 12},
    }


def result_record(
    check_id="COR-02.01.single_shall",
    implementation="v0_exact_string",
    target_id="NIO-1",
    status="PASS",
    metadata=None,
    evidence=None,
):
    return {
        "check_id": check_id,
        "implementation": implementation,
        "target_id": target_id,
        "related_ids": [],
        "status": status,
        "message": "Synthetic result.",
        "evidence": evidence or [],
        "metadata": metadata or {},
    }


def write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def make_protocol(tmp_path, records=None):
    path = tmp_path / "protocol.jsonl"
    write_jsonl(
        path,
        records
        or [
            protocol_record("NIO-1"),
            protocol_record("NIO-2", section_number="4.4"),
        ],
    )
    return path, load_protocol_jsonl(str(path))


def extract_payload(html):
    match = re.search(
        r'<script id="report-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match
    return json.loads(match.group(1))


def test_catalog_contains_53_items_in_expected_categories():
    catalog = load_catalog()
    items = list(iter_items(catalog))

    assert len(items) == 53
    assert sum(item["item_id"].startswith("COR-") for item in items) == 20
    assert sum(item["item_id"].startswith("CPL-") for item in items) == 33


def test_multiple_implementations_map_to_one_factual_concept():
    concepts = {
        concept["concept_id"]: concept for concept in iter_concepts(load_catalog())
    }
    factual = concepts["COR-02.01.factual_correct"]

    assert factual["checker_ids"] == [
        "COR-02.01.factual_correct",
        "COR-02.01.factual_correct_arinc",
    ]
    coverage = calculate_coverage(load_catalog(), CHECKS)
    assert coverage["actionable_concepts"] == 29


def test_current_registry_catalog_coverage_is_conservative():
    coverage = calculate_coverage(load_catalog(), CHECKS)

    assert coverage["implemented_concepts"] == 1
    assert coverage["partially_covered"] == 1
    assert coverage["fully_covered"] == 0


def test_coverage_classifies_all_four_item_states():
    catalog = {
        "categories": [
            {
                "category_id": "test",
                "title": "Test",
                "items": [
                    {"item_id": "FULL", "concepts": [concept("a", "implemented", ["a"])]},
                    {
                        "item_id": "PARTIAL",
                        "concepts": [
                            concept("b", "implemented", ["b"]),
                            concept("c", "not_implemented", []),
                        ],
                    },
                    {"item_id": "NONE", "concepts": [concept("d", "not_implemented", [])]},
                    {"item_id": "NA", "concepts": [concept("e", "not_implemented", [], "NOT_CHECK")]},
                ],
            }
        ]
    }

    coverage = calculate_coverage(catalog, {"a", "b"})

    assert coverage["fully_covered"] == 1
    assert coverage["partially_covered"] == 1
    assert coverage["not_implemented"] == 1
    assert coverage["not_checkable"] == 1


def concept(concept_id, maturity, checker_ids, status="CHECK"):
    return {
        "concept_id": concept_id,
        "title": concept_id,
        "interpretation_status": status,
        "maturity": maturity,
        "checker_ids": checker_ids,
        "default_checker_id": checker_ids[0] if checker_ids else None,
    }


def test_malformed_result_json_reports_filename_and_line(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text(
        json.dumps(result_record()) + "\n{broken\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_result_files([path])

    assert str(path) in str(exc_info.value)
    assert "line 2" in str(exc_info.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "UNKNOWN"),
        ("related_ids", "NIO-2"),
        ("evidence", {}),
        ("metadata", []),
    ],
)
def test_invalid_check_result_shape_is_rejected(tmp_path, field, value):
    path = tmp_path / "invalid.jsonl"
    record = result_record()
    record[field] = value
    write_jsonl(path, [record])

    with pytest.raises(ValueError, match="Invalid CheckResult"):
        load_result_files([path])


def test_multiple_result_files_are_loaded(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    write_jsonl(first, [result_record(target_id="NIO-1")])
    write_jsonl(second, [result_record(target_id="NIO-2")])

    assert len(load_result_files([first, second])) == 2


def test_repeated_key_within_one_file_is_tolerated_and_aggregated(tmp_path):
    path = tmp_path / "results.jsonl"
    write_jsonl(
        path,
        [result_record(status="PASS"), result_record(status="REVIEW")],
    )

    loaded = load_result_files([path])

    assert len(loaded) == 2
    assert aggregate_status([record.data for record in loaded]) == "REVIEW"


def test_repeated_key_across_files_is_rejected(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    write_jsonl(first, [result_record()])
    write_jsonl(second, [result_record()])

    with pytest.raises(ValueError, match="Ambiguous result dataset"):
        load_result_files([first, second])


def test_framework_sentinels_do_not_become_matrix_rows(tmp_path):
    _, protocol = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    write_jsonl(
        path,
        [
            result_record(target_id="__CHECK__", status="BLOCKED"),
            result_record(target_id="__UNKNOWN__", status="ERROR"),
            result_record(target_id="NIO-1"),
        ],
    )

    dataset = build_report_dataset(protocol, load_result_files([path]), [path])

    assert [target["id"] for target in dataset["targets"]] == ["NIO-1"]
    assert len(dataset["framework_result_indexes"]) == 2


def test_unknown_normal_target_is_integrity_error(tmp_path):
    _, protocol = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    write_jsonl(path, [result_record(target_id="NIO-404")])

    with pytest.raises(ValueError, match="does not exist in the protocol"):
        build_report_dataset(protocol, load_result_files([path]), [path])


def test_matrix_target_union_uses_protocol_order(tmp_path):
    records = [
        protocol_record("NIO-3"),
        protocol_record("NIO-1"),
        protocol_record("NIO-2"),
    ]
    _, protocol = make_protocol(tmp_path, records)
    path = tmp_path / "results.jsonl"
    write_jsonl(path, [result_record(target_id="NIO-2"), result_record(target_id="NIO-3")])

    dataset = build_report_dataset(protocol, load_result_files([path]), [path])

    assert [target["id"] for target in dataset["targets"]] == ["NIO-3", "NIO-2"]


def test_section_grouping_preserves_contiguous_protocol_order(tmp_path):
    records = [
        protocol_record("NIO-1", section_number="4.1"),
        protocol_record("NIO-2", section_number="4.1"),
        protocol_record("NIO-3", section_number=None),
    ]
    _, protocol = make_protocol(tmp_path, records)
    path = tmp_path / "results.jsonl"
    write_jsonl(path, [result_record(target_id=record["id"]) for record in records])

    dataset = build_report_dataset(protocol, load_result_files([path]), [path])

    assert dataset["section_groups"] == [
        {"section_number": "4.1", "label": "Section 4.1", "target_ids": ["NIO-1", "NIO-2"]},
        {"section_number": None, "label": "Unsectioned", "target_ids": ["NIO-3"]},
    ]


def test_unmapped_checker_is_retained_but_does_not_change_coverage(tmp_path):
    protocol_path, _ = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    write_jsonl(path, [result_record(check_id="CUSTOM.check", implementation="custom")])

    payload = extract_payload(build_report(protocol_path, [path], generated_at="2026-01-01T00:00:00Z"))

    assert payload["unmapped_checker_ids"] == ["CUSTOM.check"]
    assert payload["dataset"]["results"][0]["check_id"] == "CUSTOM.check"
    assert payload["coverage"]["implemented_concepts"] == 1


def test_catalog_default_implementation_is_selected_when_present(tmp_path):
    _, protocol = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    write_jsonl(
        path,
        [
            result_record("COR-02.01.factual_correct", "v0_llm_only"),
            result_record("COR-02.01.factual_correct_arinc", "v1_arinc_topk"),
        ],
    )
    dataset = build_report_dataset(protocol, load_result_files([path]), [path])

    prepared = _prepare_catalog(load_catalog(), dataset, {})
    factual = next(
        concept
        for category in prepared["categories"]
        for item in category["items"]
        for concept in item["concepts"]
        if concept["concept_id"] == "COR-02.01.factual_correct"
    )
    selected = next(
        variant
        for variant in factual["available_variants"]
        if variant["variant_id"] == factual["selected_variant_id"]
    )

    assert selected["check_id"] == "COR-02.01.factual_correct_arinc"
    assert factual["preferred_available"] is True


def test_catalog_falls_back_deterministically_when_default_is_absent(tmp_path):
    _, protocol = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    write_jsonl(path, [result_record("COR-02.01.factual_correct", "v0_llm_only")])
    dataset = build_report_dataset(protocol, load_result_files([path]), [path])

    prepared = _prepare_catalog(load_catalog(), dataset, {})
    factual = next(
        concept
        for category in prepared["categories"]
        for item in category["items"]
        for concept in item["concepts"]
        if concept["concept_id"] == "COR-02.01.factual_correct"
    )

    assert factual["selected_variant_id"] == factual["available_variants"][0]["variant_id"]
    assert factual["preferred_available"] is False


def test_arinc_chunks_are_ranked_and_citation_data_is_preserved(tmp_path):
    protocol_path, _ = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    metadata = {
        "retrieved_chunks": [
            {"rank": 2, "chunk_id": "E2", "text": "Evidence two"},
            {"rank": 1, "chunk_id": "E1", "text": "Evidence one"},
        ],
        "supporting_chunk_ids": ["E1"],
        "prompt": "Evidence one\nEvidence two",
    }
    write_jsonl(path, [result_record(metadata=metadata)])

    payload = extract_payload(build_report(protocol_path, [path]))
    result = payload["dataset"]["results"][0]

    assert [chunk["rank"] for chunk in sorted(result["metadata"]["retrieved_chunks"], key=lambda c: c["rank"])] == [1, 2]
    assert result["metadata"]["supporting_chunk_ids"] == ["E1"]
    assert result["_presentation"]["tokenized_prompt"]["text"] == "<E1>\n<E2>"
    assert [
        (chunk["chunk_id"], chunk["cited"])
        for chunk in result["_presentation"]["retrieved_chunks"]
    ] == [("E1", True), ("E2", False)]


def test_retrieved_chunk_presentation_does_not_mutate_audit_data():
    chunks = [
        {"rank": 2, "chunk_id": "E2", "text": "two"},
        {"rank": 1, "chunk_id": "E1", "text": "one"},
    ]

    prepared = prepare_retrieved_chunks(chunks, ["E1"])

    assert [chunk["chunk_id"] for chunk in prepared] == ["E1", "E2"]
    assert [chunk["cited"] for chunk in prepared] == [True, False]
    assert "cited" not in chunks[0]


def test_prompt_tokenization_requires_exact_matches():
    success = tokenize_prompt_evidence(
        "Before exact evidence after",
        [{"rank": 1, "text": "exact evidence"}],
    )
    fallback = tokenize_prompt_evidence(
        "Before altered evidence after",
        [{"rank": 1, "text": "exact evidence"}],
    )

    assert success == {"available": True, "text": "Before <E1> after"}
    assert fallback == {
        "available": False,
        "text": "Before altered evidence after",
    }


def test_generated_html_safely_embeds_script_like_text():
    hostile = "</script><script>alert('x')</script> & <b>markup</b>"
    html = render_html({"value": hostile})

    assert hostile not in html
    assert "\\u003c/script\\u003e" in html
    assert json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.DOTALL).group(1))["value"] == hostile


def test_generated_html_has_no_required_external_resources(tmp_path):
    protocol_path, _ = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    write_jsonl(path, [result_record()])

    html = build_report(protocol_path, [path])

    assert 'src="http' not in html
    assert 'href="http' not in html
    assert "fetch(" not in html
    assert "Matrix" in html
    assert "Result Explorer" in html
    assert "Compare implementations" in html


def test_candidate_requirement_text_can_be_resolved_even_without_own_result(tmp_path):
    protocol_path, _ = make_protocol(tmp_path)
    path = tmp_path / "results.jsonl"
    metadata = {
        "model": "fake",
        "candidates": [
            {
                "id": "NIO-2",
                "similarity": 0.8,
                "judgment": "NOT_DUPLICATE",
                "reason": "Synthetic.",
                "prompt": "Synthetic prompt.",
                "raw_response": "{}",
                "parsed_response": {},
            }
        ],
    }
    write_jsonl(
        path,
        [result_record("COR-02.12.not_duplicate", "v0_bge_topk_qwen", metadata=metadata)],
    )

    payload = extract_payload(build_report(protocol_path, [path]))

    assert payload["dataset"]["target_count"] == 1
    assert payload["dataset"]["target_by_id"]["NIO-2"]["specification"] == "Synthetic requirement."
