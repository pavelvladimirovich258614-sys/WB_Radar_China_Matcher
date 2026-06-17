# Session Handoff — WB Radar & China Matcher

## F26 — done: GUI настройки

**Последняя фича**: F26 — done.
**Active feature**: F27 — End-to-end + интеграционные тесты (status: todo, не начат).

## Что сделано

- `gui/settings.py` (новый):
  - `LLM_PROVIDERS` = openrouter/zai/groq/ollama/chatgpt_web;
  - `PROVIDER_SECRET_KEY` — имя env-переменной для каждого провайдера;
  - `SettingsSnapshot` — read-only snapshot настроек для GUI;
  - `mask_secret(value)` — маскирует секрет (показывает первые 2 и последние 4 символа);
  - `SettingsController` с DI: `save_settings`, `open_folder`, `session_status`, `on_status`;
  - `load_settings()` — читает `core.config.settings` и статусы сессий 1688/Taobao/ChatGPT;
  - `validate_settings()` — проверяет провайдер, proxy (urlparse), output/sessions paths;
  - `save_settings_to_disk()` — валидирует и вызывает injectable storage;
  - UI-секции: LLM provider + model, proxy, output/sessions paths, "Ключи / сессии" (masked password-поля), "Статус сессий", кнопки "Проверить настройки", "Сохранить", "Открыть output", "Открыть sessions", статус.
  - `_default_save_settings` пишет в `.env.local` (untracked) и обновляет in-process `settings.llm.provider/model`, `settings.proxy`;
  - `_default_open_folder` создаёт папку и открывает через explorer/open/xdg-open (fallback webbrowser);
  - `_default_session_status` проверяет непустую папку в `sessions/<site>`.
- `gui/app.py` (расширен):
  - re-export `SettingsController`, `build_settings_tab`;
  - `create_app(...)` теперь создаёт 3 вкладки в порядке: Матчер China, Разведка WB, Настройки;
  - первая вкладка остаётся Матчер China (`selected_index=0`);
  - параметр `settings_controller` для DI.
- `tests/test_gui_settings.py` — 13 не-live тестов:
  - build_settings_tab, 3 вкладки, load_settings, mask_secret, validate bad proxy, save fake storage, save failure, session statuses, validate button, open output, open sessions failure, masked API key display, public API import.
- `tests/test_gui_matcher.py` и `tests/test_gui_discovery.py` обновлены: `create_app` теперь 3 вкладки.

## Что НЕ доделано / known issues

- **F27 — End-to-end + интеграционные тесты** — следующий шаг;
- **F28 — сборка .exe** не начиналась;
- live WB/China/LLM может давать 403/капчу — защиту не обходить (AGENTS.md);
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- API-ключи LLM только в `.env` / `.env.local`, не коммитить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **603 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F26).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F26: `from gui.app import create_app, build_matcher_tab, build_discovery_tab, build_settings_tab` → **gui settings ok**.
- F00–F25 не сломаны.

## VCS

- Последний коммит F26: `F26: add GUI settings tab`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F27 — End-to-end + интеграционные тесты. Ждёт подтверждения «ОК F27».

## Known issues / constraints

- **F27/F28 не начинались**.
- **Реальные LLM-запросы** требуют ключей в `.env` — никогда не коммитить ключи.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `.env.local` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.
