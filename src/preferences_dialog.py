# preferences_dialog.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk
from .config import get_steamgriddb_key, set_steamgriddb_key


class PreferencesDialog(Adw.PreferencesDialog):
    """
    Preferences dialog to configure SteamGridDB API key and settings.
    """

    def __init__(self):
        super().__init__()
        self.set_title("Preferências")

        # Main Page
        page = Adw.PreferencesPage()
        page.set_title("Geral")
        page.set_icon_name("preferences-system-symbolic")
        self.add(page)

        # SteamGridDB Group
        group = Adw.PreferencesGroup()
        group.set_title("SteamGridDB API")
        group.set_description(
            "Adicione sua chave de API para obter capas personalizadas da comunidade SteamGridDB. "
            "Se deixado em branco, o LudusTier usará as capas oficiais da Steam Store automaticamente."
        )
        page.add(group)

        # API Key Entry Row
        self.key_entry = Adw.PasswordEntryRow()
        self.key_entry.set_title("Chave de API (SteamGridDB)")
        current_key = get_steamgriddb_key()
        self.key_entry.set_text(current_key)
        self.key_entry.connect("changed", self._on_key_changed)
        group.add(self.key_entry)

        # Action row with link
        action_row = Adw.ActionRow()
        action_row.set_title("Obter chave gratuita")
        action_row.set_subtitle("steamgriddb.com/profile/preferences/api")
        action_row.set_activatable(True)

        link_btn = Gtk.LinkButton(
            uri="https://www.steamgriddb.com/profile/preferences/api",
            label="Abrir Site"
        )
        link_btn.set_valign(Gtk.Align.CENTER)
        action_row.add_suffix(link_btn)
        group.add(action_row)

    def _on_key_changed(self, entry):
        new_key = entry.get_text()
        set_steamgriddb_key(new_key)
