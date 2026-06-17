# Session Handoff — WB Radar & China Matcher

## F20 — done: Viral detector (velocity + viral_score)

**Последняя фича**: F20 — done.
**Active feature**: F21 — Reviews collector (массовый сбор по топ-товарам) (status: todo, не начат).

## Что сделано

- `harvest/discovery.py`:
  - `ViralProduct` / `ViralResult` pydantic-модели;
  - `parse_review_date()` — парсит ISO/`YYYY-MM-DD`, отбрасывает будущие;
  - `count_reviews_since()` — отзывы не старше N дней;
  - `compute_velocity()` — `(velocity_7d, velocity_30d)`;
  - `normalize_values()` — детерминированная min-max нормализация;
  - `rating_closeness(rating, target=4.6)` — 1.0 на target, 0.0 на расстоянии ≥1.4;
  - `compute_viral_scores()` — `0.5*norm(velocity_7d) + 0.3*norm(feedbacks) + 0.2*close(rating,4.6)`, сортировка desc;
  - `niche(query, pages, top_n, wb_client, output_root)` — поиск WB → top_n по feedbacks → отзывы по imtId → скоринг → CSV в `output/viral/<query>_<date>.csv`.
- `tests/test_discovery.py` — 28 не-live тестов + 1 live-gated smoke.

## Что НЕ доделано / known issues

- **Reviews collector (F21)** не реализован — следующий шаг;
- **Description writer (F19)** ждёт F22 (VoC analyzer);
- **GUI** — позже, после F24/F25/F26;
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- WB live может давать 403 — стоп-правило AGENTS.md, защиту не обходить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **505 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F20).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F20: `from harvest.discovery import niche, compute_viral_scores` → **discovery ok**.

## VCS

- Последний коммит F20: `F20: add viral detector`.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F21 — Reviews collector (массовый сбор по топ-товарам). Ждёт подтверждения «ОК F21».

## Known issues / constraints

- **F19 не брать до F22**: Description writer зависит от VoC analyzer (F22), который пока не сделан.
- **F21 не начат**.
- **F22/F23/GUI не начаты**.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.

## Результаты проверки

- `pytest -m "not live" -q` → **505 passed, 1 skipped, 13 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F20).
- deselected: 13 live-тестов (Alibaba/1688/Taobao/WB + discovery).
- Импорт-чек F20: `from harvest.discovery import niche, compute_viral_scores` → **discovery ok**.
