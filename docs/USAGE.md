# Usage Guide

## Development setup

Clone the repository:

```bash
git clone https://github.com/pavelvladimirovich258614-sys/WB_Radar_China_Matcher.git
cd WB_Radar_China_Matcher
```

On Windows with Python 3.11:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
playwright install chromium
```

Copy `.env.example` to `.env` and fill in your keys:

```powershell
copy .env.example .env
```

Edit `.env`:

```env
OPENROUTER_API_KEY=sk-...
ZAI_API_KEY=...
GROQ_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
```

> Keys may also be placed in `.env.local` (project root) — it is git-ignored
> and is where the **Настройки** tab writes provider keys. Use the same
> variable names. Never commit `.env` or `.env.local`.

## Run the GUI

```powershell
.venv\Scripts\python.exe run.py
```

The app window opens with the **Матчер China** tab active.

## Матчер China tab

1. Enter a Wildberries article number or URL, or click **Фото** to select a
   local image.
2. Click **Найти**.
3. The app searches Alibaba, 1688, and Taobao by image, ranks results by
   visual similarity (CLIP + pHash), and extracts product videos where
   available.
4. Browse the results table. Each row shows thumbnail, site, title,
   similarity, and price.
5. Use the action buttons:
   - **Открыть** — open the China product page in the default browser.
   - **Видео** — log the video URL.
   - **Скачать** — download this candidate's video.
   - **Скачать все видео топ-5** — download videos for the top 5 candidates.

Downloaded videos are saved to `output/video/<nmId>/`.

## Разведка WB tab

1. Enter a niche or query, for example `фен для волос`.
2. Click **Найти вирусные**.
3. The app searches WB, collects reviews for top products, computes a viral
   score, and shows a sorted table.
4. Click **Выбрать** on a product to load details:
   - **Боли / Желания / Страхи** from VoC analysis.
   - **Хуки** — 5 hook variants and a video structure.
   - **Видео из отзывов** — list of review videos.
5. Click **Скачать** next to a review video to save it.
6. Click **В Матчер** to copy the product's `nmId` back to the first tab for
   China matching.

Outputs are saved under `output/`:

- `output/viral/<query>_<date>.csv`
- `output/reviews/<nmId>.json`
- `output/voc/<nmId>.json`
- `output/hooks/<nmId>.md`
- `output/video/<nmId>/`

## Настройки tab

- Select an LLM provider: `openrouter`, `zai`, `groq`, `ollama`, or
  `chatgpt_web`.
- Enter the provider key or base URL. Values are saved to `.env.local` and
  are not committed.
- Set proxy if needed.
- Configure output and sessions folders.
- View session status for 1688, Taobao, and ChatGPT.
- Click **Открыть output** or **Открыть sessions** to open those folders.

## Build the Windows executable

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The resulting `.exe` is written to:

```text
dist\WB_Radar_China_Matcher\WB_Radar_China_Matcher.exe
```

Secrets and runtime folders are not bundled. Place `.env` next to the `.exe`
for production use.

> The build bundles Flet data files (including
> `flet/controls/material/icons.json`) via `WB_Radar_China_Matcher.spec`
> (`collect_data_files("flet")`). If you rebuild by hand and the app crashes on
> startup with `FileNotFoundError: ...icons.json`, rebuild with the current
> spec — it is a packaging, not a code, issue.

## What to do on 403 / captcha

If a live source returns HTTP 403 or shows a captcha:

1. Check your internet connection and VPN/proxy settings.
2. For 1688/Taobao, use the browser session login via
   `core.browser.BrowserManager.manual_login()`.
3. Do not modify the code to bypass the challenge — this project does not use
   stealth or anti-captcha solutions.
4. Retry later or use a different marketplace in the config.

## Testing

Run the offline test suite:

```powershell
.venv\Scripts\python.exe -m pytest -m "not live" -q
```

Run live smoke tests only when configured:

```powershell
$env:WB_RADAR_RUN_LIVE = "1"
.venv\Scripts\python.exe -m pytest -m live -q
```

## Keeping your data safe

- Do not commit `.env` or `.env.local`.
- Do not commit `sessions/` or `output/`.
- Do not commit `build/`, `dist/`, or `*.exe`.
- Rotate API keys immediately if they are ever exposed.
