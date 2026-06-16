## Активная фича

F11 — Input resolver: артикул/ссылка/фото -> query image (status: todo) — следующая. **F11 НЕ начат** (ждём «ОК F11» от пользователя).

## Журнал

## F10 — done (2026-06-16)

Реализовано эстафетой из саб-агентов (PLAN → BUILD sqlite cache → BUILD JSON/CSV export → TESTS → REVIEW/DOCS). **Не закоммичено** — ждёт команды пользователя.

- **core/storage.py** — Storage-слой:
  - `Storage(db_path=None, output_dir=None)` с defaults из `settings.paths.db`/`settings.paths.output`.
  - sqlite-таблица `cache` (`key`, `namespace`, `value_json`, `created_at`, `updated_at`, `metadata_json`) + индекс по `namespace`.
  - `StorageError`, `StorageSerializationError`, модульная `make_cache_key(namespace, payload)` — стабильный sha256.
  - `get`, `set`, `get_or_fetch`, `delete`, `clear_namespace`.
  - `get_or_fetch` не вызывает `fn` при cache hit.
  - Сериализация pydantic `BaseModel` через `model_dump(mode="json")`, datetime → ISO, несериализуемое → `StorageSerializationError`.
  - `save_json(data, path_or_name)` — dict, pydantic model, list[model]; относительное имя → `output/`, абсолютный путь сохраняется как есть.
  - `save_csv(data, path_or_name, columns=None)` — list[dict], list[pydantic], pandas DataFrame (duck-typing `to_dict`/`columns`), пустой список.
- **tests/test_storage.py** — 24 не-live теста: stable cache key, default paths, set/get/overwrite, get_or_fetch hit/miss, delete, clear_namespace, pydantic/datetime сериализация, serialization error, metadata/timestamps, save_json (dict/pydantic/list/absolute path), save_csv (list[dict], list[pydantic], pandas DataFrame, empty list, columns, single dict).
- **Прогон**: `pytest -m "not live" -q` → **223 passed, 8 deselected** (было 199 passed; +24 новых не-live теста storage). F00–F08 не сломаны.
- **Без заглушек**: нет `pass`/`TODO` в бизнес-логике (только легитимные `pass` в телах exception-классов).
- **Security**: секреты не трогались; `.env`/`sessions/`/`output/`/`*.db` в `.gitignore`.
- **F10 НЕ закоммичен** — коммит по команде пользователя вида "F10: add sqlite cache and JSON/CSV export".

## F08 — done + committed (2026-06-16)

Реализовано эстафетой из 5 саб-агентов (PLAN → BUILD ZAI+Groq → BUILD Ollama+routing → TESTS → REVIEW/DOCS). Закоммичено: `d4830df` — "F08: add ZAI, Groq, and Ollama LLM providers".

- **core/llm/openai_compat.py** — общий базовый класс `OpenAICompatProvider(LLMProvider)` для OpenAI-compatible провайдеров. Содержит httpx POST, status mapping (401/403→`LLMAuthError`, 429/5xx/transport→`LLMRequestError`), парсинг `choices[0].message.content`, DI `settings`/`client`/`api_key`, timeout. Ключ не логируется и не попадает в exception-сообщения.
- **core/llm/zai.py** — `ZAIProvider(OpenAICompatProvider)`, endpoint `https://api.z.ai/v1/chat/completions`, ключ `settings.zai_api_key`, `LLMAuthError` если ключа нет.
- **core/llm/groq.py** — `GroqProvider(OpenAICompatProvider)`, endpoint `https://api.groq.com/openai/v1/chat/completions`, ключ `settings.groq_api_key`, `LLMAuthError` если ключа нет.
- **core/llm/ollama.py** — `OllamaProvider(LLMProvider)`, без API-ключа, `base_url` из `settings.ollama_base_url` с дефолтом `http://localhost:11434`, endpoint `/api/chat`, payload `{model, messages, stream: false, options: {temperature}}`, ответ `message.content`. Ошибки → `LLMRequestError`.
- **core/llm/__init__.py** — `get_provider(name=None)` теперь роутит `openrouter`, `zai`, `z.ai`, `glm`, `groq`, `ollama`. Неизвестный → `LLMError`.
- **Тесты (64 новых не-live + 3 live)**:
  - `tests/conftest.py` — общие `FakeResponse`, `FakeClient`, `CONFIG_YAML`.
  - `tests/test_llm_zai.py` — 22 теста (happy path, URL/payload/headers, kwarg forwarding, ключ из settings не в config.yaml, 401/403/429/500/418/transport, битая структура, ключ не в exception, close DI, inherited complete_json, routing alias'ы `zai`/`z.ai`/`glm`, live).
  - `tests/test_llm_groq.py` — 21 тест (аналогично ZAI, без alias'ей, live).
  - `tests/test_llm_ollama.py` — 21 тест (happy path, `/api/chat`, `stream: false`, `options.temperature`, custom/default base_url, kwarg forwarding, 400/404/429/500/418/transport, битая структура, close DI, inherited complete_json, routing, live с reachability-check).
- **Прогон**: `pytest -m "not live" -q` → **199 passed, 8 deselected** (было 136 passed, 5 deselected; +63 новых не-live теста + 3 новых live deselected). F00–F07 не сломаны.
- **Импорт-чеки**: `from core.llm.zai import ZAIProvider; from core.llm.groq import GroqProvider; from core.llm.ollama import OllamaProvider` → "llm providers ok"; `import core, matcher, harvest, gui; from core.wb_public import WBPublic; from core.browser import BrowserManager` → "f03-f06 ok".
- **Security (PASS)**: ключи читаются только из `settings.zai_api_key`/`settings.groq_api_key`/`settings.ollama_base_url` (ENV/.env, repr=False); не логируются; не в `config.yaml`; `.env` не tracked.
- **Без заглушек**: нет `pass`/`TODO` в новой бизнес-логике (только легитимные control-flow/exception-body `pass` в `base.py` и `OpenAICompatProvider._request_payload` — его тело тоже не пустое, там payload формируется).
- **F09 deferred/skipped**: ChatGPT-web не реализован, не коммичен. Опциональная фича, зависит от web-вёрстки/личной сессии OpenAI, нестабильна и не нужна для основного пайплайна (есть OpenRouter + Z.AI + Groq + Ollama).
- **F10 не начат** — Storage: sqlite-кэш + JSON/CSV экспорт.
- GUI не тронут, WB-клиенты и BrowserManager не тронуты.

## SESSION-START-04 (2026-06-16) — восстановление контекста + подготовка к F08

- Подтверждено: F00–F07 done; active_feature=F08 (status: todo, НЕ начат).
- Контроль F07: файлы `core/llm/base.py`, `core/llm/openrouter.py`, `core/llm/__init__.py` на месте; `tests/test_llm_base.py`, `tests/test_llm_openrouter.py` на месте. Файлов `core/llm/zai.py`, `core/llm/groq.py`, `core/llm/ollama.py` НЕТ (F08 не начат).
- VCS: `git log --oneline -8` → `7e7d7fe docs: close session after F07`, `2dcd3c1 docs: record F07 handoff before F08`, `5a73f5c F07: add LLM base layer and OpenRouter provider`, `61da29d docs: record package tracking fix before F07`, `f2b581f F00: track empty project packages`, `9552334 docs: record handoff before F07`, `a88980b F00-F06: complete foundation, WB clients, and browser base`. Working tree чист (untracked `.hermes/`).
- Security (PASS): `.env`/`sessions/`/`output/`/`.venv/`/`.hermes/` не tracked; API-ключей в коде нет; `config.yaml` без секретов; `.env.example` содержит только пустые плейсхолдеры. В `.gitignore` добавлен `.hermes/`.
- Тесты: `pytest -m "not live" -q` → **136 passed, 5 deselected** (ориентир совпал).
- Импорт-чеки: config ok / models ok / wb public ok / browser ok / llm ok.
- Команда проверки: `.\.venv\Scripts\python.exe -m pytest -m "not live" -q`.
- Следующий шаг: ждать «ОК F08» от пользователя. **F08 не выполнялся.**

## SESSION-CLOSE-02 (2026-06-16) — сессия закрыта после F07

- Принято: F07 (LLM слой: base + OpenRouter) — done и закоммичено.
- Статус: F00–F07 done; active_feature=F08 (НЕ начат, ждём «ОК F08»).
- Тесты: `pytest -m "not live"` → **136 passed, 5 deselected**.
- Импорт-чеки: `from core.llm import get_provider; from core.llm.base import LLMProvider` → "llm ok"; `from core.wb_public import WBPublic; from core.browser import BrowserManager` → "f03-f06 ok".
- VCS: последние коммиты `5a73f5c` (F07: add LLM base layer and OpenRouter provider), `2dcd3c1` (docs: record F07 handoff before F08). working tree чист (только untracked служебный `.hermes/`, не проектный).
- Security (всё PASS): `.env`/`sessions/`/`output/`/`.venv/`/`.hermes/` НЕ tracked; ключей в коде нет; `config.yaml` без секретов; `core/llm/` содержит только `base.py`/`openrouter.py`/`__init__.py` (zai/groq/ollama НЕ созданы → F08 не начат).
- Known issue: WB live может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту НЕ обходить. OpenRouter live требует `OPENROUTER_API_KEY` (без него live-тест skip).
- Следующий шаг: F08 — LLM провайдеры Z.AI / Groq / Ollama локальный. **F08 НЕ начат.**

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
- **F07 зафиксирован в git** — коммит **`5a73f5c`** "F07: add LLM base layer and OpenRouter provider" (8 файлов, +815/-21: core/llm/{base,openrouter,__init__}.py + tests/test_llm_{base,openrouter}.py + progress/feature_list/session-handoff). Секретов в коммите нет (`.env`/sessions/output/.venv/.hermes/__pycache__ не добавлены).
- Следующий: F08 (LLM провайдеры: Z.AI/GLM, Groq, Ollama локальный). **F08 НЕ начат** — ждём «ОК F08».

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
