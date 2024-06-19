# preferences.py
#
# Copyright 2024 Carey McLelland
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

import gi
import os
import configparser

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject

PREFERENCES_FILE = os.path.expanduser("~/.config/akamai_staging/preferences.conf")

class Preferences(Adw.PreferencesWindow):
    __gtype_name__ = "Preferences"

    def __init__(self, parent=None):
        super().__init__(transient_for=parent)
        self.set_modal(True)
        self.set_title("Preferences")

        # Create a PreferencesPage
        self.page = Adw.PreferencesPage()
        self.add(self.page)

        # Create a PreferencesGroup
        self.group = Adw.PreferencesGroup()
        self.page.add(self.group)

        # Create an ActionRow for font size
        self.font_size_row = Adw.ActionRow(title="Font Size")
        self.font_size_adjustment = Gtk.Adjustment(value=12, lower=8, upper=32, step_increment=1)
        self.font_size_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.font_size_adjustment)
        self.font_size_scale.set_digits(0)
        self.font_size_scale.set_hexpand(True)
        self.font_size_scale.connect("value-changed", self.on_font_size_changed)
        self.font_size_row.add_suffix(self.font_size_scale)

        # Add the ActionRow to the PreferencesGroup
        self.group.add(self.font_size_row)

        # Load the preferences
        self.load_preferences()

    def on_font_size_changed(self, scale):
        font_size = scale.get_value()
        print(f"Font size changed to: {font_size}")
        self.get_transient_for().apply_font_size(font_size)
        self.save_preferences()

    def save_preferences(self):
        os.makedirs(os.path.dirname(PREFERENCES_FILE), exist_ok=True)
        config = configparser.ConfigParser()
        config['Preferences'] = {
            'font_size': self.font_size_adjustment.get_value()
        }
        with open(PREFERENCES_FILE, 'w') as configfile:
            config.write(configfile)

    def load_preferences(self):
        if os.path.exists(PREFERENCES_FILE):
            config = configparser.ConfigParser()
            config.read(PREFERENCES_FILE)
            font_size = config.getfloat('Preferences', 'font_size', fallback=12)
            self.font_size_adjustment.set_value(font_size)

