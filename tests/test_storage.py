from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.models import Product, Review
from core.storage import (
    Storage,
    StorageSerializationError,
    make_cache_key,
)


@pytest.fixture
def tmp_storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "cache.db"
    output_dir = tmp_path / "output"
    return Storage(db_path=db_path, output_dir=output_dir)


def test_make_cache_key_is_stable_and_unique() -> None:
    key1 = make_cache_key("ns", {"a": 1, "b": [2, 3]})
    key2 = make_cache_key("ns", {"b": [2, 3], "a": 1})
    key3 = make_cache_key("ns", {"a": 1, "b": [3, 2]})
    key_other_ns = make_cache_key("other", {"a": 1, "b": [2, 3]})

    assert isinstance(key1, str)
    assert len(key1) == 64
    assert key1 == key2
    assert key1 != key3
    assert key1 != key_other_ns


def test_storage_uses_default_paths(monkeypatch, tmp_path: Path) -> None:
    # Avoid touching real project output/db by monkeypatching the settings
    # imported at module load time by core.storage.
    import core.storage as storage_module

    db_path = tmp_path / "default.db"
    output_dir = tmp_path / "default_output"

    class FakePaths:
        db = str(db_path)
        output = str(output_dir)
        sessions = str(tmp_path / "sessions")

    class FakeSettings:
        paths = FakePaths()

    monkeypatch.setattr(storage_module, "default_settings", FakeSettings())

    storage = Storage()
    assert storage._db_path == db_path
    assert storage._output_dir == output_dir


def test_set_and_get_roundtrip(tmp_storage: Storage) -> None:
    value = {"name": "item", "count": 42}
    tmp_storage.set("k1", value, namespace="test")
    assert tmp_storage.get("k1") == value


def test_get_missing_key_returns_none(tmp_storage: Storage) -> None:
    assert tmp_storage.get("missing") is None


def test_set_overwrites_existing_value(tmp_storage: Storage) -> None:
    tmp_storage.set("k1", "first")
    tmp_storage.set("k1", "second", namespace="ns")
    assert tmp_storage.get("k1") == "second"


def test_get_or_fetch_uses_cache_when_available(tmp_storage: Storage) -> None:
    calls: list[int] = []

    def fetch() -> int:
        calls.append(1)
        return 123

    result1 = tmp_storage.get_or_fetch("gk", fetch, namespace="ns")
    result2 = tmp_storage.get_or_fetch("gk", fetch, namespace="ns")

    assert result1 == 123
    assert result2 == 123
    assert sum(calls) == 1


def test_get_or_fetch_stores_value_on_miss(tmp_storage: Storage) -> None:
    def fetch() -> dict[str, str]:
        return {"source": "fetch"}

    value = tmp_storage.get_or_fetch("miss", fetch, namespace="ns")
    assert value == {"source": "fetch"}
    assert tmp_storage.get("miss") == {"source": "fetch"}


def test_delete_removes_key(tmp_storage: Storage) -> None:
    tmp_storage.set("del_me", "value")
    tmp_storage.delete("del_me")
    assert tmp_storage.get("del_me") is None


def test_clear_namespace_only_affects_namespace(tmp_storage: Storage) -> None:
    tmp_storage.set("a", 1, namespace="ns1")
    tmp_storage.set("b", 2, namespace="ns1")
    tmp_storage.set("c", 3, namespace="ns2")

    tmp_storage.clear_namespace("ns1")

    assert tmp_storage.get("a") is None
    assert tmp_storage.get("b") is None
    assert tmp_storage.get("c") == 3


def test_pydantic_model_serialization(tmp_storage: Storage) -> None:
    product = Product(
        nmId=12345,
        name="Test Product",
        brand="Brand",
        price=999.0,
        feedbacks=10,
        rating=4.5,
        img_url="https://example.com/img.jpg",
        url="https://example.com/product",
    )

    tmp_storage.set("pydantic", product, namespace="models")
    loaded = tmp_storage.get("pydantic")

    assert isinstance(loaded, dict)
    assert loaded["nmId"] == 12345
    assert loaded["name"] == "Test Product"
    assert loaded["rating"] == 4.5


def test_datetime_serialization(tmp_storage: Storage) -> None:
    now = datetime.now(timezone.utc)
    tmp_storage.set("dt", {"created": now}, namespace="dates")
    loaded = tmp_storage.get("dt")
    assert loaded["created"].endswith("+00:00") or loaded["created"].endswith("Z")


def test_unserializable_object_raises(tmp_storage: Storage) -> None:
    class Weird:
        pass

    with pytest.raises(StorageSerializationError):
        tmp_storage.set("bad", Weird())


def test_metadata_is_persisted(tmp_storage: Storage) -> None:
    tmp_storage.set("m1", "v1", namespace="ns", metadata={"tag": "important"})
    conn = sqlite3.connect(str(tmp_storage._db_path))
    row = conn.execute(
        "SELECT metadata_json FROM cache WHERE key = 'm1'"
    ).fetchone()
    conn.close()
    assert json.loads(row[0]) == {"tag": "important"}


def test_timestamps_set_on_write(tmp_storage: Storage) -> None:
    tmp_storage.set("t1", "v", namespace="ns")
    conn = sqlite3.connect(str(tmp_storage._db_path))
    created, updated = conn.execute(
        "SELECT created_at, updated_at FROM cache WHERE key = 't1'"
    ).fetchone()
    conn.close()
    assert created == updated
    assert datetime.fromisoformat(created)


def test_save_json_for_dict(tmp_storage: Storage) -> None:
    path = tmp_storage.save_json({"a": 1, "b": "привет"}, "data")
    assert path == tmp_storage._output_dir / "data.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == {"a": 1, "b": "привет"}


def test_save_json_for_pydantic_model(tmp_storage: Storage) -> None:
    review = Review(
        id="r1",
        nmId=123,
        text="Great product",
        rating=5,
        photo_urls=["https://example.com/p1.jpg"],
    )
    path = tmp_storage.save_json(review, "review.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["id"] == "r1"
    assert loaded["text"] == "Great product"
    assert loaded["photo_urls"] == ["https://example.com/p1.jpg"]


def test_save_json_for_list_of_models(tmp_storage: Storage) -> None:
    reviews = [
        Review(id="r1", text="one"),
        Review(id="r2", text="two"),
    ]
    path = tmp_storage.save_json(reviews, "reviews")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert len(loaded) == 2
    assert loaded[0]["id"] == "r1"
    assert loaded[1]["id"] == "r2"


def test_save_json_respects_absolute_path(tmp_storage: Storage, tmp_path: Path) -> None:
    target = tmp_path / "nested" / "absolute.json"
    path = tmp_storage.save_json({"x": 1}, target)
    assert path == target
    assert json.loads(path.read_text(encoding="utf-8")) == {"x": 1}


def test_save_csv_for_list_of_dicts(tmp_storage: Storage) -> None:
    rows = [
        {"id": "1", "name": "Alice", "score": "10"},
        {"id": "2", "name": "Bob", "score": "20"},
    ]
    path = tmp_storage.save_csv(rows, "people")
    assert path == tmp_storage._output_dir / "people.csv"

    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    loaded = list(reader)
    assert loaded == rows


def test_save_csv_for_list_of_pydantic_models(tmp_storage: Storage) -> None:
    products = [
        Product(nmId=1, name="A", brand="B", price=100.0, feedbacks=5, rating=4.0),
        Product(nmId=2, name="C", brand="D", price=200.0, feedbacks=10, rating=5.0),
    ]
    path = tmp_storage.save_csv(products, "products.csv")

    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    loaded = list(reader)
    assert len(loaded) == 2
    assert loaded[0]["nmId"] == "1"
    assert loaded[0]["name"] == "A"
    assert loaded[1]["nmId"] == "2"


def test_save_csv_for_pandas_dataframe(tmp_storage: Storage) -> None:
    try:
        import pandas as pd  # type: ignore
    except ImportError:
        pytest.skip("pandas not installed")

    df = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
    path = tmp_storage.save_csv(df, "df")

    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    loaded = list(reader)
    assert loaded == [{"x": "1", "y": "a"}, {"x": "2", "y": "b"}]


def test_save_csv_for_empty_list(tmp_storage: Storage) -> None:
    path = tmp_storage.save_csv([], "empty")
    text = path.read_text(encoding="utf-8-sig")
    assert text.strip() == ""


def test_save_csv_columns_parameter_limits_output(tmp_storage: Storage) -> None:
    rows = [
        {"id": "1", "name": "Alice", "score": "10"},
        {"id": "2", "name": "Bob", "score": "20"},
    ]
    path = tmp_storage.save_csv(rows, "limited", columns=["id", "name"])
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    loaded = list(reader)
    assert loaded == [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]


def test_save_csv_for_single_dict(tmp_storage: Storage) -> None:
    path = tmp_storage.save_csv({"a": 1, "b": "value"}, "single")
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    loaded = list(reader)
    assert loaded == [{"a": "1", "b": "value"}]
