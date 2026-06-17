# Session Handoff — WB Radar & China Matcher

## F22 — done: VoC analyzer (боли/желания/страхи JSON)

**Последняя фича**: F22 — done.
**Active feature**: F19 — Description writer (LLM: описание/подводка под видео) (status: todo, не начат).

## Что сделано

- `core/models.py`: `VocItem` расширен полями `quote` и `source_review_ids`.
- `harvest/voc.py`:
  - `load_reviews_for_voc()` — загрузка отзывов из файла/nmId/списка;
  - `chunk_reviews()` — батчи по 40;
  - `build_voc_prompt()` — prompt для LLM со схемой VoC;
  - `analyze_reviews_voc()` — анализ батчами через `complete_json`, merge + dedupe;
  - `merge_voc_results()` / `dedupe_voc_items()` — склейка и дедупликация;
  - `save_voc()` — сохранение в `output/voc/<nmId>.json`;
  - `analyze_voc_for_nmId()` — convenience pipeline load→analyze→save.
- `tests/test_voc.py` — 20 не-live тестов.

## Что НЕ доделано / known issues

- **Description writer (F19)** не реализован — следующий шаг (разблокирован после F22);
- **Hook generator (F23)** — после F19;
- **GUI** — позже, после F24/F25/F26;
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- Реальные LLM-запросы требуют ключей в `.env` (OpenRouter/Z.AI/Groq/Ollama), ключи не коммитить;
- WB live может давать 403 — стоп-правило AGENTS.md, защиту не обходить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **543 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F22).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F22: `from harvest.voc import analyze_reviews_voc, analyze_voc_for_nmId, merge_voc_results` → **voc ok**.

## VCS

- Последний коммит F22: `F22: add VoC analyzer`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F19 — Description writer (LLM: описание/подводка под видео). Ждёт подтверждения «ОК F19».

## Known issues / constraints

- **F19 разблокирован**: Description writer зависит от F08 (done), F18 (done), F22 (done).
- **F19 не начат**.
- **F23/GUI не начаты**.
- **Реальные LLM-запросы** требуют ключей в `.env` — никогда не коммитить ключи.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.

## Результаты проверки

- `pytest -m "not live" -q` → **543 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F22).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F22: `from harvest.voc import analyze_reviews_voc, analyze_voc_for_nmId, merge_voc_results` → **voc ok**.
