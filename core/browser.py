from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from core.config import Settings
from core.config import settings as default_settings

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

CAPTCHA_KEYWORDS = (
    "captcha",
    "verify",
    "robot",
    "滑块",
    "验证码",
    "人机",
    "проверка",
    "капча",
)


def sanitize_site_name(site: str) -> str:
    """Return a safe single-path-segment name for a site.

    Guarantees: never ""/"."/"..", no "/" or "\\", not absolute, a single path
    segment. Dots in the MIDDLE are preserved ("1688.com" -> "1688.com");
    leading/trailing dots are stripped (".." -> "" -> "site", "../evil" -> "_evil").
    """
    if site is None:
        site = ""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", site.strip())
    safe = safe.replace("/", "_").replace("\\", "_")
    safe = safe.strip(".")
    if safe in ("", ".", ".."):
        safe = "site"
    return safe


class BrowserManager:
    """Manages persistent Playwright Chromium contexts keyed by site.

    No stealth, no captcha bypass. ``detect_captcha`` only DETECTS and never raises.
    A real browser is spawned lazily only when no Playwright instance was injected,
    so normal ``pytest -m "not live"`` never starts Chromium.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        playwright: Optional[Any] = None,
        *,
        locale: str = "zh-CN",
    ) -> None:
        self._settings = settings or default_settings
        self._sessions_root = Path(self._settings.paths.sessions)
        self._proxy_raw = self._settings.proxy
        self._default_headless = bool(self._settings.matcher.headless)
        self._locale = locale
        self._playwright = playwright
        self._owns_playwright = playwright is None
        self._contexts: dict[str, Any] = {}

    def __enter__(self) -> "BrowserManager":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _ensure_playwright(self) -> Any:
        """Return a started sync Playwright instance.

        If an instance was injected at construction time, reuse it. Otherwise lazily
        import and start ``sync_playwright`` — this is the only path that spawns a
        real browser driver, and it is never taken during import or when a fake
        Playwright is injected for tests.
        """
        if self._playwright is None:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
        return self._playwright

    def _build_proxy_dict(self) -> Optional[dict]:
        """Build a Playwright-compatible proxy dict from settings.proxy.

        Supports ``http://``, ``https://``, ``socks5://`` schemes and bare
        ``host:port`` strings. Returns ``None`` when no proxy is configured.
        Never raises on malformed input and never fabricates credentials.
        """
        if self._proxy_raw is None:
            return None

        raw = str(self._proxy_raw).strip()
        if not raw:
            return None

        # urlparse needs a scheme to populate host/port reliably. If the user
        # passed a bare "host:port", prepend a sentinel scheme.
        if "://" not in raw:
            parsed = urlparse("//" + raw, scheme="http")
        else:
            parsed = urlparse(raw)

        scheme = parsed.scheme.lower() or "http"
        host = parsed.hostname
        if not host:
            # Cannot construct a usable server URL without a host — refuse to
            # fabricate. Treat as no proxy.
            logger.warning("Cannot parse proxy host from %r; ignoring proxy", raw)
            return None

        port = parsed.port
        if port:
            server = f"{scheme}://{host}:{port}"
        else:
            server = f"{scheme}://{host}"

        username = parsed.username or None
        password = parsed.password or None

        return {
            "server": server,
            "username": username,
            "password": password,
        }

    def _site_dir(self, site: str) -> Path:
        """Return a per-site persistent user-data directory under sessions root.

        Sanitizes ``site`` via :func:`sanitize_site_name` so arbitrary strings
        become safe filesystem segment names, then applies a defense-in-depth
        containment check: if the resolved path ever escapes the sessions root,
        it falls back to the literal "site" segment. The directory is always
        created.
        """
        safe = sanitize_site_name(site)
        root_resolved = self._sessions_root.resolve()
        path = self._sessions_root / safe
        resolved = path.resolve()
        if resolved != root_resolved and root_resolved not in resolved.parents:
            path = self._sessions_root / "site"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def new_context(self, site: str, headless: Optional[bool] = None) -> Any:
        """Return a cached-or-new persistent Chromium context for ``site``.

        No stealth flags are passed: this is a plain, automation-labeled Chrome.
        """
        if site in self._contexts:
            return self._contexts[site]

        effective_headless = (
            self._default_headless if headless is None else bool(headless)
        )
        pw = self._ensure_playwright()
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(self._site_dir(site)),
            headless=effective_headless,
            proxy=self._build_proxy_dict(),
            locale=self._locale,
            user_agent=_DEFAULT_USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        self._contexts[site] = ctx
        return ctx

    def new_page(self, site: str, url: Optional[str] = None) -> Any:
        """Open a new page in the site's context, optionally navigating to ``url``."""
        ctx = self.new_context(site)
        page = ctx.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded")
        return page

    def manual_login(self, site: str, url: Optional[str] = None) -> Path:
        """Open a VISIBLE window for the user to log in / solve captcha manually.

        After the user presses Enter, the page and context are closed. Closing a
        persistent context flushes its storage state (cookies, localStorage) to
        ``user_data_dir`` so the session survives the next run. Returns that dir.
        """
        ctx = self.new_context(site, headless=False)
        page = ctx.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded")

        where = f" по адресу {url}" if url else ""
        print(
            f"[manual_login:{site}] Войдите в видимом окне{where}. "
            "Если появится капча — решите её вручную. "
            "После завершения нажмите Enter для сохранения сессии...",
            flush=True,
        )
        input()

        try:
            try:
                page.close()
            except Exception:
                logger.exception("Failed to close page during manual_login")
            try:
                ctx.close()
            except Exception:
                logger.exception("Failed to close context during manual_login")
        finally:
            self._contexts.pop(site, None)

        return self._site_dir(site)

    def detect_captcha(self, page: Any) -> bool:
        """Return True if the page looks like a captcha/verification challenge.

        Only DETECTS. Never raises: any error → False. Each piece (title,
        content, url) is fetched independently so one failing call doesn't mask
        a positive signal from another.
        """
        if page is None:
            return False

        blob_parts: list[str] = []
        try:
            title = page.title()
            if title:
                blob_parts.append(str(title))
        except Exception:
            pass
        try:
            content = page.content()
            if content:
                blob_parts.append(str(content))
        except Exception:
            pass
        try:
            page_url = page.url
            if page_url:
                blob_parts.append(str(page_url))
        except Exception:
            pass

        blob = "\n".join(blob_parts).lower()
        for keyword in CAPTCHA_KEYWORDS:
            if keyword.lower() in blob:
                return True
        return False

    def close(self) -> None:
        """Close all cached contexts and stop Playwright if we own it."""
        for site, ctx in list(self._contexts.items()):
            try:
                ctx.close()
            except Exception:
                logger.exception("Failed to close context for site %r", site)
        self._contexts.clear()

        if self._owns_playwright and self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                logger.exception("Failed to stop Playwright")
            self._playwright = None
