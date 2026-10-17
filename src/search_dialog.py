# search_dialog.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import threading
from gi.repository import Gtk, Adw, GLib, Pango
from typing import Callable, Dict, List, Optional, Any
from .steamgrid import search_games, prepare_full_game_data, download_image_to_cache
from .config import STATUS_CHOICES


class SearchGameDialog(Adw.Dialog):
    """
    Search dialog to look up games via Steam Store & SteamGridDB,
    preview game details (poster, logo, franchise, company, genres) BEFORE adding,
    and configure tier, status, and category directly on addition.
    Inherits from modern Adw.Dialog.
    """

    def __init__(
        self,
        parent_window: Optional[Gtk.Widget] = None,
        tiers: Optional[List[Dict[str, Any]]] = None,
        categories: Optional[List[str]] = None,
        on_game_selected: Optional[Callable[[Dict], None]] = None,
    ):
        super().__init__()
        self.set_title("Adicionar Jogo")
        self.set_content_width(820)
        self.set_content_height(640)
        self.tiers = tiers or []
        self.categories = categories or []
        self.on_game_selected = on_game_selected

        self.current_preview_item: Optional[Dict] = None
        self.current_preview_data: Optional[Dict] = None

        # Main Layout
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        btn_close = Gtk.Button(label="Fechar")
        btn_close.connect("clicked", lambda _: self.close())
        header.pack_start(btn_close)
        toolbar_view.add_top_bar(header)

        # Split Container (Left: Search & Results, Right: Preview Details)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(360)
        paned.set_wide_handle(True)

        # ---------------- Left Pane: Search & Results ----------------
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left_box.set_margin_top(12)
        left_box.set_margin_bottom(12)
        left_box.set_margin_start(12)
        left_box.set_margin_end(6)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Nome do jogo (ex: Elden Ring)...")
        self.search_entry.connect("activate", self._on_search_clicked)
        search_box.append(self.search_entry)

        search_btn = Gtk.Button(label="Buscar")
        search_btn.add_css_class("suggested-action")
        search_btn.connect("clicked", self._on_search_clicked)
        search_box.append(search_btn)
        left_box.append(search_box)

        # Status spinner
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_box.set_halign(Gtk.Align.CENTER)
        self.status_box.set_margin_top(6)
        self.status_box.set_margin_bottom(6)
        self.spinner = Gtk.Spinner()
        self.status_label = Gtk.Label()
        self.status_label.add_css_class("dimmed")
        self.status_box.append(self.spinner)
        self.status_box.append(self.status_label)
        self.status_box.set_visible(False)
        left_box.append(self.status_box)

        # Results Scrolled List
        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_vexpand(True)
        scrolled_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("boxed-list")
        self.list_box.connect("row-selected", self._on_row_selected)
        scrolled_list.set_child(self.list_box)
        left_box.append(scrolled_list)

        paned.set_start_child(left_box)

        # ---------------- Right Pane: Preview Details ----------------
        self.right_scrolled = Gtk.ScrolledWindow()
        self.right_scrolled.set_vexpand(True)
        self.right_scrolled.set_hexpand(True)
        self.right_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.preview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.preview_container.set_margin_top(12)
        self.preview_container.set_margin_bottom(18)
        self.preview_container.set_margin_start(12)
        self.preview_container.set_margin_end(18)

        # Placeholder when nothing selected
        self.placeholder_state = Adw.StatusPage(
            icon_name="applications-games-symbolic",
            title="Pré-visualização do Jogo",
            description="Pesquise e selecione um jogo para ver a logo, capa e detalhes antes de adicionar.",
        )
        self.preview_container.append(self.placeholder_state)

        # Active preview content box (hidden initially)
        self.details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.details_box.set_visible(False)

        # Logo display
        self.logo_picture = Gtk.Picture()
        self.logo_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.logo_picture.set_size_request(-1, 72)
        self.logo_picture.set_halign(Gtk.Align.CENTER)
        self.details_box.append(self.logo_picture)

        # Poster & basic info horizontal header
        top_info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        top_info_box.set_halign(Gtk.Align.CENTER)

        self.poster_picture = Gtk.Picture()
        self.poster_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.poster_picture.set_size_request(120, 180) # Strict 2:3 ratio
        self.poster_picture.add_css_class("card")
        top_info_box.append(self.poster_picture)

        text_meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        text_meta_box.set_valign(Gtk.Align.CENTER)

        self.lbl_title = Gtk.Label()
        self.lbl_title.add_css_class("title-2")
        self.lbl_title.set_halign(Gtk.Align.START)
        self.lbl_title.set_wrap(True)
        self.lbl_title.set_max_width_chars(24)
        text_meta_box.append(self.lbl_title)

        self.lbl_franchise = Gtk.Label()
        self.lbl_franchise.add_css_class("heading")
        self.lbl_franchise.add_css_class("dimmed")
        self.lbl_franchise.set_halign(Gtk.Align.START)
        text_meta_box.append(self.lbl_franchise)

        self.lbl_company = Gtk.Label()
        self.lbl_company.add_css_class("body")
        self.lbl_company.set_halign(Gtk.Align.START)
        text_meta_box.append(self.lbl_company)

        self.lbl_genres = Gtk.Label()
        self.lbl_genres.add_css_class("caption")
        self.lbl_genres.add_css_class("dimmed")
        self.lbl_genres.set_halign(Gtk.Align.START)
        self.lbl_genres.set_wrap(True)
        self.lbl_genres.set_max_width_chars(28)
        text_meta_box.append(self.lbl_genres)

        top_info_box.append(text_meta_box)
        self.details_box.append(top_info_box)

        # Settings group: Tier, Status, Category
        config_group = Adw.PreferencesGroup()
        config_group.set_title("Configuração Inicial")
        self.details_box.append(config_group)

        # Tier Row
        self.row_tier = Adw.ComboRow()
        self.row_tier.set_title("Tier Inicial")
        tier_names = ["Banco de Jogos (Unranked)"] + [f"Tier {t.get('name', t.get('id'))}" for t in self.tiers]
        self.row_tier.set_model(Gtk.StringList.new(tier_names))
        self.row_tier.set_selected(0)
        config_group.add(self.row_tier)

        # Status Row
        self.row_status = Adw.ComboRow()
        self.row_status.set_title("Status do Jogo")
        self.row_status.set_model(Gtk.StringList.new([s["name"] for s in STATUS_CHOICES]))
        self.row_status.set_selected(0) # Default to Backlog ("Para Começar")
        config_group.add(self.row_status)

        # Category Row
        self.row_category = Adw.EntryRow()
        self.row_category.set_title("Categoria (ex: Cooperativo, RPG)")
        config_group.add(self.row_category)

        # Add Game Button
        self.btn_confirm_add = Gtk.Button(label="Adicionar à Tier List")
        self.btn_confirm_add.add_css_class("suggested-action")
        self.btn_confirm_add.add_css_class("pill")
        self.btn_confirm_add.set_halign(Gtk.Align.CENTER)
        self.btn_confirm_add.set_margin_top(8)
        self.btn_confirm_add.connect("clicked", self._on_confirm_add_clicked)
        self.details_box.append(self.btn_confirm_add)

        self.preview_container.append(self.details_box)
        self.right_scrolled.set_child(self.preview_container)
        paned.set_end_child(self.right_scrolled)

        toolbar_view.set_content(paned)

    def _set_loading(self, is_loading: bool, message: str = ""):
        self.status_box.set_visible(is_loading or bool(message))
        self.spinner.set_visible(is_loading)
        if is_loading:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.status_label.set_label(message)
        self.search_entry.set_sensitive(not is_loading)

    def _on_search_clicked(self, _):
        query = self.search_entry.get_text().strip()
        if not query:
            return

        self._set_loading(True, f"Buscando por '{query}'...")

        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        threading.Thread(target=self._run_search, args=(query,), daemon=True).start()

    def _run_search(self, query: str):
        results = search_games(query)
        GLib.idle_add(self._on_search_finished, results, query)

    def _on_search_finished(self, results: List[Dict], query: str):
        self._set_loading(False)
        if not results:
            self._set_loading(False, f"Nenhum jogo encontrado para '{query}'.")
            return

        for item in results:
            row = Gtk.ListBoxRow()
            row.game_item = item

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(10)
            box.set_margin_end(10)

            img = Gtk.Image.new_from_icon_name("applications-games-symbolic")
            img.set_pixel_size(24)
            img.set_valign(Gtk.Align.CENTER)
            box.append(img)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            title_lbl = Gtk.Label(label=item["title"])
            title_lbl.set_halign(Gtk.Align.START)
            title_lbl.add_css_class("heading")
            title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            info_box.append(title_lbl)

            franchise_text = item.get("franchise") or "Geral"
            source_txt = "SteamGridDB" if item.get("source") == "steamgriddb" else "Steam Store"
            meta_lbl = Gtk.Label(label=f"Franquia: {franchise_text} • {source_txt}")
            meta_lbl.set_halign(Gtk.Align.START)
            meta_lbl.add_css_class("caption")
            meta_lbl.add_css_class("dimmed")
            info_box.append(meta_lbl)

            box.append(info_box)

            row.set_child(box)
            self.list_box.append(row)

        # Select first result by default for immediate preview
        first_row = self.list_box.get_row_at_index(0)
        if first_row:
            self.list_box.select_row(first_row)

    def _on_row_selected(self, listbox, row):
        if not row or not hasattr(row, "game_item"):
            return

        item = row.game_item
        self.current_preview_item = item
        self.placeholder_state.set_visible(False)
        self.details_box.set_visible(True)

        self.btn_confirm_add.set_sensitive(False)
        self.btn_confirm_add.set_label("Carregando metadados...")

        # Run preview data preparation in background thread
        threading.Thread(target=self._fetch_preview_data, args=(item,), daemon=True).start()

    def _fetch_preview_data(self, item: Dict):
        full_data = prepare_full_game_data(item)
        GLib.idle_add(self._render_preview_details, full_data)

    def _render_preview_details(self, data: Dict):
        self.current_preview_data = data
        self.btn_confirm_add.set_sensitive(True)
        self.btn_confirm_add.set_label("Adicionar à Tier List")

        # Set title, franchise, company, genres
        self.lbl_title.set_label(data.get("title", ""))
        franchise = data.get("franchise") or "Geral"
        self.lbl_franchise.set_label(f"Franquia: {franchise}")
        company = data.get("company") or "Desconhecida"
        self.lbl_company.set_label(f"Empresa: {company}")
        genres_str = ", ".join(data.get("genres", [])) or "Sem gênero definido"
        self.lbl_genres.set_label(f"Gêneros: {genres_str}")

        # Set poster
        cover_path = data.get("cover_vertical") or data.get("cover_path")
        if cover_path and os.path.exists(cover_path):
            self.poster_picture.set_filename(cover_path)
            self.poster_picture.set_visible(True)
        else:
            self.poster_picture.set_visible(False)

        # Set logo (transparent PNG)
        logo_path = data.get("cover_logo")
        if logo_path and os.path.exists(logo_path):
            self.logo_picture.set_filename(logo_path)
            self.logo_picture.set_visible(True)
        else:
            self.logo_picture.set_visible(False)

    def _on_confirm_add_clicked(self, _):
        if not self.current_preview_data:
            return

        # Determine chosen tier
        selected_tier_idx = self.row_tier.get_selected()
        if selected_tier_idx == 0:
            chosen_tier = "UNRANKED"
        else:
            chosen_tier = self.tiers[selected_tier_idx - 1]["id"]

        # Determine chosen status
        selected_status_idx = self.row_status.get_selected()
        chosen_status = STATUS_CHOICES[selected_status_idx]["id"]

        # Determine category
        cat_text = self.row_category.get_text().strip()
        cats = [c.strip() for c in cat_text.split(",") if c.strip()] if cat_text else []

        self.current_preview_data["tier"] = chosen_tier
        self.current_preview_data["status"] = chosen_status
        if cats:
            existing = self.current_preview_data.get("categories", [])
            self.current_preview_data["categories"] = list(set(existing + cats))

        if self.on_game_selected:
            self.on_game_selected(self.current_preview_data)

        if self.get_root():
            self.close()
