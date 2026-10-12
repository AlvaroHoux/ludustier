# tests/test_ludustier.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib

Adw.init()

# Register resource if not registered
try:
    Gio.resources_get_info('/org/houx/ludustier/window.ui', Gio.ResourceLookupFlags.NONE)
except GLib.Error:
    res_path = REPO_ROOT / 'src' / 'ludustier.gresource'
    if res_path.exists():
        res = Gio.Resource.load(str(res_path))
        res._register()

from src.config import (
    DEFAULT_TIERS,
    UNRANKED_TIER,
    TIER_COLOR_PALETTE,
    load_tierlist,
    save_tierlist,
    DEFAULT_VIEW_SETTINGS,
)
from src.steamgrid import (
    detect_franchise,
    normalize_company,
    prepare_full_game_data,
    download_image_to_cache,
)
from src.exporter import (
    export_tierlist_to_png,
    export_tierlist_to_json,
    import_tierlist_from_json,
)
from src.window import LudustierWindow
from src.main import LudustierApplication


class TestConfig(unittest.TestCase):
    def test_default_tiers(self):
        tier_ids = [t["id"] for t in DEFAULT_TIERS]
        self.assertIn("S", tier_ids)
        self.assertIn("A", tier_ids)
        self.assertIn("B", tier_ids)
        self.assertIn("C", tier_ids)
        self.assertIn("D", tier_ids)

    def test_load_and_save_tierlist(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            data = load_tierlist(temp_path)
            self.assertEqual(data["title"], "Minha Tier List de Jogos")
            self.assertEqual(len(data["tiers"]), len(DEFAULT_TIERS))
            self.assertEqual(data["games"], [])
            self.assertEqual(data["view_settings"]["zoom_level"], 3)
            self.assertEqual(data["view_settings"]["view_mode"], "poster")

            # Modify and save
            data["title"] = "Tier List de Teste"
            data["games"].append({
                "id": "steam_2050650",
                "title": "Resident Evil 4",
                "tier": "S",
                "franchise": "Resident Evil",
                "company": "Capcom",
                "genres": ["Action", "Adventure"],
            })
            save_tierlist(data, temp_path)

            loaded = load_tierlist(temp_path)
            self.assertEqual(loaded["title"], "Tier List de Teste")
            self.assertEqual(len(loaded["games"]), 1)
            self.assertEqual(loaded["games"][0]["franchise"], "Resident Evil")
            self.assertEqual(loaded["games"][0]["company"], "Capcom")
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestSteamGridMetadata(unittest.TestCase):
    def test_detect_franchise(self):
        self.assertEqual(detect_franchise("Resident Evil 4"), "Resident Evil")
        self.assertEqual(detect_franchise("Resident Evil Village"), "Resident Evil")
        self.assertEqual(detect_franchise("The Witcher 3: Wild Hunt"), "The Witcher")
        self.assertEqual(detect_franchise("Dark Souls III"), "Dark Souls")
        self.assertEqual(detect_franchise("Final Fantasy VII Remake"), "Final Fantasy")
        self.assertEqual(detect_franchise("Hades II"), "Hades")
        self.assertEqual(detect_franchise("Batman: Arkham City"), "Batman: Arkham")

    def test_normalize_company(self):
        self.assertEqual(normalize_company("CAPCOM Co., Ltd."), "Capcom")
        self.assertEqual(normalize_company("FromSoftware, Inc."), "FromSoftware")
        self.assertEqual(normalize_company("CD PROJEKT RED"), "CD Projekt Red")
        self.assertEqual(normalize_company("Valve Corporation"), "Valve")
        self.assertEqual(normalize_company("Square Enix"), "Square Enix")
        self.assertEqual(normalize_company("Bandai Namco Entertainment"), "Bandai Namco")

    def test_prepare_full_game_data(self):
        raw_item = {
            "id": "steam_2050650",
            "title": "Resident Evil 4",
            "steam_appid": 2050650,
            "source": "steam",
            "cover_url": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2050650/library_600x900.jpg",
        }
        full = prepare_full_game_data(raw_item)
        self.assertEqual(full["title"], "Resident Evil 4")
        self.assertEqual(full["franchise"], "Resident Evil")
        self.assertEqual(full["company"], "Capcom")
        self.assertIn("Action", full["genres"])
        self.assertIsNotNone(full["cover_vertical"])
        self.assertTrue(os.path.exists(full["cover_vertical"]))


class TestExporter(unittest.TestCase):
    def test_export_png_and_json(self):
        dummy_tierlist = {
            "title": "Tier List Melhores Jogos",
            "tiers": [
                {"id": "S", "name": "S", "color": "#ff7f7f", "text_color": "#000000"},
                {"id": "A", "name": "A", "color": "#ffbf7f", "text_color": "#000000"},
            ],
            "games": [
                {
                    "id": "test_1",
                    "title": "Resident Evil 4",
                    "tier": "S",
                    "franchise": "Resident Evil",
                    "company": "Capcom",
                },
                {
                    "id": "test_2",
                    "title": "Elden Ring",
                    "tier": "S",
                    "franchise": "Elden Ring",
                    "company": "FromSoftware",
                },
                {
                    "id": "test_3",
                    "title": "Hades",
                    "tier": "A",
                    "franchise": "Hades",
                    "company": "Supergiant Games",
                },
            ]
        }

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_png:
            png_path = f_png.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_json:
            json_path = f_json.name

        try:
            # Test PNG export
            ok_png = export_tierlist_to_png(dummy_tierlist, png_path)
            self.assertTrue(ok_png)
            self.assertTrue(os.path.exists(png_path))
            self.assertGreater(os.path.getsize(png_path), 5000)

            # Validate generated image with PIL
            with Image.open(png_path) as img:
                self.assertGreater(img.width, 500)
                self.assertGreater(img.height, 200)

            # Test JSON export and import
            ok_json = export_tierlist_to_json(dummy_tierlist, json_path)
            self.assertTrue(ok_json)

            imported = import_tierlist_from_json(json_path)
            self.assertIsNotNone(imported)
            self.assertEqual(imported["title"], "Tier List Melhores Jogos")
            self.assertEqual(len(imported["games"]), 3)
        finally:
            if os.path.exists(png_path):
                os.unlink(png_path)
            if os.path.exists(json_path):
                os.unlink(json_path)


class TestWindowAndFeatures(unittest.TestCase):
    def setUp(self):
        self.app = LudustierApplication()
        self.win = LudustierWindow(application=self.app)

    def test_configurable_tiers(self):
        # 1. Check initial tiers
        initial_tiers_count = len(self.win.tierlist_data["tiers"])
        self.assertGreaterEqual(initial_tiers_count, 5)

        # 2. Add new tier "SS"
        new_tier = {"id": "SS", "name": "SS", "color": "#ff007f", "text_color": "#ffffff"}
        self.win._on_tier_added(new_tier)
        self.assertEqual(len(self.win.tierlist_data["tiers"]), initial_tiers_count + 1)
        self.assertEqual(self.win.tierlist_data["tiers"][-1]["name"], "SS")

        # 3. Edit tier
        updated_tier = {"id": "SS", "name": "Obra-Prima", "color": "#ffd700", "text_color": "#000000"}
        self.win._on_tier_edited(updated_tier)
        self.assertEqual(self.win.tierlist_data["tiers"][-1]["name"], "Obra-Prima")
        self.assertEqual(self.win.tierlist_data["tiers"][-1]["color"], "#ffd700")

        # 4. Move tier up
        last_idx = len(self.win.tierlist_data["tiers"]) - 1
        self.win._move_tier(last_idx, last_idx - 1)
        self.assertEqual(self.win.tierlist_data["tiers"][last_idx - 1]["name"], "Obra-Prima")

        # 5. Add a game to tier "SS" and delete tier -> verify game is safely moved to UNRANKED
        self.win.tierlist_data["games"].append({
            "id": "game_test_re4",
            "title": "Resident Evil 4",
            "tier": "SS",
            "franchise": "Resident Evil",
            "company": "Capcom",
            "genres": ["Action", "Adventure"],
        })
        self.win._on_delete_tier_clicked(updated_tier)
        self.assertEqual(len(self.win.tierlist_data["tiers"]), initial_tiers_count)
        # Check game was moved to UNRANKED and not lost!
        re4 = next(g for g in self.win.tierlist_data["games"] if g["id"] == "game_test_re4")
        self.assertEqual(re4["tier"], "UNRANKED")

    def _populate_test_games(self):
        self.win.tierlist_data["games"] = [
            {
                "id": "g1",
                "title": "Resident Evil 4",
                "tier": "S",
                "franchise": "Resident Evil",
                "company": "Capcom",
                "developers": ["CAPCOM Co., Ltd."],
                "genres": ["Action", "Adventure", "Survival Horror"],
            },
            {
                "id": "g2",
                "title": "Resident Evil Village",
                "tier": "A",
                "franchise": "Resident Evil",
                "company": "Capcom",
                "developers": ["CAPCOM Co., Ltd."],
                "genres": ["Action", "Survival Horror"],
            },
            {
                "id": "g3",
                "title": "Devil May Cry 5",
                "tier": "S",
                "franchise": "Devil May Cry",
                "company": "Capcom",
                "developers": ["CAPCOM Co., Ltd."],
                "genres": ["Action", "Hack and Slash"],
            },
            {
                "id": "g4",
                "title": "Dark Souls III",
                "tier": "S",
                "franchise": "Dark Souls",
                "company": "FromSoftware",
                "developers": ["FromSoftware, Inc."],
                "genres": ["RPG", "Action"],
            },
        ]
        self.win._update_filter_dropdown_models()
        self.win._populate_all_games()

    def test_filtering_by_franchise_company_and_genre(self):
        self._populate_test_games()

        # Check all 4 games initially visible
        self.assertEqual(len(self.win.game_cards), 4)
        for card in self.win.game_cards.values():
            self.assertTrue(card.get_visible())

        # 1. Filter by Franchise: "Resident Evil"
        self.win.filter_franchise = "Resident Evil"
        self.win._apply_filters()
        self.assertTrue(self.win.game_cards["g1"].get_visible()) # RE4
        self.assertTrue(self.win.game_cards["g2"].get_visible()) # RE Village
        self.assertFalse(self.win.game_cards["g3"].get_visible()) # DMC5 (Capcom, but not RE)
        self.assertFalse(self.win.game_cards["g4"].get_visible()) # DS3

        # 2. Filter by Company: "Capcom"
        self.win.filter_franchise = "Todas as Franquias"
        self.win.filter_company = "Capcom"
        self.win._apply_filters()
        self.assertTrue(self.win.game_cards["g1"].get_visible()) # RE4
        self.assertTrue(self.win.game_cards["g2"].get_visible()) # RE Village
        self.assertTrue(self.win.game_cards["g3"].get_visible()) # DMC5 (Capcom)
        self.assertFalse(self.win.game_cards["g4"].get_visible()) # DS3 (FromSoftware)

        # 3. Filter by Company: "FromSoftware"
        self.win.filter_company = "FromSoftware"
        self.win._apply_filters()
        self.assertFalse(self.win.game_cards["g1"].get_visible())
        self.assertFalse(self.win.game_cards["g2"].get_visible())
        self.assertFalse(self.win.game_cards["g3"].get_visible())
        self.assertTrue(self.win.game_cards["g4"].get_visible())

        # 4. Filter by Genre: "Survival Horror"
        self.win.filter_company = "Todas as Empresas"
        self.win.filter_genre = "Survival Horror"
        self.win._apply_filters()
        self.assertTrue(self.win.game_cards["g1"].get_visible())
        self.assertTrue(self.win.game_cards["g2"].get_visible())
        self.assertFalse(self.win.game_cards["g3"].get_visible())
        self.assertFalse(self.win.game_cards["g4"].get_visible())

        # 5. Search Text Filter: "Village"
        self.win.filter_genre = "Todos os Gêneros"
        self.win.filter_search = "village"
        self.win._apply_filters()
        self.assertFalse(self.win.game_cards["g1"].get_visible())
        self.assertTrue(self.win.game_cards["g2"].get_visible())
        self.assertFalse(self.win.game_cards["g3"].get_visible())
        self.assertFalse(self.win.game_cards["g4"].get_visible())

        # 6. Clear Filters
        self.win._on_clear_filters_clicked(None)
        for card in self.win.game_cards.values():
            self.assertTrue(card.get_visible())

    def test_zoom_and_view_mode_controls(self):
        card = self.win.game_cards.get("g1")
        if not card and self.win.game_cards:
            card = next(iter(self.win.game_cards.values()))

        # Test zoom levels 1 to 5
        for z in [1, 2, 3, 4, 5]:
            self.win.current_zoom = z
            self.win._save_view_settings()
            self.assertEqual(self.win.tierlist_data["view_settings"]["zoom_level"], z)

        # Test view modes
        for mode in ["poster", "header", "icon"]:
            self.win.current_view_mode = mode
            self.win._save_view_settings()
            self.assertEqual(self.win.tierlist_data["view_settings"]["view_mode"], mode)

    def test_combined_filters(self):
        self._populate_test_games()
        # Filter simultaneously by Franchise: Resident Evil AND Genre: Adventure
        self.win.filter_franchise = "Resident Evil"
        self.win.filter_company = "Capcom"
        self.win.filter_genre = "Adventure"
        self.win.filter_search = "4"
        self.win._apply_filters()

        # Only RE4 matches all criteria: Franchise RE, Company Capcom, Genre Adventure, Search "4"
        self.assertTrue(self.win.game_cards["g1"].get_visible())
        self.assertFalse(self.win.game_cards["g2"].get_visible()) # RE Village has no "4"
        self.assertFalse(self.win.game_cards["g3"].get_visible())
        self.assertFalse(self.win.game_cards["g4"].get_visible())

    def test_game_edit_dialog_logic(self):
        from src.game_edit_dialog import GameEditDialog
        test_game = {
            "id": "g_edit",
            "title": "Resident Evil 4",
            "franchise": "Resident Evil",
            "company": "Capcom",
            "genres": ["Action", "Adventure"],
        }
        saved_result = {}
        def on_saved(data):
            nonlocal saved_result
            saved_result = data

        dialog = GameEditDialog(parent_window=self.win, game_data=test_game, on_saved=on_saved)
        # Change fields
        dialog.row_title.set_text("RE4 Remake")
        dialog.row_franchise.set_text("Biohazard / Resident Evil")
        dialog.row_company.set_text("Capcom Japan")
        dialog.row_genres.set_text("Action, Survival Horror, Masterpiece")
        dialog._on_save_clicked(None)

        self.assertEqual(saved_result["title"], "RE4 Remake")
        self.assertEqual(saved_result["franchise"], "Biohazard / Resident Evil")
        self.assertEqual(saved_result["company"], "Capcom Japan")
        self.assertEqual(saved_result["genres"], ["Action", "Survival Horror", "Masterpiece"])


if __name__ == '__main__':
    unittest.main()

