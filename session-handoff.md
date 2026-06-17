# Session Handoff — WB Radar & China Matcher

## F18 — done: Video downloader + организация по nmId

**Последняя фича**: F18 — done.
**Active feature**: F20 — Viral detector (velocity + viral_score) (status: todo, не начат).

## Что сделано

- `harvest/download.py`:
  - `VideoDownloadError` + `VideoHTTPError`, `VideoContentTypeError`, `VideoTooSmallError`, `VideoTimeoutError`, `VideoNetworkError`;
  - `safe_video_filename(source, index)` → `<source>_<index>.mp4`;
  - `video_output_dir(nmId)` → `output/video/<nmId>/`;
  - `download_video(url, nmId, source, ...)` — httpx stream, retry, `.part` → rename, content-type/size проверка, возвращает `VideoAsset`;
  - `download_videos(items, nmId, source, ...)` — batch, индексация 1..N.
- `tests/test_download.py` — 21 не-live тест: успешное скачивание, пути, assets, источники, ошибки статуса/размера/типа, batch, cleanup `.part`.

## Что НЕ доделано / known issues

- **Viral detector (F20)** не реализован;
- **Description writer (F19)** ждёт F22 (VoC analyzer);
- **GUI** — позже, после F24/F25/F26;
- Чужие видеоотзывы сохраняются как референс/материал, не перезаливаются 1:1 без прав;
- WB live может давать 403 — стоп-правило AGENTS.md, защиту не обходить;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **477 passed, 1 skipped, 12 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F18).
- deselected: 12 live-тестов (Alibaba/1688/Taobao/WB).
- Импорт-чек F18: `from harvest.download import download_video, download_videos` → **download ok**.

## VCS

- Последний коммит F18: `1442cd4` — F18: add video downloader.
- Working tree чист, кроме разрешённых untracked `handoff_f15_sa1.md`, `handoff_f15_sa2.md`.
- Push не выполнялся.

## Следующий шаг

F20 — Viral detector (velocity + viral_score). Ждёт подтверждения «ОК F20».

## Known issues / constraints

- **F19 не брать до F22**: Description writer зависит от VoC analyzer (F22), который пока не сделан.
- **WB live** может давать 403 из текущего окружения — стоп-правило AGENTS.md, защиту не обходить.
- **Чужие видеоотзывы** сохраняются только как референс/материал, не перезаливаются 1:1 без прав.
- `handoff_f15_sa1.md` / `handoff_f15_sa2.md` остаются untracked и не нужны для коммита.
- `.env` / `sessions/` / `output/` / `.venv/` / `*.db` / `__pycache__/` не tracked.

## Результаты проверки

- `pytest -m "not live" -q` → **477 passed, 1 skipped, 12 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F18).
- deselected: 12 live-тестов (Alibaba/1688/Taobao/WB).
- Импорт-чек F18: `from harvest.download import download_video, download_videos` → **download ok**.
