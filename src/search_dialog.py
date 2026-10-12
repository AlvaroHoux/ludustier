# search_dialog.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from gi.repository import Gtk, Adw, GLib, Pango
from typing import Callable, Dict, List, Optional
from .steamgrid import search_games, prepare_full_game_data


class SearchGameDialog(Adw.Dialog):
    """
    Search dialog to look up games via Steam Store & SteamGridDB,
    preview metadata, and add them to the tier list.
    Inherits from modern Adw.Dialog.
    """

    def __init__(self, parent_window: Optional[Gtk.Widget] = None, on_game_selected: Optional[Callable[[Dict], None]] = None):
        super().__init__()
        self.set_title("Adicionar Jogo")
        self.set_content_width(540)
        self.set_content_height(580)
        self.on_game_selected = on_game_selected

        # Main Layout
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        btn_close = Gtk.Button(label="Fechar")
        btn_close.connect("clicked", lambda _: self.close())
        header.pack_start(btn_close)
        toolbar_view.add_top_bar(header)

        # Content Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(18)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)

        # Search bar
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Digite o nome do jogo (ex: Elden Ring)...")
        self.search_entry.connect("activate", self._on_search_clicked)
        search_box.append(self.search_entry)

        search_btn = Gtk.Button(label="Buscar")
        search_btn.add_css_class("suggested-action")
        search_btn.connect("clicked", self._on_search_clicked)
        search_box.append(search_btn)
        main_box.append(search_box)

        # Spinner & Status message
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
        main_box.append(self.status_box)

        # Results List inside ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        scrolled.set_child(self.list_box)
        main_box.append(scrolled)

        toolbar_view.set_content(main_box)

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

        # Clear existing list
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
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(12)
            box.set_margin_end(12)

            img = Gtk.Image.new_from_icon_name("applications-games-symbolic")
            img.set_pixel_size(32)
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
            source_txt = "SteamGridDB" if item["source"] == "steamgriddb" else "Steam Store"
            meta_lbl = Gtk.Label(label=f"Franquia: {franchise_text} • Fonte: {source_txt}")
            meta_lbl.set_halign(Gtk.Align.START)
            meta_lbl.add_css_class("caption")
            meta_lbl.add_css_class("dimmed")
            info_box.append(meta_lbl)
            box.append(info_box)

            add_btn = Gtk.Button(label="Adicionar")
            add_btn.add_css_class("suggested-action")
            add_btn.set_valign(Gtk.Align.CENTER)

            def make_add_callback(raw_item, btn):
                return lambda _: self._on_add_game(raw_item, btn)

            add_btn.connect("clicked", make_add_callback(item, add_btn))
            box.append(add_btn)

            row.set_child(box)
            self.list_box.append(row)

    def _on_add_game(self, item: Dict, btn: Gtk.Button):
        btn.set_sensitive(False)
        btn.set_label("Baixando...")

        def download_and_fetch():
            full_data = prepare_full_game_data(item)
            GLib.idle_add(self._finish_add_game, full_data)

        threading.Thread(target=download_and_fetch, daemon=True).start()

    def _finish_add_game(self, game_data: Dict):
        if self.on_game_selected:
            self.on_game_selected(game_data)
        if self.get_root():
            self.close()
