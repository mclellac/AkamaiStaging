import logging

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from akstaging.i18n import get_translator, set_language

_ = get_translator()

logger = logging.getLogger(__name__)

SETTINGS_ID = "com.github.mclellac.AkamaiStaging"

_theme_css_provider = None


def apply_theme(theme_str: str, display=None):
    """Applies theme color scheme across Libadwaita StyleManager, GtkSettings, and CSS providers."""
    global _theme_css_provider

    scheme_map = {
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
        "system": Adw.ColorScheme.DEFAULT,
    }
    scheme = scheme_map.get(theme_str, Adw.ColorScheme.DEFAULT)

    sm_default = Adw.StyleManager.get_default()
    if sm_default:
        sm_default.set_color_scheme(scheme)

    if not display:
        display = Gdk.Display.get_default()

    if display:
        sm_display = Adw.StyleManager.get_for_display(display)
        if sm_display:
            sm_display.set_color_scheme(scheme)

    if display:
        if _theme_css_provider is not None:
            try:
                Gtk.StyleContext.remove_provider_for_display(display, _theme_css_provider)
            except Exception:
                pass
            _theme_css_provider = None

        if theme_str in ("light", "dark"):
            _theme_css_provider = Gtk.CssProvider()
            if theme_str == "light":
                css_data = """
                @define-color window_bg_color #fafafa;
                @define-color window_fg_color rgba(0, 0, 0, 0.87);
                @define-color card_bg_color #ffffff;
                @define-color card_fg_color rgba(0, 0, 0, 0.87);
                @define-color headerbar_bg_color #f6f6f6;
                @define-color headerbar_fg_color rgba(0, 0, 0, 0.87);
                @define-color dialog_bg_color #ffffff;
                @define-color dialog_fg_color rgba(0, 0, 0, 0.87);
                @define-color popover_bg_color #ffffff;
                @define-color popover_fg_color rgba(0, 0, 0, 0.87);
                @define-color view_bg_color #ffffff;
                @define-color view_fg_color rgba(0, 0, 0, 0.87);
                """
            else:
                css_data = """
                @define-color window_bg_color #242424;
                @define-color window_fg_color #ffffff;
                @define-color card_bg_color #303030;
                @define-color card_fg_color #ffffff;
                @define-color headerbar_bg_color #303030;
                @define-color headerbar_fg_color #ffffff;
                @define-color dialog_bg_color #303030;
                @define-color dialog_fg_color #ffffff;
                @define-color popover_bg_color #303030;
                @define-color popover_fg_color #ffffff;
                @define-color view_bg_color #1e1e1e;
                @define-color view_fg_color #ffffff;
                """
            _theme_css_provider.load_from_data(css_data.encode())
            Gtk.StyleContext.add_provider_for_display(display, _theme_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)


class Preferences(Adw.PreferencesWindow):
    """
    Manages the application's preferences window.

    This window allows users to configure settings such as the application theme and language.
    Settings are loaded from and saved to GSettings.
    """

    __gtype_name__ = "AkamaiStagingPreferences"

    @property
    def THEME_OPTIONS(self):
        return [_("Light"), _("Dark"), _("System")]

    THEME_SCHEMES = [Adw.ColorScheme.FORCE_LIGHT, Adw.ColorScheme.FORCE_DARK, Adw.ColorScheme.DEFAULT]
    THEME_STRING_MAP = ["light", "dark", "system"]  # To map index to GSettings string
    DEFAULT_THEME_IDX = 2

    @property
    def LANGUAGE_OPTIONS(self):
        return [_("System Default"), _("English"), _("Français (Canada)")]

    LANGUAGE_STRING_MAP = ["system", "en", "fr"]
    DEFAULT_LANGUAGE_IDX = 0

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
        self.set_default_size(820, 600)
        self.set_size_request(780, 560)
        self.style_manager = Adw.StyleManager.get_default()

        self.settings = Gio.Settings.new(SETTINGS_ID)

        # Page 1: General & Behavior
        self.general_page = Adw.PreferencesPage(title=_("General"), icon_name="preferences-system-symbolic")
        self.add(self.general_page)

        self.general_group = Adw.PreferencesGroup(title=_("General &amp; Behavior"))
        self.general_page.add(self.general_group)

        self.auto_refresh_switch = Adw.SwitchRow(
            title=_("Automatic Hosts Refresh"), subtitle=_("Automatically re-read hosts file on external changes")
        )
        self.general_group.add(self.auto_refresh_switch)

        self.desktop_notif_switch = Adw.SwitchRow(
            title=_("Desktop Notifications"), subtitle=_("Show system notifications for IP updates and deletions")
        )
        self.general_group.add(self.desktop_notif_switch)

        # Page 2: DNS Resolver Settings
        self.network_page = Adw.PreferencesPage(title=_("Network"), icon_name="network-workgroup-symbolic")
        self.add(self.network_page)

        self.network_group = Adw.PreferencesGroup(title=_("DNS Resolver Settings"))
        self.network_page.add(self.network_group)

        self.custom_dns_switch = Adw.SwitchRow(
            title=_("Use Custom DNS Servers"), subtitle=_("Override system DNS settings for lookups")
        )
        self.network_group.add(self.custom_dns_switch)

        self.custom_dns_servers_entry = Adw.EntryRow(title=_("DNS Servers"))
        self.network_group.add(self.custom_dns_servers_entry)

        self.dns_timeout_row = Adw.ActionRow(
            title=_("DNS Timeout (seconds)"), subtitle=_("Query timeout threshold for DNS lookups")
        )
        dns_spin = Gtk.SpinButton.new_with_range(1, 30, 1)
        self.dns_spin = dns_spin
        self.dns_timeout_row.add_suffix(dns_spin)
        self.network_group.add(self.dns_timeout_row)

        # Page 3: Appearance & Theme
        self.appearance_page = Adw.PreferencesPage(title=_("Appearance"), icon_name="preferences-desktop-theme-symbolic")
        self.add(self.appearance_page)

        self.appearance_group = Adw.PreferencesGroup(title=_("Appearance &amp; Theme"))
        self.appearance_page.add(self.appearance_group)

        self.theme_combo_row = Adw.ComboRow(title=_("Theme"), subtitle=_("Choose the application color scheme"))
        self.theme_combo_row.set_model(Gtk.StringList.new(self.THEME_OPTIONS))
        self.appearance_group.add(self.theme_combo_row)

        self.language_combo_row = Adw.ComboRow(title=_("Language"), subtitle=_("Choose the application display language"))
        self.language_combo_row.set_model(Gtk.StringList.new(self.LANGUAGE_OPTIONS))
        self.appearance_group.add(self.language_combo_row)

        self.font_scale_combo_row = Adw.ComboRow(title=_("Font Scale"), subtitle=_("Adjust application font size"))
        self.font_scale_combo_row.set_model(Gtk.StringList.new(self.FONT_SCALE_OPTIONS))
        self.appearance_group.add(self.font_scale_combo_row)

        # Page 4: Security & Privilege Escalation
        self.security_page = Adw.PreferencesPage(title=_("Security"), icon_name="dialog-password-symbolic")
        self.add(self.security_page)

        self.security_group = Adw.PreferencesGroup(title=_("Security &amp; Privilege Escalation"))
        self.security_page.add(self.security_group)

        self.helper_status_row = Adw.ActionRow(
            title=_("Helper Execution Mode"), subtitle=_("PolicyKit (Linux) / osascript (macOS)")
        )
        self.security_group.add(self.helper_status_row)

        self.elevation_timeout_row = Adw.ActionRow(
            title=_("Elevated Session Timeout (s)"), subtitle=_("Cached helper elevation timeout duration")
        )
        elev_spin = Gtk.SpinButton.new_with_range(5, 60, 5)
        self.elev_spin = elev_spin
        self.elevation_timeout_row.add_suffix(elev_spin)
        self.security_group.add(self.elevation_timeout_row)

        self.load_initial_settings()

        # Connect signals after loading initial settings to avoid saving default values
        # or applying changes prematurely during initialization.
        self.theme_combo_row.connect("notify::selected", self._on_theme_preference_changed)
        self.language_combo_row.connect("notify::selected", self._on_language_changed)
        self.font_scale_combo_row.connect("notify::selected", self._on_font_scale_changed)
        self.custom_dns_switch.connect("notify::active", self._on_custom_dns_enabled_changed)
        self.custom_dns_servers_entry.connect("changed", self._on_custom_dns_servers_changed)
        self.auto_refresh_switch.connect("notify::active", self._on_auto_refresh_changed)
        self.desktop_notif_switch.connect("notify::active", self._on_desktop_notif_changed)
        self.dns_spin.connect("value-changed", self._on_dns_timeout_changed)
        self.elev_spin.connect("value-changed", self._on_elev_timeout_changed)

    def load_initial_settings(self):
        """Loads settings from GSettings and applies them to the UI widgets and application state."""
        # Load and apply theme.
        theme_str = self.settings.get_string("theme")
        try:
            theme_idx = self.THEME_STRING_MAP.index(theme_str)
        except ValueError:
            logger.warning("Invalid theme string '%s' from GSettings. Reverting to default.", theme_str)
            theme_idx = self.DEFAULT_THEME_IDX
            # Optionally, save the default back to GSettings if it was invalid
            # self.settings.set_string('theme', self.THEME_STRING_MAP[self.DEFAULT_THEME_IDX])

        if not 0 <= theme_idx < len(self.THEME_OPTIONS):  # Should not happen if THEME_STRING_MAP is correct
            theme_idx = self.DEFAULT_THEME_IDX

        self.theme_combo_row.set_selected(theme_idx)
        apply_theme(self.THEME_STRING_MAP[theme_idx], self.parent_window.get_display() if self.parent_window else None)

        # Load and apply language.
        try:
            lang_str = self.settings.get_string("language")
            lang_idx = self.LANGUAGE_STRING_MAP.index(lang_str)
        except Exception:
            lang_idx = self.DEFAULT_LANGUAGE_IDX

        self.language_combo_row.set_selected(lang_idx)
        set_language(self.LANGUAGE_STRING_MAP[lang_idx])

        # Load and apply font scale.
        font_scale_value = self.settings.get_double("font-scale")
        try:
            selected_font_scale_idx = self.FONT_SCALE_VALUES.index(font_scale_value)
        except ValueError:
            logger.warning("Invalid font_scale value '%s' from GSettings. Reverting to default.", font_scale_value)
            selected_font_scale_idx = self.DEFAULT_FONT_SCALE_IDX
            # Optionally, save the default back to GSettings
            # self.settings.set_double('font-scale', self.FONT_SCALE_VALUES[self.DEFAULT_FONT_SCALE_IDX])

        self.font_scale_combo_row.set_selected(selected_font_scale_idx)
        if hasattr(self.parent_window, "apply_font_scaling"):
            self.parent_window.apply_font_scaling(self.FONT_SCALE_VALUES[selected_font_scale_idx])

        # Load custom DNS settings
        custom_dns_enabled = self.settings.get_boolean("custom-dns-enabled")
        self.custom_dns_switch.set_active(custom_dns_enabled)

        custom_dns_servers = self.settings.get_string("custom-dns-servers")
        self.custom_dns_servers_entry.set_text(custom_dns_servers)
        self.custom_dns_servers_entry.set_sensitive(custom_dns_enabled)

        self.auto_refresh_switch.set_active(self.settings.get_boolean("auto-refresh"))
        self.desktop_notif_switch.set_active(self.settings.get_boolean("desktop-notifications"))
        self.dns_spin.set_value(float(self.settings.get_int("dns-timeout")))
        self.elev_spin.set_value(float(self.settings.get_int("elevation-timeout")))

    def get_font_scale(self) -> float:
        """
        Retrieves the saved font scale factor from GSettings.

        Returns:
            float: The saved font scale factor.
        """
        return self.settings.get_double("font-scale")

    def _on_auto_refresh_changed(self, switch, _gparam):
        self.settings.set_boolean("auto-refresh", switch.get_active())

    def _on_desktop_notif_changed(self, switch, _gparam):
        self.settings.set_boolean("desktop-notifications", switch.get_active())

    def _on_dns_timeout_changed(self, spin):
        self.settings.set_int("dns-timeout", int(spin.get_value()))

    def _on_elev_timeout_changed(self, spin):
        self.settings.set_int("elevation-timeout", int(spin.get_value()))

    def _on_theme_preference_changed(self, combo_row, _gparam):
        """Handles changes in the theme preference Adw.ComboRow and saves the new setting to GSettings."""
        selected_idx = combo_row.get_selected()
        if 0 <= selected_idx < len(self.THEME_STRING_MAP):
            theme_str = self.THEME_STRING_MAP[selected_idx]
            apply_theme(theme_str, self.parent_window.get_display() if self.parent_window else None)
            self.settings.set_string("theme", theme_str)
        else:
            logger.warning("Unexpected theme index: %s. Reverting to default system theme.", selected_idx)
            default_theme_str = self.THEME_STRING_MAP[self.DEFAULT_THEME_IDX]
            apply_theme(default_theme_str, self.parent_window.get_display() if self.parent_window else None)
            self.settings.set_string("theme", default_theme_str)
            self.theme_combo_row.set_selected(self.DEFAULT_THEME_IDX)

    def retranslate_ui(self):
        """Dynamically updates all Preferences page titles, group titles, row labels, and combo box models to active language."""
        if getattr(self, "_in_retranslate", False):
            return
        self._in_retranslate = True
        try:
            self.set_title(_("Preferences"))

            if hasattr(self, "general_page") and self.general_page:
                self.general_page.set_title(_("General"))
            if hasattr(self, "general_group") and self.general_group:
                self.general_group.set_title(_("General &amp; Behavior"))

            if hasattr(self, "auto_refresh_switch") and self.auto_refresh_switch:
                self.auto_refresh_switch.set_title(_("Automatic Hosts Refresh"))
                self.auto_refresh_switch.set_subtitle(_("Automatically re-read hosts file on external changes"))

            if hasattr(self, "desktop_notif_switch") and self.desktop_notif_switch:
                self.desktop_notif_switch.set_title(_("Desktop Notifications"))
                self.desktop_notif_switch.set_subtitle(_("Show system notifications for IP updates and deletions"))

            if hasattr(self, "network_page") and self.network_page:
                self.network_page.set_title(_("Network"))
            if hasattr(self, "network_group") and self.network_group:
                self.network_group.set_title(_("DNS Resolver Settings"))

            if hasattr(self, "custom_dns_switch") and self.custom_dns_switch:
                self.custom_dns_switch.set_title(_("Use Custom DNS Servers"))
                self.custom_dns_switch.set_subtitle(_("Override system DNS settings for lookups"))

            if hasattr(self, "custom_dns_servers_entry") and self.custom_dns_servers_entry:
                self.custom_dns_servers_entry.set_title(_("DNS Servers"))

            if hasattr(self, "dns_timeout_row") and self.dns_timeout_row:
                self.dns_timeout_row.set_title(_("DNS Timeout (seconds)"))
                self.dns_timeout_row.set_subtitle(_("Query timeout threshold for DNS lookups"))

            if hasattr(self, "appearance_page") and self.appearance_page:
                self.appearance_page.set_title(_("Appearance"))
            if hasattr(self, "appearance_group") and self.appearance_group:
                self.appearance_group.set_title(_("Appearance &amp; Theme"))

            if hasattr(self, "theme_combo_row") and self.theme_combo_row:
                self.theme_combo_row.set_title(_("Theme"))
                self.theme_combo_row.set_subtitle(_("Choose the application color scheme"))

            if hasattr(self, "language_combo_row") and self.language_combo_row:
                self.language_combo_row.set_title(_("Language"))
                self.language_combo_row.set_subtitle(_("Choose the application display language"))

            if hasattr(self, "font_scale_combo_row") and self.font_scale_combo_row:
                self.font_scale_combo_row.set_title(_("Font Scale"))
                self.font_scale_combo_row.set_subtitle(_("Adjust application font size"))

            if hasattr(self, "security_page") and self.security_page:
                self.security_page.set_title(_("Security"))
            if hasattr(self, "security_group") and self.security_group:
                self.security_group.set_title(_("Security &amp; Privilege Escalation"))

            if hasattr(self, "helper_status_row") and self.helper_status_row:
                self.helper_status_row.set_title(_("Helper Execution Mode"))
                self.helper_status_row.set_subtitle(_("PolicyKit (Linux) / osascript (macOS)"))

            if hasattr(self, "elevation_timeout_row") and self.elevation_timeout_row:
                self.elevation_timeout_row.set_title(_("Elevated Session Timeout (s)"))
                self.elevation_timeout_row.set_subtitle(_("Cached helper elevation timeout duration"))
        finally:
            self._in_retranslate = False

    def _on_language_changed(self, combo_row, _gparam):
        """Handles changes in the language preference Adw.ComboRow and saves to GSettings."""
        if getattr(self, "_in_retranslate", False):
            return
        selected_idx = combo_row.get_selected()
        if 0 <= selected_idx < len(self.LANGUAGE_STRING_MAP):
            lang_str = self.LANGUAGE_STRING_MAP[selected_idx]
            if self.settings.get_string("language") != lang_str:
                self.settings.set_string("language", lang_str)
            set_language(lang_str)
            self.retranslate_ui()
            if self.parent_window and hasattr(self.parent_window, "retranslate_ui"):
                self.parent_window.retranslate_ui()

    def _on_font_scale_changed(self, combo_row, _gparam):
        """Handles changes in the font scale preference Adw.ComboRow and saves the new setting to GSettings."""
        selected_idx = combo_row.get_selected()
        if 0 <= selected_idx < len(self.FONT_SCALE_VALUES):
            scale_factor = self.FONT_SCALE_VALUES[selected_idx]
            self.settings.set_double("font-scale", scale_factor)
            if hasattr(self.parent_window, "apply_font_scaling"):
                self.parent_window.apply_font_scaling(scale_factor)
        else:
            logger.warning("Unexpected font scale index: %s. Reverting to default.", selected_idx)
            default_scale_factor = self.FONT_SCALE_VALUES[self.DEFAULT_FONT_SCALE_IDX]
            self.settings.set_double("font-scale", default_scale_factor)
            if hasattr(self.parent_window, "apply_font_scaling"):
                self.parent_window.apply_font_scaling(default_scale_factor)
            self.font_scale_combo_row.set_selected(self.DEFAULT_FONT_SCALE_IDX)

    def _on_custom_dns_enabled_changed(self, switch, _gparam):
        is_active = switch.get_active()
        self.settings.set_boolean("custom-dns-enabled", is_active)
        self.custom_dns_servers_entry.set_sensitive(is_active)

    def _on_custom_dns_servers_changed(self, entry):
        self.settings.set_string("custom-dns-servers", entry.get_text())

    def do_destroy(self):
        """Handles the GObject destruction of the window."""
        if hasattr(self, "theme_combo_row") and self.theme_combo_row:
            self.theme_combo_row.disconnect_by_func(self._on_theme_preference_changed)

        if hasattr(self, "language_combo_row") and self.language_combo_row:
            self.language_combo_row.disconnect_by_func(self._on_language_changed)

        if hasattr(self, "font_scale_combo_row") and self.font_scale_combo_row:
            self.font_scale_combo_row.disconnect_by_func(self._on_font_scale_changed)

        if hasattr(self, "custom_dns_switch") and self.custom_dns_switch:
            self.custom_dns_switch.disconnect_by_func(self._on_custom_dns_enabled_changed)

        if hasattr(self, "custom_dns_servers_entry") and self.custom_dns_servers_entry:
            self.custom_dns_servers_entry.disconnect_by_func(self._on_custom_dns_servers_changed)

        super().do_destroy()
