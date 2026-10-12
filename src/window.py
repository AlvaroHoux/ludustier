# window.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import copy
from gi.repository import Gtk, Adw, Gdk, Gio, GLib, GObject
from typing import Dict, List, Optional, Any

from .config import (
    DEFAULT_TIERS,
    load_tierlist,
    save_tierlist,
    ensure_directories,
)
from .game_card import GameCard
from .search_dialog import SearchGameDialog
from .tier_dialog import TierDialog
from .exporter import export_tierlist_to_png, export_tierlist_to_json, import_tierlist_from_json


VIEW_MODES = [
    {"label": "Pôster (600×900)", "mode": "poster"},
    {"label": "Banner Horizontal", "mode": "header"},
    {"label": "Ícone Quadrado", "mode": "icon"},
]


@Gtk.Template(resource_path='/org/houx/ludustier/window.ui')
class LudustierWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'LudustierWindow'

    # Template Children
    toast_overlay = Gtk.Template.Child()
    toolbar_view = Gtk.Template.Child()
    btn_add_game = Gtk.Template.Child()
    btn_add_tier = Gtk.Template.Child()
    btn_toggle_search = Gtk.Template.Child()
    btn_view_options = Gtk.Template.Child()

    search_bar = Gtk.Template.Child()
    filter_search_entry = Gtk.Template.Child()
    filter_franchise_dropdown = Gtk.Template.Child()
    filter_company_dropdown = Gtk.Template.Child()
    filter_genre_dropdown = Gtk.Template.Child()
    btn_clear_filters = Gtk.Template.Child()

    filter_banner = Gtk.Template.Child()
    empty_state = Gtk.Template.Child()
    btn_empty_add_game = Gtk.Template.Child()
    main_content_box = Gtk.Template.Child()

    tiers_container = Gtk.Template.Child()
    unranked_container = Gtk.Template.Child()
    unranked_count_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ensure_directories()

        self.tierlist_data = load_tierlist()
        self.tier_flowboxes: Dict[str, Gtk.FlowBox] = {}
        self.game_cards: Dict[str, GameCard] = {}

        # View settings state
        view_settings = self.tierlist_data.get("view_settings", {})
        self.current_zoom = view_settings.get("zoom_level", 3)
        self.current_view_mode = view_settings.get("view_mode", "poster")

        # Active filter state
        self.filter_search = ""
        self.filter_franchise = "Todas as Franquias"
        self.filter_company = "Todas as Empresas"
        self.filter_genre = "Todos os Gêneros"

        # Signal block flag during dropdown rebuilds
        self._updating_filter_models = False

        # Register Window Actions
        self._register_actions()

        # Connect UI Controls
        self._setup_search_and_filters()
        self._setup_view_options_popover()
        self._setup_header_buttons()

        # Initial Render
        self._update_filter_dropdown_models()
        self._build_tier_rows()
        self._populate_all_games()

    def _register_actions(self):
        act_clear = Gio.SimpleAction.new("clear_tierlist", None)
        act_clear.connect("activate", self._on_clear_tierlist_action)
        self.add_action(act_clear)

        act_export_png = Gio.SimpleAction.new("export_png", None)
        act_export_png.connect("activate", self._on_export_png_action)
        self.add_action(act_export_png)

        act_export_json = Gio.SimpleAction.new("export_json", None)
        act_export_json.connect("activate", self._on_export_json_action)
        self.add_action(act_export_json)

        act_import_json = Gio.SimpleAction.new("import_json", None)
        act_import_json.connect("activate", self._on_import_json_action)
        self.add_action(act_import_json)

        # Toggle search action for Ctrl+F
        act_search = Gio.SimpleAction.new("toggle_search", None)
        act_search.connect("activate", lambda *_: self.btn_toggle_search.set_active(not self.btn_toggle_search.get_active()))
        self.add_action(act_search)

    def _setup_header_buttons(self):
        self.btn_add_game.connect("clicked", self._on_add_game_clicked)
        self.btn_empty_add_game.connect("clicked", self._on_add_game_clicked)
        self.btn_add_tier.connect("clicked", self._on_add_tier_clicked)

        # Connect SearchBar with ToggleButton
        self.btn_toggle_search.bind_property(
            "active",
            self.search_bar,
            "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL
        )
        self.search_bar.set_key_capture_widget(self)
        self.search_bar.connect_entry(self.filter_search_entry)
        self.filter_banner.connect("button-clicked", lambda _: self._on_clear_filters_clicked(None))

    def _setup_search_and_filters(self):
        self.filter_search_entry.connect("search-changed", self._on_search_query_changed)
        self.filter_franchise_dropdown.connect("notify::selected", self._on_franchise_filter_changed)
        self.filter_company_dropdown.connect("notify::selected", self._on_company_filter_changed)
        self.filter_genre_dropdown.connect("notify::selected", self._on_genre_filter_changed)
        self.btn_clear_filters.connect("clicked", self._on_clear_filters_clicked)

    def _setup_view_options_popover(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Section: View Mode
        lbl_mode = Gtk.Label(label="Estilo das Capas")
        lbl_mode.add_css_class("caption-heading")
        lbl_mode.set_halign(Gtk.Align.START)
        box.append(lbl_mode)

        mode_model = Gtk.StringList.new([m["label"] for m in VIEW_MODES])
        self.dropdown_view_mode = Gtk.DropDown.new(mode_model, None)

        initial_idx = 0
        for i, m in enumerate(VIEW_MODES):
            if m["mode"] == self.current_view_mode:
                initial_idx = i
                break
        self.dropdown_view_mode.set_selected(initial_idx)
        self.dropdown_view_mode.connect("notify::selected", self._on_view_mode_changed)
        box.append(self.dropdown_view_mode)

        sep = Gtk.Separator()
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        box.append(sep)

        # Section: Zoom
        lbl_zoom = Gtk.Label(label="Tamanho do Zoom")
        lbl_zoom.add_css_class("caption-heading")
        lbl_zoom.set_halign(Gtk.Align.START)
        box.append(lbl_zoom)

        zoom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        zoom_box.add_css_class("linked")
        zoom_box.set_halign(Gtk.Align.CENTER)

        btn_zoom_out = Gtk.Button(icon_name="zoom-out-symbolic", tooltip_text="Diminuir tamanho")
        btn_zoom_out.connect("clicked", self._on_zoom_out_clicked)
        zoom_box.append(btn_zoom_out)

        btn_zoom_in = Gtk.Button(icon_name="zoom-in-symbolic", tooltip_text="Aumentar tamanho")
        btn_zoom_in.connect("clicked", self._on_zoom_in_clicked)
        zoom_box.append(btn_zoom_in)

        box.append(zoom_box)

        popover.set_child(box)
        self.btn_view_options.set_popover(popover)

    # --------------------------------------------------------------------------
    # Tier Rows Construction
    # --------------------------------------------------------------------------

    def _build_tier_rows(self):
        """Construct the configurable tier rows and the unranked bank."""
        while child := self.tiers_container.get_first_child():
            self.tiers_container.remove(child)

        while child := self.unranked_container.get_first_child():
            self.unranked_container.remove(child)

        self.tier_flowboxes.clear()

        tiers = self.tierlist_data.get("tiers", DEFAULT_TIERS)
        for idx, tier in enumerate(tiers):
            tid = tier["id"]
            if tid == "UNRANKED":
                continue

            row_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_card.add_css_class("card")
            row_card.add_css_class("tier-card")

            # Tier Header Badge
            header_badge = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            header_badge.set_size_request(85, 72)
            header_badge.set_valign(Gtk.Align.FILL)
            header_badge.add_css_class("tier-header-badge")

            # Style provider for tier color
            css_prov = Gtk.CssProvider()
            css_prov.load_from_string(
                f".tier-badge-{tid} {{ background-color: {tier.get('color', '#808080')}; color: {tier.get('text_color', '#000000')}; }}"
            )
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, css_prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            header_badge.add_css_class(f"tier-badge-{tid}")

            lbl = Gtk.Label(label=tier.get("name", tid))
            lbl.set_hexpand(True)
            lbl.set_vexpand(True)
            header_badge.append(lbl)

            # Options menu button
            tier_menu_btn = Gtk.MenuButton()
            tier_menu_btn.set_icon_name("view-more-symbolic")
            tier_menu_btn.set_tooltip_text("Opções do tier")
            tier_menu_btn.add_css_class("flat")
            tier_menu_btn.set_valign(Gtk.Align.START)
            tier_menu_btn.set_halign(Gtk.Align.END)
            self._setup_tier_menu(tier_menu_btn, tier, idx, len(tiers))
            header_badge.append(tier_menu_btn)

            row_card.append(header_badge)

            # FlowBox for games
            flowbox = self._create_tier_flowbox(tid)
            row_card.append(flowbox)

            self.tiers_container.append(row_card)

        # Unranked zone FlowBox
        unranked_fb = self._create_tier_flowbox("UNRANKED")
        self.unranked_container.append(unranked_fb)

    def _setup_tier_menu(self, menu_btn: Gtk.MenuButton, tier: Dict[str, Any], index: int, total_tiers: int):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        # Edit Tier Button
        btn_edit = Gtk.Button(label="Editar tier (nome e cor)")
        btn_edit.add_css_class("flat")
        btn_edit.connect("clicked", lambda _: (popover.popdown(), self._on_edit_tier_clicked(tier)))
        box.append(btn_edit)

        # Move Up Button
        btn_up = Gtk.Button(label="Mover para cima")
        btn_up.add_css_class("flat")
        if index <= 0:
            btn_up.set_sensitive(False)
        btn_up.connect("clicked", lambda _: (popover.popdown(), self._move_tier(index, index - 1)))
        box.append(btn_up)

        # Move Down Button
        btn_down = Gtk.Button(label="Mover para baixo")
        btn_down.add_css_class("flat")
        if index >= total_tiers - 1:
            btn_down.set_sensitive(False)
        btn_down.connect("clicked", lambda _: (popover.popdown(), self._move_tier(index, index + 1)))
        box.append(btn_down)

        sep = Gtk.Separator()
        box.append(sep)

        # Delete Tier Button
        btn_del = Gtk.Button(label="Excluir tier")
        btn_del.add_css_class("destructive-action")
        btn_del.connect("clicked", lambda _: (popover.popdown(), self._on_delete_tier_clicked(tier)))
        box.append(btn_del)

        popover.set_child(box)
        menu_btn.set_popover(popover)

    def _create_tier_flowbox(self, tier_id: str) -> Gtk.FlowBox:
        flowbox = Gtk.FlowBox()
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_hexpand(True)
        flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        flowbox.set_min_children_per_line(1)
        flowbox.set_max_children_per_line(30)
        flowbox.set_column_spacing(12)
        flowbox.set_row_spacing(12)
        flowbox.add_css_class("tier-drop-area")

        drop_target = Gtk.DropTarget.new(type=str, actions=Gdk.DragAction.MOVE)
        drop_target.connect("drop", lambda target, value, x, y: self._on_game_dropped(tier_id, value))
        flowbox.add_controller(drop_target)

        self.tier_flowboxes[tier_id] = flowbox
        return flowbox

    def _on_game_dropped(self, dest_tier_id: str, game_id: str) -> bool:
        self.move_game_to_tier(game_id, dest_tier_id)
        return True

    # --------------------------------------------------------------------------
    # Tier Operations: Add, Edit, Move, Delete
    # --------------------------------------------------------------------------

    def _on_add_tier_clicked(self, _):
        dialog = TierDialog(parent_window=self, tier_data=None, on_saved=self._on_tier_added)
        dialog.present(self)

    def _on_tier_added(self, new_tier: Dict[str, Any]):
        self.tierlist_data.setdefault("tiers", []).append(new_tier)
        save_tierlist(self.tierlist_data)
        self._build_tier_rows()
        self._populate_all_games()
        self.toast_overlay.add_toast(Adw.Toast.new(f"Tier '{new_tier['name']}' adicionado"))

    def _on_edit_tier_clicked(self, tier: Dict[str, Any]):
        dialog = TierDialog(parent_window=self, tier_data=copy.deepcopy(tier), on_saved=self._on_tier_edited)
        dialog.present(self)

    def _on_tier_edited(self, updated_tier: Dict[str, Any]):
        tiers = self.tierlist_data.get("tiers", [])
        for i, t in enumerate(tiers):
            if t["id"] == updated_tier["id"]:
                tiers[i] = updated_tier
                break
        save_tierlist(self.tierlist_data)
        self._build_tier_rows()
        self._populate_all_games()
        self.toast_overlay.add_toast(Adw.Toast.new("Tier atualizado"))

    def _move_tier(self, from_idx: int, to_idx: int):
        tiers = self.tierlist_data.get("tiers", [])
        if 0 <= from_idx < len(tiers) and 0 <= to_idx < len(tiers):
            tiers[from_idx], tiers[to_idx] = tiers[to_idx], tiers[from_idx]
            save_tierlist(self.tierlist_data)
            self._build_tier_rows()
            self._populate_all_games()

    def _on_delete_tier_clicked(self, tier: Dict[str, Any]):
        tid = tier["id"]
        # Move all games in this tier to UNRANKED
        for g in self.tierlist_data.get("games", []):
            if g.get("tier") == tid:
                g["tier"] = "UNRANKED"

        self.tierlist_data["tiers"] = [t for t in self.tierlist_data.get("tiers", []) if t["id"] != tid]
        save_tierlist(self.tierlist_data)
        self._build_tier_rows()
        self._populate_all_games()
        self.toast_overlay.add_toast(Adw.Toast.new(f"Tier '{tier['name']}' excluído"))

    # --------------------------------------------------------------------------
    # Games Population and Rendering
    # --------------------------------------------------------------------------

    def _populate_all_games(self):
        self.game_cards.clear()

        for fb in self.tier_flowboxes.values():
            while child := fb.get_first_child():
                fb.remove(child)

        tiers = self.tierlist_data.get("tiers", DEFAULT_TIERS)
        games = self.tierlist_data.get("games", [])

        # Update empty state visibility
        has_games = len(games) > 0
        self.empty_state.set_visible(not has_games)
        self.main_content_box.set_visible(has_games)

        for game in games:
            tier_id = game.get("tier", "UNRANKED")
            if tier_id not in self.tier_flowboxes:
                tier_id = "UNRANKED"

            card = GameCard(
                game_data=game,
                tiers=tiers,
                on_tier_changed=self.move_game_to_tier,
                on_deleted=self.delete_game,
                on_updated=self.update_game,
                view_mode=self.current_view_mode,
                zoom_level=self.current_zoom,
            )
            self.game_cards[game["id"]] = card
            self.tier_flowboxes[tier_id].append(card)

        self._apply_filters()

    def move_game_to_tier(self, game_id: str, new_tier_id: str):
        for g in self.tierlist_data.get("games", []):
            if g["id"] == game_id:
                g["tier"] = new_tier_id
                break
        save_tierlist(self.tierlist_data)
        self._populate_all_games()

    def delete_game(self, game_id: str):
        deleted_game = None
        for g in self.tierlist_data.get("games", []):
            if g["id"] == game_id:
                deleted_game = g
                break

        self.tierlist_data["games"] = [
            g for g in self.tierlist_data.get("games", []) if g["id"] != game_id
        ]
        save_tierlist(self.tierlist_data)
        self._update_filter_dropdown_models()
        self._populate_all_games()

        # Provide Undo Toast
        if deleted_game:
            toast = Adw.Toast.new(f"'{deleted_game.get('title')}' removido")
            toast.set_button_label("Desfazer")
            toast.connect("button-clicked", lambda _: self._undo_delete(deleted_game))
            self.toast_overlay.add_toast(toast)

    def _undo_delete(self, restored_game: Dict[str, Any]):
        self.tierlist_data.setdefault("games", []).append(restored_game)
        save_tierlist(self.tierlist_data)
        self._update_filter_dropdown_models()
        self._populate_all_games()

    def update_game(self, updated_data: Dict[str, Any]):
        games = self.tierlist_data.get("games", [])
        for i, g in enumerate(games):
            if g["id"] == updated_data["id"]:
                games[i] = updated_data
                break
        save_tierlist(self.tierlist_data)
        self._update_filter_dropdown_models()
        self._apply_filters()
        self.toast_overlay.add_toast(Adw.Toast.new("Informações atualizadas"))

    def _on_add_game_clicked(self, _):
        dialog = SearchGameDialog(parent_window=self, on_game_selected=self._on_game_added)
        dialog.present(self)

    def _on_game_added(self, game_data: Dict[str, Any]):
        game_data["tier"] = "UNRANKED"

        existing = [g for g in self.tierlist_data.get("games", []) if g["id"] == game_data["id"]]
        if not existing:
            self.tierlist_data.setdefault("games", []).append(game_data)
            save_tierlist(self.tierlist_data)
            self._update_filter_dropdown_models()
            self._populate_all_games()
            self.toast_overlay.add_toast(Adw.Toast.new(f"'{game_data['title']}' adicionado ao banco"))

    # --------------------------------------------------------------------------
    # Filter Engine
    # --------------------------------------------------------------------------

    def _update_filter_dropdown_models(self):
        self._updating_filter_models = True

        games = self.tierlist_data.get("games", [])
        franchises = set()
        companies = set()
        genres = set()

        for g in games:
            fr = g.get("franchise")
            if fr:
                franchises.add(fr.strip())

            co = g.get("company")
            if co:
                companies.add(co.strip())
            for dev in g.get("developers", []):
                if dev:
                    companies.add(dev.strip())
            for pub in g.get("publishers", []):
                if pub:
                    companies.add(pub.strip())

            for genre in g.get("genres", []):
                if genre:
                    genres.add(genre.strip())

        franchise_items = ["Todas as Franquias"] + sorted(list(franchises))
        company_items = ["Todas as Empresas"] + sorted(list(companies))
        genre_items = ["Todos os Gêneros"] + sorted(list(genres))

        self.filter_franchise_dropdown.set_model(Gtk.StringList.new(franchise_items))
        self.filter_company_dropdown.set_model(Gtk.StringList.new(company_items))
        self.filter_genre_dropdown.set_model(Gtk.StringList.new(genre_items))

        self._restore_dropdown_selection(self.filter_franchise_dropdown, franchise_items, self.filter_franchise)
        self._restore_dropdown_selection(self.filter_company_dropdown, company_items, self.filter_company)
        self._restore_dropdown_selection(self.filter_genre_dropdown, genre_items, self.filter_genre)

        self._updating_filter_models = False

    def _restore_dropdown_selection(self, dropdown: Gtk.DropDown, items: List[str], target: str):
        if target in items:
            dropdown.set_selected(items.index(target))
        else:
            dropdown.set_selected(0)

    def _on_search_query_changed(self, entry: Gtk.SearchEntry):
        self.filter_search = entry.get_text().strip().lower()
        self._apply_filters()

    def _on_franchise_filter_changed(self, dropdown: Gtk.DropDown, _):
        if self._updating_filter_models:
            return
        selected = dropdown.get_selected_item()
        self.filter_franchise = selected.get_string() if selected else "Todas as Franquias"
        self._apply_filters()

    def _on_company_filter_changed(self, dropdown: Gtk.DropDown, _):
        if self._updating_filter_models:
            return
        selected = dropdown.get_selected_item()
        self.filter_company = selected.get_string() if selected else "Todas as Empresas"
        self._apply_filters()

    def _on_genre_filter_changed(self, dropdown: Gtk.DropDown, _):
        if self._updating_filter_models:
            return
        selected = dropdown.get_selected_item()
        self.filter_genre = selected.get_string() if selected else "Todos os Gêneros"
        self._apply_filters()

    def _on_clear_filters_clicked(self, _):
        self.filter_search_entry.set_text("")
        self.filter_franchise_dropdown.set_selected(0)
        self.filter_company_dropdown.set_selected(0)
        self.filter_genre_dropdown.set_selected(0)
        self.filter_search = ""
        self.filter_franchise = "Todas as Franquias"
        self.filter_company = "Todas as Empresas"
        self.filter_genre = "Todos os Gêneros"
        self._apply_filters()

    def _apply_filters(self):
        total_games = len(self.tierlist_data.get("games", []))
        visible_games = 0
        unranked_visible = 0

        for game_id, card in self.game_cards.items():
            g = card.game_data
            matches = True

            if self.filter_search:
                title = g.get("title", "").lower()
                if self.filter_search not in title:
                    matches = False

            if matches and self.filter_franchise != "Todas as Franquias":
                g_fr = g.get("franchise") or ""
                if g_fr.strip().lower() != self.filter_franchise.strip().lower():
                    matches = False

            if matches and self.filter_company != "Todas as Empresas":
                comp_match = False
                c_filter = self.filter_company.strip().lower()
                if (g.get("company") or "").strip().lower() == c_filter:
                    comp_match = True
                for dev in g.get("developers", []):
                    if dev.strip().lower() == c_filter:
                        comp_match = True
                for pub in g.get("publishers", []):
                    if pub.strip().lower() == c_filter:
                        comp_match = True
                if not comp_match:
                    matches = False

            if matches and self.filter_genre != "Todos os Gêneros":
                g_genres = [gen.strip().lower() for gen in g.get("genres", [])]
                if self.filter_genre.strip().lower() not in g_genres:
                    matches = False

            card.set_visible(matches)
            if matches:
                visible_games += 1
                if g.get("tier") == "UNRANKED":
                    unranked_visible += 1

        self.unranked_count_label.set_label(f"{unranked_visible} jogos")

        active_filters = []
        if self.filter_search:
            active_filters.append(f'"{self.filter_search}"')
        if self.filter_franchise != "Todas as Franquias":
            active_filters.append(self.filter_franchise)
        if self.filter_company != "Todas as Empresas":
            active_filters.append(self.filter_company)
        if self.filter_genre != "Todos os Gêneros":
            active_filters.append(self.filter_genre)

        if active_filters:
            desc = " • ".join(active_filters)
            self.filter_banner.set_title(f"Filtrando por: {desc} ({visible_games} de {total_games} jogos)")
            self.filter_banner.set_revealed(True)
        else:
            self.filter_banner.set_revealed(False)

    # --------------------------------------------------------------------------
    # Zoom and View Mode Controls
    # --------------------------------------------------------------------------

    def _on_view_mode_changed(self, dropdown: Gtk.DropDown, _):
        idx = dropdown.get_selected()
        if 0 <= idx < len(VIEW_MODES):
            self.current_view_mode = VIEW_MODES[idx]["mode"]
            self._save_view_settings()
            for card in self.game_cards.values():
                card.apply_view_settings(self.current_view_mode, self.current_zoom)

    def _on_zoom_in_clicked(self, _):
        if self.current_zoom < 5:
            self.current_zoom += 1
            self._save_view_settings()
            for card in self.game_cards.values():
                card.apply_view_settings(self.current_view_mode, self.current_zoom)

    def _on_zoom_out_clicked(self, _):
        if self.current_zoom > 1:
            self.current_zoom -= 1
            self._save_view_settings()
            for card in self.game_cards.values():
                card.apply_view_settings(self.current_view_mode, self.current_zoom)

    def _save_view_settings(self):
        self.tierlist_data.setdefault("view_settings", {})
        self.tierlist_data["view_settings"]["zoom_level"] = self.current_zoom
        self.tierlist_data["view_settings"]["view_mode"] = self.current_view_mode
        save_tierlist(self.tierlist_data)

    # --------------------------------------------------------------------------
    # Export and Import Operations
    # --------------------------------------------------------------------------

    def _on_export_png_action(self, action, param):
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Exportar Tier List como Imagem PNG")
        file_dialog.set_initial_name("minha_tierlist.png")

        def on_saved_png(dialog, result):
            try:
                gfile = dialog.save_finish(result)
                path = gfile.get_path()
                if path:
                    if not path.lower().endswith(".png"):
                        path += ".png"
                    success = export_tierlist_to_png(self.tierlist_data, path)
                    if success:
                        self.toast_overlay.add_toast(Adw.Toast.new("Imagem exportada com sucesso"))
            except Exception as e:
                print(f"[Export PNG] Cancelled: {e}")

        file_dialog.save(self, None, on_saved_png)

    def _on_export_json_action(self, action, param):
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Exportar Tier List em JSON")
        file_dialog.set_initial_name("tierlist_backup.json")

        def on_saved_json(dialog, result):
            try:
                gfile = dialog.save_finish(result)
                path = gfile.get_path()
                if path:
                    if not path.lower().endswith(".json"):
                        path += ".json"
                    success = export_tierlist_to_json(self.tierlist_data, path)
                    if success:
                        self.toast_overlay.add_toast(Adw.Toast.new("Arquivo JSON exportado"))
            except Exception as e:
                print(f"[Export JSON] Cancelled: {e}")

        file_dialog.save(self, None, on_saved_json)

    def _on_import_json_action(self, action, param):
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Importar Tier List de JSON")

        def on_opened_json(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                path = gfile.get_path()
                if path:
                    imported = import_tierlist_from_json(path)
                    if imported:
                        self.tierlist_data = imported
                        save_tierlist(self.tierlist_data)
                        self._update_filter_dropdown_models()
                        self._build_tier_rows()
                        self._populate_all_games()
                        self.toast_overlay.add_toast(Adw.Toast.new("Tier list importada com sucesso"))
            except Exception as e:
                print(f"[Import JSON] Cancelled: {e}")

        file_dialog.open(self, None, on_opened_json)

    def _on_clear_tierlist_action(self, action, param):
        dialog = Adw.AlertDialog.new(
            "Limpar Tier List?",
            "Esta ação removerá todos os jogos da sua lista atual."
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("clear", "Limpar")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(d, response):
            if response == "clear":
                self.tierlist_data["games"] = []
                save_tierlist(self.tierlist_data)
                self._update_filter_dropdown_models()
                self._populate_all_games()
                self.toast_overlay.add_toast(Adw.Toast.new("Lista limpa"))

        dialog.connect("response", handle_response)
        dialog.present(self)
