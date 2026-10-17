# lutris_dialog.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from gi.repository import Gtk, Adw, GLib, Pango
from typing import Callable, Dict, List, Optional, Any
from .lutris_importer import get_lutris_games, get_heroic_games


class LutrisImportDialog(Adw.Dialog):
    """
    Dialog to inspect and import games detected in Lutris and Heroic libraries,
    including play time, platforms, categories, and cover art.
    Inherits from modern Adw.Dialog.
    """

    def __init__(
        self,
        parent_window: Optional[Gtk.Widget] = None,
        tiers: Optional[List[Dict[str, Any]]] = None,
        on_imported: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ):
        super().__init__()
        self.set_title("Importar do Lutris / Heroic")
        self.set_content_width(720)
        self.set_content_height(580)
        self.tiers = tiers or []
        self.on_imported = on_imported

        # Load games
        self.detected_games = get_lutris_games() + get_heroic_games()
        self.game_checkboxes: Dict[str, Gtk.CheckButton] = {}

        # Main Layout
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        btn_cancel = Gtk.Button(label="Cancelar")
        btn_cancel.connect("clicked", lambda _: self.close())
        header.pack_start(btn_cancel)

        self.btn_import = Gtk.Button(label=f"Importar ({len(self.detected_games)})")
        self.btn_import.add_css_class("suggested-action")
        self.btn_import.connect("clicked", self._on_import_clicked)
        header.pack_end(self.btn_import)

        toolbar_view.add_top_bar(header)

        # Content Box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)

        # Banner with stats and selection helpers
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_info = Gtk.Label(label=f"{len(self.detected_games)} jogos encontrados nas suas bibliotecas.")
        lbl_info.add_css_class("heading")
        lbl_info.set_hexpand(True)
        lbl_info.set_halign(Gtk.Align.START)
        top_bar.append(lbl_info)

        btn_select_all = Gtk.Button(label="Selecionar Todos")
        btn_select_all.add_css_class("flat")
        btn_select_all.connect("clicked", lambda _: self._set_all_selected(True))
        top_bar.append(btn_select_all)

        btn_deselect_all = Gtk.Button(label="Desmarcar Todos")
        btn_deselect_all.add_css_class("flat")
        btn_deselect_all.connect("clicked", lambda _: self._set_all_selected(False))
        top_bar.append(btn_deselect_all)

        content_box.append(top_bar)

        # Scrolled List
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")

        for g in self.detected_games:
            gid = g["id"]
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(12)
            box.set_margin_end(12)

            chk = Gtk.CheckButton()
            chk.set_active(True)
            chk.connect("toggled", self._update_count)
            self.game_checkboxes[gid] = chk
            box.append(chk)

            # Thumbnail
            pic = Gtk.Picture()
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_size_request(36, 54) # 2:3 ratio
            pic.add_css_class("card")
            cover_path = g.get("cover_vertical") or g.get("cover_path")
            if cover_path and os.path.exists(cover_path):
                pic.set_filename(cover_path)
            else:
                display = Gdk.Display.get_default() if hasattr(Gdk, "Display") else None
                pic.set_paintable(None)
            box.append(pic)

            # Details
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            title_lbl = Gtk.Label(label=g.get("title", ""))
            title_lbl.set_halign(Gtk.Align.START)
            title_lbl.add_css_class("heading")
            title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            info_box.append(title_lbl)

            playtime = g.get("playtime", 0.0)
            runner = g.get("runner") or "Lutris"
            platform = g.get("platform") or "Linux"
            cats = ", ".join(g.get("categories", [])) or "Sem categoria"

            desc_parts = [f"Tempo: {playtime:.1f}h", f"{runner} ({platform})", f"Categorias: {cats}"]
            desc_lbl = Gtk.Label(label=" • ".join(desc_parts))
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.add_css_class("caption")
            desc_lbl.add_css_class("dimmed")
            info_box.append(desc_lbl)

            box.append(info_box)

            row.set_child(box)
            list_box.append(row)

        scrolled.set_child(list_box)
        content_box.append(scrolled)
        toolbar_view.set_content(content_box)

    def _set_all_selected(self, state: bool):
        for chk in self.game_checkboxes.values():
            chk.set_active(state)
        self._update_count()

    def _update_count(self, *_):
        count = sum(1 for chk in self.game_checkboxes.values() if chk.get_active())
        self.btn_import.set_label(f"Importar ({count})")
        self.btn_import.set_sensitive(count > 0)

    def _on_import_clicked(self, _):
        selected_games = []
        for g in self.detected_games:
            chk = self.game_checkboxes.get(g["id"])
            if chk and chk.get_active():
                selected_games.append(g)

        if self.on_imported:
            self.on_imported(selected_games)

        if self.get_root():
            self.close()
