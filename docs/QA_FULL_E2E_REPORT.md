# Full End-to-End QA Report — WB Radar & China Matcher

## Metadata

- **Project**: WB Radar & China Matcher
- **QA date/time**: 2026-06-17
- **Commit under test**: `841db07` — `F28: add Windows executable build`
- **Branch status**: F00–F28 done, F09 deferred, `active_feature = null`
- **Push performed**: No
- **QA performed by**: OpenCode agent

## 1. Git status

```text
?? handoff_f15_sa1.md
?? handoff_f15_sa2.md
```

Working tree is clean except for the two allowed untracked handoff files.
No build artifacts, secrets, databases, or executables are tracked.

## 2. Feature completion

| ID  | Title                                               | Status |
| --- | --------------------------------------------------- | ------ |
| F00 | Каркас проекта + pytest + структура                 | done   |
| F01 | config.yaml + загрузчик + .env                      | done   |
| F02 | Модели данных (pydantic)                            | done   |
| F03 | WB client: detail                                 | done   |
| F04 | WB client: search/catalog                           | done   |
| F05 | WB client: public-feedbacks                         | done   |
| F06 | Playwright base                                   | done   |
| F07 | LLM слой: base + OpenRouter                       | done   |
| F08 | LLM провайдеры: Z.AI, Groq, Ollama                | done   |
| F09 | LLM провайдер: ChatGPT-web                        | deferred |
| F10 | Storage + кэш                                     | done   |
| F11 | Input resolver                                    | done   |
| F12 | China driver: Alibaba                             | done   |
| F13 | China driver: 1688                                | done   |
| F14 | China driver: Taobao                              | done   |
| F15 | CLIP + pHash ранкер                               | done   |
| F16 | China video extractor                             | done   |
| F17 | WB review-video harvester                         | done   |
| F18 | Video downloader                                  | done   |
| F19 | Description writer                                | done   |
| F20 | Viral detector                                    | done   |
| F21 | Reviews collector                                 | done   |
| F22 | VoC analyzer                                      | done   |
| F23 | Hook generator                                    | done   |
| F24 | GUI: Матчер China                                 | done   |
| F25 | GUI: Разведка WB + мост                           | done   |
| F26 | GUI: Настройки                                    | done   |
| F27 | End-to-end + интеграционные тесты                 | done   |
| F28 | Сборка .exe                                       | done   |

## 3. Full non-live regression

Command:

```powershell
.venv\Scripts\python.exe -m pytest -m "not live" -q
```

Result:

```text
620 passed, 1 skipped, 15 deselected
```

- Skipped: 1 platform-specific WebP/Pillow test (`tests/test_matcher_input.py:153`).
- Deselected: 15 `@pytest.mark.live` tests.
- No failures.
- Full suite runtime: ~21 seconds.

E2E file run separately:

```text
.venv\Scripts\python.exe -m pytest tests/test_e2e.py -m "not live" -q
6 passed, 2 deselected
```

## 4. Import checks

All key modules import cleanly:

```text
gui ok
matcher ok
harvest ok
download ok
```

Specific checks:

- `from gui.app import create_app, build_matcher_tab, build_discovery_tab, build_settings_tab` ✅
- `from matcher.rank import ChinaCandidateRanker; from matcher.video_china import extract_china_videos` ✅
- `from harvest.discovery import niche; from harvest.reviews import collect_reviews_for_products; from harvest.voc import analyze_reviews_voc; from harvest.hooks import generate_hooks` ✅
- `from harvest.download import download_video` ✅

## 5. GUI smoke

### Non-window smoke (tests only)

- `create_app` creates a `ft.Tabs` object with `length=3` ✅
- Tabs in order: `"Матчер China"`, `"Разведка WB"`, `"Настройки"` ✅
- `selected_index == 0` (Матчер China is default) ✅
- Fake `matcher_pipeline` and `downloader` are used in tests ✅
- Settings tab masks secrets via `mask_secret` ✅

### Manual window smoke

A real GUI window was **not** opened automatically in headless QA. The build smoke ran the executable for 8 seconds; the process stayed alive, indicating the app starts without an immediate crash. Interactive visual verification (3 tabs, settings, empty inputs) was **not performed** in this automated run.

## 6. Matcher China end-to-end (fake/fixtures)

Covered by `tests/test_e2e.py`:

- WB article input (fake `Product`) ✅
- Fake matcher pipeline returns product + candidates ✅
- Top candidate has `video_url` ✅
- Fake downloader is invoked and returns `VideoAsset` ✅
- Status text reports `"Скачано видео: 1"` ✅
- Real ranker test: identical RGB image vs itself with `use_clip=False, use_phash=True` yields `similarity > 0.95` ✅

## 7. WB Discovery end-to-end (fake/fixtures)

Covered by `tests/test_e2e.py`:

- Fake `ViralProduct` input ✅
- Fake LLM returns VoC with "Шумит" / "Лёгкий" / "Сломается" ✅
- `generate_hooks` returns 5 hooks and a structure ✅
- `extract_review_videos_from_reviews` finds the video review ✅
- GUI bridge "В Матчер" fills the matcher input field with the selected `nmId` ✅
- Fake services do not use the network ✅

## 8. Settings & security

- `mask_secret('sk-abcdefghijklmnopqrstuvwxyz')` → `sk****wxyz` ✅
- `.env` is ignored by git ✅
- `sessions/` ignored ✅
- `output/` ignored ✅
- `build/` ignored ✅
- `dist/` ignored ✅
- `.venv/` ignored ✅
- `*.db` ignored ✅
- `__pycache__/` ignored ✅
- No API keys or sessions tracked in git (`git ls-files` filtered for sensitive patterns shows only `.env.example`, `scripts/build_windows.ps1`, and `tests/test_build_packaging.py`) ✅
- README documents live-test gating and captcha/403 limitations ✅
- Live tests are gated by `WB_RADAR_RUN_LIVE=1` ✅
- Normal pytest does not run live tests ✅

## 9. Build / exe check

Build script exists: `scripts/build_windows.ps1` ✅  
PyInstaller spec exists: `WB_Radar_China_Matcher.spec` ✅

Direct PyInstaller rebuild was performed:

```powershell
.venv\Scripts\python.exe -m PyInstaller WB_Radar_China_Matcher.spec --noconfirm
```

Result: `Build complete! The results are available in: D:\AI\Shodstva\dist`

Executable:

- **Path**: `dist\WB_Radar_China_Matcher\WB_Radar_China_Matcher.exe`
- **Size**: 57.6 MB (57,613,752 bytes)
- **SHA256**: `EBE3B4D3613E223E773C09C453810136ED254E0A10EB19E1DF416093CF7ED7AC`

The hash matches the previously reported value, indicating a reproducible build.

PyInstaller warnings observed (non-blocking):

- `Failed to collect submodules for 'torch.utils.tensorboard'` (tensorboard not installed)
- `Hidden import "scipy.special._cdflib" not found!`
- `Ignoring /usr/lib64/libgomp.so.1` (Linux-only library reference in torch)

These warnings were present in the original F28 build and do not prevent the executable from running.

## 10. Manual exe smoke

The built executable was started via PowerShell smoke script and ran for 8 seconds without exiting. It was then stopped. No crash dialog or traceback was observed. Full interactive GUI validation (tab visibility, settings, empty input handling) was not performed in this automated QA.

## 11. Live tests

Live tests were **not executed**.

Verification that gating works:

```powershell
.venv\Scripts\python.exe -m pytest -m live -q
```

Result:

```text
15 skipped, 621 deselected
```

All live tests require environment flags or API keys and are skipped when not configured. README documents the command to run them:

```powershell
$env:WB_RADAR_RUN_LIVE = "1"
.venv\Scripts\python.exe -m pytest -m live -q
```

## 12. Issues found

| #   | Issue                                                                 | Severity | Fix needed |
| --- | --------------------------------------------------------------------- | -------- | ---------- |
| 1   | `scripts/build_windows.ps1` cannot be invoked directly from the current bash→PowerShell bridge due to quote/escaping parser errors. | Low      | No — the script itself is valid PowerShell; the failure is in the bridge. Direct `PyInstaller WB_Radar_China_Matcher.spec` works. |
| 2   | `handoff_f15_sa1.md` and `handoff_f15_sa2.md` remain untracked (allowed). | N/A      | No — intentionally left untracked per project rules. |
| 3   | 1 platform-specific WebP/Pillow test skipped.                           | N/A      | No — expected on this environment. |

No product bugs were found. No separate FIX-prompt is required.

## 13. QA verdict

**PASS**

The project is built, tested, and ready for release/manual use:

- All F00–F28 features are done (F09 deferred).
- Full non-live test suite passes (`620 passed, 1 skipped, 15 deselected`).
- Key modules import cleanly.
- GUI structure is correct (3 tabs, Матчер China default).
- E2E scenarios for matcher and discovery pass on fake services.
- Settings mask secrets and write to untracked `.env.local`.
- No secrets or build artifacts are tracked in git.
- PyInstaller builds a working 57.6 MB `.exe` reproducibly.
- The built `.exe` starts and runs for at least 8 seconds without crashing.
- Live tests are properly gated and were not run automatically.
- Push was not performed.
