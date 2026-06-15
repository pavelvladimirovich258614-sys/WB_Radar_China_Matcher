## Активная фича

F07 — LLM слой: base + OpenRouter (status: todo) — следующая

## Журнал

## SESSION-CLOSE-01 (2026-06-16) — сессия зафиксирована

- Принято: F06-FIX-01 (defense-in-depth по site-имени).
- Статус: F00–F06 done; active_feature=F07 (НЕ начат).
- Тесты: pytest -m "not live" → 91 passed, 4 deselected.
- Импорт-чек: `from core.browser import BrowserManager` → "browser security ok".
- Known issue: WB-эндпоинты (card/search/feedbacks) отдают 403 из текущего окружения — стоп-правило AGENTS.md, НЕ обходить. Не-live тесты на фикстурах зелёные.
- VCS: git-репозиторий НЕ инициализирован (коммитов нет).
- Следующий шаг: F07 (LLM слой: base + OpenRouter).

## F06-FIX-01 — done (2026-06-16)

Defense-in-depth по безопасному имени site (закрытие known-issue F06).

- core/browser.py: вынесена чистая модульная функция sanitize_site_name(site)->str (regex `[^A-Za-z0-9._-]`→"_", замена "/" и "\" на "_", strip(".") краёв, fallback "site" для ""/"."/".."). ".."→"site", "."→"site", ""→"site", "alibaba"→"alibaba", "1688.com"→"1688.com", "../evil"→"_evil", "..\evil"→"_evil", "/etc/passwd"→"_etc_passwd", "C:\evil"→"C__evil".
- _site_dir теперь использует sanitize_site_name + defense-in-depth проверку через Path.resolve(): если resolved-путь вне sessions root — fallback на sessions/<site>; никогда не raise.
- Два независимых слоя защиты: sanitize (небезопасные символы/точки) + resolve-containment (symlink/FS-уровень). Обход пути (path traversal) закрыт.
- tests/test_browser.py: +10 тестов (17 кейсов): sanitize_site_name (dotdot/dot/empty/preserve/neutralize/no-separators) + _site_dir containment (forward/backslash/dotdot + параметризованный test_site_dir_always_inside_sessions_root по 8 evil-входам).
- Прогон: pytest -m "not live" → 91 passed, 4 deselected. Импорт: "browser security ok".
- Бизнес-логика manual_login/new_page/detect_captcha не изменена. F03–F06 не сломаны.

## F06 — done (2026-06-16)

Реализовано эстафетой из 5 саб-агентов (PLAN → BUILD → TESTS → REVIEW → DOCS).

- core/browser.py: класс BrowserManager (настройки инжектятся как в WBPublic; Playwright-инстанс инжектится для тестов, реальный sync_playwright стартует лениво → обычный pytest браузер не запускает).
- Persistent-контексты: sessions/<site> из settings.paths.sessions; директория создаётся автоматически; имя site санируется (re.sub небезопасных символов → "_", защита от path-traversal — разделителей / и \ нет).
- Proxy: из settings.proxy через urlparse → {server, username, password}; None/пусто → None (не передаётся в Playwright); http/https/socks5 и bare host:port; креды не выдумываются.
- Headless: new_context берёт из settings.matcher.headless (переопределяется аргументом); manual_login ВСЕГДА headless=False (видимое окно).
- Locale zh-CN, обычный Chrome UA, viewport 1280x800. БЕЗ stealth (никаких --disable-blink-features=AutomationControlled, без playwright-stealth).
- Методы: new_context(site, headless=None), new_page(site, url=None) (goto с wait_until="domcontentloaded"), manual_login(site, url=None)->Path (видимое окно, инструкция в консоль, input() ждёт Enter, затем закрывает page+context → сессия пишется на диск, возвращает sessions/<site>), detect_captcha(page)->bool (title/content/url, keywords captcha/verify/robot/滑块/验证码/人机/проверка/капча; НИКОГДА не raise, None→False; НЕ решает капчу), close(), __enter__/__exit__.
- Тесты: tests/test_browser.py — 24 не-live (FakePlaywright/FakeContext/FakePage, без реального браузера) + 1 @pytest.mark.live test_open_alibaba_and_persist_session_live (доп. гейт F06_LIVE env).
- Прогон: pytest -m "not live" → 74 passed, 4 deselected. Импорт-чек: from core.browser import BrowserManager → "browser ok".
- F03/F04/F05 не сломаны. sessions/ в .gitignore.
- следующий: F07

## F05 — done: WBPublic.get_reviews (POST feedbacks) + extract_review_video_url/photo_urls; Review.id→str, nmId→Optional.
## F04 — done: WBPublic.search (search.wb.ru v4). F03+F03-FIX-01 — done: get_detail, build_wb_image_url, dest на wb.dest.
## F02 — done: core/models.py. F01 — done: core/config.py. F00 — done: каркас.

## Заметки/проблемы

- **Live 403**: WB-эндпоинты (card/search/feedbacks) отдают 403 из текущего окружения (стоп-правило AGENTS.md). Не-live зелёные. Живые данные — с разрешённой сети/сессии.
- **F06 site-sanitization закреплена** (F06-FIX-01): sanitize_site_name + resolve-containment; path traversal закрыт, покрыт параметризованными тестами.
- **retries** = макс. попыток вкл. первую. basket-хост img_url — эвристика.
- python 3.11.9; init.sh под bash; полный init.sh на чистой машине не валидирован целиком.
