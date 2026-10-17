# game_edit_dialog.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, Adw, GLib
from typing import Callable, Dict, Any, Optional
from .config import STATUS_CHOICES


class GameEditDialog(Adw.Dialog):
    """
    Dialog to inspect and edit a game's metadata (Title, Franchise, Company, Genres,
    Status, Categories, and Playtime).
    Inherits from modern Adw.Dialog.
    """

    def __init__(
        self,
        parent_window: Optional[Gtk.Widget] = None,
        game_data: Optional[Dict[str, Any]] = None,
        on_saved: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__()
        self.set_title("Editar Informações do Jogo")
        self.set_content_width(520)
        self.set_content_height(580)
        self.game_data = game_data or {}
        self.on_saved = on_saved

        # Main layout
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        btn_cancel = Gtk.Button(label="Cancelar")
        btn_cancel.connect("clicked", lambda _: self.close())
        header.pack_start(btn_cancel)

        btn_save = Gtk.Button(label="Salvar")
        btn_save.add_css_class("suggested-action")
        btn_save.connect("clicked", self._on_save_clicked)
        header.pack_end(btn_save)

        toolbar_view.add_top_bar(header)

        # Preferences page with form rows
        page = Adw.PreferencesPage()

        # Metadata Group
        group = Adw.PreferencesGroup()
        group.set_title("Metadados Principais")
        group.set_description(
            "Ajuste os dados para categorizar e filtrar seu jogo com precisão na Tier List."
        )
        page.add(group)

        # Title Row
        self.row_title = Adw.EntryRow()
        self.row_title.set_title("Título do Jogo")
        self.row_title.set_text(self.game_data.get("title", ""))
        group.add(self.row_title)

        # Franchise Row
        self.row_franchise = Adw.EntryRow()
        self.row_franchise.set_title("Franquia")
        self.row_franchise.set_text(self.game_data.get("franchise", ""))
        group.add(self.row_franchise)

        # Company Row
        self.row_company = Adw.EntryRow()
        self.row_company.set_title("Empresa / Desenvolvedora")
        self.row_company.set_text(self.game_data.get("company", ""))
        group.add(self.row_company)

        # Genres Row
        self.row_genres = Adw.EntryRow()
        self.row_genres.set_title("Gêneros (separados por vírgula)")
        genres_list = self.game_data.get("genres", [])
        if isinstance(genres_list, list):
            self.row_genres.set_text(", ".join(genres_list))
        else:
            self.row_genres.set_text(str(genres_list))
        group.add(self.row_genres)

        # Status & Progress Group
        status_group = Adw.PreferencesGroup()
        status_group.set_title("Progresso e Categorias")
        page.add(status_group)

        # Status Combo Row
        self.row_status = Adw.ComboRow()
        self.row_status.set_title("Status do Jogo")
        status_model = Gtk.StringList.new([s["name"] for s in STATUS_CHOICES])
        self.row_status.set_model(status_model)

        current_status_id = self.game_data.get("status", "backlog")
        selected_idx = 0
        for i, s in enumerate(STATUS_CHOICES):
            if s["id"] == current_status_id or s["name"] == current_status_id:
                selected_idx = i
                break
        self.row_status.set_selected(selected_idx)
        status_group.add(self.row_status)

        # Playtime Spin Row
        self.row_playtime = Adw.SpinRow.new_with_range(0.0, 99999.0, 0.5)
        self.row_playtime.set_title("Tempo Jogado (Horas)")
        self.row_playtime.set_digits(1)
        self.row_playtime.set_value(float(self.game_data.get("playtime") or 0.0))
        status_group.add(self.row_playtime)

        # Categories Row
        self.row_categories = Adw.EntryRow()
        self.row_categories.set_title("Categorias (separadas por vírgula)")
        cats_list = self.game_data.get("categories", [])
        if isinstance(cats_list, list):
            self.row_categories.set_text(", ".join(cats_list))
        else:
            self.row_categories.set_text(str(cats_list))
        status_group.add(self.row_categories)

        toolbar_view.set_content(page)

    def _on_save_clicked(self, _):
        title = self.row_title.get_text().strip()
        if not title:
            return

        franchise = self.row_franchise.get_text().strip()
        company = self.row_company.get_text().strip()
        genres_raw = self.row_genres.get_text()
        genres = [g.strip() for g in genres_raw.split(",") if g.strip()]

        selected_status_idx = self.row_status.get_selected()
        status_id = STATUS_CHOICES[selected_status_idx]["id"]

        playtime = round(self.row_playtime.get_value(), 1)

        cats_raw = self.row_categories.get_text()
        categories = [c.strip() for c in cats_raw.split(",") if c.strip()]

        self.game_data["title"] = title
        self.game_data["franchise"] = franchise
        self.game_data["company"] = company
        self.game_data["genres"] = genres
        self.game_data["status"] = status_id
        self.game_data["playtime"] = playtime
        self.game_data["categories"] = categories

        if self.on_saved:
            self.on_saved(self.game_data)
        if self.get_root():
            self.close()
