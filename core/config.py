from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
CONFIG_PATH_ENV = "WB_RADAR_CONFIG"

SECRET_FIELD_NAMES = frozenset(
    {
        "openrouter_api_key",
        "zai_api_key",
        "groq_api_key",
        "ollama_base_url",
    }
)


class WBHosts(BaseModel):
    card: str
    search: str
    catalog: str
    feedbacks: str


class WBSettings(BaseModel):
    hosts: WBHosts
    dest: str
    rate_limit_rps: float = 1.0
    retries: int = 3


class MatcherSettings(BaseModel):
    marketplaces: list[str]
    similarity_threshold: float
    max_candidates: int
    headless: bool


class LLMSettings(BaseModel):
    provider: str
    model: str
    temperature: float


class PathsSettings(BaseModel):
    output: str
    sessions: str
    db: str


class YamlConfigSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        configured = os.environ.get(CONFIG_PATH_ENV)
        config_path = Path(configured) if configured else DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                raise ValueError(
                    f"{config_path} must contain a YAML mapping at the top level"
                )
            self._data = {
                key: value
                for key, value in raw.items()
                if key.lower() not in SECRET_FIELD_NAMES
            }

    def get_field_value(
        self, field: Any, field_name: str
    ) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    wb: WBSettings
    matcher: MatcherSettings
    llm: LLMSettings
    proxy: str | None = None
    paths: PathsSettings

    openrouter_api_key: str | None = Field(None, repr=False)
    zai_api_key: str | None = Field(None, repr=False)
    groq_api_key: str | None = Field(None, repr=False)
    ollama_base_url: str | None = Field(None, repr=False)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSource(settings_cls),
            file_secret_settings,
        )


settings = Settings()
