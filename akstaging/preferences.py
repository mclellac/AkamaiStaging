import gi
import os
import configparser

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

PREFERENCES_FILE = os.path.expanduser("~/.config/akamai_staging/preferences.conf")


class Preferences(Adw.PreferencesWindow):
    def __init__(self, parent=None):
        super().__init__(transient_for=parent)
        self.set_modal(True)
        self.set_title("Preferences")
        self.parent_window = parent

        # Create a PreferencesPage and add groups
        self.page = Adw.PreferencesPage()
        self.add(self.page)

        self.create_font_size_group()
        self.create_theme_group()

        # Load preferences initially
        self.load_preferences()

    def create_font_size_group(self):
        """Create preferences group for font size."""
        self.font_size_group = Adw.PreferencesGroup()
        self.page.add(self.font_size_group)

        self.font_size_row = Adw.ActionRow(title="Font Size")
        self.font_size_adjustment = Gtk.Adjustment(
            value=12, lower=8, upper=32, step_increment=1
        )
        self.font_size_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.font_size_adjustment
        )
        self.font_size_scale.set_digits(0)
        self.font_size_scale.set_hexpand(True)
        self.font_size_scale.connect("value-changed", self.on_font_size_changed)
        self.font_size_row.add_suffix(self.font_size_scale)

        self.font_size_group.add(self.font_size_row)

    def create_theme_group(self):
        """Create preferences group for theme selection."""
        self.theme_group = Adw.PreferencesGroup()
        self.page.add(self.theme_group)

        self.theme_row = Adw.ActionRow()
        self.theme_switch = Gtk.Switch()
        self.theme_switch.set_active(True)  # Default to dark theme enabled
        self.theme_switch.set_valign(
            Gtk.Align.CENTER
        )  # Align switch vertically to center
        self.theme_switch.set_halign(
            Gtk.Align.END
        )  # Align switch horizontally to the end
        self.theme_switch.connect("state-set", self.on_theme_switch_changed)

        self.theme_label = Gtk.Label(label="Dark Theme")
        self.theme_label.set_halign(Gtk.Align.START)  # Align label to the start

        self.theme_row.add_prefix(self.theme_label)
        self.theme_row.add_suffix(self.theme_switch)

        self.theme_group.add(self.theme_row)

    def on_font_size_changed(self, scale):
        """Handle font size change event."""
        font_size = scale.get_value()
        print(f"Font size changed to: {font_size}")
        self.get_transient_for().apply_font_size(font_size)
        self.save_preferences()

    def on_theme_switch_changed(self, switch, gparam):
        """Handle theme switch change event."""
        theme_enabled = switch.get_active()
        self.parent_window.apply_theme(theme_enabled)
        self.save_preferences()

    def save_preferences(self):
        """Save preferences to the configuration file."""
        os.makedirs(os.path.dirname(PREFERENCES_FILE), exist_ok=True)
        config = configparser.ConfigParser()
        config["Preferences"] = {
            "font_size": self.font_size_adjustment.get_value(),
            "dark_theme": "1" if self.theme_switch.get_active() else "0",
        }
        with open(PREFERENCES_FILE, "w") as configfile:
            config.write(configfile)

    def load_preferences(self):
        """Load preferences from the configuration file."""
        if os.path.exists(PREFERENCES_FILE):
            config = configparser.ConfigParser()
            config.read(PREFERENCES_FILE)
            font_size = config.getfloat("Preferences", "font_size", fallback=12)
            self.font_size_adjustment.set_value(font_size)
            dark_theme_enabled = config.getboolean(
                "Preferences", "dark_theme", fallback=True
            )
            self.theme_switch.set_active(dark_theme_enabled)
