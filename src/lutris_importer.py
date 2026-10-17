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
        conn = sqlite3.connect(str(db_path))
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

            # Infer initial status from playtime
            if playtime >= 25.0:
                status = "completed"
            elif playtime > 0.0:
                status = "playing"
            else:
                status = "backlog"

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


def get_heroic_games() -> List[Dict[str, Any]]:
    """
    Scans for Heroic Games Launcher installations and installed games.
    """
    games: List[Dict[str, Any]] = []
    for h_dir in HEROIC_CONFIG_DIRS:
        if not h_dir.exists():
            continue

        # 1. Legendary (Epic Games)
        legendary_installed = h_dir / "legendaryConfig" / "legendary" / "installed.json"
        if legendary_installed.exists():
            try:
                with open(legendary_installed, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for app_name, info in data.items():
                    title = info.get("title", app_name)
                    games.append({
                        "id": f"heroic_epic_{app_name}",
                        "title": title,
                        "tier": "UNRANKED",
                        "source": "heroic",
                        "platform": "Epic Games",
                        "runner": "Heroic",
                        "playtime": 0.0,
                        "installed": True,
                        "status": "backlog",
                        "categories": ["Epic Games"],
                        "cover_vertical": None,
                        "cover_horizontal": None,
                        "cover_path": None,
                        "company": "Epic Games",
                        "franchise": title,
                        "genres": [],
                    })
            except Exception as e:
                print(f"[Heroic Importer] Error reading Legendary config: {e}")

        # 2. GOG installed
        gog_installed = h_dir / "gog_store" / "installed.json"
        if gog_installed.exists():
            try:
                with open(gog_installed, "r", encoding="utf-8") as f:
                    data = json.load(f)
                installed_list = data.get("installed", [])
                if isinstance(installed_list, list):
                    for info in installed_list:
                        app_name = info.get("appName", "")
                        title = info.get("title", app_name or "GOG Game")
                        games.append({
                            "id": f"heroic_gog_{app_name}",
                            "title": title,
                            "tier": "UNRANKED",
                            "source": "heroic",
                            "platform": "GOG",
                            "runner": "Heroic",
                            "playtime": 0.0,
                            "installed": True,
                            "status": "backlog",
                            "categories": ["GOG"],
                            "cover_vertical": None,
                            "cover_horizontal": None,
                            "cover_path": None,
                            "company": "GOG",
                            "franchise": title,
                            "genres": [],
                        })
            except Exception as e:
                print(f"[Heroic Importer] Error reading GOG config: {e}")

    return games
