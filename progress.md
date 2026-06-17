## Активная фича

Все фичи F00–F28 завершены. Проект complete.

## Журнал

### F28 — done + committed (2026-06-17)

- **Файлы**:
  - `run.py` (обновлён): теперь импортирует и вызывает `gui.app.main` — точка входа для PyInstaller/.exe открывает GUI;
  - `scripts/build_windows.ps1` (новый):
    - PowerShell-скрипт сборки Windows .exe через PyInstaller;
    - проверяет `.venv`, устанавливает/обновляет `pyinstaller`;
    - по умолчанию запускает `pytest -m "not live" -q` перед сборкой (можно пропустить `-SkipTests`);
    - поддерживает `-OneFile` для одного .exe;
    - перечисляет `hiddenimports` для всех проектных модулей;
    - добавляет `config.yaml` и `fixtures/` в сборку;
    - исключает `.env`, `sessions/`, `output/`, `.venv/`, `build/`, `dist/`;
    - выводит путь, размер и SHA256 итогового .exe;
    - копирует `.env.example` рядом с .exe.
  - `WB_Radar_China_Matcher.spec` (новый, сгенерирован PyInstaller и отредактирован):
    - `Analysis` для `run.py`;
    - `datas` содержит `config.yaml` и `fixtures/`;
    - `hiddenimports` — все ключевые модули проекта;
    - `excludes` — `.env`, `sessions`, `output`, `.venv`, `build`, `dist`;
    - `exclude_binaries=True` + `COLLECT` → onedir-сборка по умолчанию.
  - `tests/test_build_packaging.py` (новый) — 11 не-live тестов:
    - `run.py` импортирует `gui.app.main`;
    - build script существует и использует PyInstaller;
    - build script проверяет `.venv`, запускает тесты или поддерживает `-SkipTests`;
    - build script исключает секретные/временные папки;
    - build script не содержит hardcoded API keys;
    - README содержит секцию `.exe`-сборки и упоминает `build_windows.ps1`;
    - README упоминает `.env`/`sessions`/`output`;
    - `.gitignore` исключает `build/`, `dist/`, `.env`, `sessions/`, `output/`, `.venv/`, `*.db`, `__pycache__/`;
    - `gui.app.main` callable;
    - импорт `gui.app` внутри `.venv` не открывает окно и не падает.
  - `.gitignore` (обновлён): добавлены `build/` и `dist/`.
  - `README.md` (обновлён): добавлена секция "Сборка Windows .exe" с командами PowerShell, требованиями, путём к .exe, известными ограничениями.
- **Локальная сборка**:
  - PyInstaller успешно собрал `.exe` в текущей среде Windows 10/Python 3.11;
  - Итоговый файл: `dist\WB_Radar_China_Matcher\WB_Radar_China_Matcher.exe`;
  - Размер: **57.6 MB**;
  - SHA256: `EBE3B4D3613E223E773C09C453810136ED254E0A10EB19E1DF416093CF7ED7AC`;
  - Предупреждения PyInstaller по `pyyaml`, `scipy.special._cdflib` и `torch.utils.tensorboard` — не критичны, приложение стартует.
- **Тесты**:
  - `pytest -m "not live" -q` → **620 passed, 1 skipped, 15 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F28);
  - deselected: 15 live-тестов;
  - F00–F27 не сломаны.
- **Импорт-чек F28**: `from gui.app import create_app` → **final gui import ok**.
- **Безопасность / ограничения**:
  - секреты и временные папки не включены в `.exe`;
  - `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked;
  - build/dist не коммитятся;
  - обычные тесты без сети, без реального браузера, без реального LLM;
  - push не выполнялся.
- **Коммит**: `F28: add Windows executable build`.
- **Статус проекта**: F00–F28 done; active_feature=null.

### F27 — done + committed (2026-06-17)

- **Файлы**:
  - `tests/test_e2e.py` — 6 не-live E2E/интеграционных тестов + 2 live smoke-теста:
    - `test_e2e_matcher_happy_path`: WB артикул (fake) → `build_matcher_tab` → fake `matcher_pipeline` возвращает товар и кандидатов → top candidate содержит `video_url` → `_download_one` вызывает fake `downloader` → проверяем вызов и статус "Скачано видео: 1";
    - `test_e2e_matcher_ranker_orders_candidates`: генерирует RGB-изображение в `tmp_path`, создаёт кандидата с тем же thumb → `rank_candidates(use_clip=False, use_phash=True)` возвращает кандидата с `similarity > 0.95`;
    - `test_e2e_discovery_happy_path`: fake `ViralProduct` → `analyze_reviews_voc` с fake LLM → VoC содержит "Шумит"/"Лёгкий" → `generate_hooks` с fake LLM → 5 хуков → `extract_review_videos_from_reviews` находит видеоотзыв;
    - `test_e2e_discovery_gui_bridge_fills_matcher_input`: fake discovery/voc/hooks/review_video services + bridge callback → выбор товара → кнопка "В Матчер" заполняет поле `MatcherChinaController`;
    - `test_e2e_create_app_three_tabs_with_fake_services`: `create_app` с fake сервисами строит 3 вкладки, первая — "Матчер China";
    - `test_e2e_fake_llm_not_real_llm`: `analyze_reviews_voc` с fake `LLMProvider` не выходит в сеть;
    - live-тесты:
      - `test_live_wb_to_discovery_smoke`: `@pytest.mark.live`, `pytest.skip` без `WB_RADAR_RUN_LIVE=1`, вызывает `harvest.discovery.niche` с `pages=1, top_n=2`;
      - `test_live_matcher_one_product_smoke`: `@pytest.mark.live`, `pytest.skip` без флага + дополнительный `pytest.skip` с пояснением, что требует ручных сессий.
  - `README.md` (новый):
    - описание проекта и 3 вкладок;
    - инструкция по установке через `init.sh`;
    - `.env.example` и запуск;
    - секции "Тесты": обычные (`pytest -m "not live" -q`) и live smoke tests с `WB_RADAR_RUN_LIVE=1`;
    - примечания по безопасности и границам (без обхода защит, 403/капча — known issue).
- **Тесты**:
  - `pytest -m "not live" -q` → **609 passed, 1 skipped, 15 deselected**.
  - +6 passed по `tests/test_e2e.py` в не-live прогоне;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F27);
  - deselected: 15 live-тестов (Alibaba/1688/Taobao/WB + discovery + 2 новых e2e live);
  - F00–F26 не сломаны.
- **Импорт-чек F27**: `from gui.app import create_app; from harvest.discovery import niche; from harvest.hooks import generate_hooks` → **e2e imports ok**.
- **Безопасность / ограничения**:
  - обычные e2e-тесты без сети, без реального браузера, без реального LLM;
  - live-тесты gated через `WB_RADAR_RUN_LIVE=1` и `@pytest.mark.live`;
  - live-тесты не обходят капчи/антибот/WAF;
  - `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked;
  - F28 не начиналась;
  - push не выполнялся.
- **Коммит**: `F27: add end-to-end integration tests`.
- **Следующий шаг**: F28 — сборка .exe.

### F26 — done + committed (2026-06-17)

- **Файлы**:
  - `gui/settings.py` (новый):
    - `LLM_PROVIDERS` = openrouter/zai/groq/ollama/chatgpt_web;
    - `PROVIDER_SECRET_KEY` — имя env-переменной для каждого провайдера;
    - `SettingsSnapshot` — read-only snapshot настроек для GUI;
    - `mask_secret(value)` — маскирует секрет, показывая первые 2 и последние 4 символа;
    - `SettingsController` с dependency injection: `save_settings`, `open_folder`, `session_status`, `on_status`;
    - `load_settings()` — читает `core.config.settings` и статусы сессий;
    - `validate_settings()` — проверяет провайдер, proxy (urlparse), output/sessions paths;
    - `save_settings_to_disk()` — читает контролы, валидирует, вызывает injectable `save_settings`;
    - `_on_validate()`, `_on_open_output()`, `_on_open_sessions()`;
    - `build_tab(...)` — UI: выбор LLM-провайдера и модели, proxy, пути output/sessions, секции "Ключи / сессии" (masked, password-поля), "Статус сессий" (1688/Taobao/ChatGPT), кнопки "Проверить настройки", "Сохранить", "Открыть output", "Открыть sessions", статус.
    - `_default_save_settings` пишет в `.env.local` (не tracked), обновляет in-process `settings.llm.provider/model` и `settings.proxy`;
    - `_default_open_folder` создаёт папку при необходимости и открывает через explorer/open/xdg-open, fallback на webbrowser;
    - `_default_session_status` проверяет наличие непустой папки в `sessions/<site>`.
  - `gui/app.py` (расширен):
    - re-export `SettingsController`, `build_settings_tab` из `gui.settings`;
    - `create_app(...)` теперь создаёт 3 вкладки: "Матчер China", "Разведка WB", "Настройки" (`length=3`);
    - параметр `settings_controller` для DI;
    - первая вкладка остаётся "Матчер China" (`selected_index=0`).
  - `tests/test_gui_settings.py` — 13 не-live тестов:
    - `build_settings_tab` создаёт контролы;
    - `create_app` создаёт 3 вкладки в правильном порядке;
    - `load_settings` работает на fake config;
    - `mask_secret` не показывает полный ключ;
    - `validate_settings` ловит плохой proxy;
    - `save_settings` вызывает fake storage;
    - `save_settings` отчитывается об ошибке;
    - статусы сессий отображаются;
    - кнопка "Проверить настройки" вызывает validate;
    - кнопка "Открыть output" вызывает fake opener;
    - кнопка "Открыть sessions" сообщает об ошибке;
    - API key отображается masked и в password-поле;
    - public API import check.
  - `tests/test_gui_matcher.py` — обновлён: `create_app` теперь 3 вкладки.
  - `tests/test_gui_discovery.py` — обновлён: `create_app` теперь 3 вкладки.
- **Тесты**:
  - `pytest -m "not live" -q` → **603 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F26);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F25 не сломаны.
- **Импорт-чек F26**: `from gui.app import create_app, build_matcher_tab, build_discovery_tab, build_settings_tab` → **gui settings ok**.
- **Безопасность / ограничения**:
  - секреты не отображаются в UI полностью; поля `password=True`;
  - сохранение идёт в injectable storage, по умолчанию `.env.local` (untracked);
  - `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked;
  - обычные тесты без сети, без реального браузера, без реального LLM;
  - F27/F28 не начаты;
  - push не выполнялся.
- **Коммит**: `F26: add GUI settings tab`.
- **Следующий шаг**: F27 — End-to-end + интеграционные тесты.

### F25 — done + committed (2026-06-17)

- **Файлы**:
  - `gui/app.py` (расширен):
    - `DiscoveryWBController` — контроллер вкладки "Разведка WB" с dependency injection (`discovery_service`, `voc_service`, `hooks_service`, `review_video_service`, `downloader`, `to_matcher_bridge`);
    - `build_discovery_tab(...)` — возвращает `(Tab, DiscoveryWBController)` для тестов;
    - `build_matcher_tab(...)` теперь возвращает `(Tab, MatcherChinaController)`;
    - `MatcherChinaController` дополнен методами `set_input_value()` и `focus_input()` для моста "В Матчер";
    - `create_app(...)` теперь создаёт две вкладки: "Матчер China" (первая, `selected_index=0`) и "Разведка WB";
    - внутренняя функция `bridge_to_matcher(nm_id)` заполняет поле ввода первой вкладки;
    - UI "Разведка WB": поле ниши, кнопка "Найти вирусные", таблица вирусных товаров (nmId/name/brand/viral_score/feedbacks/rating/"Выбрать"), панель деталей с VoC (боли/желания/страхи), хуками, возражениями, видео из отзывов, кнопкой "В Матчер";
    - default services: `_default_discovery_service` → `harvest.discovery.niche`, `_default_voc_service` → сбор отзывов + `analyze_reviews_voc`, `_default_hooks_service` → `generate_hooks`, `_default_review_video_service` → `get_review_videos`; не вызываются в обычных тестах;
    - безопасная обработка пустой ниши, ошибок discovery/voc/hooks/review_video, UI не падает.
  - `tests/test_gui_discovery.py` — 9 не-live тестов:
    - контроллер и вкладка создаются;
    - `create_app` создаёт 2 вкладки, первая — "Матчер China";
    - fake discovery вызывается и результаты отображаются;
    - viral_score отображается;
    - пустая ниша → статус;
    - ошибка discovery не падает;
    - выбор товара загружает VoC/хуки/видео (fake services);
    - кнопка "В Матчер" через bridge заполняет поле первой вкладки;
    - public API import check.
  - `tests/test_gui_matcher.py` — обновлён под новый возврат `build_matcher_tab`/`create_app` (2 вкладки).
- **Тесты**:
  - `pytest -m "not live" -q` → **589 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F25);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F24 не сломаны.
- **Импорт-чек F25**: `from gui.app import create_app, build_matcher_tab, build_discovery_tab` → **gui discovery ok**.
- **Безопасность / ограничения**:
  - обычные тесты без сети, без реального браузера и без реального LLM (fake services);
  - F26/F27/F28 не начаты;
  - live WB/China/LLM может давать 403/капчу — защиту не обходить;
  - push не выполнялся.
- **Коммит**: `F25: add WB discovery GUI tab`.
- **Следующий шаг**: F26 — GUI настройки.

### F24 — done + committed (2026-06-17)

- **Файлы**:
  - `gui/app.py`:
    - `MatcherChinaController` — контроллер вкладки "Матчер China" с dependency injection;
    - `build_matcher_tab(page, matcher_pipeline=None, downloader=None, output_root=None)` — строит вкладку с инжекцией fake pipeline/downloader для тестов;
    - `create_app(page, ...)` — создаёт приложение с тёмной темой, вкладка "Матчер China" первая и единственная (selected_index=0);
    - UI: поле ввода WB артикула/ссылки, кнопка "Фото" (FilePicker), кнопка "Найти", индикатор прогресса, статус, таблица/список кандидатов с thumb/site/title/similarity%/price, кнопки "Открыть"/"Видео"/"Скачать", кнопка "Скачать все видео топ-5";
    - `_default_matcher_pipeline` — thin wrapper над `matcher.input.resolve_input`, China drivers, `matcher.rank.rank_candidates`, `matcher.video_china.ChinaVideoExtractor`; не вызывается в обычных тестах;
    - обработка пустого ввода, ошибок pipeline, fallback nm_id=0 для файлов без артикула;
    - инжектированный `matcher_pipeline`/`downloader` позволяет тестировать без сети и браузера.
  - `tests/test_gui_matcher.py` — 11 не-live тестов:
    - `build_tab` создаёт все контролы;
    - `create_app` устанавливает тёмную тему и первую вкладку "Матчер China";
    - fake pipeline вызывается при поиске и результаты рендерятся;
    - similarity отображается как процент;
    - пустой ввод даёт статус/ошибку;
    - ошибка pipeline не падает;
    - кнопка "Скачать" вызывает fake downloader;
    - "Скачать все видео топ-5" берёт максимум 5 и пропускает кандидатов без видео;
    - public API import check.
- **Тесты**:
  - `pytest -m "not live" -q` → **580 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F24);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F23 не сломаны.
- **Импорт-чек F24**: `from gui.app import create_app, build_matcher_tab` → **gui matcher ok**.
- **Безопасность / ограничения**:
  - обычные тесты без сети и без реального браузера (fake `matcher_pipeline`/`downloader`);
  - F25/F26/F27/F28 не начаты;
  - live WB/China может давать 403/капчу — защиту не обходить, AGENTS.md;
  - push не выполнялся.
- **Коммит**: `F24: add China matcher GUI tab`.
- **Следующий шаг**: F25 — GUI вкладка Разведка WB + мост в Матчер.

### F23 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/hooks.py`:
    - `VideoHookSet` pydantic-модель: `hooks` (5 вариантов), `structure` (список `Scene`), `objections`;
    - `Scene` pydantic-модель: `scene`, `duration`, `content`;
    - `HookGeneratorError` / `HookResponseError`;
    - `build_hooks_prompt(voc, product=None)` — prompt на основе VoC и опционально товара;
    - `_HOOKS_JSON_SCHEMA` — JSON schema с required `hooks`/`structure`/`objections`;
    - `parse_hooks_response(raw)` — валидация + fallback на битый/неполный LLM-ответ: 5 дефолтных хуков, структура по умолчанию, возражения по умолчанию;
    - `save_hooks(nm_id, hook_set, output_root)` — сохраняет `output/hooks/<nmId>.md`;
    - `generate_hooks(voc, nm_id=None, product=None, llm_provider=None, output_root=None)` — pipeline: prompt → `complete_json` → parse → save (если nm_id задан) → return `VideoHookSet`; при ошибке LLM → fallback без падения;
    - инжектированный LLM-провайдер не закрывается, дефолтный — закрывается.
  - `tests/test_hooks.py` — 14 не-live тестов:
    - `build_hooks_prompt` содержит VoC + товар;
    - `generate_hooks` вызывает fake LLM и сохраняет `hooks/<nmId>.md`;
    - валидный fake response → `VideoHookSet` с 5 хуками, структурой и возражениями;
    - `hooks` содержит ровно 5 вариантов;
    - структура рендерится таблицей в Markdown;
    - возражения сохраняются;
    - неполный ответ LLM → fallback без падения;
    - пустой VoC не валит генерацию;
    - без `nm_id` файл не сохраняется;
    - инжектированный провайдер не закрывается, дефолтный — закрывается.
- **Тесты**:
  - `pytest -m "not live" -q` → **569 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F23);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F22 не сломаны.
- **Импорт-чек F23**: `from harvest.hooks import generate_hooks, save_hooks, build_hooks_prompt` → **hooks ok**.
- **Безопасность / ограничения**:
  - обычные тесты без сети и без реального LLM (fake `LLMProvider`);
  - F24/F25/F26 GUI не начаты;
  - API-ключи не в коде, читаются из `.env` через `core.llm.get_provider`;
  - чужие видеоотзывы используются как референс/материал, не перезаливаются 1:1;
  - push не выполнялся.
- **Коммит**: `F23: add hook generator`.
- **Следующий шаг**: F24 — GUI вкладка Матчер China.

### F19 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/describe.py`:
    - `VideoDescription` pydantic-модель: `title`, `description`, `captions` (3 варианта), `tags`;
    - `DescriptionWriterError` / `DescriptionResponseError`;
    - `build_description_prompt(video_asset, product, voc)` — prompt для LLM с данными товара, видео и VoC;
    - `_DESCRIPTION_SCHEMA` — JSON schema с required полями;
    - `parse_description_response(raw)` — валидация/нормализация ответа LLM: неполный/битый ответ → безопасный fallback (`title` default, 3 пустых `captions`, пустые `tags`);
    - `save_description(nm_id, description, output_root)` — сохраняет `output/video/<nmId>/description.json` через `Storage.save_json` (`ensure_ascii=False`, `indent=2`) и `output/video/<nmId>/description.md`;
    - `_render_description_md()` — читаемый markdown: заголовок, описание, пронумерованные подводки, теги с `#`;
    - `describe_video(video_asset, product, voc, llm_provider=None, output_root=None)` — pipeline: prompt → `complete_json` → parse → save JSON+MD → return `VideoDescription`; при ошибке LLM → fallback без падения;
    - инжектированный LLM-провайдер не закрывается, дефолтный — закрывается.
  - `tests/test_describe.py` — 12 не-live тестов:
    - `build_description_prompt` содержит Product + VoC + VideoAsset;
    - `describe_video` вызывает fake LLM и сохраняет `description.json` + `description.md`;
    - валидный fake response → `VideoDescription` с title/captions/tags;
    - сохраняются JSON и MD в `output/video/<nmId>/`;
    - `captions` содержит ровно 3 варианта;
    - tags сохраняются;
    - неполный ответ LLM → fallback без падения;
    - пустой VoC не валит генерацию;
    - битый ответ LLM → fallback;
    - инжектированный провайдер не закрывается, дефолтный — закрывается.
- **Тесты**:
  - `pytest -m "not live" -q` → **555 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F19);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F22 не сломаны.
- **Импорт-чек F19**: `from harvest.describe import describe_video, build_description_prompt, save_description` → **describe ok**.
- **Безопасность / ограничения**:
  - обычные тесты без сети и без реального LLM (fake `LLMProvider`);
  - F23/GUI не начаты;
  - API-ключи не в коде, читаются из `.env` через `core.llm.get_provider`;
  - описание пишется своё, чужие видеоотзывы используются как референс/материал;
  - push не выполнялся.
- **Коммит**: `F19: add video description writer`.
- **Следующий шаг**: F23 — Hook generator (.md хуки + структура ролика).

### F22 — done + committed (2026-06-17)

- **Файлы**:
  - `core/models.py`:
    - `VocItem` расширен полями `quote` (дословная цитата) и `source_review_ids` (источники).
  - `harvest/voc.py`:
    - `VoCAnalyzerError` / `ReviewsLoadError` / `VoCAnalysisError`;
    - `load_reviews_for_voc(path_or_nm_id, reviews, output_root)` — загружает отзывы из файла `output/reviews/<nmId>.json`, по nmId, или принимает готовый список `Review`;
    - `chunk_reviews(reviews, batch_size=40)` — разбивает на батчи по 40;
    - `build_voc_prompt(reviews)` — строит prompt для LLM со схемой VoC;
    - `_VOC_JSON_SCHEMA` — JSON schema с 7 категориями;
    - `analyze_reviews_voc(reviews, llm_provider=None, batch_size=40)` — анализ батчами через `LLMProvider.complete_json`, merge + dedupe; пустые отзывы → пустой `VoC`; битый LLM-ответ логируется и пропускается;
    - `merge_voc_results(results)` — склеивает категории из нескольких батчей;
    - `dedupe_voc_items(items)` — дедуп по нормализованному text, суммирование frequency, merge source_review_ids; сортировка по frequency desc, text asc;
    - `save_voc(nm_id, voc, output_root)` — сохраняет `output/voc/<nmId>.json` через `Storage.save_json` (`ensure_ascii=False`, `indent=2`);
    - `analyze_voc_for_nmId(nm_id, reviews_path, llm_provider, output_root, batch_size)` — convenience pipeline: load → analyze → save → return VoC.
  - `tests/test_voc.py` — 20 не-live тестов:
    - `chunk_reviews` режет по 40;
    - `analyze_reviews_voc` вызывает fake LLM для каждого батча;
    - валидный JSON от fake LLM превращается в `VoC`;
    - `merge_voc_results` склеивает категории;
    - `dedupe_voc_items` объединяет повторы и суммирует frequency;
    - сортировка по frequency desc;
    - пустые отзывы → валидный пустой VoC;
    - `save_voc` создаёт `output/voc/<nmId>.json`;
    - `analyze_voc_for_nmId` читает reviews JSON и сохраняет voc JSON;
    - битый ответ LLM обрабатывается стабильно;
    - инжектированный LLM-провайдер не закрывается, дефолтный — закрывается.
- **Тесты**:
  - `pytest -m "not live" -q` → **543 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F22);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F21 не сломаны.
- **Импорт-чек F22**: `from harvest.voc import analyze_reviews_voc, analyze_voc_for_nmId, merge_voc_results` → **voc ok**.
- **Безопасность / ограничения**:
  - обычные тесты без сети и без реального LLM (fake `LLMProvider`);
  - F19/F23/GUI не начаты;
  - API-ключи не в коде, читаются из `.env` через `core.config`;
  - push не выполнялся.
- **Коммит**: `F22: add VoC analyzer`.
- **Следующий шаг**: F19 — Description writer (LLM: описание/подводка под видео). F19 теперь разблокирован, т.к. F22 done.

### F21 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/reviews.py`:
    - `ReviewCollectionResult` pydantic-модель: `nmId`, `imtId`, `reviews_count`, `output_path`, `status`, `error`;
    - `ReviewsCollectorError` / `ProductInputError` — ошибки;
    - `_resolve_product()` — нормализует вход: `Product`, `ViralProduct`, pydantic-модели, `dict`, `int`, `str` (nmId);
    - `collect_reviews_for_product(product_or_nm_id, wb_client=None, output_root=None, max_count=1000)`:
      - если `imtId` есть — `WBPublic.get_reviews(imtId, max_count)`;
      - если только `nmId` — `WBPublic.get_detail(nmId)` для получения `imtId`;
      - сохраняет JSON в `output/reviews/<nmId>.json` через `Storage.save_json` (`ensure_ascii=False`, `indent=2`);
      - возвращает `ReviewCollectionResult`;
      - ошибки — `status="error"` + `error`;
      - инжектированный `wb_client` не закрывается, созданный по умолчанию — закрывается.
    - `collect_reviews_for_products(products, ...)` — batch; ошибка одного товара не валит весь batch; пустой вход → [].
  - `tests/test_reviews_collector.py` — 18 не-live тестов:
    - для 2 товаров создаются `output/reviews/<nmId>.json`;
    - при наличии `imtId` `get_detail` не вызывается;
    - при отсутствии `imtId` вызывается `get_detail(nmId)`;
    - `get_reviews` вызывается с правильным `imtId` и `max_count`;
    - JSON содержит список отзывов с полями `Review.model_dump(mode="json")`;
    - пустой список отзывов сохраняется как `[]`;
    - ошибка одного товара не валит batch;
    - `output_root` можно подменить на `tmp_path`;
    - входы: `Product`, `ViralProduct`, `int`, `str` nmId, `dict`;
    - товар без `imtId` после `get_detail` возвращает ошибку;
    - инжектированный клиент не закрывается, дефолтный — закрывается.
- **Тесты**:
  - `pytest -m "not live" -q` → **523 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F21);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F20 не сломаны.
- **Импорт-чек F21**: `from harvest.reviews import collect_reviews_for_product, collect_reviews_for_products` → **reviews collector ok**.
- **Безопасность / ограничения**:
  - обычные тесты без сети (fake `WBPublic`);
  - F22/F23/GUI не начаты;
  - F19 всё ещё заблокирован до F22;
  - push не выполнялся.
- **Коммит**: `F21: add reviews collector`.
- **Следующий шаг**: F22 — VoC analyzer (боли/желания/страхи JSON).

### F20 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/discovery.py`:
    - `ViralProduct` / `ViralResult` pydantic-модели;
    - `parse_review_date()` — парсит ISO и `YYYY-MM-DD` даты, отбрасывает будущие;
    - `count_reviews_since()` — считает отзывы не старше N дней;
    - `compute_velocity()` — возвращает `(velocity_7d, velocity_30d)`;
    - `normalize_values()` — min-max нормализация, детерминированная;
    - `rating_closeness(rating, target=4.6)` — 1.0 на target, линейное падение до 0.0 на расстоянии ≥1.4;
    - `compute_viral_scores()` — считает `viral_score = 0.5*norm(velocity_7d) + 0.3*norm(feedbacks) + 0.2*close(rating,4.6)` и сортирует по убыванию;
    - `niche(query, pages=1, top_n=20, wb_client=None, output_root=None)` — пайплайн:
      - `WBPublic.search(query, pages=...)`;
      - top_n по `feedbacks`;
      - `WBPublic.get_reviews(imtId)` для каждого;
      - скоринг и сортировка;
      - CSV экспорт в `output/viral/<query>_<date>.csv` через `Storage.save_csv`;
      - инжектированный `wb_client` не закрывается, созданный по умолчанию — закрывается;
      - при ошибке get_reviews продукт не пропускается, а добавляется с нулевыми velocity и логом WARNING.
  - `tests/test_discovery.py` — 28 не-live тестов + 1 live-gated:
    - парсинг дат, в т.ч. будущие отбрасываются;
    - `count_reviews_since` 7d/30d, старые не попадают;
    - `normalize_values` детерминирован;
    - `rating_closeness` максимален около 4.6;
    - `compute_viral_scores` сортирует правильно;
    - `niche()` вызывает `search()` и `get_reviews()`;
    - `top_n` ограничивает количество товаров;
    - пустая выдача search → [];
    - товар без `imtId` пропускается стабильно;
    - CSV экспорт создаётся в `output/viral/`;
    - default client создаётся/закрывается, инжектированный — нет;
    - ошибка get_reviews логируется и не падает;
    - live smoke под `@pytest.mark.live` + `WB_TEST_DISCOVERY=1`.
- **Тесты**:
  - `pytest -m "not live" -q` → **505 passed, 1 skipped, 13 deselected**.
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F20);
  - deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery);
  - F00–F18 не сломаны.
- **Импорт-чек F20**: `from harvest.discovery import niche, compute_viral_scores` → **discovery ok**.
- **Безопасность / ограничения**:
  - обычные тесты без сети (fake `WBPublic`);
  - F19/F21/F22/GUI не начаты;
  - push не выполнялся.
- **Коммит**: `F20: add viral detector`.
- **Следующий шаг**: F21 — Reviews collector (массовый сбор по топ-товарам).

### SESSION-CLOSE-F18 — сессия закрыта после F18 (2026-06-17)

- **F18 done**: коммит `1442cd4` — "F18: add video downloader".
- **Статус**: F00–F18 done; active_feature=F20 (НЕ начат, ждём «ОК F20»).
- **F19 заблокирован**: зависит от F08 (done), F18 (done), F22 (todo — VoC analyzer).
- **Тесты**: `pytest -m "not live" -q` → **477 passed, 1 skipped, 12 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F18).
- deselected: 12 live-тестов (Alibaba/1688/Taobao/WB).
- **Импорт-чек F18**: `from harvest.download import download_video, download_videos` → **download ok**.
- **VCS**: последние коммиты `1442cd4` (F18: add video downloader), `0831125` (F17: add WB review video harvester). Working tree чист, кроме untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md` — они не добавляются в git.
- **Security / ограничения (PASS)**:
  - F20/F19/GUI не начинались;
  - реальные видео не скачивались в обычных тестах;
  - чужие видеоотзывы только как референс/материал, не перезаливаются 1:1 без прав;
  - WB live может давать 403 — стоп-правило AGENTS.md, защиту не обходить;
  - `.env`, `sessions/`, `output/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.db` не tracked.
- **Push не выполнялся**.
- **Следующий шаг**: F20 — Viral detector (velocity + viral_score). Ждёт «ОК F20».

### F18 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/download.py`:
    - `VideoDownloadError` base exception;
    - `VideoHTTPError`, `VideoContentTypeError`, `VideoTooSmallError`, `VideoTimeoutError`, `VideoNetworkError` — специфические ошибки;
    - `safe_video_filename(source, index, ext)` — `china_1.mp4`, `wb_review_2.mp4` и т.д.;
    - `video_output_dir(nmId, base_output)` — `output/video/<nmId>/`, создаёт при необходимости;
    - `download_video(url, nmId, source, ...)` — httpx stream с retry (tenacity) на timeout/network/transport, `.part` → rename, cleanup при ошибках, проверка content-type и min_bytes, возвращает `VideoAsset`;
    - `download_videos(items, nmId, source, ...)` — batch, пропускает ошибки, инкрементный index.
  - `tests/test_download.py` — 21 не-live тест:
    - `safe_video_filename` (стандартные имена, нормализация index/ext, санитайз source);
    - `video_output_dir` (создание, повторный вызов);
    - `download_video`: успешное скачивание через fake httpx stream; путь `output/video/<nmId>/<source>_<i>.mp4`; возвращается `VideoAsset`; source `china` и `wb_review`; `application/octet-stream` допускается; плохой status → `VideoHTTPError`; слишком маленький файл → `VideoTooSmallError` + нет `.part`; неверный content-type → `VideoContentTypeError`; пустой URL → `VideoDownloadError`; video-расширение bypass'ит content-type; инжектированный клиент не закрывается.
    - `download_videos`: batch возвращает список assets; ошибка одного не останавливает batch.
    - public API import check.
- **Тесты**:
  - `pytest -m "not live" -q` → **477 passed, 1 skipped, 12 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F18);
  - deselected: 12 live-тестов (Alibaba/1688/Taobao/WB);
  - F00–F17 не сломаны.
- **Импорт-чек**: `from harvest.download import download_video, download_videos` → **download ok**.
- **Безопасность / ограничения**:
  - обычные тесты не скачивают реальные видео (fake httpx client/stream);
  - чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
  - F19/F20/GUI не начаты;
  - push не выполнялся.
- **Коммит**: `1442cd4` — "F18: add video downloader".
- **Следующий шаг**: F20 — Viral detector (velocity + viral_score).

### F17 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/download.py`:
    - `VideoDownloadError` base exception;
    - `VideoHTTPError`, `VideoContentTypeError`, `VideoTooSmallError`, `VideoTimeoutError`, `VideoNetworkError` — специфические ошибки;
    - `safe_video_filename(source, index, ext)` — `china_1.mp4`, `wb_review_2.mp4` и т.д.;
    - `video_output_dir(nmId, base_output)` — `output/video/<nmId>/`, создаёт при необходимости;
    - `download_video(url, nmId, source, ...)` — httpx stream с retry (tenacity) на timeout/network/transport, `.part` → rename, cleanup при ошибках, проверка content-type и min_bytes, возвращает `VideoAsset`;
    - `download_videos(items, nmId, source, ...)` — batch, пропускает ошибки, инкрементный index.
  - `tests/test_download.py` — 21 не-live тест:
    - `safe_video_filename` (стандартные имена, нормализация index/ext, санитайз source);
    - `video_output_dir` (создание, повторный вызов);
    - `download_video`: успешное скачивание через fake httpx stream; путь `output/video/<nmId>/<source>_<i>.mp4`; возвращается `VideoAsset`; source `china` и `wb_review`; `application/octet-stream` допускается; плохой status → `VideoHTTPError`; слишком маленький файл → `VideoTooSmallError` + нет `.part`; неверный content-type → `VideoContentTypeError`; пустой URL → `VideoDownloadError`; video-расширение bypass'ит content-type; инжектированный клиент не закрывается.
    - `download_videos`: batch возвращает список assets; ошибка одного не останавливает batch.
    - public API import check.
- **Тесты**:
  - `pytest -m "not live" -q` → **477 passed, 1 skipped, 12 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F18);
  - deselected: 12 live-тестов (Alibaba/1688/Taobao/WB);
  - F00–F17 не сломаны.
- **Импорт-чек**: `from harvest.download import download_video, download_videos` → **download ok**.
- **Безопасность / ограничения**:
  - обычные тесты не скачивают реальные видео (fake httpx client/stream);
  - чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
  - F19/F20/GUI не начаты;
  - push не выполнялся.
- **Коммит**: `F18: add video downloader`.
- **Следующий шаг**: F20 — Viral detector (velocity + viral_score).

### F17 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/review_video.py`:
    - `ReviewVideoItem` — dataclass-style модель с `review_id`, `nmId`, `rating`, `text`, `video_url`, `pros`, `cons`, `to_dict()`;
    - `extract_review_videos_from_reviews(reviews)` — фильтр отзывов с `video_url`, сортировка по полезности (текст/pros/cons + высокий рейтинг), битые отзывы логируются и пропускаются;
    - `get_review_videos(nmId, wb_client=None, max_count=1000, detail_provider=None)`:
      - resolve `nmId` → `imtId` (через `WBPublic.get_detail` или инжектированный `detail_provider`);
      - вызывает `WBPublic.get_reviews(imtId, max_count)`;
      - возвращает отсортированный список `ReviewVideoItem`;
      - созданный по умолчанию `WBPublic` закрывается, инжектированный — нет.
  - `tests/test_review_video.py` — 15 не-live тестов + 1 live-gated:
    - `ReviewVideoItem` fields/defaults/to_dict;
    - фильтрация только видео-отзывов;
    - пустой список → [];
    - сортировка: текст + высокий rating выше;
    - pros/cons считаются как текст;
    - битый отзыв пропускается, не падает;
    - `get_review_videos` с fake `WBPublic`:
      - detail → reviews pipeline;
      - `detail_provider` bypass;
      - пустой результат при отсутствии `imtId`;
      - пустой результат при отсутствии видео-отзывов;
      - сортировка;
      - `max_count` передаётся в `get_reviews`;
      - инжектированный клиент не закрывается.
    - public API import check;
    - live smoke под `@pytest.mark.live` + `WB_TEST_NMID` env.
- **Тесты**:
  - `pytest -m "not live" -q` → **456 passed, 1 skipped, 12 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F17);
  - deselected: 11 live-тестов (Alibaba/1688/Taobao + WB) + 1 новый live F17 = 12;
  - F00–F16 не сломаны.
- **Импорт-чек**: `from harvest.review_video import get_review_videos, extract_review_videos_from_reviews` → **review video ok**.
- **Безопасность / ограничения**:
  - видео не скачивается (это F18);
  - чужие видеоотзывы используются как референс/материал, не перезаливаются 1:1 без прав (напоминание AGENTS.md);
  - обычные тесты без сети;
  - live-тест под env-гейтом `WB_TEST_NMID`;
  - F18/F19/F20/GUI не начаты.
- **Коммит**: `F17: add WB review video harvester`.
- **Следующий шаг**: F18 — Video downloader + организация по nmId.

### F16 — done + committed (2026-06-17)

- **Файлы**:
  - `harvest/review_video.py`:
    - `ReviewVideoItem` — dataclass-style модель с `review_id`, `nmId`, `rating`, `text`, `video_url`, `pros`, `cons`, `to_dict()`;
    - `extract_review_videos_from_reviews(reviews)` — фильтр отзывов с `video_url`, сортировка по полезности (текст/pros/cons + высокий рейтинг), битые отзывы логируются и пропускаются;
    - `get_review_videos(nmId, wb_client=None, max_count=1000, detail_provider=None)`:
      - resolve `nmId` → `imtId` (через `WBPublic.get_detail` или инжектированный `detail_provider`);
      - вызывает `WBPublic.get_reviews(imtId, max_count)`;
      - возвращает отсортированный список `ReviewVideoItem`;
      - созданный по умолчанию `WBPublic` закрывается, инжектированный — нет.
  - `tests/test_review_video.py` — 15 не-live тестов + 1 live-gated:
    - `ReviewVideoItem` fields/defaults/to_dict;
    - фильтрация только видео-отзывов;
    - пустой список → [];
    - сортировка: текст + высокий rating выше;
    - pros/cons считаются как текст;
    - битый отзыв пропускается, не падает;
    - `get_review_videos` с fake `WBPublic`:
      - detail → reviews pipeline;
      - `detail_provider` bypass;
      - пустой результат при отсутствии `imtId`;
      - пустой результат при отсутствии видео-отзывов;
      - сортировка;
      - `max_count` передаётся в `get_reviews`;
      - инжектированный клиент не закрывается.
    - public API import check;
    - live smoke под `@pytest.mark.live` + `WB_TEST_NMID` env.
- **Тесты**:
  - `pytest -m "not live" -q` → **456 passed, 1 skipped, 12 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F17);
  - deselected: 11 live-тестов (Alibaba/1688/Taobao + WB) + 1 новый live F17 = 12;
  - F00–F16 не сломаны.
- **Импорт-чек**: `from harvest.review_video import get_review_videos, extract_review_videos_from_reviews` → **review video ok**.
- **Безопасность / ограничения**:
  - видео не скачивается (это F18);
  - чужие видеоотзывы используются как референс/материал, не перезаливаются 1:1 без прав (напоминание AGENTS.md);
  - обычные тесты без сети;
  - live-тест под env-гейтом `WB_TEST_NMID`;
  - F18/F19/F20/GUI не начаты.
- **Коммит**: `F17: add WB review video harvester`.
- **Следующий шаг**: F18 — Video downloader + организация по nmId.

### F16 — done + committed (2026-06-17)

- **Саб-агенты**: эстафета 1→2→3→4→5 (PLAN → BUILD HTML parsers → BUILD Playwright extractor → TESTS → REVIEW/DOCS/FINALIZE).
- **Файлы**:
  - `matcher/video_china.py` — извлечение 主图视频 из китайских карточек:
    - иерархия ошибок `VideoExtractError` → `VideoNotFoundError`;
    - `normalize_video_url` — absolute/protocol-relative/relative + base, фильтр `javascript:/data:/blob:`, раскодирование `\u002F`;
    - `looks_like_video_url` — `.mp4/.m3u8/.mov/.webm`, маркеры `cloud.video.taobao`, `video.taobao`, `vod`, `alicdn`, `cloud.video`;
    - `extract_video_urls_from_html` — `<video>/<source>` `src`/`data-src`, JSON/escaped URL в `<script>`, дедуп;
    - `pick_best_video_url` — `.mp4` > `.mov/.webm` > `.m3u8`;
    - `extract_video_url_from_html` — композиция;
    - `ChinaVideoExtractor`:
      - lazy `BrowserManager` (DI или создание при необходимости);
      - `extract_from_candidate` — открывает `candidate.url`, ждёт, detect_captcha → skip без обхода, HTML + network fallback, возвращает `model_copy(update={"has_video": ..., "video_url": ...})`;
      - `extract_for_candidates`/`extract_china_videos` — batch top-N, ошибка одного не валит batch;
      - `close`/`__enter__`/`__exit__` — закрывает только owned browser.
  - `tests/test_video_china.py` — 62 не-live теста:
    - ошибки;
    - `normalize_video_url` (absolute, http→https, protocol-relative, relative + base, javascript/data/blob, escaped URL);
    - `looks_like_video_url` (mp4/m3u8/mov/webm/CDN True; jpg/png/gif/webp/pdf False);
    - HTML extraction (video tag, source tag, script JSON, escaped URL, no video, m3u8, dedup);
    - `pick_best_video_url`;
    - `ChinaVideoExtractor` на fake `BrowserManager`/`Page`:
      - no URL/empty URL → no video;
      - video tag/script JSON/m3u8 → has_video=True + video_url;
      - captcha detected → no video, no bypass;
      - network URL fallback;
      - broken browser → no video, не падает;
      - top_n default/override;
      - batch: one error does not stop batch;
      - original Candidate не мутируется;
      - close/context manager;
    - public alias `extract_china_videos`.
  - `fixtures/china_video_video_tag.html`, `china_video_script_json.html`, `china_video_no_video.html`, `china_video_m3u8.html`.
- **Тесты**:
  - `pytest -m "not live" -q` → **441 passed, 1 skipped, 11 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F16);
  - deselected: 11 live-тестов Alibaba/1688/Taobao + ранее существовавшие live;
  - F00–F15 не сломаны.
- **Импорт-чеки**:
  - `from matcher.video_china import ChinaVideoExtractor, extract_china_videos, extract_video_url_from_html` → **video china ok**;
  - `from matcher.rank import ChinaCandidateRanker` → **f15 still ok**.
- **Безопасность / ограничения**:
  - капча только detect/skip, без обхода;
  - stealth не используется;
  - видео не скачивается (это F18);
  - обычные тесты без сети и без реального браузера;
  - F17/F18/GUI не начаты;
  - China drivers F12/F13/F14 не тронуты.
- **Коммит**: `F16: add China video extractor`.
- **Следующий шаг**: F17 — WB review-video harvester (видео из отзывов).

### F15 — done + committed (2026-06-17)

- **SA3 финализирован** после recovery-checkpoint `6f2b4f0`.
- **Файлы**:
  - `matcher/rank.py` — финальная версия:
    - иерархия ошибок `RankError` → `ImageLoadError`, `ClipUnavailableError`;
    - `load_image_rgb`, `perceptual_hash`, `phash_similarity`, `image_phash_similarity`, `normalize_score`, `combine_scores`;
    - `cosine_similarity` с поддержкой list/tuple/numpy/torch, защитой от NaN/inf/пустых векторов;
    - `ClipImageEmbedder` — ленивый CLIP-эмбеддер (open_clip/torch импортируются только внутри методов), `is_available()` с guarded import, DI для тестов через `_model`/`_preprocess`;
    - `ChinaCandidateRanker` — комбинирование CLIP + pHash, threshold/max_candidates из `settings.matcher`, сортировка по similarity desc, fallback на pHash при недоступном CLIP, обработка битых thumbnail (score=0.0), `Candidate.model_copy(update={"similarity": score})`;
    - `load_candidate_image` — загрузка thumb по URL (httpx) или локальному пути;
    - `rank_candidates` — convenience wrapper.
  - `tests/test_ranker_sa2.py` — 25 тестов базовых хелперов.
  - `tests/test_ranker_sa3.py` — 19 тестов высокоуровневого ранкера:
    - `cosine_similarity` (идентичные, ортогональные, противоположные, numpy/torch, пустые, NaN, zero-norm);
    - `ClipImageEmbedder.is_available()`, fake embedder без скачивания, lazy конструктор;
    - `load_candidate_image` локальный путь;
    - `ChinaCandidateRanker`: empty candidates, duplicate > irrelevant, threshold filtering, max_candidates, use_clip=False + phash, both modalities off → 0.0, broken candidate не падает, `model_copy` сохраняет поля, fake embedder ranking, `rank_candidates` helper, cache hit skips loader, `use_cache=False` recalculates.
- **Тесты**:
  - `pytest -m "not live" -q` → **379 passed, 1 skipped, 11 deselected**;
  - skipped: WebP/Pillow из F11 (platform-specific, не баг F15);
  - deselected: 11 live-тестов (Alibaba/1688/Taobao + ранее существовавшие live);
  - F00–F14 не сломаны.
- **Импорт-чеки**:
  - SA2 base: `from matcher.rank import RankError, ImageLoadError, ClipUnavailableError, load_image_rgb, image_phash_similarity, combine_scores` → **rank base ok**;
  - F15 ranker: `from matcher.rank import ClipImageEmbedder, ChinaCandidateRanker, rank_candidates` → **ranker f15 ok**.
- **Безопасность / ограничения**:
  - open_clip/torch не импортированы на уровне модуля;
  - обычные тесты не скачивают CLIP-модели (fake embedder);
  - обычные тесты не ходят в сеть;
  - `sessions/`, `output/`, `.venv/`, `.env`, `*.db`, `__pycache__/` не tracked.
- **Коммит**: `15b3a8b` — "F15: add CLIP and pHash ranker".
- **Следующий шаг**: F16 — China video extractor (主图视频 .mp4).

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
