from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import pytest

from core.browser import BrowserManager, sanitize_site_name
from core.config import Settings


class FakePage:
    """Stand-in for playwright.sync_api.Page used by detect_captcha/new_page."""

    def __init__(
        self,
        title: str = "",
        content: str = "",
        url: str = "",
        title_exc: Optional[Exception] = None,
        content_exc: Optional[Exception] = None,
        url_exc: Optional[Exception] = None,
    ) -> None:
        self._title = title
        self._content = content
        self._url = url
        self._title_exc = title_exc
        self._content_exc = content_exc
        self._url_exc = url_exc
        self.goto_calls: list[tuple[str, Optional[str]]] = []
        self.closed = False

    def title(self) -> str:
        if self._title_exc is not None:
            raise self._title_exc
        return self._title

    def content(self) -> str:
        if self._content_exc is not None:
            raise self._content_exc
        return self._content

    @property
    def url(self) -> str:
        if self._url_exc is not None:
            raise self._url_exc
        return self._url

    def goto(self, url: str, wait_until: Optional[str] = None) -> None:
        self.goto_calls.append((url, wait_until))

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, launch_kwargs: dict[str, Any]) -> None:
        self.launch_kwargs = launch_kwargs
        self.pages: list[FakePage] = []
        self.closed = False

    def new_page(self) -> FakePage:
        page = FakePage()
        self.pages.append(page)
        return page

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self) -> None:
        self.last_kwargs: Optional[dict[str, Any]] = None
        self.call_count = 0
        self.contexts: list[FakeContext] = []

    def launch_persistent_context(self, **kwargs: Any) -> FakeContext:
        self.call_count += 1
        self.last_kwargs = kwargs
        ctx = FakeContext(kwargs)
        self.contexts.append(ctx)
        return ctx


class FakePlaywright:
    def __init__(self) -> None:
        self.chromium = FakeChromium()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def _settings(
    tmp_path: Path, *, proxy: Optional[str] = None, headless: bool = True
) -> Settings:
    s = Settings()
    s.paths.sessions = str(tmp_path / "sessions")
    s.proxy = proxy
    s.matcher.headless = headless
    return s


def _bm(
    tmp_path: Path, *, proxy: Optional[str] = None, headless: bool = True
) -> tuple[BrowserManager, FakePlaywright]:
    pw = FakePlaywright()
    bm = BrowserManager(
        settings=_settings(tmp_path, proxy=proxy, headless=headless), playwright=pw
    )
    return bm, pw


def test_new_context_creates_site_session_dir(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    ctx = bm.new_context("alibaba")
    assert isinstance(ctx, FakeContext)
    sessions_root = tmp_path / "sessions"
    assert (sessions_root / "alibaba").is_dir()


def test_new_context_headless_defaults_from_config(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path, headless=False)
    ctx = bm.new_context("alibaba")
    assert ctx.launch_kwargs["headless"] is False

    bm2, _ = _bm(tmp_path, headless=True)
    ctx2 = bm2.new_context("taobao")
    assert ctx2.launch_kwargs["headless"] is True


def test_new_context_headless_override(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path, headless=True)
    ctx = bm.new_context("alibaba", headless=False)
    assert ctx.launch_kwargs["headless"] is False


def test_new_context_locale_zhcn(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    ctx = bm.new_context("alibaba")
    assert ctx.launch_kwargs["locale"] == "zh-CN"


def test_new_context_reuses_cached_context(tmp_path: Path) -> None:
    bm, pw = _bm(tmp_path)
    ctx1 = bm.new_context("alibaba")
    ctx2 = bm.new_context("alibaba")
    assert ctx1 is ctx2
    assert pw.chromium.call_count == 1


def test_new_page_goes_to_url(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    page = bm.new_page("alibaba", url="https://www.alibaba.com")
    assert isinstance(page, FakePage)
    assert len(page.goto_calls) == 1
    assert page.goto_calls[0][0] == "https://www.alibaba.com"
    assert page.goto_calls[0][1] == "domcontentloaded"


def test_new_page_without_url_does_not_goto(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    page = bm.new_page("alibaba")
    assert isinstance(page, FakePage)
    assert page.goto_calls == []


def test_proxy_none_yields_no_proxy(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path, proxy=None)
    assert bm._build_proxy_dict() is None
    ctx = bm.new_context("alibaba")
    assert ctx.launch_kwargs["proxy"] is None


def test_proxy_simple_server(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path, proxy="http://host:8080")
    d = bm._build_proxy_dict()
    assert d == {"server": "http://host:8080", "username": None, "password": None}


def test_proxy_with_credentials(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path, proxy="http://u:p@10.0.0.1:3128")
    d = bm._build_proxy_dict()
    assert d["server"] == "http://10.0.0.1:3128"
    assert d["username"] == "u"
    assert d["password"] == "p"


def test_proxy_socks5(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path, proxy="socks5://127.0.0.1:1080")
    d = bm._build_proxy_dict()
    assert d["server"] == "socks5://127.0.0.1:1080"
    assert d["username"] is None
    assert d["password"] is None


def test_proxy_unparsable_returns_none(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path, proxy=":::")
    assert bm._build_proxy_dict() is None


def test_site_name_sanitized(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    sessions_root = tmp_path / "sessions"
    sites = ["../etc", "1688", "taobao 拍立淘"]
    for site in sites:
        ctx = bm.new_context(site)
        user_data_dir = Path(ctx.launch_kwargs["user_data_dir"])
        name = user_data_dir.name
        assert "/" not in name, f"folder name {name!r} contains '/'"
        assert "\\" not in name, f"folder name {name!r} contains '\\'"
        assert user_data_dir.is_dir()
        assert user_data_dir.parent == sessions_root


def test_detect_captcha_none_page(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    assert bm.detect_captcha(None) is False


def test_detect_captcha_clean_page(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    page = FakePage(
        title="Products",
        content="<html>buy now</html>",
        url="https://www.alibaba.com/product/123",
    )
    assert bm.detect_captcha(page) is False


def test_detect_captcha_by_title(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    page = FakePage(title="请输入验证码", content="normal", url="https://example.com")
    assert bm.detect_captcha(page) is True


def test_detect_captcha_by_content_robot(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    page = FakePage(
        title="Access",
        content="Please verify you are not a robot",
        url="https://example.com",
    )
    assert bm.detect_captcha(page) is True


def test_detect_captcha_by_url(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    page = FakePage(
        title="x", content="y", url="https://example.com/captcha/check"
    )
    assert bm.detect_captcha(page) is True


def test_detect_captcha_russian_keyword(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    page = FakePage(
        title="Доступ",
        content="Требуется проверка (капча)",
        url="https://example.com",
    )
    assert bm.detect_captcha(page) is True


def test_detect_captcha_resilient_to_page_errors(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    # content() raises but title carries the captcha signal -> True
    page_partial = FakePage(
        title="captcha required",
        content="x",
        content_exc=RuntimeError("content boom"),
    )
    assert bm.detect_captcha(page_partial) is True

    # every accessor raises -> False, and no exception escapes
    page_all_broken = FakePage(
        title_exc=RuntimeError("t"),
        content_exc=RuntimeError("c"),
        url_exc=RuntimeError("u"),
    )
    assert bm.detect_captcha(page_all_broken) is False


def test_manual_login_forces_headless_false_and_blocks_on_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda *a: "")
    bm, pw = _bm(tmp_path, headless=True)

    result = bm.manual_login("alibaba", url="https://www.alibaba.com")

    assert isinstance(result, Path)
    assert result.exists()
    assert result.is_dir()

    assert pw.chromium.call_count == 1
    ctx = pw.chromium.contexts[0]
    assert ctx.launch_kwargs["headless"] is False
    assert ctx.pages[0].goto_calls[0][0] == "https://www.alibaba.com"
    assert ctx.pages[0].closed is True
    assert ctx.closed is True
    assert "alibaba" not in bm._contexts

    out = capsys.readouterr().out
    assert "alibaba" in out
    assert "Enter" in out


def test_close_closes_contexts(tmp_path: Path) -> None:
    bm, pw = _bm(tmp_path)
    ctx = bm.new_context("alibaba")
    assert not ctx.closed
    bm.close()
    assert ctx.closed is True
    assert "alibaba" not in bm._contexts
    assert pw.stopped is False


def test_context_manager_closes_on_exit(tmp_path: Path) -> None:
    pw = FakePlaywright()
    bm = BrowserManager(settings=_settings(tmp_path), playwright=pw)
    with bm as same:
        assert same is bm
        ctx = bm.new_context("alibaba")
        assert not ctx.closed
    assert ctx.closed is True


def test_no_stealth_flags(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    ctx = bm.new_context("alibaba")
    kw = ctx.launch_kwargs
    args = kw.get("args")
    if args is not None:
        assert args == []
    ua = kw["user_agent"]
    assert "Chrome" in ua
    assert "--disable-blink-features=AutomationControlled" not in (args or [])


@pytest.mark.live
def test_open_alibaba_and_persist_session_live() -> None:
    if not os.environ.get("F06_LIVE"):
        pytest.skip("F06_LIVE not set")

    from core.config import settings as live_settings

    bm = BrowserManager(settings=live_settings)
    try:
        result = bm.manual_login("alibaba", "https://www.alibaba.com")
        assert isinstance(result, Path)
        assert result.exists()
    finally:
        bm.close()


# --- F06-FIX-01: sanitize_site_name + _site_dir containment regression tests ---


def test_sanitize_site_name_rejects_dotdot() -> None:
    assert sanitize_site_name("..") == "site"
    assert sanitize_site_name("..") != ".."


def test_sanitize_site_name_rejects_dot() -> None:
    assert sanitize_site_name(".") == "site"


def test_sanitize_site_name_empty_fallback() -> None:
    assert sanitize_site_name("") == "site"
    assert sanitize_site_name("   ") == "site"


def test_sanitize_site_name_preserves_safe_names() -> None:
    assert sanitize_site_name("alibaba") == "alibaba"
    assert sanitize_site_name("1688.com") == "1688.com"


def test_sanitize_site_name_neutralizes_traversal() -> None:
    assert sanitize_site_name("../evil") == "_evil"
    assert sanitize_site_name("..\\evil") == "_evil"
    assert sanitize_site_name("/etc/passwd") == "_etc_passwd"


def test_sanitize_site_name_no_separators_or_absolute() -> None:
    for raw in ["..", "/etc", "\\evil", "C:\\evil", "a/b\\c"]:
        out = sanitize_site_name(raw)
        assert "/" not in out, f"output {out!r} for {raw!r} contains '/'"
        assert "\\" not in out, f"output {out!r} for {raw!r} contains '\\'"
        assert not Path(out).is_absolute(), f"output {out!r} for {raw!r} is absolute"
        assert out not in ("", ".", ".."), f"output {out!r} for {raw!r} is unsafe"


def test_site_dir_traversal_forward_slash_stays_inside_root(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    root = (tmp_path / "sessions").resolve()
    resolved = bm._site_dir("../evil").resolve()
    assert resolved.is_relative_to(root)
    assert resolved != root.parent
    assert resolved.name != ".."


def test_site_dir_traversal_backslash_stays_inside_root(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    root = (tmp_path / "sessions").resolve()
    resolved = bm._site_dir("..\\evil").resolve()
    assert resolved.is_relative_to(root)
    assert resolved != root.parent
    assert resolved.name != ".."


def test_site_dir_dotdot_stays_inside_root(tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    root = (tmp_path / "sessions").resolve()
    resolved = bm._site_dir("..").resolve()
    assert resolved.is_relative_to(root)
    assert resolved.name == "site"


@pytest.mark.parametrize(
    "evil",
    ["..", ".", "", "../evil", "..\\evil", "/etc/passwd", "C:\\evil", "../../.."],
)
def test_site_dir_always_inside_sessions_root(evil: str, tmp_path: Path) -> None:
    bm, _ = _bm(tmp_path)
    root = (tmp_path / "sessions").resolve()
    resolved = bm._site_dir(evil).resolve()
    assert resolved.is_relative_to(root)
    assert resolved != root.parent
