# Session Handoff — WB Radar & China Matcher

## SESSION-CLOSE-03 (2026-06-16) — F08 done

- **Последняя фича: F08 — LLM провайдеры: Z.AI(GLM), Groq, Ollama локальный** (status: done).
- **F00–F08** подтверждены done; **active_feature = F09** (ChatGPT-web опц., НЕ начат).
- **Что сделано в F08:**
  - `core/llm/openai_compat.py` — общий `OpenAICompatProvider(LLMProvider)` для OpenAI-compatible API.
  - `core/llm/zai.py` — `ZAIProvider`, endpoint `https://api.z.ai/v1/chat/completions`, ключ `ZAI_API_KEY`.
  - `core/llm/groq.py` — `GroqProvider`, endpoint `https://api.groq.com/openai/v1/chat/completions`, ключ `GROQ_API_KEY`.
  - `core/llm/ollama.py` — `OllamaProvider`, без ключа, endpoint `{OLLAMA_BASE_URL}/api/chat`, default `http://localhost:11434`.
  - `core/llm/__init__.py` — `get_provider` роутит `openrouter`, `zai`, `z.ai`, `glm`, `groq`, `ollama`.
  - `tests/conftest.py` + `tests/test_llm_zai.py` + `tests/test_llm_groq.py` + `tests/test_llm_ollama.py` — контрактные тесты на моках + live-тесты под `@pytest.mark.live`.
- **Результат проверки:** `pytest -m "not live" -q` → **199 passed, 8 deselected**.
- **Импорт-чек:** `from core.llm.zai import ZAIProvider; from core.llm.groq import GroqProvider; from core.llm.ollama import OllamaProvider` → "llm providers ok".
- **Security:** ключи только в `.env`/ENV, не в коде/config.yaml; не логируются; `repr=False`.

## Known issues (НЕ обходить)

- WB live = 403 из текущего окружения — стоп-правило AGENTS.md.
- `get_provider("zai")`/`("groq")` без ключа поднимает `LLMAuthError` — это ожидаемое поведение, не баг.

## Команды проверки

- Тесты (не-live): `.\.venv\Scripts\python.exe -m pytest -m "not live" -q` → **199 passed, 8 deselected**.
- Live ZAI: `$env:ZAI_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_zai.py -s`
- Live Groq: `$env:GROQ_API_KEY="..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_groq.py -s`
- Live Ollama: `$env:OLLAMA_BASE_URL="http://localhost:11434"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_ollama.py -s`

## Следующий шаг

**F09 — LLM провайдер: ChatGPT-web (опц., аккаунт-сессия)**. Завязки F09 = [F07, F06] (оба done). **F09 НЕ начат** — жду решения пользователя: выполнить F09 или пропустить.

## История предыдущих сессий

### SESSION-START-04 (2026-06-16) — восстановление контекста + подготовка к F08

- Подтверждено: F00–F07 done; active_feature=F08 (status: todo, НЕ начат).
- VCS: последние коммиты `7e7d7fe docs: close session after F07`, `2dcd3c1 docs: record F07 handoff before F08`, `5a73f5c F07: add LLM base layer and OpenRouter provider`, etc.
- Тесты: `pytest -m "not live" -q` → 136 passed, 5 deselected.
- Security: `.env`/`sessions/`/`output/`/`.venv/`/`.hermes/` не tracked; ключей в коде нет.

### SESSION-CLOSE-02 (2026-06-16) — сессия закрыта после F07

- F07 done: `core/llm/base.py`, `openrouter.py`, `__init__.py`, тесты.
- active_feature=F08 (todo).

(End of file)
