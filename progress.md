## Активная фича

F08 — LLM провайдеры: Z.AI/Groq/Ollama (status: todo) — следующая. **F08 НЕ начат** (ждём «ОК F08» от пользователя).

## Журнал

## F07 — done (2026-06-16)

Реализовано эстафетой из 5 саб-агентов (PLAN → BUILD → TESTS → REVIEW → DOCS).

- **core/llm/base.py** — `LLMProvider(ABC)` с `@abstractmethod complete(messages,**kw)->str` / `@abstractmethod close()->None`, `__enter__/__exit__` (контекст-менеджер зовёт close), и **конкретным template-method `complete_json(messages, schema=None, *, json_retries=None, **kw)->dict`** с ретраем на битом JSON: на каждой попытке зовёт `complete`, парсит через `extract_json`; если не dict — добавляет corrective hint ("not valid JSON...") и ретраит; если dict, но не хватает ключей из `schema["required"]` — добавляет hint ("missing required keys...") и ретраит; после исчерпания попыток → `LLMJSONError`. Hints добавляются в локальную копию messages (caller's list не мутируется). По умолчанию `DEFAULT_JSON_RETRIES=3`.
- **`extract_json(text)->object|None`** — 4 стратегии: raw `json.loads`, fenced ```json/```, первая `{...}`, первый массив `[...]`; `None` для пустого/не-JSON.
- **Иерархия исключений**: `LLMError` → `LLMAuthError` / `LLMRequestError` / `LLMJSONError` (все в `__all__`).
- **core/llm/openrouter.py** — `OpenRouterProvider(LLMProvider)`: `httpx.Client` POST на `https://openrouter.ai/api/v1/chat/completions`; **ключ из `settings.openrouter_api_key`** (repr=False, НИКОГДА не логируется, НИКОГДА не попадает в exception-сообщения — только HTTP status/transport-error repr); модель/температура из `settings.llm`; headers Authorization/Content-Type/HTTP-Referer/X-Title; DI (`settings=None`→default_settings, `client=None`→создаёт httpx.Client и владеет им, иначе не закрывает injected). **Status-mapping**: 401/403→`LLMAuthError`, 429/5xx/transport(`httpx.HTTPError`)/не-JSON-body/сломанная-структура→`LLMRequestError`, прочие non-200→`LLMRequestError`. `complete_json` унаследован из base. Если ключ не задан → `LLMAuthError` в конструкторе.
- **core/llm/__init__.py** — `get_provider(name=None)->LLMProvider`: `None`→`settings.llm.provider`; `"openrouter"`→`OpenRouterProvider()`; неизвестное имя → `LLMError` (вендор-агностик). Ре-экспортирует все исключения, base-класс и провайдер.
- **Тесты (46 всего)**: `tests/test_llm_base.py` — 22 теста (extract_json 7 кейсов; complete_json success/fenced/retry/schema-ok/schema-missing/non-dict/propagation-LlmRequest/propagation-LlmAuth/exhaustion/retries=1; abstractness; ctx manager; constant). `tests/test_llm_openrouter.py` — 24 теста (complete URL/headers/payload/model-temperature/kwarg-forwarding; status 200/401/403/429/500/418; transport error; broken-choices; missing-choices; non-JSON body; key-not-in-exception; key-from-settings-not-config-yaml; close ownership; `_json_retries`=3; inherited complete_json; get_provider openrouter/None/unknown) — все на **FakeClient/FakeResponse** (без сети), плюс **1 `@pytest.mark.live` test_openrouter_complete_live** (гейт `OPENROUTER_API_KEY` env, skip без ключа).
- **Прогон**: `pytest -m "not live" -q` → **136 passed, 5 deselected** (91 был до F07 + 45 новых не-live = 136).
- **Импорт-чек**: `from core.llm import get_provider; from core.llm.base import LLMProvider` → "llm ok".
- **F03–F06 не сломаны**: `import core, matcher, harvest, gui; from core.wb_public import WBPublic; from core.browser import BrowserManager` → "f03-f06 ok".
- **Безопасность**: `config.yaml` НЕ содержит api_key (только provider/model/temperature); ключи только в `.env`/ENV через `settings.openrouter_api_key`; `.env.example` имеет пустой `OPENROUTER_API_KEY=` плейсхолдер. Ключ не в repr, не в logger, не в exception-текстах.
- **core/llm/ содержит ТОЛЬКО** `base.py`, `openrouter.py`, `__init__.py` — файлов zai.py/groq.py/ollama.py НЕТ (**F08 не начат**).
- Заглушек `pass`/`TODO`/"implement later"/"stub" НЕТ (только легитимные `pass` в телах exception-классов, `except: pass` control-flow в extract_json, и `def close(self): pass` / `with ...: pass` в test-doubles).
- Следующий: F08 (LLM провайдеры: Z.AI/GLM, Groq, Ollama локальный).

## SESSION-START-03-FIX (2026-06-16) — git-fix: track empty project packages

- Цель: первый checkpoint должен воспроизводить F00–F06 на чистом checkout, включая пакеты gui/harvest/matcher.
- gui/, harvest/, matcher/ уже содержали пустые `__init__.py` (0 строк) от F00-каркаса, но не попали в первый
  коммит `a88980b`. Добавлены в git: `git add gui/__init__.py harvest/__init__.py matcher/__init__.py`.
- Коммит **`f2b581f`** — "F00: track empty project packages" (3 файла, +0 строк; пустые стабы, бизнес-логики нет).
- **gui/harvest/matcher теперь tracked.** `__pycache__/` и служебные каталоги (.hermes/, .factory/) НЕ добавлены.
- Тесты: `pytest -m "not live"` → **91 passed, 4 deselected**.
- Импорт-чек: `import core, matcher, harvest, gui` → **packages ok**.
- active_feature = F07 (НЕ начат). F07 НЕ выполнялся.
- Коммиты на данный момент: `a88980b` (F00-F06), `9552334` (docs handoff), `f2b581f` (packages fix).

## SESSION-START-02 (2026-06-16) — восстановление контекста + git checkpoint

- Восстановлено состояние: F00–F06 done, F06-FIX-01 done, active_feature=F07 (НЕ начат).
- Подтверждено: `core/llm/` не существует → код LLM-слоя не тронут (F07 не начинался).
- Тесты: `pytest -m "not live"` → **91 passed, 4 deselected** (бенчмарк совпал).
- Импорт-чеки: config ok / models ok / wb public ok / browser ok — все зелёные.
- VCS: `git init` выполнен. Создан первый checkpoint-коммит **`a88980b`** —
  "F00-F06: complete foundation, WB clients, and browser base" (29 файлов, +3718 строк).
- .gitignore проверен: `.env`, `sessions/`, `output/`, `.venv/`, `__pycache__/`, `*.pyc`, `*.db`,
  `.pytest_cache/`, `.factory/` — в git не попадают. Секретов в staged-диффе нет (`.env.example` — пустой шаблон).
- **F00–F06 зафиксированы в git.** Следующий шаг: F07 (LLM слой: base + OpenRouter).
- Команда проверки: `.\.venv\Scripts\python.exe -m pytest -m "not live"` → 91 passed, 4 deselected.
- Known issue: WB-эндпоинты (card/search/feedbacks) отдают 403 из текущего окружения — стоп-правило AGENTS.md,
  защиту НЕ обходить. Не-live тесты на фикстурах зелёные.
- F07 НЕ выполнялся в этой сессии (только восстановление + checkpoint). Ждём «ОК F07».

## SESSION-CLOSE-01 (2026-06-16) — сессия зафиксирована

- Принято: F06-FIX-01 (defense-in-depth по site-имени).
- Статус: F00–F06 done; active_feature=F07 (НЕ начат).
- Тесты: pytest -m "not live" → 91 passed, 4 deselected.
- Импорт-чек: `from core.browser import BrowserManager` → "browser security ok".
- Known issue: WB-эндпоинты (card/search/feedbacks) отдают 403 из текущего окружения — стоп-правило AGENTS.md, НЕ обходить. Не-live тесты на фикстурах зелёные.
- VCS: git-репозиторий НЕ инициализирован (коммитов нет).
- Следующий шаг: F07 (LLM слой: base + OpenRouter).

## F06-FIX-01 — done (2026-06-16)

Defense-in-depth по безопасному имени site (закрытие known-issue F06).

- core/browser.py: вынесена чистая модульная функция sanitize_site_name(site)->str (regex `[^A-Za-z0-9._-]`→"_", замена "/" и "\" на "_", strip(".") краёв, fallback "site" для ""/"."/".."). ".."→"site", "."→"site", ""→"site", "alibaba"→"alibaba", "1688.com"→"1688.com", "../evil"→"_evil", "..\evil"→"_evil", "/etc/passwd"→"_etc_passwd", "C:\evil"→"C__evil".
- _site_dir теперь использует sanitize_site_name + defense-in-depth проверку через Path.resolve(): если resolved-путь вне sessions root — fallback на sessions/<site>; никогда не raise.
- Два независимых слоя защиты: sanitize (небезопасные символы/точки) + resolve-containment (symlink/FS-уровень). Обход пути (path traversal) закрыт.
- tests/test_browser.py: +10 тестов (17 кейсов): sanitize_site_name (dotdot/dot/empty/preserve/neutralize/no-separators) + _site_dir containment (forward/backslash/dotdot + параметризованный test_site_dir_always_inside_sessions_root по 8 evil-входам).
- Прогон: pytest -m "not live" → 91 passed, 4 deselected. Импорт: "browser security ok".
- Бизнес-логика manual_login/new_page/detect_captcha не изменена. F03–F06 не сломаны.

## F06 — done (2026-06-16)

Реализовано эстафетой из 5 саб-агентов (PLAN → BUILD → TESTS → REVIEW → DOCS).

- core/browser.py: класс BrowserManager (настройки инжектятся как в WBPublic; Playwright-инстанс инжектится для тестов, реальный sync_playwright стартует лениво → обычный pytest браузер не запускает).
- Persistent-контексты: sessions/<site> из settings.paths.sessions; директория создаётся автоматически; имя site санируется (re.sub небезопасных символов → "_", защита от path-traversal — разделителей / и \ нет).
- Proxy: из settings.proxy через urlparse → {server, username, password}; None/пусто → None (не передаётся в Playwright); http/https/socks5 и bare host:port; креды не выдумываются.
- Headless: new_context берёт из settings.matcher.headless (переопределяется аргументом); manual_login ВСЕГДА headless=False (видимое окно).
- Locale zh-CN, обычный Chrome UA, viewport 1280x800. БЕЗ stealth (никаких --disable-blink-features=AutomationControlled, без playwright-stealth).
- Методы: new_context(site, headless=None), new_page(site, url=None) (goto с wait_until="domcontentloaded"), manual_login(site, url=None)->Path (видимое окно, инструкция в консоль, input() ждёт Enter, затем закрывает page+context → сессия пишется на диск, возвращает sessions/<site>), detect_captcha(page)->bool (title/content/url, keywords captcha/verify/robot/滑块/验证码/人机/проверка/капча; НИКОГДА не raise, None→False; НЕ решает капчу), close(), __enter__/__exit__.
- Тесты: tests/test_browser.py — 24 не-live (FakePlaywright/FakeContext/FakePage, без реального браузера) + 1 @pytest.mark.live test_open_alibaba_and_persist_session_live (доп. гейт F06_LIVE env).
- Прогон: pytest -m "not live" → 74 passed, 4 deselected. Импорт-чек: from core.browser import BrowserManager → "browser ok".
- F03/F04/F05 не сломаны. sessions/ в .gitignore.
- следующий: F07

## F05 — done: WBPublic.get_reviews (POST feedbacks) + extract_review_video_url/photo_urls; Review.id→str, nmId→Optional.
## F04 — done: WBPublic.search (search.wb.ru v4). F03+F03-FIX-01 — done: get_detail, build_wb_image_url, dest на wb.dest.
## F02 — done: core/models.py. F01 — done: core/config.py. F00 — done: каркас.

## Заметки/проблемы

- **Live 403**: WB-эндпоинты (card/search/feedbacks) отдают 403 из текущего окружения (стоп-правило AGENTS.md). Не-live зелёные. Живые данные — с разрешённой сети/сессии.
- **F06 site-sanitization закреплена** (F06-FIX-01): sanitize_site_name + resolve-containment; path traversal закрыт, покрыт параметризованными тестами.
- **retries** = макс. попыток вкл. первую. basket-хост img_url — эвристика.
- python 3.11.9; init.sh под bash; полный init.sh на чистой машине не валидирован целиком.
