"""Configuration management via config.yaml."""

from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
DATA_DIR = ROOT_DIR / "data"
SOURCES_DIR = DATA_DIR / "sources"
DB_DIR = DATA_DIR / "db"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_active_subject() -> str:
    config = load_config()
    return config["active_subject"]


def get_subject_profile(name: str | None = None) -> dict[str, Any]:
    config = load_config()
    name = name or config["active_subject"]
    subjects = config.get("subjects", {})
    if name not in subjects:
        raise KeyError(f"Subject '{name}' not found in config.yaml")
    return subjects[name]


def get_db_path(name: str | None = None) -> Path:
    config = load_config()
    name = name or config["active_subject"]
    return DB_DIR / f"{name}.db"


def list_subjects() -> dict[str, dict[str, Any]]:
    config = load_config()
    return config.get("subjects", {})


def switch_subject(name: str) -> None:
    config = load_config()
    if name not in config.get("subjects", {}):
        raise KeyError(f"Subject '{name}' not found in config.yaml")
    config["active_subject"] = name
    save_config(config)
