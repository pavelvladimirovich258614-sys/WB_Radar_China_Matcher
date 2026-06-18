from __future__ import annotations

import logging
import re
import subprocess
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
import flet as ft

from core.llm.base import LLMAuthError, LLMRequestError

logger = logging.getLogger(__name__)


def _safe_update_page(page: Any) -> None:
    """Best-effort ``page.update()`` (no-op on test doubles without update).

    Mirrors ``gui.app._safe_update_page`` but kept local to avoid a circular
    import (``gui.app`` imports from this module). In a real Flet desktop
    client this is what actually pushes mutated control properties to the
    screen; in unit tests the page double has no ``update`` attribute and the
    call is a safe no-op.
    """
    update = getattr(page, "update", None)
    if callable(update):
        try:
            update()
        except Exception:
            pass


SESSION_SITES = ("1688", "taobao", "chatgpt")

# Providers supported by the project out of the box.  Keep in sync with
# core.llm.get_provider; chatgpt_web is intentionally separate because it is a
# browser-backed provider and may be unavailable.
LLM_PROVIDERS = ("openrouter", "zai", "groq", "ollama", "chatgpt_web")

# Which provider uses which env variable (case-insensitive pydantic-settings
# accepts both lower/upper and dots).
PROVIDER_SECRET_KEY = {
    "openrouter": "OPENROUTER_API_KEY",
    "zai": "ZAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "ollama": "OLLAMA_BASE_URL",
}

SaveSettings = Callable[[dict[str, str]], bool]
FolderOpener = Callable[[str], bool]
SessionChecker = Callable[[str], str]


def _default_open_folder(path: str) -> bool:
    """Open ``path`` in the default file manager.

    Creates the directory if it does not exist.  Falls back to ``webbrowser``
    when the platform-specific command is unavailable.  Any exception is logged
    and swallowed — the caller receives True/False and shows a status message.
    """
    target = Path(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.warning("Could not create folder %s: %s", path, exc)
        return False

    platform = __import__("sys").platform
    try:
        if platform == "win32":
            subprocess.run(["explorer", str(target)], check=False)
        elif platform == "darwin":
            subprocess.run(["open", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target)], check=False)
        return True
    except Exception as exc:
        logger.warning("Native folder opener failed: %s", exc)
        try:
            webbrowser.open(f"file://{target.resolve()}")
            return True
        except Exception:
            return False


def _default_session_status(site: str) -> str:
    """Return a human-readable session status by checking the sessions dir."""
    from core.config import settings

    safe = re.sub(r"[^A-Za-z0-9._-]", "_", site.strip()).strip(".") or site
    sessions_root = Path(settings.paths.sessions)
    site_dir = sessions_root / safe
    try:
        if not site_dir.exists():
            return "нет сессии"
        # A persistent context writes multiple files; treat any non-empty dir
        # as a logged-in session.  This is a cheap heuristic, not a guarantee.
        files = [p for p in site_dir.iterdir() if p.is_file()]
        return "активна" if files else "папка пуста"
    except Exception as exc:
        logger.warning("Session status check failed for %s: %s", site, exc)
        return "ошибка проверки"


def _default_save_settings(values: dict[str, str]) -> bool:
    """Persist user settings to ``.env.local`` in the project root.

    Secrets are stored in the untracked local env file, never in tracked files.
    """
    from core.config import PROJECT_ROOT, settings

    env_path = PROJECT_ROOT / ".env.local"
    lines: list[str] = []
    try:
        if env_path.exists():
            raw = env_path.read_text(encoding="utf-8")
            for line in raw.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key, _value = stripped.split("=", 1)
                    if key.strip() not in values:
                        lines.append(line)
    except Exception as exc:
        logger.warning("Could not read existing .env.local: %s", exc)

    for key, value in values.items():
        lines.append(f'{key}="{value.replace(chr(34), chr(92)+chr(34))}"')

    lines.append("")  # trailing newline
    try:
        env_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception as exc:
        logger.exception("Failed to write .env.local")
        return False

    # Update in-process settings only for the fields we know are safe to mutate.
    # We deliberately do NOT overwrite secret attributes that may already be
    # populated from .env; reloading the whole settings object would re-read all
    # env files and could lose values the user has not touched.
    try:
        if "llm.provider" in values:
            provider = values["llm.provider"].strip().lower()
            if provider in LLM_PROVIDERS:
                settings.llm.provider = provider
        if "llm.model" in values:
            settings.llm.model = values["llm.model"].strip()
        if "proxy" in values:
            proxy = values["proxy"].strip() or None
            settings.proxy = proxy
    except Exception as exc:
        logger.warning("Could not update in-process settings: %s", exc)

    return True


def mask_secret(value: str | None, visible: int = 4) -> str:
    """Mask a secret so only the last few characters are visible.

    Examples:
        "sk-abcdefghijklmnopqrstuvwxyz" -> "sk-****wxyz"
        "abcd" -> "abcd" (too short to mask)
        None -> "" (empty)
    """
    if not value:
        return ""
    text = str(value)
    if len(text) <= visible + 2:
        return "*" * len(text) if len(text) > visible else text
    return f"{text[:2]}****{text[-visible:]}"


# --------------------------------------------------------------------------- #
# Online provider key check
# --------------------------------------------------------------------------- #
#
# ``check_provider_online`` performs a single minimal chat-completion request
# against the selected LLM provider to verify the API key/model/connectivity.
# It REUSES the existing project providers (core.llm.*) — same endpoints, auth
# headers and transport — instead of inventing a parallel HTTP client. The
# httpx client is injectable so tests never touch the network.
#
# Security: the API key is never logged or printed; only a masked form is
# returned. ``Authorization`` headers are produced by the provider and not
# logged here.

DEFAULT_CHECK_TIMEOUT = 20.0
_ONLINE_CHECK_PROMPT = [{"role": "user", "content": "Reply with exactly: OK"}]

# Friendly labels and which providers support an online ping.
_PROVIDER_LABEL = {
    "openrouter": "OpenRouter",
    "zai": "ZAI",
    "groq": "Groq",
    "ollama": "Ollama",
    "chatgpt_web": "ChatGPT-web",
}

# Online check statuses — stable identifiers (do not localise these values).
CHECK_OK = "ok"
CHECK_AUTH_ERROR = "auth_error"
CHECK_MODEL_ERROR = "model_error"
CHECK_NETWORK_ERROR = "network_error"
CHECK_MISSING_KEY = "missing_key"
CHECK_NOT_SUPPORTED = "not_supported"
CHECK_UNKNOWN_ERROR = "unknown_error"

_HTTP_STATUS_RE = re.compile(r"HTTP\s+(\d{3})", re.IGNORECASE)


@dataclass
class ProviderCheckResult:
    """Structured result of an online provider check."""

    ok: bool
    status: str
    message: str
    masked_key: str = ""


# Injectable online-check callable (defaults to :func:`check_provider_online`).
OnlineChecker = Callable[..., ProviderCheckResult]


class _ProbeLLM:
    """Minimal stand-in for ``Settings.llm`` used to build a probe provider."""

    def __init__(self, model: str, temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature


class _ProbeSettings:
    """Minimal stand-in for ``Settings`` carrying only what a provider needs.

    Only the attribute relevant to the selected provider is populated, so the
    provider reads the just-entered key/model even before the user saves.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        base_url: str | None,
    ) -> None:
        self.llm = _ProbeLLM(model)
        self.openrouter_api_key = api_key if provider == "openrouter" else None
        self.zai_api_key = api_key if provider == "zai" else None
        self.groq_api_key = api_key if provider == "groq" else None
        self.ollama_base_url = base_url if provider == "ollama" else None


def _provider_class(provider: str) -> Any | None:
    """Lazy import of the provider class for ``provider`` (avoids heavy import
    at GUI startup and keeps this module decoupled)."""
    normalized = (provider or "").strip().lower()
    if normalized in ("zai", "z.ai", "glm"):
        from core.llm.zai import ZAIProvider

        return ZAIProvider
    if normalized == "openrouter":
        from core.llm.openrouter import OpenRouterProvider

        return OpenRouterProvider
    if normalized == "groq":
        from core.llm.groq import GroqProvider

        return GroqProvider
    if normalized == "ollama":
        from core.llm.ollama import OllamaProvider

        return OllamaProvider
    return None


def _extract_http_status(message: str) -> int | None:
    match = _HTTP_STATUS_RE.search(message or "")
    return int(match.group(1)) if match else None


def _build_check_client(timeout: float, proxy: str | None) -> httpx.Client:
    """Build an httpx client honouring an optional proxy across httpx versions."""
    if not proxy:
        return httpx.Client(timeout=timeout)
    try:
        return httpx.Client(timeout=timeout, proxy=proxy)
    except TypeError:  # older httpx used ``proxies``
        return httpx.Client(timeout=timeout, proxies=proxy)


def check_provider_online(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    proxy: str | None = None,
    timeout: float = DEFAULT_CHECK_TIMEOUT,
    *,
    client: httpx.Client | None = None,
) -> ProviderCheckResult:
    """Run a minimal online check against ``provider``.

    Returns a :class:`ProviderCheckResult`. The API key is never logged or
    returned in full — only ``masked_key`` is exposed. The ``client`` argument
    is injectable so tests can drive this through ``httpx.MockTransport``
    without any network access.
    """
    normalized = (provider or "").strip().lower()
    label = _PROVIDER_LABEL.get(normalized, normalized)
    masked = mask_secret(api_key) if (api_key and normalized != "ollama") else ""

    cls = _provider_class(normalized)
    if cls is None:
        return ProviderCheckResult(
            False,
            CHECK_NOT_SUPPORTED,
            f"Онлайн-проверка для провайдера «{label}» не реализована.",
            masked,
        )

    if normalized != "ollama" and not api_key:
        return ProviderCheckResult(
            False,
            CHECK_MISSING_KEY,
            f"Не задан API-ключ для «{label}».",
            masked,
        )

    if normalized == "ollama" and not base_url:
        from core.llm.ollama import DEFAULT_OLLAMA_BASE_URL

        base_url = DEFAULT_OLLAMA_BASE_URL

    probe = _ProbeSettings(normalized, model, api_key, base_url)
    owns_client = client is None
    if owns_client:
        client = _build_check_client(timeout, proxy)

    try:
        prov = cls(settings=probe, client=client, timeout=timeout)
        try:
            prov.complete(list(_ONLINE_CHECK_PROMPT), max_tokens=8)
        finally:
            # Provider does not own the injected client; we close it below.
            pass
    except LLMAuthError:
        return ProviderCheckResult(
            False,
            CHECK_AUTH_ERROR,
            f"Ключ «{label}» не принят: ошибка авторизации (401/403).",
            masked,
        )
    except LLMRequestError as exc:
        status = _extract_http_status(str(exc))
        if status in (400, 404, 422):
            return ProviderCheckResult(
                False,
                CHECK_MODEL_ERROR,
                f"Ключ «{label}» принят, но модель «{model or '?'}» недоступна (HTTP {status}).",
                masked,
            )
        if status is not None:
            return ProviderCheckResult(
                False,
                CHECK_NETWORK_ERROR,
                f"Не удалось подключиться к «{label}» (HTTP {status}). Проверьте интернет/proxy.",
                masked,
            )
        return ProviderCheckResult(
            False,
            CHECK_NETWORK_ERROR,
            f"Не удалось подключиться к «{label}». Проверьте интернет/proxy.",
            masked,
        )
    except httpx.TimeoutException:
        return ProviderCheckResult(
            False,
            CHECK_NETWORK_ERROR,
            f"Таймаут подключения к «{label}». Проверьте интернет/proxy.",
            masked,
        )
    except httpx.HTTPError:
        return ProviderCheckResult(
            False,
            CHECK_NETWORK_ERROR,
            f"Сетевая ошибка при обращении к «{label}». Проверьте интернет/proxy.",
            masked,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ProviderCheckResult(
            False,
            CHECK_UNKNOWN_ERROR,
            f"Ошибка онлайн-проверки: {exc}",
            masked,
        )
    finally:
        if owns_client and client is not None:
            try:
                client.close()
            except Exception:
                pass

    return ProviderCheckResult(
        True,
        CHECK_OK,
        f"Онлайн-проверка «{label}» прошла. Модель «{model or '?'}» ответила.",
        masked,
    )


def _read_secret_from_env(key_name: str) -> str | None:
    """Read a secret value for ``key_name`` from ``.env`` then ``.env.local``.

    ``.env.local`` wins (read last). Used to resolve a key the user already
    saved without relying on in-process settings mutation. Never logs values.
    """
    from core.config import PROJECT_ROOT

    value: str | None = None
    for fname in (".env", ".env.local"):
        path = PROJECT_ROOT / fname
        try:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                k, v = stripped.split("=", 1)
                if k.strip() == key_name:
                    value = v.strip().strip('"').strip("'")
        except Exception as exc:
            logger.warning("Could not read %s for %s: %s", fname, key_name, exc)
    return value


@dataclass
class SettingsSnapshot:
    """Read-only snapshot of the settings relevant to the GUI."""

    provider: str = "openrouter"
    model: str = ""
    proxy: str | None = None
    output_dir: str = "./output"
    sessions_dir: str = "./sessions"
    openrouter_api_key: str | None = None
    zai_api_key: str | None = None
    groq_api_key: str | None = None
    ollama_base_url: str | None = None
    sessions: dict[str, str] = field(default_factory=dict)


class SettingsController:
    """Controller for the Settings tab.

    Keeps all UI controls as attributes and accepts injectable helpers so tests
    can run without touching real files, browser sessions, or the network.
    """

    def __init__(
        self,
        *,
        save_settings: SaveSettings | None = None,
        open_folder: FolderOpener | None = None,
        session_status: SessionChecker | None = None,
        on_status: Callable[[str], Any] | None = None,
        online_checker: OnlineChecker | None = None,
        check_timeout: float = DEFAULT_CHECK_TIMEOUT,
    ) -> None:
        self.save_settings = save_settings or _default_save_settings
        self.open_folder = open_folder or _default_open_folder
        self.session_status = session_status or _default_session_status
        self.on_status = on_status
        # Injectable so tests never hit the network. Defaults to the real
        # online check, which is only invoked on an explicit user click.
        self.online_checker = online_checker or check_provider_online
        self.check_timeout = check_timeout
        self.page: Any | None = None

        self.provider_dropdown: ft.Dropdown | None = None
        self.model_field: ft.TextField | None = None
        self.proxy_field: ft.TextField | None = None
        self.output_dir_field: ft.TextField | None = None
        self.sessions_dir_field: ft.TextField | None = None
        self.key_fields: dict[str, ft.TextField] = {}
        self.status_text: ft.Text | None = None
        self.local_status_text: ft.Text | None = None
        self.online_status_text: ft.Text | None = None
        self.key_status_text: ft.Text | None = None
        self.session_status_texts: dict[str, ft.Text] = {}
        self.content_container: ft.Container | None = None

        self._snapshot = SettingsSnapshot()

    def load_settings(self) -> SettingsSnapshot:
        """Load a snapshot from the current project config/env."""
        from core.config import settings

        sessions = {
            "1688": self.session_status("1688"),
            "taobao": self.session_status("taobao"),
            "chatgpt": self.session_status("chatgpt"),
        }
        self._snapshot = SettingsSnapshot(
            provider=settings.llm.provider,
            model=settings.llm.model,
            proxy=settings.proxy,
            output_dir=settings.paths.output,
            sessions_dir=settings.paths.sessions,
            openrouter_api_key=settings.openrouter_api_key,
            zai_api_key=settings.zai_api_key,
            groq_api_key=settings.groq_api_key,
            ollama_base_url=settings.ollama_base_url,
            sessions=sessions,
        )
        return self._snapshot

    def mask_secret(self, value: str | None) -> str:
        return mask_secret(value)

    def _push(self) -> None:
        """Push pending UI mutations to the live Flet client (no-op in tests)."""
        _safe_update_page(self.page)

    def _set_status(self, message: str) -> None:
        if self.status_text is not None:
            self.status_text.value = message
        if self.on_status is not None:
            try:
                self.on_status(message)
            except Exception:
                pass
        self._push()

    def _read_controls(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if self.provider_dropdown is not None:
            values["llm.provider"] = str(self.provider_dropdown.value or "").strip()
        if self.model_field is not None:
            values["llm.model"] = str(self.model_field.value or "").strip()
        if self.proxy_field is not None:
            values["proxy"] = str(self.proxy_field.value or "").strip()
        if self.output_dir_field is not None:
            values["paths.output"] = str(self.output_dir_field.value or "").strip()
        if self.sessions_dir_field is not None:
            values["paths.sessions"] = str(self.sessions_dir_field.value or "").strip()
        for provider, key_name in PROVIDER_SECRET_KEY.items():
            field_obj = self.key_fields.get(provider)
            if field_obj is None:
                continue
            raw = str(field_obj.value or "").strip()
            if raw:
                values[key_name] = raw
        return values

    def validate_settings(self, values: dict[str, str] | None = None) -> list[str]:
        """Validate user-editable settings and return a list of error messages."""
        if values is None:
            values = self._read_controls()
        errors: list[str] = []

        provider = values.get("llm.provider", "").strip().lower()
        if provider not in LLM_PROVIDERS:
            errors.append(f"Неизвестный LLM-провайдер: {provider!r}")

        model = values.get("llm.model", "").strip()
        if not model:
            errors.append("Не задана модель LLM")

        proxy = values.get("proxy", "").strip()
        if proxy:
            # Accept bare host:port as well as explicit scheme.
            check = proxy if "://" in proxy else "http://" + proxy
            from urllib.parse import urlparse

            parsed = urlparse(check)
            if not parsed.hostname:
                errors.append(f"Некорректный proxy: {proxy!r}")

        output_dir = values.get("paths.output", "").strip()
        sessions_dir = values.get("paths.sessions", "").strip()
        for name, path in (("output", output_dir), ("sessions", sessions_dir)):
            if not path:
                errors.append(f"Путь {name} не задан")
            elif not re.match(r"^[^<>:\"|?*]*$", path):
                # very rough Windows-reserved-char sanity check
                errors.append(f"Путь {name} содержит запрещённые символы")

        return errors

    def save_settings_to_disk(self, _event: ft.ControlEvent | None = None) -> bool:
        """Read controls, validate, save secrets to .env.local, refresh UI."""
        values = self._read_controls()
        errors = self.validate_settings(values)
        if errors:
            self._set_status("Ошибки: " + "; ".join(errors))
            return False

        self._set_status("Сохранение настроек...")
        ok = self.save_settings(values)
        if ok:
            self._set_status("Настройки сохранены в .env.local")
            self._refresh_session_statuses()
            self._refresh_key_status()
        else:
            self._set_status("Не удалось сохранить настройки")
        return ok

    def _refresh_session_statuses(self) -> None:
        for site, text_control in self.session_status_texts.items():
            text_control.value = self.session_status(site)
        self._push()

    # ----- status badges + secret resolution ------------------------------ #

    def _set_local_status(self, value: str) -> None:
        if self.local_status_text is not None:
            self.local_status_text.value = value
        self._push()

    def _set_online_status(self, value: str) -> None:
        if self.online_status_text is not None:
            self.online_status_text.value = value
        self._push()

    def _resolve_probe_secret(self, provider: str) -> str | None:
        """Resolve the secret/base_url to probe for ``provider``.

        Prefers a freshly-typed value from the UI field (the masked placeholder
        contains ``****`` and is never treated as a real key); otherwise falls
        back to the value persisted in ``.env`` / ``.env.local``. Never logs
        the value.
        """
        field_obj = self.key_fields.get(provider)
        field_val = str(field_obj.value or "").strip() if field_obj else ""
        if field_val and "****" not in field_val:
            return field_val
        key_name = PROVIDER_SECRET_KEY.get(provider)
        if key_name:
            return _read_secret_from_env(key_name)
        return None

    def _refresh_key_status(self) -> None:
        """Update the “Ключ” badge for the currently selected provider."""
        if self.key_status_text is None:
            return
        provider = ""
        if self.provider_dropdown is not None:
            provider = str(self.provider_dropdown.value or "").strip().lower()
        key_name = PROVIDER_SECRET_KEY.get(provider, provider)
        resolved = self._resolve_probe_secret(provider) if provider else None
        if resolved:
            self.key_status_text.value = f"{key_name}: найден {mask_secret(resolved)}"
        else:
            self.key_status_text.value = f"{key_name}: не найден"
        self._push()

    def _on_validate(self, _event: ft.ControlEvent | None = None) -> None:
        """Local-only validation (the “Проверить локально” button).

        Verifies provider/model/proxy/paths AND that a key for the selected
        provider is present. Never touches the network — that is the job of
        ``_on_check_online``. The status is explicit that the online check has
        not run, so it never reads as a silent “ключ рабочий”.
        """
        self._set_status("Локальная проверка…")
        values = self._read_controls()
        errors = self.validate_settings(values)
        provider = values.get("llm.provider", "").strip().lower()
        key_name = PROVIDER_SECRET_KEY.get(provider, provider)

        if errors:
            self._set_local_status("НЕ ПРОЙДЕНА")
            self._set_status("Проверка не пройдена: " + "; ".join(errors))
            return

        if provider == "chatgpt_web":
            self._set_local_status("OK")
            self._set_status(
                "Локальная проверка пройдена. Онлайн-проверка для chatgpt_web "
                "не реализована (браузерный провайдер)."
            )
            return

        resolved = self._resolve_probe_secret(provider)
        if not resolved:
            self._set_local_status("НЕТ КЛЮЧА")
            self._set_status(
                f"Не найден {key_name}. Введите ключ и нажмите «Сохранить», "
                f"затем «Проверить ключ онлайн»."
            )
            return

        self._set_local_status("OK")
        self._refresh_key_status()
        self._set_status(
            f"Локальная проверка пройдена. Ключ найден: {key_name} "
            f"{mask_secret(resolved)}. Онлайн-проверка ещё не выполнялась — "
            f"нажмите «Проверить ключ онлайн»."
        )

    def _on_check_online(self, _event: ft.ControlEvent | None = None) -> None:
        """Online provider check (the “Проверить ключ онлайн” button).

        Performs one minimal chat-completion request to the selected provider.
        Requires local validation to pass and a key to be present. The key is
        never printed — only masked. This is the ONLY place the app contacts an
        LLM provider from the Settings tab, and only on an explicit click.
        """
        values = self._read_controls()
        provider = values.get("llm.provider", "").strip().lower()
        model = values.get("llm.model", "").strip()
        proxy = values.get("proxy", "").strip() or None
        key_name = PROVIDER_SECRET_KEY.get(provider, provider)

        errors = self.validate_settings(values)
        if errors:
            self._set_online_status("НЕВОЗМОЖНА")
            self._set_status(
                "Сначала исправьте локальные ошибки: " + "; ".join(errors)
            )
            return

        if provider == "chatgpt_web":
            self._set_online_status("НЕ РЕАЛИЗОВАНА")
            self._set_status(
                "Онлайн-проверка для chatgpt_web не реализована (браузерный "
                "провайдер). Локальная проверка пройдена."
            )
            return

        resolved = self._resolve_probe_secret(provider)
        if not resolved:
            self._set_online_status("НЕТ КЛЮЧА")
            self._set_status(
                f"Не найден {key_name}. Введите ключ и нажмите «Сохранить», "
                f"затем повторите онлайн-проверку."
            )
            return

        self._set_status("Онлайн-проверка… (может занять несколько секунд)")
        self._set_online_status("ВЫПОЛНЯЕТСЯ…")
        try:
            result = self.online_checker(
                provider=provider,
                model=model,
                api_key=resolved if provider != "ollama" else None,
                base_url=resolved if provider == "ollama" else None,
                proxy=proxy,
                timeout=self.check_timeout,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_online_status("ОШИБКА")
            self._set_status(f"Ошибка онлайн-проверки: {exc}")
            return

        self._set_online_status("OK" if result.ok else "ОШИБКА")
        self._set_status(result.message)

    def _on_open_output(self, _event: ft.ControlEvent | None = None) -> None:
        path = "./output"
        if self.output_dir_field is not None:
            path = self.output_dir_field.value or path
        self._set_status("Открываю папку output…")
        ok = self.open_folder(path)
        self._set_status("Открыта папка output" if ok else "Не удалось открыть output")

    def _on_open_sessions(self, _event: ft.ControlEvent | None = None) -> None:
        path = "./sessions"
        if self.sessions_dir_field is not None:
            path = self.sessions_dir_field.value or path
        self._set_status("Открываю папку sessions…")
        ok = self.open_folder(path)
        self._set_status(
            "Открыта папка sessions" if ok else "Не удалось открыть sessions"
        )

    def _build_provider_row(self) -> ft.Row:
        snapshot = self._snapshot
        self.provider_dropdown = ft.Dropdown(
            label="LLM провайдер",
            options=[ft.dropdown.Option(p) for p in LLM_PROVIDERS],
            value=snapshot.provider if snapshot.provider in LLM_PROVIDERS else "openrouter",
            expand=True,
        )
        self.model_field = ft.TextField(
            label="Модель",
            value=snapshot.model,
            hint_text="например openai/gpt-4o-mini",
            expand=True,
        )
        return ft.Row(
            [self.provider_dropdown, self.model_field],
            spacing=12,
        )

    def _build_proxy_row(self) -> ft.Row:
        snapshot = self._snapshot
        self.proxy_field = ft.TextField(
            label="Прокси",
            value=snapshot.proxy or "",
            hint_text="http://user:pass@host:port или socks5://host:port",
            expand=True,
        )
        return ft.Row([self.proxy_field], spacing=12)

    def _build_paths_row(self) -> ft.Row:
        snapshot = self._snapshot
        self.output_dir_field = ft.TextField(
            label="Папка output",
            value=snapshot.output_dir,
            expand=True,
        )
        self.sessions_dir_field = ft.TextField(
            label="Папка sessions",
            value=snapshot.sessions_dir,
            expand=True,
        )
        return ft.Row(
            [self.output_dir_field, self.sessions_dir_field],
            spacing=12,
        )

    def _build_keys_section(self) -> ft.Column:
        snapshot = self._snapshot
        key_values = {
            "openrouter": snapshot.openrouter_api_key,
            "zai": snapshot.zai_api_key,
            "groq": snapshot.groq_api_key,
            "ollama": snapshot.ollama_base_url,
        }
        rows: list[ft.Control] = []
        self.key_fields.clear()
        for provider in LLM_PROVIDERS:
            if provider not in PROVIDER_SECRET_KEY:
                continue
            key_name = PROVIDER_SECRET_KEY[provider]
            current = key_values.get(provider)
            field_obj = ft.TextField(
                label=f"{key_name} (хранится в .env.local)",
                value=self.mask_secret(current),
                password=True,
                can_reveal_password=False,
                hint_text="введите ключ для сохранения",
                expand=True,
            )
            self.key_fields[provider] = field_obj
            rows.append(field_obj)
        return ft.Column(
            [ft.Text("Ключи / сессии", weight=ft.FontWeight.W_600)] + rows,
            spacing=8,
        )

    def _build_sessions_section(self) -> ft.Column:
        snapshot = self._snapshot
        rows: list[ft.Control] = []
        self.session_status_texts.clear()
        for site in SESSION_SITES:
            status = snapshot.sessions.get(site, "неизвестно")
            status_text = ft.Text(status, size=12, color=ft.Colors.ON_SURFACE_VARIANT)
            self.session_status_texts[site] = status_text
            rows.append(
                ft.Row(
                    [
                        ft.Text(site.capitalize(), width=80),
                        status_text,
                    ],
                    spacing=8,
                )
            )
        return ft.Column(
            [ft.Text("Статус сессий", weight=ft.FontWeight.W_600)] + rows,
            spacing=8,
        )

    def _build_status_checks_section(self) -> ft.Column:
        """Badges: local-check / online-check / key status (last action below)."""
        self.local_status_text = ft.Text(
            "не выполнялась", size=12, color=ft.Colors.ON_SURFACE_VARIANT
        )
        self.online_status_text = ft.Text(
            "не выполнялась", size=12, color=ft.Colors.ON_SURFACE_VARIANT
        )
        self.key_status_text = ft.Text(
            "—", size=12, color=ft.Colors.ON_SURFACE_VARIANT
        )
        return ft.Column(
            [
                ft.Text("Статус проверок", weight=ft.FontWeight.W_600),
                ft.Row(
                    [ft.Text("Локальная проверка", width=160), self.local_status_text],
                    spacing=8,
                ),
                ft.Row(
                    [ft.Text("Онлайн-проверка", width=160), self.online_status_text],
                    spacing=8,
                ),
                ft.Row(
                    [ft.Text("Ключ", width=160), self.key_status_text],
                    spacing=8,
                ),
            ],
            spacing=8,
        )

    def _build_actions_section(self) -> ft.Row:
        return ft.Row(
            [
                ft.Button(
                    "Сохранить",
                    icon=ft.Icons.SAVE,
                    on_click=self.save_settings_to_disk,
                ),
                ft.Button(
                    "Проверить локально",
                    icon=ft.Icons.FACT_CHECK,
                    on_click=self._on_validate,
                ),
                ft.Button(
                    "Проверить ключ онлайн",
                    icon=ft.Icons.CLOUD_DONE,
                    on_click=self._on_check_online,
                ),
                ft.Button(
                    "Открыть output",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=self._on_open_output,
                ),
                ft.Button(
                    "Открыть sessions",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=self._on_open_sessions,
                ),
            ],
            spacing=12,
            wrap=True,
        )

    def build_content(self, page: ft.Page) -> ft.Container:
        """Build the settings section content as a standalone control."""
        self.page = page
        self.load_settings()

        self.status_text = ft.Text(
            "Готов к настройке",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        content = ft.Column(
            [
                ft.Text("Настройки", weight=ft.FontWeight.W_600, size=18),
                self._build_provider_row(),
                self._build_proxy_row(),
                self._build_paths_row(),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                self._build_keys_section(),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                self._build_sessions_section(),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                self._build_status_checks_section(),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                self._build_actions_section(),
                ft.Text("Последнее действие:", size=11, weight=ft.FontWeight.W_500),
                self.status_text,
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        container = ft.Container(content=content, padding=16, expand=True)
        self.content_container = container
        # Seed the key badge from whatever is already saved in .env/.env.local.
        self._refresh_key_status()
        return container

    def build_tab(self, _page: ft.Page) -> ft.Tab:
        """Legacy ft.Tab wrapper (kept for backward compatibility)."""
        container = self.build_content(_page)
        tab = ft.Tab(label="Настройки")
        tab.content = container
        return tab


def build_settings_tab(
    page: ft.Page,
    *,
    save_settings: SaveSettings | None = None,
    open_folder: FolderOpener | None = None,
    session_status: SessionChecker | None = None,
    online_checker: OnlineChecker | None = None,
) -> tuple[ft.Tab, SettingsController]:
    """Build the Settings tab with dependency injection for tests."""
    controller = SettingsController(
        save_settings=save_settings,
        open_folder=open_folder,
        session_status=session_status,
        online_checker=online_checker,
    )
    return controller.build_tab(page), controller
