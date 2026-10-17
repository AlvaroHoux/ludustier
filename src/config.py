# config.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import copy
import shutil
from pathlib import Path
from typing import Dict, List, Any

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ludustier"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ludustier"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ludustier" / "covers"

CONFIG_FILE = CONFIG_DIR / "config.json"
TIERLIST_FILE = DATA_DIR / "tierlist.json"

DEFAULT_TIERS: List[Dict[str, str]] = [
    {"id": "S", "name": "S", "color": "#ff7f7f", "text_color": "#000000"},
    {"id": "A", "name": "A", "color": "#ffbf7f", "text_color": "#000000"},
    {"id": "B", "name": "B", "color": "#ffff7f", "text_color": "#000000"},
    {"id": "C", "name": "C", "color": "#7fff7f", "text_color": "#000000"},
    {"id": "D", "name": "D", "color": "#7fbfff", "text_color": "#000000"},
]

UNRANKED_TIER: Dict[str, str] = {
    "id": "UNRANKED",
    "name": "Banco / Não Ranqueado",
    "color": "#9e9e9e",
    "text_color": "#ffffff",
}

# Compatibility reference for legacy code expecting TIER_DEFINITIONS
TIER_DEFINITIONS = DEFAULT_TIERS + [UNRANKED_TIER]

TIER_COLOR_PALETTE = [
    {"name": "Vermelho", "color": "#ff7f7f", "text_color": "#000000"},
    {"name": "Laranja", "color": "#ffbf7f", "text_color": "#000000"},
    {"name": "Amarelo", "color": "#ffff7f", "text_color": "#000000"},
    {"name": "Verde Claro", "color": "#bfff7f", "text_color": "#000000"},
    {"name": "Verde", "color": "#7fff7f", "text_color": "#000000"},
    {"name": "Ciano", "color": "#7fffff", "text_color": "#000000"},
    {"name": "Azul Claro", "color": "#7fbfff", "text_color": "#000000"},
    {"name": "Azul", "color": "#7f7fff", "text_color": "#ffffff"},
    {"name": "Roxo", "color": "#bf7fff", "text_color": "#ffffff"},
    {"name": "Rosa / Magenta", "color": "#ff7fbf", "text_color": "#000000"},
    {"name": "Ouro", "color": "#ffd700", "text_color": "#000000"},
    {"name": "Cinza", "color": "#808080", "text_color": "#ffffff"},
]

DEFAULT_VIEW_SETTINGS = {
    "zoom_level": 3,      # 1: XS, 2: S, 3: M, 4: L, 5: XL
    "view_mode": "poster", # "poster" (vertical 600x900), "header" (banner), "icon" (compact)
    "show_title": True,     # info shown on each card
    "show_playtime": True,
    "show_status": True,
    "show_platform": True,
}

STATUS_CHOICES = [
    {"id": "backlog", "name": "Para Começar", "icon": "appointment-soon-symbolic"},
    {"id": "playing", "name": "Em Andamento", "icon": "media-playback-start-symbolic"},
    {"id": "completed", "name": "Finalizado", "icon": "emblem-ok-symbolic"},
    {"id": "platinum", "name": "Platinado", "icon": "starred-symbolic"},
    {"id": "dropped", "name": "Abandonado", "icon": "process-stop-symbolic"},
]

DEFAULT_CATEGORIES: List[str] = ["Favoritos", "Cooperativo", "Em Rotação"]


def ensure_directories():
    """Ensure user data and cache directories exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_directories()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"steamgriddb_api_key": ""}


def save_config(config_data: dict):
    ensure_directories()
    _write_json_atomic(config_data, CONFIG_FILE)
    os.chmod(CONFIG_FILE, 0o600)  # holds the API key


def get_steamgriddb_key() -> str:
    return load_config().get("steamgriddb_api_key", "").strip()


def set_steamgriddb_key(key: str):
    cfg = load_config()
    cfg["steamgriddb_api_key"] = key.strip()
    save_config(cfg)


def _write_json_atomic(data: dict, filepath: Path):
    """Writes next to the target and renames, so a crash never leaves a half-written file."""
    tmp = filepath.with_suffix(filepath.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, filepath)


def normalize_tierlist(data: Any) -> dict:
    """Fills missing keys with defaults and drops games that cannot be shown (no id/title)."""
    if not isinstance(data, dict):
        data = {}

    if "title" not in data or not data["title"]:
        data["title"] = "Minha Tier List de Jogos"

    if "tiers" not in data or not isinstance(data["tiers"], list) or len(data["tiers"]) == 0:
        data["tiers"] = copy.deepcopy(DEFAULT_TIERS)

    if "games" not in data or not isinstance(data["games"], list):
        data["games"] = []
    data["games"] = [g for g in data["games"] if isinstance(g, dict) and g.get("id") and g.get("title")]

    if "categories" not in data or not isinstance(data["categories"], list):
        data["categories"] = copy.deepcopy(DEFAULT_CATEGORIES)

    if "view_settings" not in data or not isinstance(data["view_settings"], dict):
        data["view_settings"] = copy.deepcopy(DEFAULT_VIEW_SETTINGS)
    else:
        for k, v in DEFAULT_VIEW_SETTINGS.items():
            if k not in data["view_settings"]:
                data["view_settings"][k] = v

    return data


def load_tierlist(filepath: Path = TIERLIST_FILE) -> dict:
    ensure_directories()
    data: Any = {}
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # Keep the unreadable file: the next save would otherwise overwrite it with an empty list
            shutil.copy2(filepath, filepath.with_suffix(filepath.suffix + ".corrupt"))
            data = {}
    return normalize_tierlist(data)


def backup_tierlist(filepath: Path = TIERLIST_FILE):
    if filepath.exists():
        shutil.copy2(filepath, filepath.with_suffix(filepath.suffix + ".bak"))


def save_tierlist(data: dict, filepath: Path = TIERLIST_FILE):
    ensure_directories()
    _write_json_atomic(data, filepath)
