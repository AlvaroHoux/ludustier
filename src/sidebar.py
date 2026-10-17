# sidebar.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
from gi.repository import Gtk, Adw, GObject

from .config import STATUS_CHOICES, DEFAULT_CATEGORIES, save_tierlist
from .game_card import type_icon


class SidebarMixin:
    """Sidebar of LudustierWindow: navigation, status, category, source, runner and platform lists.

    Relies on the window's template children and on `tierlist_data`, `current_sidebar_mode`,
    `main_view_stack`, `_apply_filters` and friends.
    """

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
