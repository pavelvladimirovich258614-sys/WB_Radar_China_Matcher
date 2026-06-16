# Session Handoff — WB Radar & China Matcher

## F14 — done: China driver: Taobao 拍立淘 (опц., логин)

**Последняя фича**: F14 — done.
**Active feature**: F15 — CLIP + pHash ранкер (1:1) (status: todo, не начат).

## Что сделано

- `matcher/china/taobao.py`:
  - иерархия ошибок `TaobaoSearchError` → `TaobaoCaptchaError`, `TaobaoLoginRequiredError`, `TaobaoNoResultsError`;
  - чистые функции: `is_captcha_html`, `is_login_required_html`, `is_empty_results_html`, `normalize_candidate_url`;
  - `parse_results_html` — парсер выдачи Taobao без сети, балансировка вложенных `<div>`, поддержка `data-src`/`data-ks-lazyload`/`data-price`/`data-title`/`title`/`alt`, цен ¥/￥, видео-признаков;
  - `TaobaoImageSearchDriver`: `search_by_image`, `close`, `__enter__/__exit__`;
  - интеграция `BrowserManager` (site="taobao") и `Storage` (cache namespace `"taobao:image_search"`);
  - ownership browser: закрывает только созданный самим драйвером `BrowserManager`;
- `matcher/china/__init__.py` — ре-экспорт Taobao-сущностей с алиасами (`is_taobao_*`, `normalize_taobao_candidate_url`, `parse_taobao_results_html`);
- `fixtures/taobao_search_results.html` — 6 карточек (4 валидных + 1 дубликат + 1 phone-ссылка), relative/protocol-relative/absolute URL, разные цены, видео-признаки;
- `fixtures/taobao_captcha.html` — 验证码/滑块/robot/security check;
- `fixtures/taobao_login.html` — 登录/密码/账号/请登录;
- `fixtures/taobao_empty.html` — 暂无搜索结果/没有结果;
- `tests/test_taobao_driver.py` — 34 не-live теста + 1 live-gated тест.

## Что НЕ доделано / known issues

- **Taobao требует логин-сессию**: без `sessions/taobao/` live-тест skip'ается; если сессия протухла — `TaobaoLoginRequiredError`;
- **captcha/anti-bot не обходятся**: код бросает `TaobaoCaptchaError`;
- **парсер может потребовать уточнения** под живую вёрстку при смене селекторов Taobao;
- **WebP/Pillow skip** — platform-specific, не баг F14.

## Следующий шаг

F15 — CLIP + pHash ранкер (1:1). Фича не начата.

## Команда проверки

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live" -q
```

Результат: **325 passed, 1 skipped, 11 deselected**.

## Commit

F14: add Taobao image search driver — `bbe84287626dfc96aafe7b25b194d5173db9f815`

Закоммичено, не запушено.

## Live-команда Taobao

Создать сессию (один раз):

```powershell
.\.venv\Scripts\python.exe -c "from core.browser import BrowserManager; BrowserManager().manual_login('taobao', url='https://www.taobao.com/markets/pic/search')"
```

Затем запуск live-теста:

```powershell
$env:TAOBAO_LIVE="1"; .\.venv\Scripts\python.exe -m pytest -m live tests/test_taobao_driver.py -s
```
