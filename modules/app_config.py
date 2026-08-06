from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def resolve_runtime_root(base_dir: Path, env: dict[str, str] | None = None) -> Path:
    env = env or os.environ
    candidates = []
    local_app_data = env.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(Path(local_app_data) / "ArezOne")
    candidates.append(base_dir / "runtime")
    candidates.append(base_dir)
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    return base_dir / "runtime"


def _resolve_user_dir(base_dir: Path) -> Path:
    return resolve_runtime_root(base_dir)


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    USER_DIR = _resolve_user_dir(BASE_DIR)
    DATA_DIR = USER_DIR / "data"
    CONFIG_DIR = USER_DIR / "config"
    ASSETS_DIR = BASE_DIR / "assets"
else:
    BASE_DIR = Path(__file__).resolve().parents[1]
    DATA_DIR = BASE_DIR / "data"
    CONFIG_DIR = BASE_DIR / "config"
    ASSETS_DIR = BASE_DIR / "assets"
CONFIG_PATH = CONFIG_DIR / "settings.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "app_name": "AREZONE",
    "business_name": "AREZONE",
    "version": "v2.0 Voicetest",
    "slogan": "POS rapido, claro y profesional",
    "authors": "Alejandro Sanchez Quimbayo",
    "support_email": "AREZSUPRIV@GMAIL.COM",
    "default_seller": "GLORIA MENDIETA",
    "currency": "COP",
    "invoice_prefix": "POS-",
    "source_excel": "RPTARJETA_TO_XLS.xlsx",
}


def _migrate_legacy_config() -> None:
    try:
        legacy_config = Path(__file__).resolve().parents[1] / "config" / "settings.json"
        if legacy_config.exists() and not CONFIG_PATH.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(legacy_config.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass


def ensure_app_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_config()


def load_config() -> dict[str, Any]:
    ensure_app_dirs()
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    config = DEFAULT_CONFIG.copy()
    config.update({k: v for k, v in data.items() if v is not None})
    return config


def save_config(config: dict[str, Any]) -> None:
    ensure_app_dirs()
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    CONFIG_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
