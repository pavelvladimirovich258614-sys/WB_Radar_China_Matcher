# Session Handoff — WB Radar & China Matcher

## Состояние на закрытие сессии (2026-06-16, F07 done)

- Последняя работа в сессии: **F07 — LLM слой: base + OpenRouter** (status: done).
- Выполнено: **F00, F01, F02, F03, F04, F05, F06, F06-FIX-01, F07** — все done (см. feature_list.json).
- **active_feature = F08 (status: todo). F08 НЕ начат** — ждём «ОК F08» от пользователя. Завязки F08 = [F07] (done).
- **VCS: git инициализирован.** Коммиты:
  - `a88980b` — F00-F06: complete foundation, WB clients, and browser base (29 файлов, +3718).
  - `9552334` — docs: record handoff before F07.
  - `f2b581f` — F00: track empty project packages (gui/harvest/matcher `__init__.py`).
  - `61da29d` — *(последний коммит перед F07, если был; сверить с `git log --oneline`)*.
- Коммита F07 ещё нет (оркестратор коммитит по команде пользователя). Файлы F07 готовы к staged: `core/llm/base.py`, `core/llm/openrouter.py`, `core/llm/__init__.py`, `tests/test_llm_base.py`, `tests/test_llm_openrouter.py`.

## Что было сделано в F07

- **core/llm/base.py**: `LLMProvider(ABC)` (abstract `complete`/`close`, ctx-manager) + конкретный template-method `complete_json(messages, schema, *, json_retries)->dict` с ретраем на битом JSON и corrective hints (локальная копия messages, caller не мутируется); `extract_json` (4 стратегии); иерархия `LLMError → LLMAuthError/LLMRequestError/LLMJSONError`.
- **core/llm/openrouter.py**: `OpenRouterProvider(LLMProvider)` — httpx POST на `openrouter.ai/api/v1/chat/completions`; ключ из `settings.openrouter_api_key` (repr=False, не логируется, не в exception); DI settings/client; status-mapping 401/403→Auth, 429/5xx/transport/shape→Request; `complete_json` унаследован.
- **core/llm/__init__.py**: `get_provider(name=None)->LLMProvider` (None→config default; "openrouter"→instance; unknown→LLMError) + ре-экспорты.
- **Тесты (46)**: `test_llm_base.py` (22), `test_llm_openrouter.py` (23 не-live на FakeClient + 1 `@pytest.mark.live` под `OPENROUTER_API_KEY`).

## Что важно знать новому агенту

- **С чего начать завтра:** прочитай AGENTS.md → progress.md → TZ.md (Часть VI, секция F08). Сделать только F08 (LLM провайдеры: Z.AI/GLM, Groq, Ollama локальный). Завязки F08 = [F07] (done). **Старт F08 — только после «ОК F08» от пользователя.**
- **Первое действие F08:** реализовать `ZaiProvider`/`GroqProvider`/`OllamaProvider` как подклассы `LLMProvider` (переиспользовать `complete_json` из base); добавить ветки в `get_provider` (`__init__.py`); ключи `ZAI_API_KEY`/`GROQ_API_KEY` из settings (ENV), `OLLAMA_BASE_URL` (default `http://localhost:11434`). Тесты на моках httpx; live под `@pytest.mark.live`.
- **Инвариант:** LLM-провайдер выбирается из config (`settings.llm.provider`) — код не завязан на вендора. Каждый новый провайдер = подкласс `LLMProvider` + ветка в `get_provider`. Ключи только в `.env`/ENV, НЕ в config.yaml, НЕ в exception-сообщениях, НЕ в логах.

## Known issues (НЕ обходить)

- **WB live = 403** из текущего окружения: card.wb.ru / search.wb.ru / feedbacks отдают 403 (стоп-правило AGENTS.md, п.9.9.6 оферты WB). Не-live тесты на fixtures/wb_*.json зелёные; live-тесты корректно отрабатывают 403 → исключение без выдумки данных. Живые данные получать с разрешённой сети/сессии.
- **OpenRouter live** требует `OPENROUTER_API_KEY` в окружении: `get_provider()`/`OpenRouterProvider()` читают `settings.openrouter_api_key`; без ключа live-тест skip-ается (`pytest.skip`), а конструктор провайдера в реальном коде поднимет `LLMAuthError`.
- **retries** трактуется как макс. попыток вкл. первую (3) — и для WB, и для `complete_json` (`DEFAULT_JSON_RETRIES=3`).
- **basket-хост img_url** — эвристика (vol//144+1); точная корзина валидируется на live.
- **feedbacks-хост** в config = feedbacks.api.wb.ru (TZ F05 канонический — public-feedbacks.wildberries.ru; смена значения в config.yaml при необходимости).

## Безопасность (закрыто в F06-FIX-01, подтверждено в F07)

- **sanitize_site_name** + `_site_dir` resolve-containment: path traversal по site-имени закрыт (".."→"site", "../evil"→"_evil" и т.д.), покрыто параметризованными тестами. sessions/ гарантированно внутри settings.paths.sessions.
- **Секреты не в git**: `.env`/`sessions/`/`output/` в .gitignore. `.env.example` — пустой шаблон (вкл. `OPENROUTER_API_KEY=`, `ZAI_API_KEY=`, `GROQ_API_KEY=`, `OLLAMA_BASE_URL=http://localhost:11434`).
- **config.yaml НЕ содержит ключей**: только `wb`/`matcher`/`llm`(provider/model/temperature)/`proxy`/`paths`. Тест `test_key_from_settings_not_config_yaml` инвариантно проверяет отсутствие `api_key` в config.yaml.
- **Ключ OpenRouter** не попадает в repr/logger/exception-сообщения — только в заголовок `Authorization: Bearer ...`. Тест `test_key_not_in_exception_message` подтверждает.

## Команды проверки

- Тесты (не-live): `.\.venv\Scripts\python.exe -m pytest -m "not live"` → ожидаемо **136 passed, 5 deselected**.
- Импорт-чек LLM: `.\.venv\Scripts\python.exe -c "from core.llm import get_provider; from core.llm.base import LLMProvider; print('llm ok')"`.
- Импорт-чек F03–F06: `.\.venv\Scripts\python.exe -c "import core, matcher, harvest, gui; from core.wb_public import WBPublic; from core.browser import BrowserManager; print('f03-f06 ok')"`.
- Git: `git log --oneline` → `f2b581f` / `9552334` / `a88980b` (+ последующие после коммита F07).
- Live F03: `$env:WB_TEST_NMID="<артикул>"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_wb_public_detail.py::test_get_detail_live -s`
- Live F04: `$env:WB_TEST_QUERY="фен"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_wb_public_search.py::test_search_live -s`
- Live F05: `$env:WB_TEST_IMTID="<imtId>"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_wb_public_feedbacks.py::test_get_reviews_live -s`
- Live F06 (сессии): `$env:F06_LIVE=1; .\.venv\Scripts\python.exe -m pytest -m live tests/test_browser.py::test_open_alibaba_and_persist_session_live -s`
- **Live F07 (OpenRouter)**: `$env:OPENROUTER_API_KEY="sk-or-..."; .\.venv\Scripts\python.exe -m pytest -m live tests/test_llm_openrouter.py -s`

## Стоп

Новые фичи не начинать без подтверждения пользователя. **F08 НЕ начат.** Ждём «ОК F08».
