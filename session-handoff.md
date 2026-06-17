# Session Handoff — WB Radar & China Matcher

## F15 — done: CLIP + pHash ранкер (1:1)

**Последняя фича**: F15 — done.
**Active feature**: F16 — China video extractor (主图视频 .mp4) (status: todo, не начат).

## Что сделано

- `matcher/rank.py` — финализирован:
  - иерархия ошибок `RankError` → `ImageLoadError`, `ClipUnavailableError`;
  - `load_image_rgb` для `Path | str | bytes | PIL.Image.Image`;
  - `perceptual_hash`, `phash_similarity`, `image_phash_similarity`;
  - `normalize_score`, `combine_scores` с `clip_weight=0.7`, `phash_weight=0.3`;
  - `cosine_similarity` для list/tuple/numpy/torch, защита от NaN/inf/пустых векторов;
  - `ClipImageEmbedder` — ленивый CLIP-эмбеддер (open_clip/torch импортируются только внутри методов), `is_available()` с guarded import, DI для тестов;
  - `ChinaCandidateRanker` — комбинирование CLIP + pHash, threshold/max_candidates из `settings.matcher`, сортировка desc, fallback на pHash, обработка битых thumbnail, `Candidate.model_copy(update={"similarity": score})`;
  - `load_candidate_image`, `rank_candidates` convenience wrapper.
- `tests/test_ranker_sa2.py` — 25 тестов базовых хелперов.
- `tests/test_ranker_sa3.py` — 19 тестов высокоуровневого ранкера (cosine, ClipImageEmbedder, ChinaCandidateRanker, cache).

## Что НЕ доделано / known issues

- **Реальные CLIP-модели в обычных тестах не скачивались** — использовались fake embedder / fake loader;
- **Live/real CLIP smoke** можно сделать позже вручную отдельно;
- **WB live 403** из текущего окружения остаётся known issue (стоп-правило AGENTS.md, защиту не обходить);
- **F16 не начинался**;
- GUI не тронут;
- China drivers не изменялись;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **379 passed, 1 skipped, 11 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F15).
- deselected: 11 live-тестов (Alibaba/1688/Taobao + ранее существовавшие live).
- Импорт-чек SA2: `from matcher.rank import RankError, ImageLoadError, ClipUnavailableError, load_image_rgb, image_phash_similarity, combine_scores` → **rank base ok**.
- Импорт-чек F15: `from matcher.rank import ClipImageEmbedder, ChinaCandidateRanker, rank_candidates` → **ranker f15 ok**.

## VCS

- Последний checkpoint: `6f2b4f0` — F15: checkpoint pHash ranker recovery.
- Новый финальный коммит: `15b3a8b` — **F15: add CLIP and pHash ranker**.
- Последний коммит до F15: `42102ad` — F14: add Taobao image search driver.
- Untracked: `handoff_f15_sa1.md`, `handoff_f15_sa2.md` — не в git.
- Push не выполнялся.

## Следующий шаг

F16 — China video extractor (主图视频 .mp4). Фича не начата. Ждёт подтверждения «ОК F16».

## Команда проверки

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live" -q
```
