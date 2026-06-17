# Session Handoff — WB Radar & China Matcher

## F23 — done: Hook generator (.md хуки + структура ролика)

**Последняя фича**: F23 — done.
**Active feature**: F24 — GUI вкладка Матчер China (status: todo, не начат).

## Что сделано

- `harvest/hooks.py`:
  - `VideoHookSet` pydantic-модель: `hooks` (5 вариантов), `structure` (список `Scene`), `objections`;
  - `Scene` pydantic-модель: `scene`, `duration`, `content`;
  - `HookGeneratorError` / `HookResponseError`;
  - `build_hooks_prompt(voc, product=None)` — prompt на основе VoC и опционально товара;
  - `_HOOKS_JSON_SCHEMA` — JSON schema с required `hooks`/`structure`/`objections`;
  - `parse_hooks_response(raw)` — валидация + fallback на битый/неполный LLM-ответ (5 дефолтных хуков, структура по умолчанию, возражения по умолчанию);
  - `save_hooks(nm_id, hook_set, output_root)` — сохраняет `output/hooks/<nmId>.md`;
  - `generate_hooks(voc, nm_id=None, product=None, llm_provider=None, output_root=None)` — pipeline: prompt → LLM → parse → save (если nm_id задан) → return;
  - инжектированный LLM-провайдер не закрывается, дефолтный — закрывается.
- `tests/test_hooks.py` — 14 не-live тестов:
  - `build_hooks_prompt` содержит VoC + товар;
  - `generate_hooks` вызывает fake LLM и сохраняет `.md`;
  - валидный fake response → `VideoHookSet` с 5 хуками, структурой и возражениями;
  - сохраняется Markdown в `output/hooks/<nmId>/`;
  - `hooks` содержит ровно 5 вариантов;
  - структура рендерится таблицей;
  - неполный/битый ответ LLM → fallback без падения;
  - пустой VoC не валит генерацию;
  - без `nm_id` файл не сохраняется;
  - инжектированный провайдер не закрывается, дефолтный — закрывается.

## Что НЕ доделано / known issues

- **GUI** — следующий блок: F24/F25/F26;
- **End-to-end + .exe** — после GUI;
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- Реальные LLM-запросы требуют ключей в `.env` (OpenRouter/Z.AI/Groq/Ollama), ключи не коммитить;
- WB live может давать 403 — стоп-правило AGENTS.md, защиту не обходить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **569 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F23).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F23: `from harvest.hooks import generate_hooks, save_hooks, build_hooks_prompt` → **hooks ok**.
- F00–F22 не сломаны.

## VCS

- Последний коммит F23: `F23: add hook generator`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F24 — GUI вкладка Матчер China (Flet, поле артикула/фото, таблица кандидатов, скачивание видео). Ждёт подтверждения «ОК F24».

## Known issues / constraints

- **GUI не начинался**.
- **Реальные LLM-запросы** требуют ключей в `.env` — никогда не коммитить ключи.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.
