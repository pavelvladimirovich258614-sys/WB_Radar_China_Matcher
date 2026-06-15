# Session Handoff — WB Radar & China Matcher

## Состояние на закрытие сессии (2026-06-16, SESSION-START-03-FIX)

- Последняя работа в сессии: **git-fix — добавлены пустые пакеты gui/harvest/matcher в репозиторий** (новой бизнес-логики не писалось).
- Выполнено: **F00, F01, F02, F03, F04, F05, F06, F06-FIX-01** — все done (см. feature_list.json).
- **active_feature = F07 (status: todo). F07 НЕ начат** — код LLM-слоя не тронут (`core/llm/` не существует).
- **VCS: git инициализирован.** Коммиты:
  - `a88980b` — F00-F06: complete foundation, WB clients, and browser base (29 файлов, +3718).
  - `9552334` — docs: record handoff before F07.
  - `f2b581f` — F00: track empty project packages (gui/harvest/matcher `__init__.py`).
- **gui/harvest/matcher теперь tracked** (пустые `__init__.py`, стабы F00-каркаса). Чистый checkout воспроизводит F00–F06.

## Что важно знать новому агенту

- **С чего начать завтра:** прочитай AGENTS.md → progress.md → TZ.md (Часть VI, секция F07). Сделать только F07 (LLM слой: base + OpenRouter). Завязки F07 = [F01] (done). **Старт F07 — только после «ОК F07» от пользователя.**
- **Первое действие F07:** core/llm/base.py (LLMProvider: complete(messages)->str, complete_json(messages, schema)->dict с ретраем на битом JSON) + core/llm/openrouter.py (POST openrouter.ai/api/v1/chat/completions, ключ OPENROUTER_API_KEY из .env, модель из settings.llm.model) + core/llm/__init__.py (get_provider(name)->инстанс). Тесты на моках httpx; live под @pytest.mark.live.
- **LLM-провайдер выбирается из config** (settings.llm.provider / settings.llm.model) — код не завязан на вендора (инвариант AGENTS.md).

## Known issues (НЕ обходить)

- **WB live = 403** из текущего окружения: card.wb.ru / search.wb.ru / feedbacks отдают 403 (стоп-правило AGENTS.md, п.9.9.6 оферты WB). Не-live тесты на fixtures/wb_*.json зелёные; live-тесты (под @pytest.mark.live) корректно отрабатывают 403 → WBRequestError без выдумки данных. Живые данные получать с разрешённой сети/сессии.
- **retries** трактуется как макс. попыток вкл. первую (3).
- **basket-хост img_url** — эвристика (vol//144+1); точная корзина валидируется на live.
- **feedbacks-хост** в config = feedbacks.api.wb.ru (TZ F05 канонический — public-feedbacks.wildberries.ru; смена значения в config.yaml при необходимости).

## Безопасность (закрыто в F06-FIX-01)

- sanitize_site_name + _site_dir resolve-containment: path traversal по site-имени закрыт (".."→"site", "../evil"→"_evil" и т.д.), покрыто параметризованными тестами. sessions/ гарантированно внутри settings.paths.sessions.
- Секреты не в git: `.env`/`sessions/`/`output/` в .gitignore, в коммите `a88980b` их нет. `.env.example` — пустой шаблон.

## Команды проверки

- Тесты: `.\.venv\Scripts\python.exe -m pytest -m "not live"` → ожидаемо **91 passed, 4 deselected**.
- Импорт-чек пакетов: `.\.venv\Scripts\python.exe -c "import core, matcher, harvest, gui; print('packages ok')"`.
- Импорт-чек browser: `.\.venv\Scripts\python.exe -c "from core.browser import BrowserManager; print('browser ok')"`.
- Git: `git log --oneline` → `f2b581f` / `9552334` / `a88980b`.
- Live F03: `$env:WB_TEST_NMID="<артикул>"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_wb_public_detail.py::test_get_detail_live -s`
- Live F04: `$env:WB_TEST_QUERY="фен"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_wb_public_search.py::test_search_live -s`
- Live F05: `$env:WB_TEST_IMTID="<imtId>"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_wb_public_feedbacks.py::test_get_reviews_live -s`
- Live F06 (сессии): `$env:F06_LIVE=1; .\.venv\Scripts\python.exe -m pytest -m live tests/test_browser.py::test_open_alibaba_and_persist_session_live -s`

## Стоп

Новые фичи не начинать без подтверждения пользователя. F07 НЕ начат. Ждём «ОК F07».
