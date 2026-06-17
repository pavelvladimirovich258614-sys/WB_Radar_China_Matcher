# Session Handoff — WB Radar & China Matcher

## F16 — done: China video extractor (主图视频 .mp4)

**Последняя фича**: F16 — done.
**Active feature**: F17 — WB review-video harvester (видео из отзывов) (status: todo, не начат).

## Что сделано

- `matcher/video_china.py` — финальная версия:
  - `VideoExtractError` → `VideoNotFoundError`;
  - `normalize_video_url` — absolute/protocol-relative/relative + base, фильтр `javascript:/data:/blob:`, раскодирование `\u002F`;
  - `looks_like_video_url` — `.mp4/.m3u8/.mov/.webm`, маркеры `cloud.video.taobao`, `video.taobao`, `vod`, `alicdn`, `cloud.video`;
  - `extract_video_urls_from_html` — `<video>/<source>` `src`/`data-src`, JSON/escaped URL в `<script>`, дедуп;
  - `pick_best_video_url` — `.mp4` > `.mov/.webm` > `.m3u8`;
  - `extract_video_url_from_html`;
  - `ChinaVideoExtractor`:
    - lazy `BrowserManager`;
    - `extract_from_candidate` — открывает карточку, detect_captcha → skip без обхода, HTML + network fallback;
    - `extract_for_candidates`/`extract_china_videos` — batch top-N;
    - ошибка одного кандидата не валит batch;
    - возвращает `Candidate.model_copy(update={...})`, не мутирует оригинал;
    - `close`/`__enter__`/`__exit__`.
- `tests/test_video_china.py` — 62 не-live теста.
- `fixtures/china_video_video_tag.html`, `china_video_script_json.html`, `china_video_no_video.html`, `china_video_m3u8.html`.

## Что НЕ доделано / known issues

- **Live extraction с реальных площадок** требует ручных сессий/логина и может упереться в капчу — обход не реализован;
- **Video downloader не реализован** — это F18;
- **F16 только возвращает `video_url`/`has_video`**, не скачивает файлы;
- **F17 не начинался**;
- **F18 downloader не начинался**;
- GUI не тронут;
- China drivers F12/F13/F14 не изменялись;
- Push не выполнялся.

## Результаты проверки

- `pytest -m "not live" -q` → **441 passed, 1 skipped, 11 deselected**.
- skipped: WebP/Pillow из F11 (platform-specific, не баг F16).
- deselected: 11 live-тестов (Alibaba/1688/Taobao + ранее существовавшие live).
- Импорт-чек F16: `from matcher.video_china import ChinaVideoExtractor, extract_china_videos, extract_video_url_from_html` → **video china ok**.
- Импорт-чек F15: `from matcher.rank import ChinaCandidateRanker` → **f15 still ok**.

## VCS

- Последний коммит F15: `d3d32e4` — F15: add CLIP and pHash ranker.
- Новый коммит F16: будет `F16: add China video extractor`.
- Untracked: `handoff_f15_sa1.md`, `handoff_f15_sa2.md` — не в git.
- Push не выполнялся.

## Следующий шаг

F17 — WB review-video harvester (видео из отзывов). Фича не начата. Ждёт подтверждения «ОК F17».

## Команда проверки

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live" -q
```
