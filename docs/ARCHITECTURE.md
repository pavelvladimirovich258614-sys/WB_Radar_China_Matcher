# Architecture

## Overview

WB Radar & China Matcher is a desktop Python application built with Flet. It
combines public Wildberries endpoints, browser automation via Playwright,
image similarity ranking (CLIP + pHash), LLM analysis, and video downloading into
a single GUI with three tabs:

1. **Матчер China** — find a 1:1 supplier on Alibaba, 1688, or Taobao from a WB
   article, URL, or local photo.
2. **Разведка WB** — discover viral WB products, analyze reviews, extract
   pains/desires/fears (VoC), generate hooks, and download review videos.
3. **Настройки** — choose the LLM provider, proxy, output/session folders, and
   check login session status.

## Module structure

```text
core/          — shared foundation
  config.py    — pydantic-settings, config.yaml + .env
  models.py    — pydantic models: Product, Review, Candidate, VoC, VideoAsset
  wb_public.py — public WB endpoints: detail, search, feedbacks
  browser.py   — Playwright sessions, proxy, manual login, captcha detection
  llm/         — LLM provider interface and implementations
  storage.py   — sqlite cache + JSON/CSV export

matcher/       — China 1:1 matching pipeline
  input.py     — WB article/URL/photo → query.jpg
  rank.py      — CLIP + pHash ranking
  video_china.py — extract product videos from China detail pages
  china/       — site-specific image-search drivers
    alibaba.py
    s1688.py
    taobao.py

harvest/       — WB research pipeline
  discovery.py — viral product detection
  reviews.py   — batch review collector
  voc.py       — VoC analyzer (pains, desires, fears, triggers, objections, language)
  hooks.py     — hook generator and video structure
  review_video.py — collect videos from WB reviews
  download.py  — video downloader organized by nmId
  describe.py   — LLM-generated video descriptions and captions

gui/           — Flet desktop UI
  app.py       — main app with 3 tabs and DI-friendly controllers
  settings.py  — Settings tab with secret masking

scripts/       — build and utility scripts
  build_windows.ps1 — PyInstaller Windows build

tests/         — unit, integration, e2e and live-smoke tests
fixtures/      — saved real-world responses for deterministic offline tests
```

## Flow: Матчер China

```text
User input (nmId / WB URL / photo)
    ↓
matcher.input.resolve_input
    ↓
query.jpg  +  Product metadata
    ↓
China drivers (Alibaba/1688/Taobao) search by image
    ↓
List[Candidate]
    ↓
matcher.rank.rank_candidates (CLIP + pHash)
    ↓
Top candidates sorted by similarity
    ↓
matcher.video_china.ChinaVideoExtractor
    ↓
Candidates with has_video / video_url
    ↓
GUI table: thumb | site | title | similarity | price | actions
    ↓
Download via harvest.download.download_videos
    ↓
output/video/<nmId>/china_*.mp4
```

## Flow: Разведка WB

```text
User enters a niche query
    ↓
harvest.discovery.niche
    ↓
WB search → top-by-feedbacks products → fetch reviews
    ↓
compute_viral_scores (velocity_7d, feedbacks, rating)
    ↓
ViralResult + CSV export
    ↓
User selects a product in GUI
    ↓
harvest.reviews.collect_reviews_for_product
    ↓
harvest.voc.analyze_reviews_voc (LLM)
    ↓
VoC JSON: боли / желания / страхи / триггеры / восторги / возражения / язык
    ↓
harvest.hooks.generate_hooks
    ↓
output/hooks/<nmId>.md
    ↓
harvest.review_video.get_review_videos
    ↓
Download video reviews via harvest.download
    ↓
output/video/<nmId>/wb_review_*.mp4
```

## LLM / VoC / hooks flow

```text
Reviews batch (≤40 items)
    ↓
build_voc_prompt
    ↓
LLMProvider.complete_json(schema=VOC_SCHEMA)
    ↓
_parse_voc_response → merge → dedupe
    ↓
VoC model
    ↓
build_hooks_prompt(VoC, product)
    ↓
LLMProvider.complete_json(schema=HOOKS_SCHEMA)
    ↓
parse_hooks_response → fallback defaults if malformed
    ↓
VideoHookSet (5 hooks + structure + objections)
    ↓
save_hooks → output/hooks/<nmId>.md
```

## Dependency injection for testing

Controllers in `gui/app.py` and `gui/settings.py` accept injectable services:

- `matcher_pipeline`
- `downloader`
- `discovery_service`
- `voc_service`
- `hooks_service`
- `review_video_service`
- `save_settings`
- `open_folder`
- `session_status`

Default implementations use real project modules, but tests pass fake callables
so the UI can be exercised without opening a window, browser, or network.

## Data models

Key Pydantic models live in `core/models.py`:

- `Product` — WB catalog item with nmId/imtId, rating, feedbacks, image URL.
- `Review` — WB review with text, rating, date, pros/cons, photo/video URLs.
- `Candidate` — China marketplace item with thumb, price, similarity, video.
- `VocItem` — insight with frequency, quote, source review ids.
- `VoC` — collection of insight categories in Russian.
- `VideoAsset` — downloaded video reference with source and local path.

## Configuration

`config.yaml` provides non-secret settings: WB hosts, marketplace list, rate
limits, similarity threshold, LLM provider/model, output/session paths. Secrets
are loaded exclusively from `.env` / `.env.local` via `pydantic-settings`.
