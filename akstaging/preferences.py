import os
import logging
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

from akstaging.i18n import get_translator

_ = get_translator()

logger = logging.getLogger(__name__)

SETTINGS_ID = "com.github.mclellac.AkamaiStaging"


class Preferences(Adw.PreferencesWindow):
    """
    Manages the application's preferences window.

    This window allows users to configure settings such as the application theme.
    Settings are loaded from and saved to a configuration file
    (`~/.config/akamai_staging/preferences.conf`).
    Automatic backup behavior configuration has been removed.
    """
    __gtype_name__ = "AkamaiStagingPreferences"

    @property
    def THEME_OPTIONS(self):
        return [_("Light"), _("Dark"), _("System")]

    THEME_SCHEMES = [Adw.ColorScheme.PREFER_LIGHT, Adw.ColorScheme.PREFER_DARK, Adw.ColorScheme.DEFAULT]
    THEME_STRING_MAP = ["light", "dark", "system"]  # To map index to GSettings string
    DEFAULT_THEME_IDX = 2

    @property
    def FONT_SCALE_OPTIONS(self):
        return [_("System Default"), _("110%"), _("120%"), _("130%"), _("140%"), _("150%")]

    FONT_SCALE_VALUES = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
    DEFAULT_FONT_SCALE_IDX = 0

    DEFAULT_CUSTOM_DNS_ENABLED = False
    DEFAULT_CUSTOM_DNS_SERVERS = ""

    def __init__(self, parent_window, **kwargs):
        """
        Initializes the Preferences window.

        Args:
            parent_window: The main application window, used for transient_for and display context.
            **kwargs: Additional keyword arguments for Adw.PreferencesWindow.
        """
        super().__init__(transient_for=parent_window, modal=True, **kwargs)
        self.parent_window = parent_window
        self.set_search_enabled(False)
        self.style_manager = Adw.StyleManager.get_for_display(parent_window.get_display())

        self.settings = Gio.Settings.new(SETTINGS_ID)

        page = Adw.PreferencesPage()
        self.add(page)

        appearance_group = Adw.PreferencesGroup(title=_("Appearance"))
        page.add(appearance_group)

        self.theme_combo_row = Adw.ComboRow(
            title=_("Theme"),
            subtitle=_("Choose the application color scheme")
        )
        self.theme_combo_row.set_model(Gtk.StringList.new(self.THEME_OPTIONS))
        appearance_group.add(self.theme_combo_row)

        self.font_scale_combo_row = Adw.ComboRow(
            title=_("Font Scale"),
            subtitle=_("Adjust application font size")
        )
        self.font_scale_combo_row.set_model(Gtk.StringList.new(self.FONT_SCALE_OPTIONS))
        appearance_group.add(self.font_scale_combo_row)

        network_group = Adw.PreferencesGroup(title=_("Network"))
        page.add(network_group)

        self.custom_dns_switch = Adw.SwitchRow(
            title=_("Use Custom DNS Servers"),
            subtitle=_("Override system DNS settings for lookups")
        )
        network_group.add(self.custom_dns_switch)

        self.custom_dns_servers_entry = Adw.EntryRow(
            title=_("DNS Servers")
        )
        network_group.add(self.custom_dns_servers_entry)

        self.load_initial_settings()

        # Connect signals after loading initial settings to avoid saving default values
        # or applying changes prematurely during initialization.
        self.theme_combo_row.connect("notify::selected", self._on_theme_preference_changed)
        self.font_scale_combo_row.connect("notify::selected", self._on_font_scale_changed)
        self.custom_dns_switch.connect("notify::active", self._on_custom_dns_enabled_changed)
        self.custom_dns_servers_entry.connect("changed", self._on_custom_dns_servers_changed)

    def load_initial_settings(self):
        """Loads settings from GSettings and applies them to the UI widgets and application state."""
        # Load and apply theme.
        theme_str = self.settings.get_string('theme')
        try:
            theme_idx = self.THEME_STRING_MAP.index(theme_str)
        except ValueError:
            logger.warning("Invalid theme string '%s' from GSettings. Reverting to default.", theme_str)
            theme_idx = self.DEFAULT_THEME_IDX
            # Optionally, save the default back to GSettings if it was invalid
            # self.settings.set_string('theme', self.THEME_STRING_MAP[self.DEFAULT_THEME_IDX])

        if not 0 <= theme_idx < len(self.THEME_OPTIONS): # Should not happen if THEME_STRING_MAP is correct
            theme_idx = self.DEFAULT_THEME_IDX

        self.theme_combo_row.set_selected(theme_idx)
        self.style_manager.set_color_scheme(self.THEME_SCHEMES[theme_idx])

        # Load and apply font scale.
        font_scale_value = self.settings.get_double('font-scale')
        try:
            selected_font_scale_idx = self.FONT_SCALE_VALUES.index(font_scale_value)
        except ValueError:
            logger.warning("Invalid font_scale value '%s' from GSettings. Reverting to default.", font_scale_value)
            selected_font_scale_idx = self.DEFAULT_FONT_SCALE_IDX
            # Optionally, save the default back to GSettings
            # self.settings.set_double('font-scale', self.FONT_SCALE_VALUES[self.DEFAULT_FONT_SCALE_IDX])

        self.font_scale_combo_row.set_selected(selected_font_scale_idx)
        if hasattr(self.parent_window, 'apply_font_scaling'):
            self.parent_window.apply_font_scaling(self.FONT_SCALE_VALUES[selected_font_scale_idx])

        # Load custom DNS settings
        custom_dns_enabled = self.settings.get_boolean('custom-dns-enabled')
        self.custom_dns_switch.set_active(custom_dns_enabled)

        custom_dns_servers = self.settings.get_string('custom-dns-servers')
        self.custom_dns_servers_entry.set_text(custom_dns_servers)
        self.custom_dns_servers_entry.set_sensitive(custom_dns_enabled)

    def get_font_scale(self) -> float:
        """
        Retrieves the saved font scale factor from GSettings.

        Returns:
            float: The saved font scale factor.
        """
        return self.settings.get_double('font-scale')

    def _on_theme_preference_changed(self, combo_row, _gparam):
        """Handles changes in the theme preference Adw.ComboRow and saves the new setting to GSettings."""
        selected_idx = combo_row.get_selected()
        if 0 <= selected_idx < len(self.THEME_SCHEMES) and selected_idx < len(self.THEME_STRING_MAP):
            self.style_manager.set_color_scheme(self.THEME_SCHEMES[selected_idx])
            self.settings.set_string('theme', self.THEME_STRING_MAP[selected_idx])
        else:
            logger.warning("Unexpected theme index: %s. Reverting to default system theme.", selected_idx)
            default_scheme = self.THEME_SCHEMES[self.DEFAULT_THEME_IDX]
            self.style_manager.set_color_scheme(default_scheme)
            self.settings.set_string('theme', self.THEME_STRING_MAP[self.DEFAULT_THEME_IDX])
            self.theme_combo_row.set_selected(self.DEFAULT_THEME_IDX)

    def _on_font_scale_changed(self, combo_row, _gparam):
        """Handles changes in the font scale preference Adw.ComboRow and saves the new setting to GSettings."""
        selected_idx = combo_row.get_selected()
        if 0 <= selected_idx < len(self.FONT_SCALE_VALUES):
            scale_factor = self.FONT_SCALE_VALUES[selected_idx]
            self.settings.set_double('font-scale', scale_factor)
            if hasattr(self.parent_window, 'apply_font_scaling'):
                self.parent_window.apply_font_scaling(scale_factor)
        else:
            logger.warning("Unexpected font scale index: %s. Reverting to default.", selected_idx)
            default_scale_factor = self.FONT_SCALE_VALUES[self.DEFAULT_FONT_SCALE_IDX]
            self.settings.set_double('font-scale', default_scale_factor)
            if hasattr(self.parent_window, 'apply_font_scaling'):
                self.parent_window.apply_font_scaling(default_scale_factor)
            self.font_scale_combo_row.set_selected(self.DEFAULT_FONT_SCALE_IDX)

    def _on_custom_dns_enabled_changed(self, switch, _gparam):
        is_active = switch.get_active()
        self.settings.set_boolean('custom-dns-enabled', is_active)
        self.custom_dns_servers_entry.set_sensitive(is_active)

    def _on_custom_dns_servers_changed(self, entry):
        self.settings.set_string('custom-dns-servers', entry.get_text())

    def do_destroy(self):
        """
        Handles the GObject destruction of the window.
        It's good practice to disconnect signal handlers here to prevent potential issues,
        though Python's garbage collection and GObject's own mechanisms usually handle this.
        Using `disconnect_by_func` is safe even if the handler isn't connected or was connected multiple times
        (it will only remove one instance per call if multiply connected, which is usually a bug anyway).
        """
        if hasattr(self, 'theme_combo_row') and self.theme_combo_row:
            self.theme_combo_row.disconnect_by_func(self._on_theme_preference_changed)
        
        if hasattr(self, 'font_scale_combo_row') and self.font_scale_combo_row:
            self.font_scale_combo_row.disconnect_by_func(self._on_font_scale_changed)
        
        if hasattr(self, 'custom_dns_switch') and self.custom_dns_switch:
            self.custom_dns_switch.disconnect_by_func(self._on_custom_dns_enabled_changed)

        if hasattr(self, 'custom_dns_servers_entry') and self.custom_dns_servers_entry:
            self.custom_dns_servers_entry.disconnect_by_func(self._on_custom_dns_servers_changed)
            
        super().do_destroy()
