# Session Handoff — WB Radar & China Matcher

## SESSION-CLOSE-04 (2026-06-16) — F10 built, awaiting commit

- **Последняя выполненная фича: F10 — Storage: sqlite-кэш + JSON/CSV экспорт** (status: done, НЕ закоммичена — ждёт команды пользователя).
- **Последняя закоммиченная фича: F08 — LLM провайдеры: Z.AI(GLM), Groq, Ollama локальный** (status: done).
- **F09 — LLM провайдер: ChatGPT-web (опц., аккаунт-сессия)** — **deferred/skipped** (не реализован, не коммичен).
- **Активная фича: F11 — Input resolver: артикул/ссылка/фото -> query image** (status: todo, НЕ начат).
- **F00–F10** подтверждены done.

## VCS

- **F10 НЕ закоммичен.** Изменения в working tree:
  - `core/storage.py` — sqlite cache + JSON/CSV export.
  - `tests/test_storage.py` — 24 не-live контрактных теста.
- Последний коммит: `d4830df` — "F08: add ZAI, Groq, and Ollama LLM providers" (12 файлов, +1060/-57).

## Что сделано в F10

- `core/storage.py` — Storage-слой:
  - `Storage(db_path=None, output_dir=None)` с defaults из `settings.paths.db`/`settings.paths.output`.
  - sqlite-таблица `cache` (`key`, `namespace`, `value_json`, `created_at`, `updated_at`, `metadata_json`) + индекс по `namespace`.
  - `make_cache_key(namespace, payload)` — стабильный sha256.
  - `get`, `set`, `get_or_fetch`, `delete`, `clear_namespace`.
  - `get_or_fetch` не вызывает `fn` при cache hit.
  - Сериализация pydantic `BaseModel` через `model_dump(mode="json")`, datetime → ISO.
  - `StorageSerializationError` для несериализуемых объектов.
  - `save_json(data, path_or_name)` — dict, pydantic model, list[model] в `output/`.
  - `save_csv(data, path_or_name, columns=None)` — list[dict], list[pydantic], pandas DataFrame, пустой список.
- `tests/test_storage.py` — 24 не-live теста:
  - `make_cache_key`, stable/unstable payload + namespace.
  - default paths, set/get roundtrip, overwrite, cache hit/miss, delete, clear_namespace.
  - pydantic/datetime сериализация, ошибка сериализации, metadata/timestamps.
  - `save_json` для dict/pydantic/list + абсолютный путь.
  - `save_csv` для list[dict], list[pydantic], pandas DataFrame, пустой список, columns-параметр, одиночный dict.

## Почему F09 deferred

F09 (ChatGPT-web) — опциональная фича. Она нестабильна (зависит от web-вёрстки OpenAI и личной сессии), против ToS OpenAI и не нужна для основного пайплайна, потому что уже есть: OpenRouter, Z.AI, Groq, Ollama.

## Known issues

- WB live может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- ChatGPT-web не реализован и отложен.

## Команды проверки

- Тесты (не-live): `.\.venv\Scripts\python.exe -m pytest -m "not live" -q` → **223 passed, 8 deselected** (199 → +24 новых не-live теста storage).
- Live ZAI: `$env:ZAI_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_zai.py -s`
- Live Groq: `$env:GROQ_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_groq.py -s`
- Live Ollama: `$env:OLLAMA_BASE_URL="http://localhost:11434"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_ollama.py -s`

## Следующий шаг

**F11 — Input resolver: артикул/ссылка/фото -> query image** (deps: [F03]). **F11 НЕ начат** — ждём «ОК F11».

## История

- SESSION-START-04: восстановление + подготовка к F08.
- F08: done + committed.
- F09: deferred.
- F10: done, не закоммичен (ожидает команды пользователя).

(End of file)
