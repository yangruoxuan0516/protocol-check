from dataclasses import dataclass
from pathlib import Path
from typing import Optional
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class QwenConfig:
    model: str
    base_url: str
    api_key: str
    temperature: float = 0.0


@dataclass
class BGEConfig:
    model: str = "BAAI/bge-m3"
    base_url: str = ""
    api_key: str = ""


@dataclass
class DataConfig:
    protocol: str = ""


@dataclass
class EmbeddingsConfig:
    cache_dir: str = ".cache/protocol_check/embeddings"


@dataclass
class StandardsConfig:
    arinc664p2: str = ""
    arinc664p7: str = ""


@dataclass
class NIORetrievalConfig:
    top_k: int = 5


@dataclass
class StandardRetrievalConfig:
    top_k: int = 5


@dataclass
class RetrievalConfig:
    nio: NIORetrievalConfig
    standard: StandardRetrievalConfig


@dataclass
class RunnerConfig:
    output_dir: str = "outputs"


@dataclass
class AppConfig:
    qwen: QwenConfig
    bge: BGEConfig
    data: DataConfig
    embeddings: EmbeddingsConfig
    standards: StandardsConfig
    retrieval: RetrievalConfig
    runner: RunnerConfig


def load_config(path: Optional[str] = None) -> AppConfig:
    config_path = (
        Path(path)
        if path is not None
        else BASE_DIR / "config.toml"
    )

    if not config_path.exists():
        raise RuntimeError(
            f"Config file not found: {config_path}\n"
            "Create config.toml based on config.example.toml."
        )

    with config_path.open("rb") as f:
        data = tomllib.load(f)

    qwen_data = data["qwen"]
    generation_data = qwen_data.get("generation", {})
    bge_data = data.get("bge", {})
    data_paths = data.get("data", {})
    embeddings_data = data.get("embeddings", {})
    standards_data = data.get("standards", {})
    retrieval_data = data.get("retrieval", {})
    nio_retrieval_data = retrieval_data.get("nio", {})
    standard_retrieval_data = retrieval_data.get("standard", {})
    runner_data = data.get("runner", {})

    return AppConfig(
        qwen=QwenConfig(
            model=qwen_data["model"],
            base_url=qwen_data["base_url"],
            api_key=qwen_data["api_key"],
            temperature=generation_data.get("temperature", 0.0),
        ),
        bge=BGEConfig(
            model=bge_data.get("model", "BAAI/bge-m3"),
            base_url=bge_data.get("base_url", ""),
            api_key=bge_data.get("api_key", ""),
        ),
        data=DataConfig(
            protocol=data_paths.get("protocol", ""),
        ),
        embeddings=EmbeddingsConfig(
            cache_dir=embeddings_data.get(
                "cache_dir",
                ".cache/protocol_check/embeddings",
            ),
        ),
        standards=StandardsConfig(
            arinc664p2=standards_data.get("arinc664p2", ""),
            arinc664p7=standards_data.get("arinc664p7", ""),
        ),
        retrieval=RetrievalConfig(
            nio=NIORetrievalConfig(
                top_k=nio_retrieval_data.get("top_k", 5),
            ),
            standard=StandardRetrievalConfig(
                top_k=standard_retrieval_data.get("top_k", 5),
            ),
        ),
        runner=RunnerConfig(
            output_dir=runner_data.get("output_dir", "outputs"),
        ),
    )
