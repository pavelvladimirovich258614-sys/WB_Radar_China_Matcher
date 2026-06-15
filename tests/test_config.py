from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.config import Settings

VALID_CONFIG: dict = {
    "wb": {
        "hosts": {
            "card": "https://card.wb.ru",
            "search": "https://search.wb.ru",
            "catalog": "https://catalog.wb.ru",
            "feedbacks": "https://feedbacks.api.wb.ru",
        },
        "dest": "-1257786",
        "rate_limit_rps": 1.0,
        "retries": 3,
    },
    "matcher": {
        "marketplaces": ["alibaba", "s1688", "taobao"],
        "similarity_threshold": 0.85,
        "max_candidates": 20,
        "headless": False,
    },
    "llm": {
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
        "temperature": 0.4,
    },
    "proxy": None,
    "paths": {
        "output": "./output",
        "sessions": "./sessions",
        "db": "./cache.db",
    },
}

SECRET_ENV_VARS = [
    "OPENROUTER_API_KEY",
    "ZAI_API_KEY",
    "GROQ_API_KEY",
    "OLLAMA_BASE_URL",
]


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    for var in SECRET_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("WB_RADAR_CONFIG", raising=False)
    monkeypatch.delenv("PROXY", raising=False)
    yield


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    path = _write_config(tmp_path, VALID_CONFIG)
    monkeypatch.setenv("WB_RADAR_CONFIG", str(path))
    return path


def test_loads_config_yaml(config_path):
    settings = Settings()

    assert settings.wb.hosts.card == "https://card.wb.ru"
    assert settings.wb.hosts.feedbacks == "https://feedbacks.api.wb.ru"
    assert settings.wb.rate_limit_rps == 1.0
    assert settings.wb.retries == 3
    assert settings.matcher.marketplaces == ["alibaba", "s1688", "taobao"]
    assert settings.llm.provider == "openrouter"
    assert settings.llm.model == "openai/gpt-4o-mini"
    assert settings.llm.temperature == 0.4
    assert settings.paths.output == "./output"
    assert settings.paths.db == "./cache.db"


def test_required_sections_present(config_path):
    settings = Settings()

    for section in ("wb", "matcher", "llm", "paths"):
        assert hasattr(settings, section)

    for host_field in ("card", "search", "catalog", "feedbacks"):
        assert getattr(settings.wb.hosts, host_field)

    assert settings.wb.dest
    assert not hasattr(settings.wb.hosts, "dest")

    assert isinstance(settings.matcher.similarity_threshold, float)
    assert isinstance(settings.matcher.max_candidates, int)
    assert isinstance(settings.matcher.headless, bool)
    assert isinstance(settings.matcher.marketplaces, list)
    assert settings.proxy is None


def test_dest_lives_at_wb_level_not_in_hosts(config_path):
    settings = Settings()

    assert settings.wb.dest == "-1257786"
    assert not hasattr(settings.wb.hosts, "dest")


def test_env_overrides_yaml_values(config_path, monkeypatch):
    monkeypatch.setenv("LLM__PROVIDER", "groq")
    monkeypatch.setenv("LLM__MODEL", "llama-3")
    monkeypatch.setenv("MATCHER__SIMILARITY_THRESHOLD", "0.5")

    settings = Settings()

    assert settings.llm.provider == "groq"
    assert settings.llm.model == "llama-3"
    assert settings.matcher.similarity_threshold == 0.5
    assert settings.llm.temperature == 0.4


def test_secrets_not_read_from_yaml(tmp_path, monkeypatch):
    poisoned = dict(VALID_CONFIG)
    poisoned["openrouter_api_key"] = "LEAKED_FROM_YAML"
    poisoned["groq_api_key"] = "ALSO_LEAKED"
    path = _write_config(tmp_path, poisoned)
    monkeypatch.setenv("WB_RADAR_CONFIG", str(path))

    settings = Settings()

    assert settings.openrouter_api_key is None
    assert settings.groq_api_key is None


def test_secrets_read_from_env(config_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    settings = Settings()

    assert settings.openrouter_api_key == "sk-from-env"
    assert settings.ollama_base_url == "http://ollama:11434"
