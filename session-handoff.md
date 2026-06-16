# Session Handoff — WB Radar & China Matcher

## SESSION-CLOSE-07 (2026-06-16) — F11 committed

- **Последняя закоммиченная фича: F11 — Input resolver: артикул/ссылка/фото -> query image** (status: done).
  - Коммит: `461daa0` — "F11: add input resolver for WB items and images" (5 файлов, +656/-27).
- **Предыдущий коммит: F10 — Storage: sqlite-кэш + JSON/CSV экспорт** (status: done).
- **F09 — LLM провайдер: ChatGPT-web (опц., аккаунт-сессия)** — **deferred/skipped**.
- **Активная фича: F12 — China driver: Alibaba.com image search (дефолт, без логина)** (status: todo, НЕ начат).
- **F00–F11** подтверждены done.

## VCS

- **F11 закоммичен.** В working tree нет изменений F11.
- Последние коммиты:
  - `461daa0` — F11: add input resolver for WB items and images (5 файлов, +656/-27)
  - `1432b34` — F10: add sqlite cache and export storage
  - `d4830df` — F08: add ZAI, Groq, and Ollama LLM providers

## Что сделано в F11

- `matcher/input.py` — Input resolver:
  - `ResolvedInput` dataclass: `query_image_path`, `source_type` (`wb_nm`/`wb_url`/`file`), `nmId`, `product`, `original_input`, `meta`.
  - Иерархия ошибок: `InputResolverError`, `InvalidInputError`, `ImageDownloadError`, `ImageValidationError`.
  - `parse_wb_nm_id(value)` — int/строка 5–12 цифр.
  - `is_wb_url(value)` — http(s) + `wildberries.ru` + `/catalog/<nmId>/detail.aspx`.
  - `extract_wb_nm_id_from_url(url)` — извлекает nmId только с WB-доменов.
  - `normalize_image_to_query_jpg(src, output_path)` — Pillow RGB JPEG thumbnail, поддержка Path/bytes/BytesIO.
  - `resolve_input(value, *, wb_client=None, output_dir=None)`:
    - WB артикул → `get_detail` → скачать `img_url` → `output/query.jpg`.
    - WB ссылка → извлечь nmId → `get_detail` → скачать → `output/query.jpg`.
    - локальное фото → RGB JPEG → `output/query.jpg`.
    - default `output_dir` из `settings.paths.output`; injected `wb_client` не закрывается.
- `tests/test_matcher_input.py` — 22 не-live теста:
  - парсинг nmId, WB-URL, query-параметры, сторонние домены.
  - локальный файл: jpg, png с alpha, webp, unsupported ext, missing, broken.
  - WB-путь: мок WBPublic + download, пустой img_url, ошибка download, default client создаётся/закрывается.
  - нормализация и resize, unrecognized input.

## Почему F09 deferred

F09 (ChatGPT-web) — опциональная фича. Она нестабильна (зависит от web-вёрстки OpenAI и личной сессии), против ToS OpenAI и не нужна для основного пайплайна, потому что уже есть: OpenRouter, Z.AI, Groq, Ollama.

## Known issues

- WB live может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- ChatGPT-web не реализован и отложен.
- 1 skipped тест в F11 (`test_resolve_local_webp`): Pillow в текущем venv не поддерживает WebP (`Image.registered_extensions().get(".webp")` is None). Это platform-specific ограничение сборки Pillow, не баг кода.
- F11-SMOKE-01 пройден: локальная PNG → `output/query.jpg` JPEG RGB. Smoke-файл удалён, `output/query.jpg` не tracked.

## Команды проверки

- Тесты (не-live): `.\.venv\Scripts\python.exe -m pytest -m "not live" -q` → **244 passed, 1 skipped, 8 deselected** (223 → +21 новых не-live теста F11, +1 skipped WebP).
- Live ZAI: `$env:ZAI_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_zai.py -s`
- Live Groq: `$env:GROQ_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_groq.py -s`
- Live Ollama: `$env:OLLAMA_BASE_URL="http://localhost:11434"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_ollama.py -s`

## Следующий шаг

**F12 — China driver: Alibaba.com image search (дефолт, без логина)** (deps: [F06, F11]). **F12 НЕ начат** — ждём «ОК F12».

## История

- SESSION-START-04: восстановление + подготовка к F08.
- F08: done + committed.
- F09: deferred.
- F10: done + committed.
- F11: done + committed.

(End of file)
