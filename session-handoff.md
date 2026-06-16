# Session Handoff — WB Radar & China Matcher

## SESSION-CLOSE-03 (2026-06-16) — F08 committed, F09 deferred, F10 pending

- **Последняя закоммиченная фича: F08 — LLM провайдеры: Z.AI(GLM), Groq, Ollama локальный** (status: done).
- **F09 — LLM провайдер: ChatGPT-web (опц., аккаунт-сессия)** — **deferred/skipped** (не реализован, не коммичен).
- **Активная фича: F10 — Storage: sqlite-кэш + JSON/CSV экспорт** (status: todo, НЕ начат).
- **F00–F08** подтверждены done.

## VCS

- Коммит F08: `d4830df` — "F08: add ZAI, Groq, and Ollama LLM providers" (12 файлов, +1060/-57).
- Последние коммиты:
  - `d4830df` — F08: add ZAI, Groq, and Ollama LLM providers
  - `d306449` — docs: prepare session for F08
  - `7e7d7fe` — docs: close session after F07
  - `2dcd3c1` — docs: record F07 handoff before F08
  - `5a73f5c` — F07: add LLM base layer and OpenRouter provider

## Что сделано в F08

- `core/llm/openai_compat.py` — общий `OpenAICompatProvider(LLMProvider)` для OpenAI-compatible API.
- `core/llm/zai.py` — `ZAIProvider`, endpoint `https://api.z.ai/v1/chat/completions`, ключ `ZAI_API_KEY`.
- `core/llm/groq.py` — `GroqProvider`, endpoint `https://api.groq.com/openai/v1/chat/completions`, ключ `GROQ_API_KEY`.
- `core/llm/ollama.py` — `OllamaProvider`, без ключа, endpoint `{OLLAMA_BASE_URL}/api/chat`, default `http://localhost:11434`.
- `core/llm/__init__.py` — `get_provider` роутит `openrouter`, `zai`, `z.ai`, `glm`, `groq`, `ollama`.
- `tests/conftest.py` + `tests/test_llm_zai.py` + `tests/test_llm_groq.py` + `tests/test_llm_ollama.py` — контрактные тесты на моках + live-тесты под `@pytest.mark.live`.

## Почему F09 deferred

F09 (ChatGPT-web) — опциональная фича. Она нестабильна (зависит от web-вёрстки OpenAI и личной сессии), против ToS OpenAI и не нужна для основного пайплайна, потому что уже есть: OpenRouter, Z.AI, Groq, Ollama.

## Known issues

- WB live может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- ChatGPT-web не реализован и отложен.

## Команды проверки

- Тесты (не-live): `.\.venv\Scripts\python.exe -m pytest -m "not live" -q` → **199 passed, 8 deselected**.
- Live ZAI: `$env:ZAI_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_zai.py -s`
- Live Groq: `$env:GROQ_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_groq.py -s`
- Live Ollama: `$env:OLLAMA_BASE_URL="http://localhost:11434"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_ollama.py -s`

## Следующий шаг

**F10 — Storage: sqlite-кэш + JSON/CSV экспорт** (deps: [F02]). **F10 НЕ начат** — ждём «ОК F10».

## История

- SESSION-START-04: восстановление + подготовка к F08.
- F08: done + committed.
- F09: deferred.

(End of file)
