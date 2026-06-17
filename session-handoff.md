# Session Handoff — WB Radar & China Matcher

## RECOVERY-CLOSE-F15 — checkpoint

**Последний коммит до F15**: `42102ad` — F14: add Taobao image search driver.
**Текущий новый коммит**: будет создан в recovery — `F15: checkpoint pHash ranker recovery`.
**Статус F15**: in_progress / checkpoint (НЕ done).

## Что сделано

- Восстановлена сессия после обрыва по лимитам.
- Подтверждено, что SA1 и SA2 выполнены:
  - `matcher/rank.py` — иерархия ошибок `RankError` → `ImageLoadError`, `ClipUnavailableError`;
  - `load_image_rgb`, `perceptual_hash`, `phash_similarity`, `image_phash_similarity`, `normalize_score`, `combine_scores`;
  - дополнительно в `matcher/rank.py` уже присутствуют `ClipImageEmbedder`, `ChinaCandidateRanker`, `rank_candidates`, `load_candidate_image`, `cosine_similarity` (результат работы, сохранившейся после обрыва, но SA3 официально не завершён).
- `tests/test_ranker_sa2.py` — 25 тестов базовых хелперов.
- `tests/test_ranker_sa3.py` существует, но **SA3 официально не начинался** и в рамках recovery не дорабатывался.

## Результаты проверки

- `pytest -m "not live" -q` → **379 passed, 1 skipped, 11 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F15).
- deselected: 11 live-тестов (Alibaba/1688/Taobao + ранее существовавшие live).
- Импорт-чек SA2: `from matcher.rank import RankError, ImageLoadError, ClipUnavailableError, load_image_rgb, image_phash_similarity, combine_scores` → **rank base ok**.
- Импорт-чек F15-ранкера: `from matcher.rank import ClipImageEmbedder, ChinaCandidateRanker, rank_candidates` → **ranker f15 ok**.

## Что НЕ доделано / known issues

- **F15 не закрыта** — SA3 (ClipImageEmbedder + ChinaCandidateRanker + Storage cache + финальные тесты) официально не выполнен.
- `tests/test_ranker_sa3.py` существует, но не отражает завершённый SA3.
- **F16 не начинался**.
- GUI не тронут.
- China drivers (`matcher/china/alibaba.py`, `s1688.py`, `taobao.py`) не изменялись.
- **Push не выполнялся**.

## Временный мусор

Удалены: `test_esc.txt`, `test_esc2.txt`, `x.txt`.
Не в git: `handoff_f15_sa1.md`, `handoff_f15_sa2.md` (их содержание перенесено в этот handoff).

## Следующий шаг

F15 SA3 — завершить высокоуровневый ранкер:
1. Доработать/утвердить `ClipImageEmbedder` (lazy open_clip/torch, `is_available`, `embed_image`, `cosine_similarity`).
2. Доработать/утвердить `ChinaCandidateRanker` (downloader injection, CLIP+pHash, `top_k`/threshold, cache, `use_cache=False`).
3. Прогнать `tests/test_ranker_sa3.py` и при необходимости дополнить.
4. Полный `pytest -m "not live"` зелёный.
5. Обновить `feature_list.json`: F15 → done, active_feature → F16.
6. Сделать финальный коммит F15.

## Команда проверки

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live" -q
```

## VCS

- Последний коммит до F15: `42102ad`.
- Recovery-коммит: `F15: checkpoint pHash ranker recovery` (matcher/rank.py, tests/test_ranker_sa2.py, progress.md, session-handoff.md, feature_list.json).
- Push не выполнялся.
