## Активная фича

F15 — CLIP + pHash ранкер (1:1) (status: in_progress). Завязка F11 done. SA1/SA2 выполнены; SA3 не начинался.

## Журнал

## Журнал

### RECOVERY-CLOSE-F15 — checkpoint (2026-06-17)

- **Сессия оборвалась по лимитам** после завершения SA2. Новый коммит не был создан.
- **Восстановлено и проверено**:
  - `matcher/rank.py` на месте;
  - `tests/test_ranker_sa2.py` — 25 тестов;
  - `tests/test_ranker_sa3.py` существует (финальные тесты), но **SA3 не начинался официально** — файл оставлен без изменений в рамках recovery;
  - `pytest -m "not live" -q` → **379 passed, 1 skipped, 11 deselected**;
  - импорт-чек SA2: `from matcher.rank import RankError, ImageLoadError, ClipUnavailableError, load_image_rgb, image_phash_similarity, combine_scores` → OK;
  - импорт-чек F15-ранкера: `from matcher.rank import ClipImageEmbedder, ChinaCandidateRanker, rank_candidates` → OK;
- **F15 статус**: in_progress / checkpoint. НЕ считается done, т.к. SA3 (ClipImageEmbedder + ChinaCandidateRanker + Storage cache) официально не выполнялся; высокоуровневый ранкер в `matcher/rank.py` уже присутствует, но требует завершения SA3 для полного DoD.
- **Временный мусор удалён**: `test_esc.txt`, `test_esc2.txt`, `x.txt`.
- **Не в git**: `handoff_f15_sa1.md`, `handoff_f15_sa2.md` (их суть перенесена в `session-handoff.md`).
- **F16 не начинался**. GUI не тронут. China drivers не изменены. Push не выполнялся.
- **Следующий шаг**: F15 SA3 — финализировать `ClipImageEmbedder` + `ChinaCandidateRanker`, прогнать полный `tests/test_ranker_sa3.py`, обновить `feature_list.json`/`progress.md` и сделать финальный коммит F15.

### F14 — done (2026-06-16)

- **Саб-агенты**: эстафета 1→2→3→4→5 (PLAN → BUILD module+errors → BUILD Playwright flow+parser → TESTS/REGRESSION → REVIEW/DOCS/FINALIZE).
- **Файлы**:
  - `matcher/china/taobao.py` — драйвер Taobao image search:
    - иерархия ошибок `TaobaoSearchError` → `TaobaoCaptchaError`, `TaobaoLoginRequiredError`, `TaobaoNoResultsError`;
    - чистые функции `is_captcha_html`, `is_login_required_html`, `is_empty_results_html`, `normalize_candidate_url`;
    - `parse_results_html` — стандартная библиотека, извлечение карточек с балансировкой вложенных `<div>`, поддержка `data-src`, `data-ks-lazyload`, `data-price`, `data-title`, `title`, `alt`, ¥/￥ цен, video/play-признаков;
    - `TaobaoImageSearchDriver` с `search_by_image`, `close`, `__enter__/__exit__`;
    - интеграция `BrowserManager` (site="taobao") и `Storage` (cache namespace `"taobao:image_search"`);
    - ownership browser: закрывает только созданный самим драйвером `BrowserManager`;
  - `matcher/china/__init__.py` — ре-экспорт Taobao-сущностей с алиасами;
  - `fixtures/taobao_search_results.html`, `taobao_captcha.html`, `taobao_login.html`, `taobao_empty.html`;
  - `tests/test_taobao_driver.py` — 34 не-live теста + 1 live-gated тест.
- **Ручной логин перед live**:
  - создать сессию: `BrowserManager().manual_login("taobao", url="https://www.taobao.com/markets/pic/search")`;
  - войти в видимом окне, решить капчу руками, нажать Enter;
  - сессия сохранится в `sessions/taobao/`;
  - затем: `$env:TAOBAO_LIVE="1"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_taobao_driver.py -s`.
- **Тесты**:
  - `pytest -m "not live" -q` → **325 passed, 1 skipped, 11 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F14);
  - deselected: 3 live-теста Alibaba/1688/Taobao (Alibaba + 1688 + Taobao) + 8 ранее существовавших live = 11;
  - live-тест Taobao без `TAOBAO_LIVE=1` корректно deselected/skip'ается.
- **Security/review PASS**:
  - в бизнес-логике нет `pass`/`TODO`/`реализуем позже` (только легитимные control-flow `pass`);
  - нет stealth/anti-bot bypass/captcha_solver;
  - captcha/login обрабатываются исключениями, не обходятся;
  - browser ownership: `close()` закрывает только созданный драйвером `BrowserManager`;
  - `sessions/`, `output/`, `*.db`, `.venv/`, `.hermes/` не tracked.
- **Следующий шаг**: F15 — CLIP + pHash ранкер 1:1.


### F13 — done + committed (2026-06-16)

- **Саб-агенты**: эстафета 1→2→3→4→5 (PLAN → BUILD module+errors → BUILD Playwright flow+parser → TESTS/REGRESSION → REVIEW/DOCS/FINALIZE).
- **Коммит**: `835f78c` — "F13: add 1688 image search driver".
- **Файлы**:
  - `matcher/china/s1688.py` — драйвер 1688 image search:
    - иерархия ошибок `S1688SearchError` → `S1688CaptchaError`, `S1688LoginRequiredError`, `S1688NoResultsError`;
    - чистые функции `is_captcha_html`, `is_login_required_html`, `is_empty_results_html`, `normalize_candidate_url`, `parse_results_html`;
    - `S1688ImageSearchDriver` с `search_by_image`, `close`, `__enter__/__exit__`;
    - кэш `Storage` namespace `"1688:image_search"`, ключ `sha256(image_bytes) + max_results`;
    - Playwright flow через `BrowserManager.new_page(site="1688")`, upload `input[type=file]`, fallback на кнопку, wait, detect_captcha/login, parse;
  - `matcher/china/__init__.py` — ре-экспорт `S1688ImageSearchDriver`, ошибок, хелперов;
  - `fixtures/s1688_search_results.html`, `s1688_captcha.html`, `s1688_login.html`, `s1688_empty.html`;
  - `tests/test_s1688_driver.py` — 21 не-live тест + 1 live-gated тест.
- **Ручной логин перед live**:
  - создать сессию: `BrowserManager().manual_login("1688", url="https://www.1688.com")`;
  - войти в видимом окне, решить капчу руками, нажать Enter;
  - сессия сохранится в `sessions/1688/`;
  - затем: `$env:S1688_LIVE="1"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_s1688_driver.py -s`.
- **Тесты**:
  - `pytest -m "not live" -q` → **291 passed, 1 skipped, 10 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F13);
  - live-тест без `S1688_LIVE=1` корректно skip'ается (1 skipped).
- **Security/review PASS**:
  - в бизнес-логике нет `pass`/`TODO`/`реализуем позже` (только легитимные control-flow `pass`);
  - нет stealth/anti-bot bypass/captcha_solver;
  - captcha/login обрабатываются исключениями, не обходятся;
  - browser ownership: `close()` закрывает только созданный драйвером `BrowserManager`;
  - `sessions/`, `output/`, `*.db`, `.venv/` не tracked.
- **Следующий шаг**: F14 — Taobao image search.

## F13-SA4 — review (2026-06-16)

- **Задача**: TESTS / FIXTURES / LIVE GATED / REGRESSION.
- **Код не изменялся**: `matcher/china/s1688.py` и `matcher/china/__init__.py` оставлены без изменений (зона ответственности саб-агента 3).
- **tests/test_s1688_driver.py** — финальная полировка тестов:
  - Добавлены/обновлены контрактные тесты парсера:
    - `test_parse_results_finds_candidates` — ≥4 кандидата, проверка `site/title/url/thumb_url/price/has_video/video_url`, URL абсолютные.
    - `test_parse_results_deduplicates_by_url` — дедупликация по URL.
    - `test_parse_results_absolute_and_protocol_relative_urls` — относительные и protocol-relative URL нормализуются в абсолютные `https://`.
    - `test_normalize_candidate_url_variants` — параметризованная проверка нормализации относительных/protocol-relative/абсолютных URL.
    - `test_parse_results_respects_max_results` + `test_parse_results_max_results_zero_returns_empty` — ограничение `max_results`.
    - `test_parse_results_detects_captcha` → `S1688CaptchaError`; `test_parse_results_detects_login` → `S1688LoginRequiredError`; `test_parse_results_empty` → `S1688NoResultsError`; `test_parse_results_no_cards_raises_no_results`.
  - Усилены тесты `search_by_image` без сети:
    - `test_driver_search_by_image_missing_file` → `S1688SearchError("Image not found")`.
    - `test_driver_search_by_image_fake_browser` — fake `BrowserManager`/page возвращает HTML fixture → `list[Candidate]`.
    - `test_driver_search_by_image_fake_browser_login/empty/captcha/captcha_after_upload` — специальные ошибки при соответствующем content.
    - `test_driver_search_by_image_fake_browser_no_input_raises` → `S1688SearchError("upload input not found")`.
    - `test_driver_search_by_image_fake_browser_falls_back_to_button_click` — fallback на кнопку протестирован.
  - Cache:
    - `test_driver_uses_cache_and_skips_browser` — `use_cache=True` не вызывает `_upload_and_search` (проверка `assert_not_called`).
    - `test_driver_use_cache_false_refetches` — `use_cache=False` игнорирует stale cache и делает ровно один вызов `_upload_and_search`.
    - `test_driver_cache_returns_candidates_without_parsing` — cache hit возвращает кандидатов и не вызывает `parse_results_html`.
- **Live-тест**:
  - Один live-тест `test_search_by_image_live` в `tests/test_s1688_driver.py`.
  - Маркировка: `@pytest.mark.live` + `@pytest.mark.skipif(not os.environ.get("S1688_LIVE"), reason="S1688_LIVE=1 required")`.
  - Gating: env-флаг `S1688_LIVE=1`.
  - Проверка persistent-сессии `sessions/1688/` (skip, если отсутствует или пустая).
  - При captcha/login/anti-bot — `pytest.skip("1688 requires login/captcha")`, а не fail.
- **Regression**:
  - `pytest -m "not live" -q` → **291 passed, 1 skipped, 10 deselected** (было 282 passed, 1 skipped, 10 deselected; +9 новых не-live тестов F13-SA4).
  - F00–F12 не сломаны.
- **Без заглушек**: в бизнес-логике нет `pass`/`TODO`.
- **Security**: captcha/login не обходятся; секреты/сессии не трогались; `output/`, `sessions/`, `*.db` в `.gitignore`.

- **Что остаётся саб-агенту 5 (REVIEW / DOCS / FINALIZE)**:
  - code review `matcher/china/s1688.py` и `tests/test_s1688_driver.py`;
  - документирование ручного flow создания `sessions/1688` через `core.browser.BrowserManager.manual_login` перед live-тестом;
  - финальная проверка `pytest -m "not live" -q` и live-gating;
  - обновление `session-handoff.md` и коммит F13.

## F13-SA2 — in_progress (2026-06-16)

- **matcher/china/s1688.py** — создан драйвер 1688:
  - Иерархия ошибок: `S1688SearchError`, `S1688CaptchaError`, `S1688LoginRequiredError`, `S1688NoResultsError`.
  - Чистые функции: `is_captcha_html`, `is_login_required_html`, `is_empty_results_html`, `normalize_candidate_url`, `parse_results_html`.
  - `S1688ImageSearchDriver`: `search_by_image`, `close`, `__enter__`, `__exit__`.
  - Cache: `Storage`, namespace `"1688:image_search"`, ключ `sha256(image_bytes) + max_results`.
  - Playwright flow: `new_page(site="1688")`, `_detect_page_issues`, upload `input[type=file]`, wait, parse.
  - Обработка ошибок: captcha/login/no-results/missing-file/upload-not-found.

- **matcher/china/__init__.py** — ре-экспорт 1688-сущностей.

- **Фикстуры**:
  - `fixtures/s1688_search_results.html` (4 карточки + 1 дубликат + 1 phone-ссылка).
  - `fixtures/s1688_captcha.html`.
  - `fixtures/s1688_login.html`.
  - `fixtures/s1688_empty.html`.

- **tests/test_s1688_driver.py** — 21 не-live тест:
  - парсинг выдачи, дедупликация, max_results;
  - детекция captcha/login/empty/no-cards;
  - `normalize_candidate_url`;
  - missing file, cache hit/miss, fake-browser search, captcha via `detect_captcha`;
  - close owned browser, context manager.

- **Прогон**: `pytest -m "not live" -q` → **278 passed, 1 skipped, 10 deselected**.
- F00–F12 не сломаны.
- Без заглушек в бизнес-логике (только легитимные `pass` в телах exception-классов).
- Security: captcha/login не обходятся; секреты не трогались; `output/`, `sessions/`, `*.db` в `.gitignore`.

- **Что остаётся саб-агенту 3 (BUILD / PLAYWRIGHT FLOW + PARSER)**:
  - уточнить реальные селекторы 1688 picture-search;
  - доработать парсер под живую выдачу при необходимости;
  - live-смоук с ручным логином/сессией.

## F12 — done + committed (2026-06-16)

Реализовано эстафетой из 5 саб-агентов (PLAN → BUILD module+errors → BUILD Playwright flow+parser → TESTS → REVIEW/DOCS). **Закоммичено** — коммит F12.

- **matcher/china/__init__.py** — публичный API пакета `ChinaSearchDriver`, `AlibabaImageSearchDriver`, ошибки, `parse_results_html`.
- **matcher/china/base.py** — `ChinaSearchDriver` как `typing.Protocol` с `search_by_image(image_path, *, max_results=None, use_cache=True) -> list[Candidate]`.
- **matcher/china/alibaba.py** — Alibaba image-search driver:
  - `AlibabaSearchError`, `AlibabaCaptchaError`, `AlibabaLoginRequiredError`, `AlibabaNoResultsError`.
  - `parse_results_html(html)` — чистая функция без сети, парсит карточки стандартной библиотекой.
  - `AlibabaImageSearchDriver`: `search_by_image()` → кэш `Storage`, Alibaba picture search, загрузка `input[type=file]`, детекция captcha/login, возврат до `max_candidates` кандидатов.
- **fixtures/** — `alibaba_search_results.html`, `alibaba_captcha.html`, `alibaba_login.html`, `alibaba_empty.html`, `dummy_query.jpg`.
- **tests/test_alibaba_driver.py** — 14 тестов (13 passed, 1 deselected live):
  - парсинг выдачи, captcha/login/no-results, `max_results`, missing file, cache hit/miss, close owned browser.
- **Прогон**: `pytest -m "not live" -q` → **257 passed, 1 skipped, 9 deselected**.
- **Skip**: WebP/Pillow skip из F11 — platform-specific, не баг F12.
- **Security**: captcha/login не обходятся; секреты/сессии не трогались; `output/`, `sessions/`, `*.db` в `.gitignore`.
- **Live-команда Alibaba**: `$env:ALIBABA_LIVE="1"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_alibaba_driver.py -s`.
- **Следующий шаг**: F13 — 1688 image search (логин-сессия). **F13 не начат**.

## F11 — done (2026-06-16)

Реализовано эстафетой из 5 саб-агентов (PLAN → BUILD parsing → BUILD resolve+normalize → TESTS → REVIEW/DOCS). **Не закоммичено** — ждёт команды пользователя.

- **matcher/input.py** — Input resolver:
  - `ResolvedInput` dataclass: `query_image_path`, `source_type`, `nmId`, `product`, `original_input`, `meta`.
  - `InputResolverError`, `InvalidInputError`, `ImageDownloadError`, `ImageValidationError`.
  - `parse_wb_nm_id(value)` — int/строка 5–12 цифр.
  - `is_wb_url(value)` — http(s) + `wildberries.ru` + `/catalog/<nmId>/detail.aspx`.
  - `extract_wb_nm_id_from_url(url)` — извлекает nmId, отвергает сторонние домены.
  - `normalize_image_to_query_jpg(src, output_path, *, max_size, quality)` — Pillow RGB JPEG, thumbnail, поддержка Path/bytes/BytesIO.
  - `resolve_input(value, *, wb_client=None, output_dir=None)` — единый вход:
    - WB артикул → `wb_client.get_detail(nmId)` → скачать `img_url` → `output/query.jpg`.
    - WB ссылка → извлечь nmId → `get_detail` → скачать → `output/query.jpg`.
    - локальное фото `.jpg/.jpeg/.png/.webp` → RGB JPEG → `output/query.jpg`.
    - `output_dir` default из `settings.paths.output`.
    - Внедрённый `wb_client` не закрывается; созданный по умолчанию — закрывается.
- **tests/test_matcher_input.py** — 22 теста (21 passed, 1 skipped WebP; без сети):
  - парсинг nmId из int/string/мусора;
  - `is_wb_url` и `extract_wb_nm_id_from_url` включая query-параметры и сторонние домены;
  - локальный файл: jpg, PNG с alpha → RGB JPEG, WebP, unsupported ext, missing file, broken image;
  - WB-путь: мок WBPublic + мок скачивания, пустой `img_url`, ошибка download, default client создаётся/закрывается;
  - `normalize_image_to_query_jpg` и resize;
  - unrecognized input → `InvalidInputError`.
- **Прогон**: `pytest -m "not live" -q` → **244 passed, 1 skipped, 8 deselected** (было 223 passed + 1 skipped; +21 новых не-live теста F11). F00–F10 не сломаны.
- **Без заглушек**: нет `pass`/`TODO` в бизнес-логике (только легитимные `pass` в телах exception-классов).
- **Security**: `output/` не tracked; секреты не трогались; нет новых внешних запросов в обычных тестах.
- **F11 зафиксирован в git** — коммит **`461daa0`** "F11: add input resolver for WB items and images" (5 файлов, +656/-27: `matcher/input.py`, `tests/test_matcher_input.py`, `progress.md`, `feature_list.json`, `session-handoff.md`).
- **F11-SMOKE-01 (ручной)**: локальная PNG `fixtures/smoke_input.png` (RGBA 300×300) → `resolve_input()` → `output/query.jpg` — `source_type=file`, format=JPEG, mode=RGB, size=(300, 300). Smoke-файл удалён после теста; `output/query.jpg` не в git.
- **F12 не начат**; китайские сайты, CLIP/pHash, GUI не тронуты.

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
- **F10 зафиксирован в git** — коммит **`1432b34`** "F10: add sqlite cache and export storage" (5 файлов, +594/-23: `core/storage.py`, `tests/test_storage.py`, `progress.md`, `feature_list.json`, `session-handoff.md`).

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
