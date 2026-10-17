# window.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import copy
from gi.repository import Gtk, Adw, Gdk, Gio, GLib, GObject
from typing import Dict, List, Optional, Any

from .config import (
    DEFAULT_TIERS,
    STATUS_CHOICES,
    DEFAULT_CATEGORIES,
    load_tierlist,
    save_tierlist,
    ensure_directories,
)
from .game_card import (
    GameCard,
    type_icon,
    DIMENSIONS_POSTER,
    DIMENSIONS_HEADER,
    DIMENSIONS_ICON,
)
from .search_dialog import SearchGameDialog
from .tier_dialog import TierDialog
from .lutris_dialog import LutrisImportDialog
from .lutris_importer import get_lutris_games
from .game_edit_dialog import GameEditDialog
from .exporter import export_tierlist_to_png, export_tierlist_to_json, import_tierlist_from_json


VIEW_MODES = [
    {"label": "Pôster (600×900)", "mode": "poster"},
    {"label": "Banner Horizontal", "mode": "header"},
    {"label": "Ícone Quadrado", "mode": "icon"},
]


BADGE_OPTIONS = {
    "show_title": "Título",
    "show_playtime": "Horas jogadas",
    "show_status": "Status",
    "show_platform": "Plataforma e runner",
}


@Gtk.Template(resource_path='/org/houx/ludustier/window.ui')
class LudustierWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'LudustierWindow'

    # Template Children
    toast_overlay = Gtk.Template.Child()
    toolbar_view = Gtk.Template.Child()
    btn_toggle_sidebar = Gtk.Template.Child()
    btn_add_game = Gtk.Template.Child()
    btn_import_lutris = Gtk.Template.Child()
    btn_add_tier = Gtk.Template.Child()
    window_title = Gtk.Template.Child()
    btn_toggle_search = Gtk.Template.Child()
    btn_view_options = Gtk.Template.Child()

    search_bar = Gtk.Template.Child()
    filter_search_entry = Gtk.Template.Child()
    filter_company_dropdown = Gtk.Template.Child()
    filter_genre_dropdown = Gtk.Template.Child()
    btn_clear_filters = Gtk.Template.Child()

    split_view = Gtk.Template.Child()
    sidebar_nav_list = Gtk.Template.Child()
    sidebar_status_list = Gtk.Template.Child()
    btn_add_category = Gtk.Template.Child()
    sidebar_category_list = Gtk.Template.Child()
    sidebar_source_list = Gtk.Template.Child()

    main_view_stack = Gtk.Template.Child()

    filter_banner = Gtk.Template.Child()
    empty_state = Gtk.Template.Child()
    btn_empty_add_game = Gtk.Template.Child()
    main_content_box = Gtk.Template.Child()

    tiers_container = Gtk.Template.Child()
    unranked_container = Gtk.Template.Child()
    unranked_count_label = Gtk.Template.Child()

    library_title_label = Gtk.Template.Child()
    library_flowbox = Gtk.Template.Child()
    detail_bar_revealer = Gtk.Template.Child()
    detail_bar_box = Gtk.Template.Child()
    detail_poster_pic = Gtk.Template.Child()
    detail_title_lbl = Gtk.Template.Child()
    detail_platform_lbl = Gtk.Template.Child()
    detail_playtime_lbl = Gtk.Template.Child()
    detail_status_lbl = Gtk.Template.Child()
    detail_extra_lbl = Gtk.Template.Child()
    detail_tier_lbl = Gtk.Template.Child()
    btn_detail_edit = Gtk.Template.Child()
    btn_detail_close = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ensure_directories()

        self.tierlist_data = load_tierlist()
        self.tier_flowboxes: Dict[str, Gtk.FlowBox] = {}
        self.game_cards: Dict[str, GameCard] = {}
        self.library_cards: Dict[str, GameCard] = {}
        self.selected_game_for_detail: Optional[Dict[str, Any]] = None

        # View settings state
        view_settings = self.tierlist_data.get("view_settings", {})
        self.current_zoom = view_settings.get("zoom_level", 3)
        self.current_view_mode = view_settings.get("view_mode", "poster")
        self.badge_settings = {k: view_settings.get(k, True) for k in BADGE_OPTIONS}

        # Active filter state
        self.filter_search = ""
        self.filter_company = "Todas as Empresas"
        self.filter_genre = "Todos os Gêneros"

        # Active sidebar filter state
        self.current_sidebar_mode = "tierlist" # "tierlist", "all", "status:X", "category:X", "source:X"

        # Signal block flag during dropdown rebuilds
        self._updating_filter_models = False

        # Register Window Actions
        self._register_actions()

        # Connect UI Controls
        self._setup_sidebar()
        self._setup_search_and_filters()
        self._setup_view_options_popover()
        self._setup_header_buttons()
        self._setup_detail_bar()

        self._sync_lutris_library()
        self._setup_drag_autoscroll()

        # Initial Render
        self._update_filter_dropdown_models()
        self._build_sidebar_items()
        self._build_tier_rows()
        self._populate_all_games()

    def _setup_drag_autoscroll(self):
        """Scrolls the tier list while a card is dragged near its top or bottom edge."""
        scrolled = self.main_content_box.get_ancestor(Gtk.ScrolledWindow)
        adj = scrolled.get_vadjustment()
        state = {"y": None, "source": 0}
        edge, max_speed = 80, 24

        def tick():
            y, h = state["y"], scrolled.get_height()
            if y is None:
                state["source"] = 0
                return False
            if y < edge:
                adj.set_value(adj.get_value() - max_speed * (edge - y) / edge)
            elif y > h - edge:
                adj.set_value(adj.get_value() + max_speed * (y - (h - edge)) / edge)
            return True

        def on_motion(_ctl, _x, y):
            state["y"] = y
            if not state["source"]:
                state["source"] = GLib.timeout_add(16, tick)

        motion = Gtk.DropControllerMotion()
        motion.connect("motion", on_motion)
        motion.connect("leave", lambda _c: state.update(y=None))
        scrolled.add_controller(motion)

    def _sync_lutris_library(self):
        """Adds Lutris games not yet in the list, skipping ones the user removed."""
        games = self.tierlist_data["games"]
        known = {g["id"] for g in games} | set(self.tierlist_data.get("removed_ids", []))
        titles = {g["title"].lower() for g in games}
        fresh = get_lutris_games()
        by_id = {g["id"]: g for g in games}
        changed = False
        for f in fresh:  # keep type/playtime current for games imported by older versions
            old = by_id.get(f["id"])
            for k in ("runner", "runner_name", "platform", "service", "installed", "playtime"):
                if old is not None and old.get(k) != f.get(k):
                    old[k] = f.get(k)
                    changed = True
        new = [g for g in fresh if g["id"] not in known and g["title"].lower() not in titles]
        games.extend(new)
        if new or changed:
            save_tierlist(self.tierlist_data)

    def _register_actions(self):
        act_import = Gio.SimpleAction.new("import_lutris", None)
        act_import.connect("activate", self._on_import_lutris_action)
        self.add_action(act_import)

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
        self.btn_import_lutris.connect("clicked", self._on_import_lutris_action)
        self.btn_add_tier.connect("clicked", self._on_add_tier_clicked)
        self.btn_add_category.connect("clicked", self._on_add_category_clicked)

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

    def _setup_sidebar(self):
        # Sync toggle button with split_view show-sidebar
        self.btn_toggle_sidebar.bind_property(
            "active",
            self.split_view,
            "show-sidebar",
            GObject.BindingFlags.BIDIRECTIONAL
        )

        self.sidebar_nav_list.connect("row-activated", self._on_nav_row_activated)
        self.sidebar_status_list.connect("row-activated", self._on_status_row_activated)
        self.sidebar_category_list.connect("row-activated", self._on_category_row_activated)
        self.sidebar_source_list.connect("row-activated", self._on_source_row_activated)

    def _build_sidebar_items(self):
        # 1. Navigation items: Tier List & Todos os Jogos
        while child := self.sidebar_nav_list.get_first_child():
            self.sidebar_nav_list.remove(child)

        all_games = self.tierlist_data.get("games", [])
        total_count = len(all_games)

        row_tierlist = self._create_sidebar_row("view-column-symbolic", "Tier List")
        row_tierlist.mode_id = "tierlist"
        self.sidebar_nav_list.append(row_tierlist)

        row_all = self._create_sidebar_row("applications-games-symbolic", "Todos os Jogos", str(total_count))
        row_all.mode_id = "all"
        self.sidebar_nav_list.append(row_all)

        # 2. Status items
        while child := self.sidebar_status_list.get_first_child():
            self.sidebar_status_list.remove(child)

        for s in STATUS_CHOICES:
            s_id = s["id"]
            count = sum(1 for g in all_games if g.get("status") == s_id)
            row_s = self._create_sidebar_row(s["icon"], s["name"], str(count) if count > 0 else "")
            row_s.status_id = s_id
            self.sidebar_status_list.append(row_s)

        # 3. Category items
        while child := self.sidebar_category_list.get_first_child():
            self.sidebar_category_list.remove(child)

        cats = self.tierlist_data.get("categories", DEFAULT_CATEGORIES)
        for cat in cats:
            count = sum(1 for g in all_games if cat in g.get("categories", []))
            row_c = self._create_sidebar_row("folder-symbolic", cat, str(count) if count > 0 else "")
            row_c.category_name = cat
            self.sidebar_category_list.append(row_c)

        # 4. Source items
        while child := self.sidebar_source_list.get_first_child():
            self.sidebar_source_list.remove(child)

        lutris_count = sum(1 for g in all_games if g.get("source") == "lutris")
        row_lutris = self._create_sidebar_row("applications-games-symbolic", "Lutris", str(lutris_count) if lutris_count > 0 else "")
        row_lutris.source_id = "lutris"
        self.sidebar_source_list.append(row_lutris)

        heroic_count = sum(1 for g in all_games if g.get("source") == "heroic")
        row_heroic = self._create_sidebar_row("applications-games-symbolic", "Heroic", str(heroic_count) if heroic_count > 0 else "")
        row_heroic.source_id = "heroic"
        self.sidebar_source_list.append(row_heroic)

        self._build_type_sidebar(all_games)

    def _build_type_sidebar(self, all_games):
        """Runner and platform filters (Linux, Wine, Steam, Flatpak / Windows, PlayStation 2...), as in Lutris."""
        if not hasattr(self, "sidebar_type_lists"):
            parent = self.sidebar_source_list.get_parent()
            self.sidebar_type_lists = {}
            for key, title in (("runner", "Runners"), ("platform", "Plataformas")):
                label = Gtk.Label(label=title, halign=Gtk.Align.START, margin_start=8, margin_top=12)
                label.add_css_class("caption-heading")
                label.add_css_class("dimmed")
                lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
                lb.add_css_class("navigation-sidebar")
                lb.connect("row-activated", self._on_type_row_activated)
                parent.append(label)
                parent.append(lb)
                self.sidebar_type_lists[key] = lb
        for key, lb in self.sidebar_type_lists.items():
            while child := lb.get_first_child():
                lb.remove(child)
            field = "runner_name" if key == "runner" else "platform"
            counts = {}
            for g in all_games:
                v = g.get(field) or (g.get("runner") if key == "runner" else "")
                if v:
                    counts[v] = counts.get(v, 0) + 1
            for value in sorted(counts):
                row = self._create_sidebar_row(type_icon(value) or "applications-games-symbolic", value, str(counts[value]))
                row.type_filter = (key, value)
                lb.append(row)

    def _on_type_row_activated(self, listbox, row):
        key, value = row.type_filter
        self.current_sidebar_mode = f"{key}:{value}"
        self.main_view_stack.set_visible_child_name("library")
        self.library_title_label.set_label(f"{'Runner' if key == 'runner' else 'Plataforma'}: {value}")
        self.window_title.set_subtitle(value)
        self._apply_filters()

    def _create_sidebar_row(self, icon_name: str, label_text: str, badge_text: str = "") -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(8)
        box.set_margin_end(8)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        box.append(icon)

        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        box.append(lbl)

        if badge_text:
            badge = Gtk.Label(label=badge_text)
            badge.add_css_class("dimmed")
            badge.add_css_class("caption")
            box.append(badge)

        row.set_child(box)
        return row

    def _on_nav_row_activated(self, listbox, row):
        mode = getattr(row, "mode_id", "tierlist")
        if mode == "tierlist":
            self.current_sidebar_mode = "tierlist"
            self.main_view_stack.set_visible_child_name("tierlist")
            self.window_title.set_subtitle("Tier List")
        else:
            self.current_sidebar_mode = "all"
            self.main_view_stack.set_visible_child_name("library")
            self.library_title_label.set_label("Todos os Jogos")
            self.window_title.set_subtitle("Todos os Jogos")
        self._apply_filters()

    def _on_status_row_activated(self, listbox, row):
        s_id = getattr(row, "status_id", "")
        self.current_sidebar_mode = f"status:{s_id}"
        s_name = next((s["name"] for s in STATUS_CHOICES if s["id"] == s_id), s_id)
        self.main_view_stack.set_visible_child_name("library")
        self.library_title_label.set_label(f"Status: {s_name}")
        self.window_title.set_subtitle(s_name)
        self._apply_filters()

    def _on_category_row_activated(self, listbox, row):
        cat_name = getattr(row, "category_name", "")
        self.current_sidebar_mode = f"category:{cat_name}"
        self.main_view_stack.set_visible_child_name("library")
        self.library_title_label.set_label(f"Categoria: {cat_name}")
        self.window_title.set_subtitle(cat_name)
        self._apply_filters()

    def _on_source_row_activated(self, listbox, row):
        src_id = getattr(row, "source_id", "")
        self.current_sidebar_mode = f"source:{src_id}"
        src_name = "Lutris" if src_id == "lutris" else "Heroic"
        self.main_view_stack.set_visible_child_name("library")
        self.library_title_label.set_label(f"Fonte: {src_name}")
        self.window_title.set_subtitle(src_name)
        self._apply_filters()

    def _on_add_category_clicked(self, _):
        dialog = Adw.AlertDialog.new("Nova Categoria", "Digite o nome da nova categoria para seus jogos.")
        entry = Gtk.Entry()
        entry.set_placeholder_text("Nome da categoria (ex: Favoritos, RPGs)")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("create", "Criar")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        def handle_response(d, response):
            if response == "create":
                name = entry.get_text().strip()
                if name:
                    cats = self.tierlist_data.setdefault("categories", copy.deepcopy(DEFAULT_CATEGORIES))
                    if name not in cats:
                        cats.append(name)
                        save_tierlist(self.tierlist_data)
                        self._build_sidebar_items()
                        self.toast_overlay.add_toast(Adw.Toast.new(f"Categoria '{name}' criada"))

        dialog.connect("response", handle_response)
        dialog.present(self)

    def _setup_detail_bar(self):
        self.btn_detail_close.connect("clicked", lambda _: self.detail_bar_revealer.set_reveal_child(False))
        self.btn_detail_edit.connect("clicked", self._on_detail_edit_clicked)

    def _on_detail_edit_clicked(self, _):
        if not self.selected_game_for_detail:
            return
        dialog = GameEditDialog(
            parent_window=self,
            game_data=self.selected_game_for_detail,
            on_saved=self._on_detail_saved,
        )
        dialog.present(self)

    def _on_detail_saved(self, updated_data: Dict[str, Any]):
        games = self.tierlist_data.get("games", [])
        for i, g in enumerate(games):
            if g["id"] == updated_data["id"]:
                games[i] = updated_data
                break
        save_tierlist(self.tierlist_data)
        self._build_sidebar_items()
        self._populate_all_games()
        self._show_game_in_detail_bar(updated_data)

    def _show_game_in_detail_bar(self, game_data: Dict[str, Any]):
        self.selected_game_for_detail = game_data
        self.detail_title_lbl.set_label(game_data.get("title", ""))

        platform = game_data.get("platform") or "Linux"
        runner = game_data.get("runner_name") or game_data.get("runner") or game_data.get("source", "")
        self.detail_platform_lbl.set_label(f"Plataforma: {platform} ({runner})")

        playtime = float(game_data.get("playtime") or 0)
        self.detail_playtime_lbl.set_label(f"Tempo: {playtime:.1f}h" if playtime > 0 else "Tempo: 0h")

        status_id = game_data.get("status", "backlog")
        status_name = next((s["name"] for s in STATUS_CHOICES if s["id"] == status_id), status_id)
        self.detail_status_lbl.set_label(f"Status: {status_name}")

        tier_id = game_data.get("tier", "UNRANKED")
        self.detail_tier_lbl.set_label(f"Tier: {tier_id}")

        extra = [
            f"Empresa: {game_data['company']}" if game_data.get("company") else "",
            f"Franquia: {game_data['franchise']}" if game_data.get("franchise") else "",
            f"Gêneros: {', '.join(game_data['genres'])}" if game_data.get("genres") else "",
            f"Categorias: {', '.join(game_data['categories'])}" if game_data.get("categories") else "",
            f"Origem: {game_data.get('source', '').title()}" if game_data.get("source") else "",
            "Instalado" if game_data.get("installed") else ("Não instalado" if "installed" in game_data else ""),
        ]
        self.detail_extra_lbl.set_label(" • ".join(x for x in extra if x))

        cover_path = game_data.get("cover_vertical") or game_data.get("cover_path")
        if cover_path and os.path.exists(cover_path):
            self.detail_poster_pic.set_filename(cover_path)
            self.detail_poster_pic.set_visible(True)
        else:
            self.detail_poster_pic.set_visible(False)

        self.detail_bar_revealer.set_reveal_child(True)

    def _setup_search_and_filters(self):
        self.filter_search_entry.connect("search-changed", self._on_search_query_changed)
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

        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_poster = Gtk.ToggleButton(label="Pôster")
        btn_header = Gtk.ToggleButton(label="Banner")
        btn_icon = Gtk.ToggleButton(label="Ícone")

        btn_header.set_group(btn_poster)
        btn_icon.set_group(btn_poster)

        if self.current_view_mode == "header":
            btn_header.set_active(True)
        elif self.current_view_mode == "icon":
            btn_icon.set_active(True)
        else:
            btn_poster.set_active(True)

        btn_poster.connect("toggled", lambda b: b.get_active() and self._set_view_mode("poster"))
        btn_header.connect("toggled", lambda b: b.get_active() and self._set_view_mode("header"))
        btn_icon.connect("toggled", lambda b: b.get_active() and self._set_view_mode("icon"))

        mode_box.append(btn_poster)
        mode_box.append(btn_header)
        mode_box.append(btn_icon)
        box.append(mode_box)

        sep = Gtk.Separator()
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        box.append(sep)

        # Section: Zoom Scale (1 to 5)
        lbl_zoom = Gtk.Label(label="Nível de Zoom")
        lbl_zoom.add_css_class("caption-heading")
        lbl_zoom.set_halign(Gtk.Align.START)
        box.append(lbl_zoom)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 5, 1)
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_value(self.current_zoom)
        scale.connect("value-changed", self._on_zoom_changed)
        box.append(scale)

        sep2 = Gtk.Separator()
        sep2.set_margin_top(4)
        sep2.set_margin_bottom(4)
        box.append(sep2)

        lbl_info = Gtk.Label(label="Informações nos Cards")
        lbl_info.add_css_class("caption-heading")
        lbl_info.set_halign(Gtk.Align.START)
        box.append(lbl_info)
        for key, label in BADGE_OPTIONS.items():
            chk = Gtk.CheckButton(label=label)
            chk.set_active(self.badge_settings[key])
            chk.connect("toggled", self._on_badge_option_toggled, key)
            box.append(chk)

        popover.set_child(box)
        self.btn_view_options.set_popover(popover)

    def _on_badge_option_toggled(self, chk: Gtk.CheckButton, key: str):
        self.badge_settings[key] = chk.get_active()
        self._save_view_settings()
        for card in (*self.game_cards.values(), *self.library_cards.values()):
            card.set_badges(self.badge_settings)

    def _save_view_settings(self):
        self.tierlist_data.setdefault("view_settings", {}).update(self.badge_settings)
        self.tierlist_data.setdefault("view_settings", {})["view_mode"] = self.current_view_mode
        self.tierlist_data.setdefault("view_settings", {})["zoom_level"] = self.current_zoom
        save_tierlist(self.tierlist_data)

    def _set_view_mode(self, mode: str):
        self.current_view_mode = mode
        self._save_view_settings()
        self._build_tier_rows()
        self._populate_all_games()

    def _on_zoom_changed(self, scale: Gtk.Scale):
        new_val = int(round(scale.get_value()))
        if new_val != self.current_zoom:
            self.current_zoom = new_val
            self._save_view_settings()
            self._build_tier_rows()
            self._populate_all_games()

    def _build_tier_rows(self):
        """
        Constructs the configurable tier rows with fixed width badges (100px)
        and consistent minimum row heights, preventing jarring resizes.
        """
        while child := self.tiers_container.get_first_child():
            self.tiers_container.remove(child)

        while child := self.unranked_container.get_first_child():
            self.unranked_container.remove(child)

        self.tier_flowboxes.clear()

        # Calculate consistent minimum row height based on current view mode and zoom
        if self.current_view_mode == "header":
            w, h = DIMENSIONS_HEADER.get(self.current_zoom, (176, 82))
        elif self.current_view_mode == "icon":
            w, h = DIMENSIONS_ICON.get(self.current_zoom, (80, 80))
        else: # poster
            w, h = DIMENSIONS_POSTER.get(self.current_zoom, (120, 180))

        row_min_height = h + 32

        tiers = self.tierlist_data.get("tiers", DEFAULT_TIERS)
        for idx, tier in enumerate(tiers):
            tid = tier["id"]
            if tid == "UNRANKED":
                continue

            row_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_card.set_size_request(-1, row_min_height)
            row_card.add_css_class("card")
            row_card.add_css_class("tier-card")

            # Tier Header Badge: strictly fixed width (100px)
            header_badge = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            header_badge.set_size_request(100, -1)
            header_badge.set_hexpand(False)
            header_badge.set_vexpand(True)
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

            # Top action bar inside badge
            badge_top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            tier_menu_btn = Gtk.MenuButton()
            tier_menu_btn.set_icon_name("view-more-symbolic")
            tier_menu_btn.set_tooltip_text("Opções do tier")
            tier_menu_btn.add_css_class("flat")
            tier_menu_btn.set_valign(Gtk.Align.START)
            tier_menu_btn.set_halign(Gtk.Align.END)
            tier_menu_btn.set_hexpand(True)
            self._setup_tier_menu(tier_menu_btn, tier, idx, len(tiers))
            badge_top_box.append(tier_menu_btn)
            header_badge.append(badge_top_box)

            # Prominent Centered Tier Letter Label
            lbl = Gtk.Label(label=tier.get("name", tid))
            lbl.add_css_class("title-1")
            lbl.set_halign(Gtk.Align.CENTER)
            lbl.set_valign(Gtk.Align.CENTER)
            lbl.set_hexpand(True)
            lbl.set_vexpand(True)
            header_badge.append(lbl)

            row_card.append(header_badge)

            # FlowBox for games in this tier
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

        btn_edit = Gtk.Button(label="Editar tier (nome e cor)")
        btn_edit.add_css_class("flat")
        btn_edit.connect("clicked", lambda _: (popover.popdown(), self._on_edit_tier_clicked(tier)))
        box.append(btn_edit)

        btn_up = Gtk.Button(label="Mover para cima")
        btn_up.add_css_class("flat")
        if index <= 0:
            btn_up.set_sensitive(False)
        btn_up.connect("clicked", lambda _: (popover.popdown(), self._move_tier(index, index - 1)))
        box.append(btn_up)

        btn_down = Gtk.Button(label="Mover para baixo")
        btn_down.add_css_class("flat")
        if index >= total_tiers - 1:
            btn_down.set_sensitive(False)
        btn_down.connect("clicked", lambda _: (popover.popdown(), self._move_tier(index, index + 1)))
        box.append(btn_down)

        sep = Gtk.Separator()
        box.append(sep)

        btn_del = Gtk.Button(label="Excluir tier")
        btn_del.add_css_class("destructive-action")
        btn_del.connect("clicked", lambda _: (popover.popdown(), self._on_delete_tier_clicked(tier)))
        box.append(btn_del)

        popover.set_child(box)
        menu_btn.set_popover(popover)

    def _create_tier_flowbox(self, tier_id: str) -> Gtk.FlowBox:
        flowbox = Gtk.FlowBox()
        flowbox.set_valign(Gtk.Align.FILL)
        flowbox.set_hexpand(True)
        flowbox.set_vexpand(True)
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
        for g in self.tierlist_data.get("games", []):
            if g.get("tier") == tid:
                g["tier"] = "UNRANKED"

        self.tierlist_data["tiers"] = [t for t in self.tierlist_data.get("tiers", []) if t["id"] != tid]
        save_tierlist(self.tierlist_data)
        self._build_tier_rows()
        self._populate_all_games()
        self.toast_overlay.add_toast(Adw.Toast.new(f"Tier '{tier['name']}' removido"))

    # --------------------------------------------------------------------------
    # Populating Games in Tiers and Library Grid
    # --------------------------------------------------------------------------

    def _populate_all_games(self):
        # 1. Clear existing FlowBoxes
        for fb in self.tier_flowboxes.values():
            while child := fb.get_first_child():
                fb.remove(child)

        while child := self.library_flowbox.get_first_child():
            self.library_flowbox.remove(child)

        self.game_cards.clear()
        self.library_cards.clear()

        all_games = self.tierlist_data.get("games", [])
        total_games_count = len(all_games)

        # Empty state toggle for tier list
        if total_games_count == 0:
            self.empty_state.set_visible(True)
            self.main_content_box.set_visible(False)
        else:
            self.empty_state.set_visible(False)
            self.main_content_box.set_visible(True)

        tiers = self.tierlist_data.get("tiers", DEFAULT_TIERS)
        unranked_visible_count = 0

        for game in all_games:
            gid = game["id"]
            tier_id = game.get("tier", "UNRANKED")

            card = self._make_card(game, tiers)
            self.game_cards[gid] = card

            target_fb = self.tier_flowboxes.get(tier_id)
            if not target_fb:
                target_fb = self.tier_flowboxes.get("UNRANKED")

            if target_fb:
                target_fb.append(card)

            lib_card = self._make_card(game, tiers)
            self.library_cards[gid] = lib_card
            self.library_flowbox.append(lib_card)

        self._apply_filters()

    def _make_card(self, game, tiers, on_selected=None) -> GameCard:
        return GameCard(
            game_data=game,
            tiers=tiers,
            on_tier_changed=self.move_game_to_tier,
            on_deleted=self.delete_game,
            on_updated=self.update_game_data,
            view_mode=self.current_view_mode,
            zoom_level=self.current_zoom,
            on_selected=on_selected or self._show_game_in_detail_bar,
            badges=self.badge_settings,
        )

    def _apply_filters(self):
        unranked_visible_count = 0
        for gid, card in self.game_cards.items():
            matches = self._game_matches_filters(card.game_data)
            card.get_parent().set_visible(matches)
            if matches and card.game_data.get("tier", "UNRANKED") == "UNRANKED":
                unranked_visible_count += 1

        for gid, card in self.library_cards.items():
            matches = self._game_matches_filters(card.game_data) and self._game_matches_sidebar_selection(card.game_data)
            card.get_parent().set_visible(matches)

        self.unranked_count_label.set_label(f"{unranked_visible_count} jogos")
        self._update_filter_banner()

    def _game_matches_sidebar_selection(self, game: Dict[str, Any]) -> bool:
        mode = self.current_sidebar_mode
        if mode in ("tierlist", "all"):
            return True
        if mode.startswith("status:"):
            target_status = mode.split(":", 1)[1]
            return game.get("status") == target_status
        if mode.startswith("category:"):
            target_cat = mode.split(":", 1)[1]
            return target_cat in game.get("categories", [])
        if mode.startswith("runner:"):
            return (game.get("runner_name") or game.get("runner")) == mode.split(":", 1)[1]
        if mode.startswith("platform:"):
            return game.get("platform") == mode.split(":", 1)[1]
        if mode.startswith("source:"):
            target_src = mode.split(":", 1)[1]
            return game.get("source") == target_src
        return True

    def _game_matches_filters(self, game: Dict[str, Any]) -> bool:
        title = game.get("title", "").lower()
        company = (game.get("company") or "").lower()
        genres = [g.lower() for g in game.get("genres", [])]

        if self.filter_search and self.filter_search.lower() not in title:
            return False

        if self.filter_company != "Todas as Empresas":
            if company != self.filter_company.lower():
                return False

        if self.filter_genre != "Todos os Gêneros":
            if self.filter_genre.lower() not in genres:
                return False

        return True

    def _update_filter_banner(self):
        active_parts = []
        if self.filter_search:
            active_parts.append(f"Busca: '{self.filter_search}'")
        if self.filter_company != "Todas as Empresas":
            active_parts.append(f"Empresa: {self.filter_company}")
        if self.filter_genre != "Todos os Gêneros":
            active_parts.append(f"Gênero: {self.filter_genre}")

        if active_parts:
            self.filter_banner.set_title(" • ".join(active_parts))
            self.filter_banner.set_revealed(True)
        else:
            self.filter_banner.set_revealed(False)

    # --------------------------------------------------------------------------
    # Game CRUD & Drag-and-Drop
    # --------------------------------------------------------------------------

    def move_game_to_tier(self, game_id: str, new_tier_id: str):
        game = next((g for g in self.tierlist_data.get("games", []) if g["id"] == game_id), None)
        card = self.game_cards.get(game_id)
        target_fb = self.tier_flowboxes.get(new_tier_id)
        if not game or not card or not target_fb:
            return
        game["tier"] = new_tier_id
        save_tierlist(self.tierlist_data)
        # Deferred: removing the dragged widget inside its own drop handler is unsafe
        GLib.idle_add(self._reparent_card, card, target_fb)

    def _reparent_card(self, old_card: Gtk.Widget, target_fb: Gtk.FlowBox):
        """Swaps the moved game's card for a fresh one in the target tier (cheap: one card, not the whole list)."""
        gid = old_card.game_id
        old_card.get_parent().get_parent().remove(old_card.get_parent())
        card = self._make_card(self.library_cards[gid].game_data, self.tierlist_data.get("tiers", DEFAULT_TIERS))
        self.game_cards[gid] = card
        target_fb.append(card)
        lib = self.library_cards[gid]
        lib._setup_menu()
        lib._update_tooltip()
        self._apply_filters()
        return False

    def update_game_data(self, updated_game: Dict[str, Any]):
        games = self.tierlist_data.get("games", [])
        for i, g in enumerate(games):
            if g["id"] == updated_game["id"]:
                games[i] = updated_game
                break
        save_tierlist(self.tierlist_data)
        self._update_filter_dropdown_models()
        self._build_sidebar_items()
        self._populate_all_games()

    def delete_game(self, game_id: str):
        deleted_game = None
        games = self.tierlist_data.get("games", [])
        for g in games:
            if g["id"] == game_id:
                deleted_game = g
                break

        self.tierlist_data["games"] = [g for g in games if g["id"] != game_id]
        self.tierlist_data.setdefault("removed_ids", []).append(game_id)
        save_tierlist(self.tierlist_data)

        self._update_filter_dropdown_models()
        self._build_sidebar_items()
        self._populate_all_games()

        if deleted_game:
            toast = Adw.Toast.new(f"'{deleted_game.get('title')}' removido")
            toast.set_button_label("Desfazer")
            toast.connect("button-clicked", lambda _: self._undo_delete(deleted_game))
            self.toast_overlay.add_toast(toast)

    def _undo_delete(self, restored_game: Dict[str, Any]):
        self.tierlist_data.setdefault("games", []).append(restored_game)
        removed = self.tierlist_data.get("removed_ids", [])
        if restored_game["id"] in removed:
            removed.remove(restored_game["id"])
        save_tierlist(self.tierlist_data)
        self._update_filter_dropdown_models()
        self._build_sidebar_items()
        self._populate_all_games()
        self.toast_overlay.add_toast(Adw.Toast.new(f"'{restored_game.get('title')}' restaurado"))

    # --------------------------------------------------------------------------
    # Adding Games & Lutris/Heroic Import
    # --------------------------------------------------------------------------

    def _on_add_game_clicked(self, _):
        dialog = SearchGameDialog(
            parent_window=self,
            tiers=self.tierlist_data.get("tiers", DEFAULT_TIERS),
            categories=self.tierlist_data.get("categories", DEFAULT_CATEGORIES),
            on_game_selected=self._on_game_added_from_dialog,
        )
        dialog.present(self)

    def _on_game_added_from_dialog(self, game_data: Dict[str, Any]):
        games = self.tierlist_data.setdefault("games", [])
        for i, g in enumerate(games):
            if g["id"] == game_data["id"]:
                games[i] = game_data
                break
        else:
            games.append(game_data)

        save_tierlist(self.tierlist_data)
        self._update_filter_dropdown_models()
        self._build_sidebar_items()
        self._populate_all_games()
        self.toast_overlay.add_toast(Adw.Toast.new(f"'{game_data.get('title')}' adicionado"))

    def _on_import_lutris_action(self, *args):
        dialog = LutrisImportDialog(
            parent_window=self,
            tiers=self.tierlist_data.get("tiers", DEFAULT_TIERS),
            on_imported=self._on_games_imported_from_lutris,
        )
        dialog.present(self)

    def _on_games_imported_from_lutris(self, imported_games: List[Dict[str, Any]]):
        if not imported_games:
            return

        existing_games = self.tierlist_data.setdefault("games", [])
        existing_ids = {g["id"] for g in existing_games}
        existing_titles = {g["title"].lower() for g in existing_games}

        added_count = 0
        skipped_count = 0
        new_categories = set(self.tierlist_data.get("categories", DEFAULT_CATEGORIES))

        for g in imported_games:
            if g["id"] in existing_ids or g["title"].lower() in existing_titles:
                skipped_count += 1
                continue
            existing_games.append(g)
            existing_ids.add(g["id"])
            existing_titles.add(g["title"].lower())
            added_count += 1

            for c in g.get("categories", []):
                new_categories.add(c)

        self.tierlist_data["categories"] = list(new_categories)
        save_tierlist(self.tierlist_data)

        self._update_filter_dropdown_models()
        self._build_sidebar_items()
        self._populate_all_games()

        self.toast_overlay.add_toast(Adw.Toast.new(f"{added_count} jogos importados ({skipped_count} já existiam)"))

    # --------------------------------------------------------------------------
    # Filters & SearchBar
    # --------------------------------------------------------------------------

    def _on_search_query_changed(self, entry):
        self.filter_search = entry.get_text().strip()
        self._populate_all_games()

    def _on_company_filter_changed(self, dropdown, _):
        if self._updating_filter_models:
            return
        selected_item = dropdown.get_selected_item()
        if selected_item:
            self.filter_company = selected_item.get_string()
            self._populate_all_games()

    def _on_genre_filter_changed(self, dropdown, _):
        if self._updating_filter_models:
            return
        selected_item = dropdown.get_selected_item()
        if selected_item:
            self.filter_genre = selected_item.get_string()
            self._populate_all_games()

    def _on_clear_filters_clicked(self, _):
        self.filter_search_entry.set_text("")
        self.filter_company_dropdown.set_selected(0)
        self.filter_genre_dropdown.set_selected(0)
        self.filter_search = ""
        self.filter_company = "Todas as Empresas"
        self.filter_genre = "Todos os Gêneros"
        self._populate_all_games()

    def _update_filter_dropdown_models(self):
        self._updating_filter_models = True

        companies = set()
        genres = set()

        for g in self.tierlist_data.get("games", []):
            if c := g.get("company"):
                companies.add(c)
            for gen in g.get("genres", []):
                if gen:
                    genres.add(gen)

        c_list = ["Todas as Empresas"] + sorted(list(companies))
        g_list = ["Todos os Gêneros"] + sorted(list(genres))

        self.filter_company_dropdown.set_model(Gtk.StringList.new(c_list))
        self.filter_genre_dropdown.set_model(Gtk.StringList.new(g_list))

        self._updating_filter_models = False

    # --------------------------------------------------------------------------
    # Export / Import / Clear Actions
    # --------------------------------------------------------------------------

    def _on_export_png_action(self, action, param):
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Salvar Imagem da Tier List")
        file_dialog.set_initial_name("minha_tierlist.png")

        png_filter = Gtk.FileFilter.new()
        png_filter.set_name("Imagem PNG (*.png)")
        png_filter.add_pattern("*.png")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(png_filter)
        file_dialog.set_filters(filters)

        def on_saved(dialog, result):
            try:
                gfile = dialog.save_finish(result)
                if gfile:
                    out_path = gfile.get_path()
                    success = export_tierlist_to_png(
                        self.tierlist_data,
                        out_path,
                        view_mode=self.current_view_mode,
                        zoom_level=self.current_zoom,
                    )
                    if success:
                        self.toast_overlay.add_toast(Adw.Toast.new("Imagem PNG exportada com sucesso"))
                    else:
                        self.toast_overlay.add_toast(Adw.Toast.new("Erro ao exportar imagem PNG"))
            except Exception as e:
                print(f"[Export PNG] Cancelled: {e}")

        file_dialog.save(self, None, on_saved)

    def _on_export_json_action(self, action, param):
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Exportar Tier List (JSON)")
        file_dialog.set_initial_name("tierlist_backup.json")

        json_filter = Gtk.FileFilter.new()
        json_filter.set_name("Arquivo JSON (*.json)")
        json_filter.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(json_filter)
        file_dialog.set_filters(filters)

        def on_saved_json(dialog, result):
            try:
                gfile = dialog.save_finish(result)
                if gfile:
                    out_path = gfile.get_path()
                    if export_tierlist_to_json(self.tierlist_data, out_path):
                        self.toast_overlay.add_toast(Adw.Toast.new("Arquivo JSON exportado com sucesso"))
            except Exception as e:
                print(f"[Export JSON] Cancelled: {e}")

        file_dialog.save(self, None, on_saved_json)

    def _on_import_json_action(self, action, param):
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Importar Tier List (JSON)")

        json_filter = Gtk.FileFilter.new()
        json_filter.set_name("Arquivo JSON (*.json)")
        json_filter.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(json_filter)
        file_dialog.set_filters(filters)

        def on_opened_json(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                if gfile:
                    in_path = gfile.get_path()
                    imported = import_tierlist_from_json(in_path)
                    if imported:
                        self.tierlist_data = imported
                        save_tierlist(self.tierlist_data)
                        self._update_filter_dropdown_models()
                        self._build_sidebar_items()
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
                self._build_sidebar_items()
                self._populate_all_games()
                self.toast_overlay.add_toast(Adw.Toast.new("Lista limpa"))

        dialog.connect("response", handle_response)
        dialog.present(self)
