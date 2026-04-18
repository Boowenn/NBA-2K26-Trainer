"""Runtime resource helpers for local and packaged builds."""

from __future__ import annotations

import os
import sys


def resource_path(*parts: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, *parts)


def app_icon_path() -> str:
    return resource_path("assets", "trainer_icon.ico")
