# tier_dialog.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid
from gi.repository import Gtk, Adw, Gdk, GLib
from typing import Callable, Dict, Optional, Any
from .config import TIER_COLOR_PALETTE


class TierDialog(Adw.Dialog):
    """
    Dialog to create a new tier or edit an existing tier's name and color.
    Uses modern Adw.Dialog and Adw.PreferencesPage.
    """

    def __init__(
        self,
        parent_window: Optional[Gtk.Widget] = None,
        tier_data: Optional[Dict[str, Any]] = None,
        on_saved: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__()
        self.is_editing = tier_data is not None
        self.tier_data = tier_data or {
            "id": f"tier_{uuid.uuid4().hex[:8]}",
            "name": "Novo Tier",
            "color": "#ff7f7f",
            "text_color": "#000000",
        }
        self.on_saved = on_saved

        self.set_title("Editar Tier" if self.is_editing else "Novo Tier")
        self.set_content_width(440)
        self.set_content_height(480)

        self.current_color = self.tier_data.get("color", "#ff7f7f")
        self.current_text_color = self.tier_data.get("text_color", "#000000")

        # Main Layout
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        btn_cancel = Gtk.Button(label="Cancelar")
        btn_cancel.connect("clicked", lambda _: self.close())
        header.pack_start(btn_cancel)

        btn_save = Gtk.Button(label="Salvar" if self.is_editing else "Adicionar")
        btn_save.add_css_class("suggested-action")
        btn_save.connect("clicked", self._on_save_clicked)
        header.pack_end(btn_save)

        toolbar_view.add_top_bar(header)

        # Preferences Page & Groups
        page = Adw.PreferencesPage()

        # Preview Group
        preview_group = Adw.PreferencesGroup()
        preview_group.set_title("Pré-visualização")

        self.preview_box = Gtk.Box()
        self.preview_box.set_size_request(80, 72)
        self.preview_box.set_halign(Gtk.Align.CENTER)
        self.preview_box.add_css_class("tier-header-badge")
        self.preview_box.set_margin_top(12)
        self.preview_box.set_margin_bottom(12)

        self.preview_label = Gtk.Label(label=self.tier_data.get("name", "Tier"))
        self.preview_label.set_hexpand(True)
        self.preview_label.set_vexpand(True)
        self.preview_box.append(self.preview_label)

        preview_group.add(self.preview_box)
        page.add(preview_group)

        # Details Group
        details_group = Adw.PreferencesGroup()
        details_group.set_title("Configurações do Tier")

        self.name_entry = Adw.EntryRow()
        self.name_entry.set_title("Nome do Tier")
        self.name_entry.set_text(self.tier_data.get("name", ""))
        self.name_entry.connect("changed", self._on_name_changed)
        details_group.add(self.name_entry)

        page.add(details_group)

        # Color Group
        color_group = Adw.PreferencesGroup()
        color_group.set_title("Cor de Destaque")
        color_group.set_description("Selecione a cor para o cabeçalho do tier.")

        flow_colors = Gtk.FlowBox()
        flow_colors.set_selection_mode(Gtk.SelectionMode.NONE)
        flow_colors.set_min_children_per_line(6)
        flow_colors.set_max_children_per_line(6)
        flow_colors.set_column_spacing(12)
        flow_colors.set_row_spacing(12)
        flow_colors.set_halign(Gtk.Align.CENTER)
        flow_colors.set_margin_top(6)
        flow_colors.set_margin_bottom(12)

        for item in TIER_COLOR_PALETTE:
            c_hex = item["color"]
            t_hex = item["text_color"]
            btn = Gtk.Button()
            btn.set_size_request(36, 36)
            btn.set_tooltip_text(item["name"])
            btn.add_css_class("color-swatch-circle")

            prov = Gtk.CssProvider()
            prov.load_from_string(
                f"button.swatch-{c_hex.replace('#', '')} {{ background-color: {c_hex}; }}"
            )
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(display, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            btn.add_css_class(f"swatch-{c_hex.replace('#', '')}")

            def make_color_cb(bg, fg):
                return lambda _: self._select_color(bg, fg)

            btn.connect("clicked", make_color_cb(c_hex, t_hex))
            flow_colors.append(btn)

        color_group.add(flow_colors)
        page.add(color_group)

        toolbar_view.set_content(page)
        self._update_preview()

    def _select_color(self, bg: str, fg: str):
        self.current_color = bg
        self.current_text_color = fg
        self._update_preview()

    def _on_name_changed(self, entry):
        text = entry.get_text().strip()
        self.preview_label.set_label(text or "Tier")

    def _update_preview(self):
        css_prov = Gtk.CssProvider()
        css_prov.load_from_string(
            f".tier-preview-custom {{ background-color: {self.current_color}; color: {self.current_text_color}; font-weight: bold; font-size: 1.25rem; border-radius: 8px; }}"
        )
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, css_prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        self.preview_box.add_css_class("tier-preview-custom")
        self.preview_label.set_label(self.name_entry.get_text().strip() or "Tier")

    def _on_save_clicked(self, _):
        name = self.name_entry.get_text().strip()
        if not name:
            return

        self.tier_data["name"] = name
        self.tier_data["color"] = self.current_color
        self.tier_data["text_color"] = self.current_text_color

        if self.on_saved:
            self.on_saved(self.tier_data)
        if self.get_root():
            self.close()
