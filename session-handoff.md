# Session Handoff — WB Radar & China Matcher

## F27 — done: End-to-end + интеграционные тесты

**Последняя фича**: F27 — done.
**Active feature**: F28 — Сборка .exe (flet pack) + проверка на чистой машине (status: todo, не начат).

## Что сделано

- `tests/test_e2e.py` — 6 не-live E2E/интеграционных тестов + 2 live smoke-теста:
  - `test_e2e_matcher_happy_path`: fake `matcher_pipeline` + fake `downloader` → матчер доходит до скачивания top-кандидата;
  - `test_e2e_matcher_ranker_orders_candidates`: используется реальный `rank_candidates` на двух одинаковых сгенерированных изображениях (pHash-only, без CLIP);
  - `test_e2e_discovery_happy_path`: fake `ViralProduct` → VoC (fake LLM) → hooks (fake LLM) → видео из отзывов;
  - `test_e2e_discovery_gui_bridge_fills_matcher_input`: мост "В Матчер" заполняет input первой вкладки;
  - `test_e2e_create_app_three_tabs_with_fake_services`: `create_app` строит 3 вкладки с fake сервисами;
  - `test_e2e_fake_llm_not_real_llm`: убедиться, что fake LLM действительно используется;
  - live-тесты `test_live_wb_to_discovery_smoke` и `test_live_matcher_one_product_smoke` под `@pytest.mark.live` + `WB_RADAR_RUN_LIVE=1`.
- `README.md` (новый):
  - описание приложения и 3 вкладок;
  - установка через `init.sh`;
  - `.env.example` и запуск;
  - секции обычных и live-тестов;
  - безопасность и границы.

## Что НЕ доделано / known issues

- **F28 — Сборка .exe (flet pack) + проверка на чистой машине** — следующий шаг;
- live WB/China/LLM может давать 403/капчу — защиту не обходить (AGENTS.md);
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- API-ключи LLM только в `.env` / `.env.local`, не коммитить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **609 passed, 1 skipped, 15 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F27).
- deselected: 15 live-тестов (Alibaba/1688/Taobao/WB + discovery + 2 e2e live).
- Импорт-чек F27: `from gui.app import create_app; from harvest.discovery import niche; from harvest.hooks import generate_hooks` → **e2e imports ok**.
- F00–F26 не сломаны.

## VCS

- Последний коммит F27: `F27: add end-to-end integration tests`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F28 — Сборка .exe (flet pack) + проверка на чистой машине. Ждёт подтверждения «ОК F28».

## Known issues / constraints

- **F28 не начиналась**.
- **Реальные LLM-запросы** требуют ключей в `.env` — никогда не коммитить ключи.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `.env.local` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.
