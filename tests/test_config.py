from config import load_config


def test_retrieval_paths_and_defaults_load_from_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[qwen]
model = "fake-qwen"
base_url = ""
api_key = ""

[bge]
model = "fake-bge"
base_url = ""
api_key = ""

[data]
protocol = "protocol.jsonl"

[embeddings]
cache_dir = "cache/embeddings"

[standards]
arinc664p2 = "p2.jsonl"
arinc664p7 = "p7.jsonl"

[retrieval.nio]
top_k = 7

[retrieval.standard]
top_k = 9
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(str(config_path))

    assert config.data.protocol == "protocol.jsonl"
    assert config.embeddings.cache_dir == "cache/embeddings"
    assert config.standards.arinc664p2 == "p2.jsonl"
    assert config.standards.arinc664p7 == "p7.jsonl"
    assert config.retrieval.nio.top_k == 7
    assert config.retrieval.standard.top_k == 9
