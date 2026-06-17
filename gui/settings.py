from __future__ import annotations

import logging
import re
import subprocess
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import flet as ft

logger = logging.getLogger(__name__)

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
    ) -> None:
        self.save_settings = save_settings or _default_save_settings
        self.open_folder = open_folder or _default_open_folder
        self.session_status = session_status or _default_session_status
        self.on_status = on_status

        self.provider_dropdown: ft.Dropdown | None = None
        self.model_field: ft.TextField | None = None
        self.proxy_field: ft.TextField | None = None
        self.output_dir_field: ft.TextField | None = None
        self.sessions_dir_field: ft.TextField | None = None
        self.key_fields: dict[str, ft.TextField] = {}
        self.status_text: ft.Text | None = None
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

    def _set_status(self, message: str) -> None:
        if self.status_text is not None:
            self.status_text.value = message
        if self.on_status is not None:
            try:
                self.on_status(message)
            except Exception:
                pass

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
            self._set_status("Настройки сохранены")
            self._refresh_session_statuses()
        else:
            self._set_status("Не удалось сохранить настройки")
        return ok

    def _refresh_session_statuses(self) -> None:
        for site, text_control in self.session_status_texts.items():
            text_control.value = self.session_status(site)

    def _on_validate(self, _event: ft.ControlEvent | None = None) -> None:
        errors = self.validate_settings()
        if errors:
            self._set_status("Проверка не пройдена: " + "; ".join(errors))
        else:
            self._set_status("Настройки корректны")

    def _on_open_output(self, _event: ft.ControlEvent | None = None) -> None:
        path = "./output"
        if self.output_dir_field is not None:
            path = self.output_dir_field.value or path
        ok = self.open_folder(path)
        self._set_status("Открыта папка output" if ok else "Не удалось открыть output")

    def _on_open_sessions(self, _event: ft.ControlEvent | None = None) -> None:
        path = "./sessions"
        if self.sessions_dir_field is not None:
            path = self.sessions_dir_field.value or path
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
            status_text = ft.Text(status, size=12, color=ft.Colors.GREY_400)
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

    def _build_actions_section(self) -> ft.Row:
        return ft.Row(
            [
                ft.Button(
                    "Проверить настройки",
                    icon=ft.Icons.VERIFIED,
                    on_click=self._on_validate,
                ),
                ft.Button(
                    "Сохранить",
                    icon=ft.Icons.SAVE,
                    on_click=self.save_settings_to_disk,
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

    def build_content(self, _page: ft.Page) -> ft.Container:
        """Build the settings section content as a standalone control."""
        self.load_settings()

        self.status_text = ft.Text(
            "Готов к настройке",
            size=12,
            color=ft.Colors.GREY_400,
        )

        content = ft.Column(
            [
                ft.Text("Настройки", weight=ft.FontWeight.W_600, size=18),
                self._build_provider_row(),
                self._build_proxy_row(),
                self._build_paths_row(),
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                self._build_keys_section(),
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                self._build_sessions_section(),
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                self._build_actions_section(),
                self.status_text,
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        container = ft.Container(content=content, padding=16, expand=True)
        self.content_container = container
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
) -> tuple[ft.Tab, SettingsController]:
    """Build the Settings tab with dependency injection for tests."""
    controller = SettingsController(
        save_settings=save_settings,
        open_folder=open_folder,
        session_status=session_status,
    )
    return controller.build_tab(page), controller
