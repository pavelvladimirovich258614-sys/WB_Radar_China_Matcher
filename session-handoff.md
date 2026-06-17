# Session Handoff — WB Radar & China Matcher

## F24 — done: GUI вкладка Матчер China

**Последняя фича**: F24 — done.
**Active feature**: F25 — GUI вкладка Разведка WB + мост в Матчер (status: todo, не начат).

## Что сделано

- `gui/app.py`:
  - `MatcherChinaController` — контроллер вкладки "Матчер China" с dependency injection (`matcher_pipeline`, `downloader`, `output_root`);
  - `build_matcher_tab(...)` и `create_app(...)` — публичный API для GUI;
  - Тёмная тема, вкладка "Матчер China" первая и единственная (`selected_index=0`);
  - Поле ввода WB артикула/ссылки, кнопка "Фото" через `FilePicker`, кнопка "Найти";
  - Прогресс/статус поиска;
  - Список кандидатов: thumb, площадка, название, similarity %, цена, кнопки "Открыть"/"Видео"/"Скачать";
  - Кнопка "Скачать все видео топ-5" — берёт топ-5 кандидатов с `video_url`;
  - `_default_matcher_pipeline` — thin wrapper над `matcher.input.resolve_input`, China drivers, `matcher.rank.rank_candidates`, `matcher.video_china.ChinaVideoExtractor`; не используется в обычных тестах;
  - Пустой ввод → статус, ошибка pipeline → статус, без падения UI;
  - Инжектированные pipeline/downloader позволяют тестировать без сети и браузера.
- `tests/test_gui_matcher.py` — 11 не-live тестов:
  - создание вкладки и всех контролов;
  - `create_app` → тёмная тема, первая вкладка "Матчер China";
  - fake pipeline вызывается и результаты рендерятся;
  - similarity как процент;
  - пустой ввод, ошибка pipeline;
  - скачивание одного и топ-5 видео через fake downloader;
  - public API import check.

## Что НЕ доделано / known issues

- **F25 — GUI вкладка Разведка WB + мост в Матчер** — следующий шаг;
- **F26/F27/F28** не начинались;
- live WB/China может давать 403/капчу — защиту не обходить (AGENTS.md);
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- API-ключи LLM только в `.env`, не коммитить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **580 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F24).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F24: `from gui.app import create_app, build_matcher_tab` → **gui matcher ok**.
- F00–F23 не сломаны.

## VCS

- Последний коммит F24: `F24: add China matcher GUI tab`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F25 — GUI вкладка Разведка WB + мост в Матчер. Ждёт подтверждения «ОК F25».

## Known issues / constraints

- **F25/F26/F27/F28 не начинались**.
- **Реальные LLM-запросы** требуют ключей в `.env` — никогда не коммитить ключи.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.
