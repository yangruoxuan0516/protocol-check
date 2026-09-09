import json
from types import SimpleNamespace

import pytest

import run as run_module
from domain.model import NIO, Protocol
from domain.standard import StandardChunk
from run import get_inspection_targets, write_inspection_incrementally
from services.standard_retriever import StandardMatch


class FakeProgress:
    def __init__(self):
        self.completed = 0

    def update(self, amount):
        self.completed += amount


class FakeNIORetriever:
    def __init__(self):
        self.requested_ids = []

    def get_embedding(self, nio_id):
        self.requested_ids.append(nio_id)
        return [1.0, 0.0]


class FakeStandardRetriever:
    def __init__(self, output_path):
        self.output_path = output_path
        self.calls = 0
        self.chunk = StandardChunk(
            chunk_id="ARINC664P7-3.4.2-TEXT-001",
            document="ARINC664P7",
            content_type="text",
            section_number="3.4.2",
            section_title="Virtual Links",
            page_start=42,
            page_end=43,
            text="Retrieved standard evidence.",
        )

    def search_by_vector(self, query_embedding, top_k):
        self.calls += 1
        if self.calls == 2:
            first_line = self.output_path.read_text(encoding="utf-8").splitlines()
            assert len(first_line) == 1
        return [StandardMatch(chunk=self.chunk, similarity=0.8421)][:top_k]


def test_inspection_skips_headers_reuses_vectors_and_writes_incrementally(tmp_path):
    requirement_one = NIO(
        id="NIO-1",
        specification="First requirement.",
        type="requirement",
        section_number="4.1",
    )
    header = NIO(
        id="NIO-2",
        specification="Section heading",
        type="section_header",
        section_number="4.2",
    )
    requirement_two = NIO(
        id="NIO-3",
        specification="Second requirement.",
        type="requirement",
        section_number=None,
    )
    protocol = Protocol("protocol", "Protocol", [requirement_one, header, requirement_two])
    targets = get_inspection_targets(protocol, limit=5)
    output_path = tmp_path / "inspection.jsonl"
    nio_retriever = FakeNIORetriever()
    standard_retriever = FakeStandardRetriever(output_path)
    progress = FakeProgress()

    with output_path.open("x", encoding="utf-8") as output_file:
        count = write_inspection_incrementally(
            targets,
            nio_retriever,
            standard_retriever,
            5,
            output_file,
            progress,
        )

    records = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert count == 2
    assert progress.completed == 2
    assert nio_retriever.requested_ids == ["NIO-1", "NIO-3"]
    assert [record["target_id"] for record in records] == ["NIO-1", "NIO-3"]
    assert records[0]["query"] == "First requirement."
    assert records[0]["target_section_number"] == "4.1"
    match = records[0]["matches"][0]
    assert match == {
        "rank": 1,
        "chunk_id": "ARINC664P7-3.4.2-TEXT-001",
        "document": "ARINC664P7",
        "content_type": "text",
        "section_number": "3.4.2",
        "section_title": "Virtual Links",
        "page_start": 42,
        "page_end": 43,
        "similarity": 0.8421,
        "text": "Retrieved standard evidence.",
    }


def test_inspection_limit_counts_requirement_queries_only():
    protocol = Protocol(
        "protocol",
        "Protocol",
        [
            NIO("header", "Header", "section_header"),
            NIO("requirement-1", "One", "requirement"),
            NIO("requirement-2", "Two", "requirement"),
        ],
    )

    targets = get_inspection_targets(protocol, limit=1)

    assert [target.id for target in targets] == ["requirement-1"]


class FakeBGE:
    def __init__(self, api_key, base_url, model):
        self.model = model

    def embed(self, texts):
        vectors = {
            "Configured requirement.": [1.0, 0.0],
            "Explicit requirement.": [1.0, 0.0],
            "P2 evidence.": [1.0, 0.0],
            "P7 evidence.": [0.0, 1.0],
        }
        return [vectors[text] for text in texts]


class FakeTqdm(FakeProgress):
    totals = []

    def __init__(self, total, **kwargs):
        super().__init__()
        self.totals.append(total)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def write_protocol(path, nio_id, specification):
    path.write_text(
        json.dumps(
            {
                "id": nio_id,
                "type": "requirement",
                "section_number": "4.3",
                "specification": specification,
                "rationale": None,
                "req": "Yes",
                "source": {
                    "file": "protocol.docx",
                    "table": 1,
                    "word_row": 12,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def write_standard(path, document, text):
    path.write_text(
        json.dumps(
            {
                "chunk_id": f"{document}-1.1-TEXT-001",
                "document": document,
                "content_type": "text",
                "section_number": "1.1",
                "section_title": "Test",
                "page_start": 1,
                "page_end": 1,
                "text": text,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_inspection_main_uses_config_override_and_overwrite_protection(
    tmp_path,
    monkeypatch,
):
    configured_protocol = tmp_path / "configured.jsonl"
    explicit_protocol = tmp_path / "explicit.jsonl"
    p2_path = tmp_path / "p2.jsonl"
    p7_path = tmp_path / "p7.jsonl"
    write_protocol(configured_protocol, "CONFIGURED", "Configured requirement.")
    write_protocol(explicit_protocol, "EXPLICIT", "Explicit requirement.")
    write_standard(p2_path, "ARINC664P2", "P2 evidence.")
    write_standard(p7_path, "ARINC664P7", "P7 evidence.")
    config = SimpleNamespace(
        data=SimpleNamespace(protocol=str(configured_protocol)),
        bge=SimpleNamespace(api_key="fake", base_url="fake", model="fake-bge"),
        embeddings=SimpleNamespace(cache_dir=str(tmp_path / "cache")),
        standards=SimpleNamespace(
            arinc664p2=str(p2_path),
            arinc664p7=str(p7_path),
        ),
        retrieval=SimpleNamespace(
            nio=SimpleNamespace(top_k=5),
            standard=SimpleNamespace(top_k=5),
        ),
    )
    args = SimpleNamespace(
        input=None,
        inspect_standard_retrieval=True,
        rebuild_embeddings=False,
        limit=5,
        top_k=1,
        output=str(tmp_path / "configured-output.jsonl"),
        overwrite=False,
    )
    monkeypatch.setattr(run_module, "load_config", lambda: config)
    monkeypatch.setattr(run_module, "parse_args", lambda: args)
    monkeypatch.setattr(run_module, "BGEEmbeddingService", FakeBGE)
    monkeypatch.setattr(run_module, "tqdm", FakeTqdm)

    run_module.main()

    configured_record = json.loads(
        (tmp_path / "configured-output.jsonl").read_text(encoding="utf-8")
    )
    assert configured_record["target_id"] == "CONFIGURED"

    explicit_output = tmp_path / "explicit-output.jsonl"
    original = "do not replace\n"
    explicit_output.write_text(original, encoding="utf-8")
    args.input = str(explicit_protocol)
    args.output = str(explicit_output)

    with pytest.raises(SystemExit, match="Output file already exists"):
        run_module.main()
    assert explicit_output.read_text(encoding="utf-8") == original

    args.overwrite = True
    run_module.main()
    explicit_record = json.loads(explicit_output.read_text(encoding="utf-8"))
    assert explicit_record["target_id"] == "EXPLICIT"
    assert FakeTqdm.totals[-1] == 1
