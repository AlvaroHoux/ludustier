# main.py
#
# Copyright 2026 Alvaro
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

from gettext import gettext as _

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import os
from gi.repository import Gtk, Gio, Adw, Gdk, GLib

Adw.init()

# Ensure gresource is registered even when running directly in source directory
try:
    Gio.resources_get_info('/org/houx/ludustier/window.ui', Gio.ResourceLookupFlags.NONE)
except GLib.Error:
    res_path = os.path.join(os.path.dirname(__file__), 'ludustier.gresource')
    if os.path.exists(res_path):
        res = Gio.Resource.load(res_path)
        res._register()

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.window import LudustierWindow
    from src.preferences_dialog import PreferencesDialog
else:
    from .window import LudustierWindow
    from .preferences_dialog import PreferencesDialog


class LudustierApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='org.houx.ludustier',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/org/houx/ludustier')
        self.create_action('quit', lambda *_: self.quit(), ['<control>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action, ['<control>comma'])
        self.set_accels_for_action('win.toggle_search', ['<control>f'])
        self.set_accels_for_action('window.close', ['<control>w'])

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()

    def _load_css(self):
        """Loads custom CSS stylesheet for LudusTier."""
        try:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_resource('/org/houx/ludustier/style.css')
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
        except Exception as e:
            print(f"[CSS] Error loading stylesheet: {e}")

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        win = self.props.active_window
        if not win:
            win = LudustierWindow(application=self)
        win.present()

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(
            application_name='LudusTier',
            application_icon='org.houx.ludustier',
            version='0.1.0',
            developer_name='Alvaro',
            website='https://github.com/AlvaroHoux/ludustier',
            issue_url='https://github.com/AlvaroHoux/ludustier/issues',
            copyright='© 2026 Alvaro',
            license_type=Gtk.License.GPL_3_0,
        )
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        win = self.props.active_window
        prefs = PreferencesDialog()
        prefs.present(win)

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version="0.1.0"):
    """The application's entry point."""
    app = LudustierApplication()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
