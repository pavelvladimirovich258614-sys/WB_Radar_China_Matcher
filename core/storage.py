from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import settings as default_settings
from core.models import BaseModel as WBBaseModel


class StorageError(Exception):
    pass


class StorageSerializationError(StorageError):
    pass


class Storage:
    def __init__(
        self,
        db_path: str | Path | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        self._db_path = Path(
            db_path if db_path is not None else default_settings.paths.db
        )
        self._output_dir = Path(
            output_dir
            if output_dir is not None
            else default_settings.paths.output
        )
        self._ensure_parent(self._db_path)
        self._ensure_parent(self._output_dir)
        self._init_db()

    @staticmethod
    def _ensure_parent(path: Path) -> None:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    namespace TEXT,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_namespace ON cache(namespace)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    @staticmethod
    def make_cache_key(namespace: str, payload: Any) -> str:
        normalized_payload = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, default=str
        )
        raw = f"{namespace}:{normalized_payload}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_json(value: Any) -> str:
        def default(obj: Any) -> Any:
            if isinstance(obj, WBBaseModel):
                return obj.model_dump(mode="json")
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        try:
            return json.dumps(value, ensure_ascii=False, default=default)
        except TypeError as exc:
            raise StorageSerializationError(f"failed to serialize value: {exc}") from exc

    @staticmethod
    def _from_json(raw: str) -> Any:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StorageSerializationError(
                f"failed to deserialize cached value: {exc}"
            ) from exc

    def get(self, key: str) -> Any | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return self._from_json(row[0])

    def set(
        self,
        key: str,
        value: Any,
        namespace: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        value_json = self._to_json(value)
        metadata_json = self._to_json(metadata) if metadata is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache (key, namespace, value_json, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    namespace = excluded.namespace,
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (key, namespace, value_json, now, now, metadata_json),
            )

    def get_or_fetch(
        self,
        key: str,
        fn: Callable[[], Any],
        namespace: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = fn()
        self.set(key, value, namespace=namespace, metadata=metadata)
        return value

    def delete(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear_namespace(self, namespace: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cache WHERE namespace = ?", (namespace,))

    def save_json(
        self,
        data: Any,
        path_or_name: str | Path,
        *,
        ensure_ascii: bool = False,
        indent: int = 2,
    ) -> Path:
        path = self._resolve_output_path(path_or_name, suffix=".json")
        self._ensure_parent(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                self._serialize_for_export(data),
                f,
                ensure_ascii=ensure_ascii,
                indent=indent,
            )
        return path

    def _resolve_output_path(self, path_or_name: str | Path, suffix: str) -> Path:
        path = Path(path_or_name)
        if path.parent == Path("."):
            path = self._output_dir / path.name
        if not path.suffix:
            path = path.with_suffix(suffix)
        return path

    @staticmethod
    def _serialize_for_export(value: Any) -> Any:
        if isinstance(value, WBBaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [Storage._serialize_for_export(item) for item in value]
        if isinstance(value, dict):
            return {
                k: Storage._serialize_for_export(v) for k, v in value.items()
            }
        return value

    def save_csv(
        self,
        data: Any,
        path_or_name: str | Path,
        *,
        columns: list[str] | None = None,
    ) -> Path:
        path = self._resolve_output_path(path_or_name, suffix=".csv")
        self._ensure_parent(path)

        rows = self._normalize_csv_rows(data)
        fieldnames = columns if columns is not None else self._infer_fieldnames(rows)

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, extrasaction="ignore"
            )
            writer.writeheader()
            if rows:
                writer.writerows(rows)
        return path

    @staticmethod
    def _normalize_csv_rows(data: Any) -> list[dict[str, Any]]:
        if data is None:
            return []
        if isinstance(data, WBBaseModel):
            return [data.model_dump(mode="json")]
        if isinstance(data, dict):
            return [dict(data)]
        if isinstance(data, list):
            return [
                item.model_dump(mode="json")
                if isinstance(item, WBBaseModel)
                else dict(item)
                for item in data
            ]
        # pandas DataFrame
        if hasattr(data, "to_dict") and hasattr(data, "columns"):
            records = data.to_dict(orient="records")
            if isinstance(records, list):
                return [dict(row) for row in records]
        raise StorageSerializationError(
            f"Cannot convert {type(data).__name__} to CSV rows"
        )

    @staticmethod
    def _infer_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return []
        return list(rows[0].keys())


def make_cache_key(namespace: str, payload: Any) -> str:
    return Storage.make_cache_key(namespace, payload)


__all__ = [
    "Storage",
    "StorageError",
    "StorageSerializationError",
    "make_cache_key",
]
