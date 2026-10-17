"""User-facing string catalog and locale persistence."""

from __future__ import annotations

import json
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
SETTINGS_DIR = Path.home() / ".cfd-simulation"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "fr", "pl", "zh")
DEFAULT_LOCALE = "en"

_catalog: dict[str, str] = {}
_locale: str = DEFAULT_LOCALE


def get_locale() -> str:
    return _locale


def _load_catalog(locale: str) -> None:
    global _catalog
    path = LOCALES_DIR / f"{locale}.json"
    if not path.is_file():
        path = LOCALES_DIR / f"{DEFAULT_LOCALE}.json"
    with path.open(encoding="utf-8") as fh:
        _catalog = json.load(fh)


def set_locale(locale: str) -> None:
    global _locale
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE
    _locale = locale
    _load_catalog(_locale)


def t(key: str) -> str:
    return _catalog.get(key, key)


def locale_label(code: str) -> str:
    return t(f"locale.{code}")


def load_settings() -> dict:
    if not SETTINGS_FILE.is_file():
        return {}
    try:
        with SETTINGS_FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(data: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with SETTINGS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def init_from_settings() -> str:
    settings = load_settings()
    raw = settings.get("locale", DEFAULT_LOCALE)
    locale = raw if raw in SUPPORTED_LOCALES else DEFAULT_LOCALE
    set_locale(locale)
    return locale
