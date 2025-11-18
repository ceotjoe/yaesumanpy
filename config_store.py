from __future__ import annotations

import json
from pathlib import Path

from data_model import MainConfig


CONFIG_DIR = Path.home() / ".yaesuman"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> MainConfig:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return MainConfig(
                callsign=data.get("callsign", "EA7EE"),
                gps=data.get("gps", "N037126800W007038500"),
                quality=data.get("quality", "LOW"),
                overlay_url=data.get("overlay_url", ""),
            ).normalized()
        except (ValueError, OSError):
            pass
    return MainConfig().normalized()


def save_config(config: MainConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(
            {
                "callsign": config.callsign,
                "gps": config.gps,
                "quality": config.quality,
                "overlay_url": config.overlay_url,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
