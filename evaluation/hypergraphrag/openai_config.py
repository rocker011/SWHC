from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Optional


DEFAULT_OPENAI_CHAT_MODEL = "deepseek-chat"
LOCAL_EMBED_MODEL_PREFIX = "local:"
DEFAULT_LOCAL_EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_OPENAI_EMBED_MODEL = f"{LOCAL_EMBED_MODEL_PREFIX}{DEFAULT_LOCAL_EMBED_MODEL}"
DEFAULT_OPENAI_BASE_URL = "https://api.deepseek.com"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "api_config.txt"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    base_url: Optional[str]
    model: str
    embed_model: str


def _clean_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_openai_config_path(config_file: Optional[str] = None) -> Path:
    if config_file is None:
        return DEFAULT_CONFIG_PATH
    return Path(config_file).expanduser().resolve()


def _parse_mapping_config(lines: list[str]) -> dict[str, str]:
    config: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            raise RuntimeError(
                "api_config.txt must use either ordered lines or KEY=VALUE lines consistently."
            )
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            config[key] = value
    return config


def _load_env_file(env_path: Path = DEFAULT_ENV_PATH) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_env_config() -> Optional[OpenAIConfig]:
    _load_env_file()
    api_key = _clean_value(os.getenv("OPENAI_API_KEY")) or _clean_value(
        os.getenv("DEEPSEEK_API_KEY")
    )
    if api_key is None:
        return None
    base_url = _clean_value(os.getenv("OPENAI_BASE_URL")) or DEFAULT_OPENAI_BASE_URL
    model = (
        _clean_value(os.getenv("OPENAI_MODEL"))
        or _clean_value(os.getenv("HGRAG_GENERATION_MODEL"))
        or DEFAULT_OPENAI_CHAT_MODEL
    )
    embed_model = _clean_value(os.getenv("OPENAI_EMBED_MODEL")) or DEFAULT_OPENAI_EMBED_MODEL
    return OpenAIConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        embed_model=embed_model,
    )


@lru_cache(maxsize=4)
def load_openai_config(config_file: Optional[str] = None) -> OpenAIConfig:
    env_config = _load_env_config()
    if env_config is not None:
        return env_config

    config_path = get_openai_config_path(config_file)
    if not config_path.exists():
        raise RuntimeError(f"Missing config file: {config_path}")

    raw_lines = config_path.read_text(encoding="utf-8").splitlines()
    lines = [
        line.strip()
        for line in raw_lines
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        raise RuntimeError(f"Config file is empty: {config_path}")

    if any("=" in line for line in lines):
        config = _parse_mapping_config(lines)
        api_key = _clean_value(config.get("OPENAI_API_KEY"))
        base_url = _clean_value(config.get("OPENAI_BASE_URL"))
        model = _clean_value(config.get("OPENAI_MODEL")) or DEFAULT_OPENAI_CHAT_MODEL
        embed_model = (
            _clean_value(config.get("OPENAI_EMBED_MODEL"))
            or DEFAULT_OPENAI_EMBED_MODEL
        )
    else:
        if len(lines) < 3:
            raise RuntimeError(
                f"Config file {config_path} must contain at least 3 lines: "
                "API key, base URL, chat model."
            )
        api_key = _clean_value(lines[0])
        base_url = _clean_value(lines[1])
        model = _clean_value(lines[2]) or DEFAULT_OPENAI_CHAT_MODEL
        embed_model = (
            _clean_value(lines[3]) if len(lines) >= 4 else DEFAULT_OPENAI_EMBED_MODEL
        )

    if api_key is None:
        raise RuntimeError(f"OPENAI_API_KEY is missing in {config_path}")

    return OpenAIConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        embed_model=embed_model,
    )


def get_openai_api_key(
    api_key: Optional[str] = None, config_file: Optional[str] = None
) -> str:
    return _clean_value(api_key) or load_openai_config(config_file).api_key


def ensure_openai_api_key(
    api_key: Optional[str] = None, config_file: Optional[str] = None
) -> str:
    return get_openai_api_key(api_key=api_key, config_file=config_file)


def get_openai_base_url(
    base_url: Optional[str] = None,
    default: Optional[str] = None,
    config_file: Optional[str] = None,
) -> Optional[str]:
    config_base_url = load_openai_config(config_file).base_url
    return _clean_value(base_url) or config_base_url or _clean_value(default) or DEFAULT_OPENAI_BASE_URL


def get_openai_model(
    model: Optional[str] = None,
    default: str = DEFAULT_OPENAI_CHAT_MODEL,
    config_file: Optional[str] = None,
) -> str:
    config_model = load_openai_config(config_file).model
    return _clean_value(model) or config_model or default


def get_openai_embed_model(
    model: Optional[str] = None,
    default: str = DEFAULT_OPENAI_EMBED_MODEL,
    config_file: Optional[str] = None,
) -> str:
    config_model = load_openai_config(config_file).embed_model
    return _clean_value(model) or config_model or default


def parse_embed_model_spec(
    model: Optional[str] = None, config_file: Optional[str] = None
) -> tuple[str, str]:
    resolved_model = get_openai_embed_model(model=model, config_file=config_file)
    if resolved_model.startswith(LOCAL_EMBED_MODEL_PREFIX):
        local_model = _clean_value(
            resolved_model[len(LOCAL_EMBED_MODEL_PREFIX) :]
        ) or DEFAULT_LOCAL_EMBED_MODEL
        return "local", local_model
    return "remote", resolved_model


def is_local_embed_model(
    model: Optional[str] = None, config_file: Optional[str] = None
) -> bool:
    mode, _ = parse_embed_model_spec(model=model, config_file=config_file)
    return mode == "local"


def get_local_embed_model(
    model: Optional[str] = None, config_file: Optional[str] = None
) -> Optional[str]:
    mode, resolved_model = parse_embed_model_spec(
        model=model, config_file=config_file
    )
    return resolved_model if mode == "local" else None
