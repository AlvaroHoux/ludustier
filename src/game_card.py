# game_card.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from gi.repository import Gtk, Gdk, GLib, Pango
from typing import Callable, List, Dict, Optional, Any
from .game_edit_dialog import GameEditDialog
from .config import STATUS_CHOICES


# Exact 2:3 ratio for posters (width, height)
DIMENSIONS_POSTER = {
    1: (70, 105),
    2: (90, 135),
    3: (120, 180), # Default
    4: (150, 225),
    5: (180, 270),
}

# Standard horizontal banner ratio (~2.14:1)
DIMENSIONS_HEADER = {
    1: (100, 47),
    2: (136, 64),
    3: (176, 82),  # Default
    4: (220, 103),
    5: (260, 122),
}

# Exact 1:1 ratio for square icons
DIMENSIONS_ICON = {
    1: (48, 48),
    2: (64, 64),
    3: (80, 80),   # Default
    4: (100, 100),
    5: (120, 120),
}


class GameCard(Gtk.Box):
    """
    Game card widget for GNOME HIG.
    Maintains exact poster aspect ratio (2:3), source badges, playtime,
    status badges, and Lutris-like visual cues.
    """

    def __init__(
        self,
        game_data: Dict[str, Any],
        tiers: List[Dict[str, Any]],
        on_tier_changed: Callable[[str, str], None],
        on_deleted: Callable[[str], None],
        on_updated: Callable[[Dict[str, Any]], None],
        view_mode: str = "poster",
        zoom_level: int = 3,
        on_selected: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.game_data = game_data
        self.game_id = game_data["id"]
        self.tiers = tiers
        self.on_tier_changed = on_tier_changed
        self.on_deleted = on_deleted
        self.on_updated = on_updated
        self.view_mode = view_mode
        self.zoom_level = zoom_level
        self.on_selected = on_selected

        # Strictly align to start and avoid horizontal stretching
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_hexpand(False)
        self.set_vexpand(False)

        self.add_css_class("card")
        self.add_css_class("game-card-widget")

        # Container for picture and badges
        self.overlay = Gtk.Overlay()
        self.overlay.set_halign(Gtk.Align.CENTER)
        self.overlay.set_valign(Gtk.Align.CENTER)

        # Cover Image Picture
        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.set_can_shrink(True)
        self.picture.add_css_class("game-cover-image")
        self.overlay.set_child(self.picture)

        # Status badge (top-left)
        self.status_badge = Gtk.Image()
        self.status_badge.set_pixel_size(16)
        self.status_badge.set_valign(Gtk.Align.START)
        self.status_badge.set_halign(Gtk.Align.START)
        self.status_badge.set_margin_top(6)
        self.status_badge.set_margin_start(6)
        self.status_badge.add_css_class("card-status-badge")
        self.overlay.add_overlay(self.status_badge)

        # Source / Platform badge (bottom-right)
        self.source_badge = Gtk.Label()
        self.source_badge.set_valign(Gtk.Align.END)
        self.source_badge.set_halign(Gtk.Align.END)
        self.source_badge.set_margin_bottom(6)
        self.source_badge.set_margin_end(6)
        self.source_badge.add_css_class("caption")
        self.source_badge.add_css_class("card-source-badge")
        self.overlay.add_overlay(self.source_badge)

        # Playtime badge (bottom-left)
        self.playtime_badge = Gtk.Label()
        self.playtime_badge.set_valign(Gtk.Align.END)
        self.playtime_badge.set_halign(Gtk.Align.START)
        self.playtime_badge.set_margin_bottom(6)
        self.playtime_badge.set_margin_start(6)
        self.playtime_badge.add_css_class("caption")
        self.playtime_badge.add_css_class("card-playtime-badge")
        self.overlay.add_overlay(self.playtime_badge)

        # Quick action menu button (top-right)
        self.menu_button = Gtk.MenuButton()
        self.menu_button.set_icon_name("view-more-symbolic")
        self.menu_button.set_tooltip_text("Opções do jogo")
        self.menu_button.add_css_class("flat")
        self.menu_button.add_css_class("circular")
        self.menu_button.set_valign(Gtk.Align.START)
        self.menu_button.set_halign(Gtk.Align.END)
        self.menu_button.set_margin_top(4)
        self.menu_button.set_margin_end(4)
        self._setup_menu()
        self.overlay.add_overlay(self.menu_button)

        self.append(self.overlay)

        # Title Label
        self.title_label = Gtk.Label(label=game_data.get("title", "Desconhecido"))
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_halign(Gtk.Align.CENTER)
        self.title_label.add_css_class("caption-heading")
        self.append(self.title_label)

        # Click controller to select
        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", self._on_card_clicked)
        self.add_controller(click_gesture)

        # Setup Drag Source for Tier List DnD
        self._setup_drag_source()

        # Apply current view dimensions, badges, and cover art
        self.apply_view_settings(view_mode, zoom_level)
        self._update_badges()
        self._update_tooltip()

    def _on_card_clicked(self, gesture, n_press, x, y):
        if self.on_selected:
            self.on_selected(self.game_data)

    def _setup_drag_source(self):
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", lambda s, x, y: Gdk.ContentProvider.new_for_value(self.game_id))
        self.add_controller(drag_source)

    def _update_badges(self):
        # 1. Status badge
        status = self.game_data.get("status", "")
        if status == "platinum":
            self.status_badge.set_from_icon_name("starred-symbolic")
            self.status_badge.set_visible(True)
            self.status_badge.set_tooltip_text("Platinado")
        elif status == "completed":
            self.status_badge.set_from_icon_name("emblem-ok-symbolic")
            self.status_badge.set_visible(True)
            self.status_badge.set_tooltip_text("Finalizado")
        elif status == "playing":
            self.status_badge.set_from_icon_name("media-playback-start-symbolic")
            self.status_badge.set_visible(True)
            self.status_badge.set_tooltip_text("Em Andamento")
        elif status == "backlog":
            self.status_badge.set_from_icon_name("appointment-soon-symbolic")
            self.status_badge.set_visible(True)
            self.status_badge.set_tooltip_text("Para Começar")
        elif status == "dropped":
            self.status_badge.set_from_icon_name("process-stop-symbolic")
            self.status_badge.set_visible(True)
            self.status_badge.set_tooltip_text("Abandonado")
        else:
            self.status_badge.set_visible(False)

        # 2. Source / Platform badge
        source = self.game_data.get("source", "")
        platform = self.game_data.get("platform", "")
        if source == "lutris":
            self.source_badge.set_label("Lutris")
            self.source_badge.set_visible(True)
        elif source == "heroic":
            self.source_badge.set_label("Heroic")
            self.source_badge.set_visible(True)
        elif source == "steam" or self.game_data.get("steam_appid"):
            self.source_badge.set_label("Steam")
            self.source_badge.set_visible(True)
        elif platform:
            self.source_badge.set_label(platform[:6])
            self.source_badge.set_visible(True)
        else:
            self.source_badge.set_visible(False)

        # 3. Playtime badge
        playtime = float(self.game_data.get("playtime") or 0)
        if playtime > 0:
            if playtime >= 1.0:
                self.playtime_badge.set_label(f"{playtime:.1f}h")
            else:
                self.playtime_badge.set_label("<1h")
            self.playtime_badge.set_visible(True)
        else:
            self.playtime_badge.set_visible(False)

    def _update_tooltip(self):
        title = self.game_data.get("title", "")
        franchise = self.game_data.get("franchise") or "Nenhuma"
        company = self.game_data.get("company") or "Desconhecida"
        genres = ", ".join(self.game_data.get("genres", [])) or "Geral"
        tier = self.game_data.get("tier", "UNRANKED")
        status = self.game_data.get("status", "Nenhum")
        playtime = float(self.game_data.get("playtime") or 0)

        lines = [
            f"<b>{GLib.markup_escape_text(title)}</b>",
            f"Tier: {tier}",
            f"Status: {status}",
            f"Tempo Jogado: {playtime:.1f} horas" if playtime > 0 else "Tempo Jogado: 0h",
            f"Franquia: {GLib.markup_escape_text(franchise)}",
            f"Empresa: {GLib.markup_escape_text(company)}",
            f"Gêneros: {GLib.markup_escape_text(genres)}",
        ]
        self.set_tooltip_markup("\n".join(lines))

    def apply_view_settings(self, view_mode: str, zoom_level: int):
        """Adjusts cover dimensions, picture fit, and cover asset based on zoom and view mode."""
        self.view_mode = view_mode
        self.zoom_level = max(1, min(5, zoom_level))

        # Determine effective dimensions
        if view_mode == "header":
            w, h = DIMENSIONS_HEADER.get(self.zoom_level, (176, 82))
        elif view_mode == "icon":
            w, h = DIMENSIONS_ICON.get(self.zoom_level, (80, 80))
        else: # poster
            w, h = DIMENSIONS_POSTER.get(self.zoom_level, (120, 180))

        # Enforce exact bounds
        self.overlay.set_size_request(w, h)
        self.picture.set_size_request(w, h)
        self.set_size_request(w, -1)

        # Pick best image asset for mode
        img_path = None
        if view_mode == "header":
            img_path = self.game_data.get("cover_horizontal")
        elif view_mode == "icon":
            img_path = self.game_data.get("cover_icon")
        else: # poster
            img_path = self.game_data.get("cover_vertical")

        # Fallback to any available cover
        if not img_path or not os.path.exists(img_path):
            img_path = (
                self.game_data.get("cover_vertical")
                or self.game_data.get("cover_path")
                or self.game_data.get("cover_horizontal")
                or self.game_data.get("cover_icon")
            )

        if img_path and os.path.exists(img_path):
            self.picture.set_filename(img_path)
        else:
            display = Gdk.Display.get_default()
            if display:
                theme = Gtk.IconTheme.get_for_display(display)
                paintable = theme.lookup_icon(
                    "applications-games-symbolic", None, 64, 1, Gtk.TextDirection.NONE, Gtk.IconLookupFlags.NONE
                )
                if paintable:
                    self.picture.set_paintable(paintable)
                else:
                    self.picture.set_paintable(None)
            else:
                self.picture.set_paintable(None)

        # Title adjustments
        if view_mode == "icon" and self.zoom_level <= 2:
            self.title_label.set_visible(False)
        else:
            self.title_label.set_visible(True)
            self.title_label.set_max_width_chars(max(8, w // 8))

    def _setup_menu(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        tier_label = Gtk.Label(label="Mover para Tier")
        tier_label.add_css_class("caption-heading")
        tier_label.set_halign(Gtk.Align.START)
        box.append(tier_label)

        current_tier = self.game_data.get("tier", "UNRANKED")

        # Ranked Tiers
        for tier in self.tiers:
            tid = tier["id"]
            tier_btn = Gtk.Button(label=f"Tier {tier['name']}")
            tier_btn.add_css_class("flat")
            if tid == current_tier:
                tier_btn.set_sensitive(False)

            def make_tier_handler(target_id, pop):
                return lambda _: (pop.popdown(), self.on_tier_changed(self.game_id, target_id))

            tier_btn.connect("clicked", make_tier_handler(tid, popover))
            box.append(tier_btn)

        # Unranked option
        unranked_btn = Gtk.Button(label="Banco de Jogos")
        unranked_btn.add_css_class("flat")
        if current_tier == "UNRANKED":
            unranked_btn.set_sensitive(False)
        unranked_btn.connect(
            "clicked",
            lambda _: (popover.popdown(), self.on_tier_changed(self.game_id, "UNRANKED")),
        )
        box.append(unranked_btn)

        sep = Gtk.Separator()
        box.append(sep)

        # Change Status Submenu
        status_label = Gtk.Label(label="Status")
        status_label.add_css_class("caption-heading")
        status_label.set_halign(Gtk.Align.START)
        box.append(status_label)

        for s in STATUS_CHOICES:
            s_btn = Gtk.Button(label=s["name"])
            s_btn.add_css_class("flat")
            def make_status_handler(s_id, pop):
                return lambda _: (pop.popdown(), self._set_status(s_id))
            s_btn.connect("clicked", make_status_handler(s["id"], popover))
            box.append(s_btn)

        sep2 = Gtk.Separator()
        box.append(sep2)

        # Edit Game Details Button
        edit_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        edit_icon = Gtk.Image.new_from_icon_name("document-edit-symbolic")
        edit_lbl = Gtk.Label(label="Editar detalhes...")
        edit_box.append(edit_icon)
        edit_box.append(edit_lbl)
        edit_btn = Gtk.Button(child=edit_box)
        edit_btn.add_css_class("flat")
        edit_btn.connect("clicked", lambda _: (popover.popdown(), self._on_edit_details()))
        box.append(edit_btn)

        # Delete Game Button
        del_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        del_icon = Gtk.Image.new_from_icon_name("user-trash-symbolic")
        del_lbl = Gtk.Label(label="Remover jogo")
        del_box.append(del_icon)
        del_box.append(del_lbl)
        del_btn = Gtk.Button(child=del_box)
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", lambda _: (popover.popdown(), self.on_deleted(self.game_id)))
        box.append(del_btn)

        popover.set_child(box)
        self.menu_button.set_popover(popover)

    def _set_status(self, new_status: str):
        self.game_data["status"] = new_status
        self._update_badges()
        self._update_tooltip()
        self.on_updated(self.game_data)

    def _on_edit_details(self):
        root = self.get_root()
        dialog = GameEditDialog(
            parent_window=root if isinstance(root, Gtk.Window) else None,
            game_data=self.game_data,
            on_saved=self._on_saved_details,
        )
        dialog.present(root if isinstance(root, Gtk.Window) else None)

    def _on_saved_details(self, updated_data: Dict[str, Any]):
        self.game_data = updated_data
        self.title_label.set_label(updated_data.get("title", ""))
        self._update_badges()
        self._update_tooltip()
        self.on_updated(self.game_data)
