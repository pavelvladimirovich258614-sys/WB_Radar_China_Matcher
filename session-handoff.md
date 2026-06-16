# Session Handoff — WB Radar & China Matcher

## F13 — done: China driver: 1688 image search (логин-сессия)

**Последняя фича**: F13 — done.

## Что сделано

- `matcher/china/s1688.py`:
  - иерархия ошибок `S1688SearchError` → `S1688CaptchaError`, `S1688LoginRequiredError`, `S1688NoResultsError`;
  - чистые функции: `is_captcha_html`, `is_login_required_html`, `is_empty_results_html`, `normalize_candidate_url`, `parse_results_html`;
  - `S1688ImageSearchDriver`: `search_by_image`, `close`, `__enter__/__exit__`;
  - интеграция `BrowserManager` (site="1688") и `Storage` (cache namespace `"1688:image_search"`);
  - ownership browser: закрывает только созданный самим драйвером `BrowserManager`;
- `matcher/china/__init__.py` — ре-экспорт 1688-сущностей;
- `fixtures/s1688_search_results.html`, `s1688_captcha.html`, `s1688_login.html`, `s1688_empty.html`;
- `tests/test_s1688_driver.py` — 21 не-live тест + 1 live-gated тест.

## Что НЕ доделано / known issues

- **1688 требует логин-сессию**: без `sessions/1688/` live-тест skip'ается; если сессия протухла — `S1688LoginRequiredError`;
- **captcha/anti-bot не обходятся**: код бросает `S1688CaptchaError`;
- **парсер может потребовать уточнения** под живую вёрстку при смене селекторов 1688.

## Следующий шаг

F14 — China driver: Taobao 拍立淘 (опц., логин). Фича не начата.

## Команда проверки

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live" -q
```

Результат: **291 passed, 1 skipped, 10 deselected**.

## Live-команда 1688

Создать сессию (один раз):

```powershell
.\.venv\Scripts\python.exe -c "from core.browser import BrowserManager; BrowserManager().manual_login('1688', url='https://www.1688.com')"
```

Затем запуск live-теста:

```powershell
$env:S1688_LIVE="1"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_s1688_driver.py -s
```
