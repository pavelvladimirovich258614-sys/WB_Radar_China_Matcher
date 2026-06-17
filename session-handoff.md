# Session Handoff — WB Radar & China Matcher

## F25 — done: GUI вкладка Разведка WB + мост в Матчер

**Последняя фича**: F25 — done.
**Active feature**: F26 — GUI настройки: провайдеры LLM/прокси/логины (status: todo, не начат).

## Что сделано

- `gui/app.py` (расширен):
  - `DiscoveryWBController` — контроллер вкладки "Разведка WB" с DI (`discovery_service`, `voc_service`, `hooks_service`, `review_video_service`, `downloader`, `to_matcher_bridge`);
  - `build_discovery_tab(...)` — возвращает `(Tab, DiscoveryWBController)`;
  - `build_matcher_tab(...)` — возвращает `(Tab, MatcherChinaController)`;
  - `MatcherChinaController` получил `set_input_value()` и `focus_input()` для моста "В Матчер";
  - `create_app(...)` — две вкладки: "Матчер China" (первая, `selected_index=0`) и "Разведка WB";
  - Внутренний `bridge_to_matcher(nm_id)` заполняет поле ввода первой вкладки;
  - UI "Разведка WB": поле ниши, кнопка "Найти вирусные", таблица товаров с viral_score/feedbacks/rating, панель деталей с VoC (боли/желания/страхи), хуками, возражениями, видео из отзывов, кнопка "В Матчер";
  - Default services — thin wrappers над `harvest.discovery.niche`, `harvest.reviews`, `harvest.voc.analyze_reviews_voc`, `harvest.hooks.generate_hooks`, `harvest.review_video.get_review_videos`; не используются в обычных тестах;
  - Безопасная обработка пустой ниши и ошибок сервисов — UI не падает.
- `tests/test_gui_discovery.py` — 9 не-live тестов:
  - создание вкладки и контролов;
  - две вкладки, первая — "Матчер China";
  - fake discovery, отображение viral_score;
  - пустая ниша, ошибка discovery;
  - выбор товара → VoC/хуки/видео (fake services);
  - "В Матчер" через bridge заполняет поле первой вкладки;
  - public API import check.
- `tests/test_gui_matcher.py` — обновлён под новый API `build_matcher_tab`/`create_app`.

## Что НЕ доделано / known issues

- **F26 — GUI настройки** — следующий шаг;
- **F27/F28** не начинались;
- live WB/China/LLM может давать 403/капчу — защиту не обходить (AGENTS.md);
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- API-ключи LLM только в `.env`, не коммитить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **589 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F25).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F25: `from gui.app import create_app, build_matcher_tab, build_discovery_tab` → **gui discovery ok**.
- F00–F24 не сломаны.

## VCS

- Последний коммит F25: `F25: add WB discovery GUI tab`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F26 — GUI настройки: провайдеры LLM/прокси/логины. Ждёт подтверждения «ОК F26».

## Known issues / constraints

- **F26/F27/F28 не начинались**.
- **Реальные LLM-запросы** требуют ключей в `.env` — никогда не коммитить ключи.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.
