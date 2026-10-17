# lutris_importer.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

LUTRIS_DB_PATHS = [
    Path.home() / ".local" / "share" / "lutris" / "pga.db",
    Path.home() / ".var" / "app" / "net.lutris.Lutris" / "data" / "lutris" / "pga.db",
]

LUTRIS_COVER_DIRS = [
    Path.home() / ".local" / "share" / "lutris" / "coverart",
    Path.home() / ".var" / "app" / "net.lutris.Lutris" / "data" / "lutris" / "coverart",
    Path.home() / ".cache" / "lutris" / "coverart",
]

LUTRIS_BANNER_DIRS = [
    Path.home() / ".local" / "share" / "lutris" / "banners",
    Path.home() / ".var" / "app" / "net.lutris.Lutris" / "data" / "lutris" / "banners",
    Path.home() / ".cache" / "lutris" / "banners",
]

HEROIC_CONFIG_DIRS = [
    Path.home() / ".config" / "heroic",
    Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic",
]


RUNNER_NAMES = {"linux": "Linux", "wine": "Wine", "steam": "Steam", "flatpak": "Flatpak", "pcsx2": "PCSX2"}


def runner_label(runner: str) -> str:
    """Lutris-style runner name (Linux, Wine, Steam, Flatpak, ...)."""
    return RUNNER_NAMES.get(runner.lower(), runner.title()) if runner else ""


def find_lutris_db() -> Optional[Path]:
    """Finds the local Lutris SQLite database path if available."""
    for p in LUTRIS_DB_PATHS:
        if p.exists():
            return p
    return None


def get_lutris_games() -> List[Dict[str, Any]]:
    """
    Reads games from the Lutris PGA database, including playtime, platform,
    categories, and local cover art.
    """
    db_path = find_lutris_db()
    if not db_path:
        return []

    try:
        # read-only so a running Lutris holding the DB lock cannot make the import fail
        conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Load categories dictionary: id -> name
        categories_map = {}
        try:
            cursor.execute("SELECT id, name FROM categories")
            for row in cursor.fetchall():
                categories_map[row["id"]] = row["name"]
        except Exception:
            pass

        # Load game-to-category associations
        game_categories = {}
        try:
            cursor.execute("SELECT game_id, category_id FROM games_categories")
            for row in cursor.fetchall():
                c_name = categories_map.get(row["category_id"])
                if c_name:
                    game_categories.setdefault(row["game_id"], []).append(c_name)
        except Exception:
            pass

        cursor.execute(
            """
            SELECT id, name, slug, runner, platform, service, service_id, playtime, installed
            FROM games
            ORDER BY name ASC
            """
        )
        rows = cursor.fetchall()

        games: List[Dict[str, Any]] = []
        for r in rows:
            game_id = r["id"]
            name = r["name"] or "Sem Título"
            slug = r["slug"] or ""
            runner = r["runner"] or ""
            platform = r["platform"] or "Linux"
            service = r["service"] or ""
            service_id = r["service_id"]
            raw_playtime = float(r["playtime"] or 0)
            playtime = round(raw_playtime, 1)
            installed = bool(r["installed"])
            cats = game_categories.get(game_id, [])

            # Check cover in Lutris coverart directories
            cover_path = None
            if slug:
                for cdir in LUTRIS_COVER_DIRS:
                    candidate = cdir / f"{slug}.jpg"
                    if candidate.exists():
                        cover_path = str(candidate)
                        break
                    candidate_png = cdir / f"{slug}.png"
                    if candidate_png.exists():
                        cover_path = str(candidate_png)
                        break

            # Check banner in Lutris banners directories
            banner_path = None
            if slug:
                for bdir in LUTRIS_BANNER_DIRS:
                    candidate = bdir / f"{slug}.jpg"
                    if candidate.exists():
                        banner_path = str(candidate)
                        break
                    candidate_png = bdir / f"{slug}.png"
                    if candidate_png.exists():
                        banner_path = str(candidate_png)
                        break

            status = "playing" if playtime > 0.0 else "backlog"

            # Parse Steam AppID if available
            steam_appid = None
            if service == "steam" and service_id and str(service_id).isdigit():
                steam_appid = int(service_id)

            games.append({
                "id": f"lutris_{game_id}",
                "title": name,
                "slug": slug,
                "tier": "UNRANKED",
                "source": "lutris",
                "runner": runner,
                "runner_name": runner_label(runner),
                "platform": platform,
                "service": service,
                "steam_appid": steam_appid,
                "playtime": playtime,
                "installed": installed,
                "status": status,
                "categories": cats,
                "cover_vertical": cover_path,
                "cover_horizontal": banner_path,
                "cover_path": cover_path or banner_path,
                "company": "Lutris Library",
                "franchise": name,
                "genres": [],
            })

        conn.close()
        return games
    except Exception as e:
        print(f"[Lutris Importer] Error querying database {db_path}: {e}")
        return []


def _heroic_game(prefix: str, app_name: str, title: str, store: str, platform: str, service: str, default_platform: str) -> Dict[str, Any]:
    windows = str(platform or default_platform).lower() == "windows"
    return {
        "id": f"heroic_{prefix}_{app_name}",
        "title": title,
        "tier": "UNRANKED",
        "source": "heroic",
        "platform": "Windows" if windows else "Linux",
        "runner": "wine" if windows else "linux",
        "runner_name": "Wine" if windows else "Linux",
        "service": service,
        "playtime": 0.0,
        "installed": True,
        "status": "backlog",
        "categories": [store],
        "cover_vertical": None,
        "cover_horizontal": None,
        "cover_path": None,
        "company": store,
        "franchise": title,
        "genres": [],
    }


def get_heroic_games() -> List[Dict[str, Any]]:
    """Scans for Heroic Games Launcher installations and installed games (Epic via Legendary, GOG)."""
    games: List[Dict[str, Any]] = []
    for h_dir in HEROIC_CONFIG_DIRS:
        legendary = h_dir / "legendaryConfig" / "legendary" / "installed.json"
        gog = h_dir / "gog_store" / "installed.json"
        try:
            if legendary.exists():
                with open(legendary, "r", encoding="utf-8") as f:
                    for app_name, info in json.load(f).items():
                        games.append(_heroic_game("epic", app_name, info.get("title", app_name), "Epic Games",
                                                  info.get("platform"), "epic", "Windows"))
            if gog.exists():
                with open(gog, "r", encoding="utf-8") as f:
                    for info in json.load(f).get("installed", []):
                        app_name = info.get("appName", "")
                        games.append(_heroic_game("gog", app_name, info.get("title", app_name or "GOG Game"), "GOG",
                                                  info.get("platform"), "gog", "windows"))
        except Exception as e:
            print(f"[Heroic Importer] Error reading {h_dir}: {e}")

    return games
