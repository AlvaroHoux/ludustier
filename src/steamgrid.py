# steamgrid.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Dict, Optional, Any
from .config import CACHE_DIR, get_steamgriddb_key


USER_AGENT = "LudusTier/0.1.0 (GTK 4 Linux; +https://github.com/AlvaroHoux/ludustier)"

COMMON_FRANCHISES = [
    "Resident Evil", "Silent Hill", "Final Fantasy", "The Witcher", "Dark Souls",
    "Grand Theft Auto", "Monster Hunter", "Devil May Cry", "Street Fighter",
    "The Elder Scrolls", "Fallout", "Assassin's Creed", "Far Cry", "Call of Duty",
    "Battlefield", "Halo", "Gears of War", "God of War", "Tomb Raider", "Mass Effect",
    "Dragon Age", "Persona", "Shin Megami Tensei", "Yakuza", "Like a Dragon",
    "Kingdom Hearts", "Metal Gear", "Borderlands", "BioShock", "Dishonored",
    "Doom", "Wolfenstein", "Quake", "Need for Speed", "Dead Space", "Civilization",
    "Total War", "Age of Empires", "The Sims", "SimCity", "Diablo", "Warcraft",
    "StarCraft", "Overwatch", "Hollow Knight", "Hades", "Mega Man", "Castlevania",
    "Super Mario", "The Legend of Zelda", "Metroid", "Pokemon", "Kirby", "Donkey Kong",
    "Sonic", "Tekken", "Mortal Kombat", "Guilty Gear", "Crash Bandicoot", "Spyro",
    "Rayman", "Half-Life", "Portal", "Counter-Strike", "Left 4 Dead", "Team Fortress",
    "Dota", "Baldur's Gate", "Divinity", "Pillars of Eternity", "Dragon Quest",
    "Tales of", "Star Wars", "Batman: Arkham", "Spider-Man", "Uncharted", "The Last of Us",
    "Horizon", "Gran Turismo", "Forza", "Red Dead", "Max Payne", "Alan Wake", "Control",
    "S.T.A.L.K.E.R.", "Dying Light", "Metro", "Deus Ex", "Hitman", "Payday", "Arma",
    "Kingdom Come", "Watch Dogs", "Tom Clancy", "Splinter Cell", "Rainbow Six", "Ghost Recon"
]


def normalize_company(raw: str) -> str:
    """Normalizes developer or publisher corporate names to a clean company brand."""
    if not raw:
        return "Independente"
    raw_str = raw.strip()
    clean = re.sub(
        r'[\s,]*(?:Co\.,\s*Ltd\.?|Inc\.?|LLC\.?|Corp\.?|Corporation|Interactive|Entertainment|Studios?|Software|Games?)\.?$',
        '',
        raw_str,
        flags=re.IGNORECASE
    ).strip()

    lower = clean.lower()
    if "capcom" in lower:
        return "Capcom"
    if "fromsoftware" in lower:
        return "FromSoftware"
    if "cd projekt" in lower:
        return "CD Projekt Red"
    if "square enix" in lower:
        return "Square Enix"
    if "bandai namco" in lower:
        return "Bandai Namco"
    if "electronic arts" in lower or lower == "ea":
        return "Electronic Arts"
    if "ubisoft" in lower:
        return "Ubisoft"
    if "bethesda" in lower:
        return "Bethesda"
    if "valve" in lower:
        return "Valve"
    if "konami" in lower:
        return "Konami"
    if "sega" in lower:
        return "Sega"
    if "supergiant" in lower:
        return "Supergiant Games"
    if "rockstar" in lower:
        return "Rockstar Games"
    if "nintendo" in lower:
        return "Nintendo"
    if "playstation" in lower or "sony" in lower:
        return "Sony Interactive"
    if "xbox" in lower or "microsoft" in lower:
        return "Xbox Game Studios"

    return clean or raw_str


def detect_franchise(title: str) -> str:
    """Attempts to deduce franchise/series name from game title."""
    for f in COMMON_FRANCHISES:
        if re.search(r'\b' + re.escape(f) + r'\b', title, re.IGNORECASE):
            return f

    # Try subtitle pattern: 'Series Name: Subtitle' or 'Series Name - Subtitle'
    for sep in [':', ' - ', ' – ']:
        if sep in title:
            candidate = title.split(sep)[0].strip()
            # Clean trailing numbers or Roman numerals
            candidate = re.sub(r'\s+(?:[0-9]+|[IVXLCDM]+)$', '', candidate, flags=re.IGNORECASE).strip()
            if len(candidate) > 2:
                return candidate

    # Try trailing number pattern: 'Series 2', 'Series III'
    m = re.match(r'^(.*?)\s+(?:[0-9]+|[IVXLCDM]+)(?:\s|$)', title, re.IGNORECASE)
    if m and len(m.group(1).strip()) > 2:
        return m.group(1).strip()

    return title.strip()


def download_image_to_cache(url: str, filename_prefix: str) -> Optional[str]:
    """Downloads an image from URL and caches it locally. Returns the local path or None."""
    if not url:
        return None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        ext = os.path.splitext(path)[1]
        if not ext or len(ext) > 5 or "?" in ext:
            ext = ".jpg"

        safe_filename = "".join(c for c in filename_prefix if c.isalnum() or c in ("-", "_")) + ext
        local_path = CACHE_DIR / safe_filename

        # If already cached and valid size (>500 bytes), return it
        if local_path.exists() and local_path.stat().st_size > 500:
            return str(local_path)

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
            if len(data) > 500:
                with open(local_path, "wb") as f:
                    f.write(data)
                return str(local_path)
        return None
    except Exception as e:
        print(f"[LudusTier Cache] Failed to download {url}: {e}")
        return None


def fetch_steam_game_details(steam_appid: int, title: str) -> Dict[str, Any]:
    """
    Fetches full metadata for a Steam game:
    - genres, categories, developers, publishers
    - guesses the franchise from the title
    - computes normalized company name
    """
    developers: List[str] = []
    publishers: List[str] = []
    genres: List[str] = []
    categories: List[str] = []

    # 1. Store appdetails API
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={steam_appid}&l=english"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            app_info = data.get(str(steam_appid), {}).get("data", {})
            if app_info:
                developers = app_info.get("developers", [])
                publishers = app_info.get("publishers", [])
                genres = [g.get("description", "") for g in app_info.get("genres", []) if g.get("description")]
                categories = [c.get("description", "") for c in app_info.get("categories", []) if c.get("description")]
    except Exception as e:
        print(f"[Steam Details] Error querying appdetails for {steam_appid}: {e}")

    franchise = detect_franchise(title)

    # Compute normalized primary company
    primary_dev = developers[0] if developers else ""
    primary_pub = publishers[0] if publishers else ""
    company = normalize_company(primary_dev or primary_pub)

    # Standard Steam asset URLs
    cover_vertical_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{steam_appid}/library_600x900.jpg"
    cover_horizontal_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{steam_appid}/header.jpg"
    cover_icon_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{steam_appid}/capsule_231x87.jpg"
    cover_logo_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{steam_appid}/logo.png"

    return {
        "developers": developers,
        "publishers": publishers,
        "company": company,
        "franchise": franchise,
        "genres": genres,
        "categories": categories,
        "cover_vertical_url": cover_vertical_url,
        "cover_horizontal_url": cover_horizontal_url,
        "cover_icon_url": cover_icon_url,
        "cover_logo_url": cover_logo_url,
    }


def search_games(query: str) -> List[Dict]:
    """
    Search games using SteamGridDB (if API key is configured) or Steam Store Search.
    Returns list of dicts with game summary.
    """
    query = query.strip()
    if not query:
        return []

    api_key = get_steamgriddb_key()
    results = []

    # 1. Try SteamGridDB if API key is present
    if api_key:
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{encoded_query}"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": USER_AGENT,
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success") and data.get("data"):
                    for item in data["data"]:
                        game_id = item.get("id")
                        name = item.get("name")
                        if not game_id or not name:
                            continue

                        # Fetch covers for this game
                        covers = _fetch_steamgriddb_covers(game_id, api_key)
                        results.append({
                            "id": f"sgdb_{game_id}",
                            "title": name,
                            "cover_vertical_url": covers.get("vertical"),
                            "cover_horizontal_url": covers.get("horizontal"),
                            "cover_icon_url": covers.get("icon") or covers.get("vertical"),
                            "cover_url": covers.get("vertical") or covers.get("horizontal"),
                            "source": "steamgriddb",
                            "steamgrid_id": game_id,
                            "steam_appid": None,
                            "franchise": detect_franchise(name),
                            "company": "Comunidade SteamGridDB",
                            "genres": [],
                        })
                    if results:
                        return results
        except Exception as e:
            print(f"[SteamGridDB] Error searching SteamGridDB: {e}")

    # 2. Fallback to Steam Store Search (No API Key needed)
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://store.steampowered.com/api/storesearch/?term={encoded_query}&l=english&cc=US"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            for item in items:
                app_id = item.get("id")
                name = item.get("name")
                if not app_id or not name:
                    continue

                cover_vert = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}/library_600x900.jpg"
                cover_horiz = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg"
                cover_icon = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}/capsule_231x87.jpg"

                results.append({
                    "id": f"steam_{app_id}",
                    "title": name,
                    "cover_vertical_url": cover_vert,
                    "cover_horizontal_url": cover_horiz,
                    "cover_icon_url": cover_icon,
                    "cover_url": cover_vert,
                    "source": "steam",
                    "steam_appid": app_id,
                    "steamgrid_id": None,
                    "franchise": detect_franchise(name),
                    "company": "Steam",
                    "genres": [],
                })
    except Exception as e:
        print(f"[SteamStore] Error searching Steam Store: {e}")

    return results


def _fetch_steamgriddb_covers(game_id: int, api_key: str) -> Dict[str, Optional[str]]:
    """Fetches vertical, horizontal, and icon covers from SteamGridDB."""
    covers = {"vertical": None, "horizontal": None, "icon": None}
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT}

    # Vertical 600x900
    try:
        url_v = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=600x900"
        req = urllib.request.Request(url_v, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("success") and d.get("data"):
                covers["vertical"] = d["data"][0].get("url") or d["data"][0].get("thumb")
    except Exception:
        pass

    # Horizontal 460x215 or 920x430
    try:
        url_h = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=460x215,920x430"
        req = urllib.request.Request(url_h, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("success") and d.get("data"):
                covers["horizontal"] = d["data"][0].get("url") or d["data"][0].get("thumb")
    except Exception:
        pass

    # Icon
    try:
        url_i = f"https://www.steamgriddb.com/api/v2/icons/game/{game_id}"
        req = urllib.request.Request(url_i, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("success") and d.get("data"):
                covers["icon"] = d["data"][0].get("url") or d["data"][0].get("thumb")
    except Exception:
        pass

    return covers


def prepare_full_game_data(item: Dict) -> Dict:
    """
    Downloads assets and retrieves full metadata (franchise, company, genres)
    ready to be saved into the tierlist.
    """
    title = item.get("title", "Jogo")
    steam_appid = item.get("steam_appid")
    steamgrid_id = item.get("steamgrid_id")

    meta: Dict[str, Any] = {}
    if steam_appid:
        meta = fetch_steam_game_details(steam_appid, title)
    else:
        # Generic or SteamGridDB item
        meta = {
            "developers": [],
            "publishers": [],
            "company": item.get("company") or "Desconhecido",
            "franchise": item.get("franchise") or detect_franchise(title),
            "genres": item.get("genres", []),
            "categories": [],
            "cover_vertical_url": item.get("cover_vertical_url") or item.get("cover_url"),
            "cover_horizontal_url": item.get("cover_horizontal_url"),
            "cover_icon_url": item.get("cover_icon_url"),
        }

    # Download vertical cover (600x900)
    vert_url = meta.get("cover_vertical_url") or item.get("cover_url")
    local_vert = None
    if vert_url:
        local_vert = download_image_to_cache(vert_url, f"cover_vert_{item['id']}")

    # Download horizontal header cover (460x215)
    horiz_url = meta.get("cover_horizontal_url")
    local_horiz = None
    if horiz_url:
        local_horiz = download_image_to_cache(horiz_url, f"cover_horiz_{item['id']}")
    elif local_vert:
        local_horiz = local_vert

    # Download icon cover
    icon_url = meta.get("cover_icon_url")
    local_icon = None
    if icon_url:
        local_icon = download_image_to_cache(icon_url, f"cover_icon_{item['id']}")
    elif local_vert:
        local_icon = local_vert

    # Download logo (transparent PNG)
    logo_url = meta.get("cover_logo_url")
    local_logo = None
    if logo_url:
        local_logo = download_image_to_cache(logo_url, f"cover_logo_{item['id']}")

    full_game = {
        "id": item["id"],
        "title": title,
        "tier": item.get("tier", "UNRANKED"),
        "steam_appid": steam_appid,
        "steamgrid_id": steamgrid_id,
        "franchise": meta.get("franchise") or detect_franchise(title),
        "company": meta.get("company") or "Desconhecido",
        "developers": meta.get("developers", []),
        "publishers": meta.get("publishers", []),
        "genres": meta.get("genres", []),
        "categories": meta.get("categories", []),
        "cover_vertical": local_vert,
        "cover_horizontal": local_horiz,
        "cover_icon": local_icon,
        "cover_logo": local_logo,
        "cover_path": local_vert or local_horiz or local_icon, # backwards compatibility
    }

    return full_game
