# Session Handoff — WB Radar & China Matcher

## SESSION-CLOSE-08 (2026-06-16) — F12 committed

- **Закрытая фича: F12 — China driver: Alibaba.com image search (дефолт, без логина)** (status: done).
- **Коммит F12**: будет зафиксирован в этом сеансе (сообщение `F12: add Alibaba.com image search driver`).
- **F00–F11** остаются done.
- **Активная фича: F13** — China driver: 1688 image search (логин-сессия) (status: todo).
- **F13 не начат**.

## VCS (до коммита)

- Working tree содержит F12-изменения.
- Предстоящий коммит: `F12: add Alibaba.com image search driver`.
- Последние коммиты на момент начала сессии:
  - `461daa0` — F11: add input resolver for WB items and images
  - `1432b34` — F10: add sqlite cache and export storage
  - `d4830df` — F08: add ZAI, Groq, and Ollama LLM providers

## Что сделано в F12

- `matcher/china/__init__.py`, `matcher/china/base.py`, `matcher/china/alibaba.py`.
- `ChinaSearchDriver` Protocol + `AlibabaImageSearchDriver`.
- Иерархия ошибок: `AlibabaSearchError`, `AlibabaCaptchaError`, `AlibabaLoginRequiredError`, `AlibabaNoResultsError`.
- `parse_results_html(html)` — чистая функция без сети/Chromium.
- Playwright flow: открытие `alibaba.com/picture/search.htm`, загрузка query.jpg, ожидание результатов.
- Captcha/login детектируются, но **не обходятся** — выбрасываются специфические исключения.
- Кэш через `Storage` (`namespace="alibaba:image_search"`).
- Фикстуры и 14 тестов в `tests/test_alibaba_driver.py`.

## Проверки

- `pytest -m "not live" -q` → **257 passed, 1 skipped, 9 deselected**.
- 1 skipped: WebP/Pillow skip из F11 — platform-specific ограничение сборки Pillow.
- Импорт-чек F12: `from matcher.china.alibaba import AlibabaImageSearchDriver, parse_results_html` → ok.
- Слой-регрессия: `resolve_input`, `Storage`, `WBPublic`, `BrowserManager`, `get_provider` → ok.
- F13/F14/F15/F16 не начаты.
- GUI не тронут (только базовый `__init__.py`).

## Known issues / risks

- Alibaba live может столкнуться с captcha/login/anti-bot. Код не обходит защиту.
- Live-прогон Alibaba только вручную: `$env:ALIBABA_LIVE="1"; pytest -m live tests/test_alibaba_driver.py -s`.
- HTML-парсер Alibaba рассчитан на структуру 2024–2025; при смене вёрстки live может вернуть `AlibabaNoResultsError` — тогда обновить селекторы по свежей выдаче без обхода защиты.

## Следующий шаг

- **F13 — China driver: 1688 image search (логин-сессия)**.
- Сессия закрыта. Жду отдельного `SESSION-START-F13` промпта.
