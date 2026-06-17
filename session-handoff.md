# Session Handoff — WB Radar & China Matcher

## F28 — done: Сборка Windows .exe

**Последняя фича**: F28 — done.
**Active feature**: `null` — проект F00–F28 complete.

## Что сделано

- `run.py` обновлён: теперь вызывает `gui.app.main`, что позволяет PyInstaller собрать GUI-приложение.
- `scripts/build_windows.ps1` — PowerShell-скрипт сборки Windows `.exe` через PyInstaller:
  - проверка `.venv`;
  - установка `pyinstaller`;
  - запуск `pytest -m "not live"` перед сборкой (или `-SkipTests`);
  - onedir по умолчанию, `-OneFile` опционально;
  - `hiddenimports` для всех проектных модулей;
  - `config.yaml` и `fixtures/` включаются в сборку;
  - `.env`, `sessions/`, `output/`, `.venv/`, `build/`, `dist/` исключаются;
  - выводит путь, размер и SHA256 итогового `.exe`.
- `WB_Radar_China_Matcher.spec` — PyInstaller spec для повторяемой сборки.
- `tests/test_build_packaging.py` — 11 не-live тестов на наличие и корректность build-артефактов.
- `.gitignore` обновлён: добавлены `build/` и `dist/`.
- `README.md` обновлён: секция "Сборка Windows .exe".
- **Локальная сборка выполнена**:
  - `dist\WB_Radar_China_Matcher\WB_Radar_China_Matcher.exe`;
  - размер: 57.6 MB;
  - SHA256: `EBE3B4D3613E223E773C09C453810136ED254E0A10EB19E1DF416093CF7ED7AC`.

## Проект завершён

F00–F28 все со статусом `done` (F09 deferred).

## Результаты проверки

- `pytest -m "not live" -q` → **620 passed, 1 skipped, 15 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific).
- deselected: 15 live-тестов.
- Импорт-чек: `from gui.app import create_app` → **final gui import ok**.
- F00–F27 не сломаны.

## VCS

- Последний коммит F28: `F28: add Windows executable build`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.
- `build/`, `dist/`, `.env`, `sessions/`, `output/`, `.venv/`, `*.db`, `__pycache__/` не tracked.

## Known issues / constraints

- **Реальные LLM-запросы** требуют ключей в `.env` — никогда не коммитить ключи.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.

---

## Desktop UI checkpoint

**Дата/время:** Thu Jun 18 2026.

### Текущий статус

- Проект F00–F28 завершён (F09 deferred).
- Release опубликован и запушен.
- Full E2E QA: PASS.
- Desktop `.exe` собирается и запускается.
- Flet `icons.json` packaging пофиксен (collect_data_files("flet")).
- FilePicker пофиксен — регистрируется через `page.services` (не `page.overlay`).
- `ft.Tabs` заменены на кастомный desktop shell (`ShellController`: sidebar + swappable content).
- UI polish done: night/day themes, themed sidebar, radial glow, theme switch (☀/☾).

### Post-release desktop-фиксы (commits)

- `3e7a05b` — fix: include Flet data files in Windows build
- `dccd53a` — fix: register Flet FilePicker in page.services (not overlay)
- `8cdb6f3` — fix: make desktop GUI navigation interactive
- `21ddef5` — style: polish desktop UI themes  ← HEAD

### Последний артефакт

- exe: `dist\WB_Radar_China_Matcher\WB_Radar_China_Matcher.exe`
- SHA256: `848E18D0C020A355D45CB8F27528B4D9B0679E15F31BAB7F30827FAE0074C121`
- pytest: **660 passed, 1 skipped, 15 deselected**.
- Ветка `master` синхронизирована с `origin/master`.

### Что пользователь уже видел

- Приложение открывается, есть красивый night UI.
- Слева кликабельное меню (Матчер China / Разведка WB / Настройки).
- Ночная тема выглядит лучше прежнего; day-тема добавлена.
- В «Настройки» видны поля provider/model/proxy/output/sessions/keys.

### Куда вставлять ключи (ответ на вопрос пользователя)

- Локально в `D:\AI\Shodstva\.env.local` (git-ignored):
  - `ZAI_API_KEY=...`
  - `OPENROUTER_API_KEY=...`
  - `GROQ_API_KEY=...`
  - `OLLAMA_BASE_URL=http://localhost:11434`
- Либо через вкладку «Настройки» (она сама пишет в `.env.local`).
- `.env.local` **никогда не коммитить**.

### Что проверить завтра

- Переключатель Night/Day.
- Клик по Матчер / Разведка / Настройки.
- Кнопка «Фото» (FilePicker через `page.services`).
- Пустой ввод в Матчере (подсказка, без падения).
- Реальный ключ ZAI/OpenRouter + запуск боевого поиска.
- Подготовка простого способа установки: GitHub Release / portable zip / installer (не сегодня).
