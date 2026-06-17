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

- Последний коммит F17: `0831125` — F17: add WB review video harvester.
- Новый коммит F18: будет `F18: add video downloader`.
- Untracked: `handoff_f15_sa1.md`, `handoff_f15_sa2.md` — не в git.
- Push не выполнялся.

## Следующий шаг

F20 — Viral detector (velocity + viral_score). Ждёт подтверждения «ОК F20».

## Команда проверки

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live" -q
```
