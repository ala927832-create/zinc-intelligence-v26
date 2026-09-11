from __future__ import annotations

from .utils import CONFIG_DIR, read_json


def load_settings() -> dict:
    return read_json(CONFIG_DIR / "settings.json", {})
