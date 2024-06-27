# window.py
import configparser
import logging
import os
import re
import sys

from akstaging.aklib import AkamaiLib as akl
from akstaging.defs import APP_NAME, COPYRIGHT, RESOURCE_PATH, VERSION
from akstaging.dns_utils import DNSUtils as ns
from akstaging.hosts import HostsFileEdit as hfe
from akstaging.preferences import Preferences

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

PREFERENCES_FILE = os.path.expanduser("~/.config/akamai_staging/preferences.conf")

# Load and register the resource bundle
resource_path = RESOURCE_PATH
try:
    resource = Gio.Resource.load(resource_path)
    Gio.resources_register(resource)
except GLib.Error as e:
    logging.error(f"Failed to load resource: {e}")
    sys.exit(1)

# Load CSS styles from the resource bundle
style_provider = Gtk.CssProvider()

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/github/mclellac/AkamaiStaging/gtk/window.ui")
class AkamaiStagingWindow(Adw.ApplicationWindow):
    """Main application window for the Akamai Staging tool."""

    __gtype_name__ = "AkamaiStagingWindow"

    button_add_ip: Gtk.Button = Gtk.Template.Child()
    button_delete: Gtk.Button = Gtk.Template.Child()
    column_view_entries: Gtk.ColumnView = Gtk.Template.Child()
    textview_status: Gtk.TextView = Gtk.Template.Child()
    entry_domain: Gtk.Entry = Gtk.Template.Child()

    def __init__(self, application=None):
        """Initialize the Akamai Staging window with the given application."""
        super().__init__(application=application)
        logger.debug("Initializing AkamaiStagingWindow")

        self._verify_ui_elements()
        self._initialize_helpers()
        self._initialize_ui_actions()
        self._initialize_store()
        self.create_column_view_columns()
        self._connect_signals()
        self.set_size_request(700, 650)  # Minimum width of 600 and height of 400
        self.style_manager = Adw.StyleManager.get_for_display(Gdk.Display.get_default())
        self.load_preferences()

    # Initialization methods
    def _verify_ui_elements(self):
        """Verify that all UI elements are correctly loaded."""
        assert self.button_add_ip is not None, "button_add_ip is not loaded"
        assert self.button_delete is not None, "button_delete is not loaded"
        assert self.column_view_entries is not None, "column_view_entries is not loaded"
        assert self.textview_status is not None, "textview_status is not loaded"
        assert self.entry_domain is not None, "entry_domain is not loaded"

    def _initialize_helpers(self):
        """Initialize helper classes."""
        self.hfe = hfe()
        self.akl = akl()
        self.ns = ns()

    def _initialize_ui_actions(self):
        """Initialize application actions."""
        self.create_action("quit", lambda *_: self.quit(), ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("preferences", self.on_preferences_action)

    def _initialize_store(self):
        """Initialize the data store for the column view."""
        self.store = Gio.ListStore.new(DataObject)
        self.selection_model = Gtk.SingleSelection(model=self.store)
        self.column_view_entries.set_model(self.selection_model)

    def _connect_signals(self):
        """Connect UI signals to their respective handlers."""
        self.entry_domain.connect("activate", self.on_entry_domain_activate)
        self.button_add_ip.connect(
            "clicked",
            lambda btn: self.on_get_ip_button_clicked(btn, self.entry_domain, self.textview_status)
        )
        self.button_delete.connect(
            "clicked",
            lambda btn: self.on_delete_button_clicked(btn, self.column_view_entries)
        )

    # Action methods
    def create_action(self, name, callback, shortcuts=None):
        """Create and register a new action."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.get_application().add_action(action)
        if shortcuts:
            self.get_application().set_accels_for_action(f"app.{name}", shortcuts)

    def on_about_action(self, widget, _):
        """Show the About dialog."""
        about = Adw.AboutWindow(
            transient_for=self.get_root(),
            application_name=APP_NAME,
            application_icon="com.github.mclellac.AkamaiStaging",
            developer_name="Carey McLelland",
            version=VERSION,
            developers=["Carey McLelland <careymclelland@gmail.com>"],
            copyright=COPYRIGHT,
            license_type=Gtk.License.GPL_3_0_ONLY,
        )
        about.present()

    def on_preferences_action(self, widget, _):
        logger.info("Preferences action activated")
        dialog = Preferences(self)
        dialog.present()

    def on_preferences_dialog_close(self, dialog):
        if not dialog.is_revealing():
            font_size = dialog.font_size_row.get_value()
            self.apply_font_size(font_size)
            dialog.destroy()

    def apply_font_size(self, font_size):
        """Apply the selected font size to UI elements using CSS."""
        css_provider = Gtk.CssProvider()
        css = f"""
        * {{ font-size: {font_size}pt; }}  /* Apply to all widgets */
        """
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def apply_theme(self, dark_theme_enabled):
        """Apply the selected theme (dark or light)."""
        if dark_theme_enabled:
            self.style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        else:
            self.style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

    def load_preferences(self):
        """Load preferences from the configuration file."""
        if os.path.exists(PREFERENCES_FILE):
            config = configparser.ConfigParser()
            config.read(PREFERENCES_FILE)
            dark_theme_enabled = config.getboolean("Preferences", "dark_theme", fallback=True)
            self.apply_theme(dark_theme_enabled)
            # Load and apply font size preference
            font_size = config.get("Preferences", "font_size", fallback=12)
            self.apply_font_size(font_size)

    def do_activate(self):
        """Activate the application window."""
        win = self.props.active_window
        if not win:
            logger.debug("Creating new AkamaiStagingWindow instance")
            win = AkamaiStagingWindow(application=self)
            logger.debug("Presenting window")
            win.present()
        else:
            self.props.active_window.present()

    # Column view methods
    def create_column_view_columns(self):
        """Create and append columns to the column view."""
        logger.debug("Creating column view columns")

        # Create and append the IP address column
        ip_column = self._create_and_append_column(
            title="IP Address",
            setup_func=self.setup_ip_column,
            bind_func=self.bind_ip_column,
        )
        # Create and append the hostname column
        hostname_column = self._create_and_append_column(
            title="Hostname",
            setup_func=self.setup_hostname_column,
            bind_func=self.bind_hostname_column,
        )

        # Populate the store after setting up the columns
        self.populate_store(self.store)

    def _create_and_append_column(self, title, setup_func, bind_func):
        """Create and append a column helper method."""
        logger.debug(f"Creating and appending column: {title}")
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", setup_func)
        factory.connect("bind", bind_func)

        column = Gtk.ColumnViewColumn(title=title, factory=factory)
        column.set_expand(True)  # Horizontally expand
        self.column_view_entries.append_column(column)
        logger.debug(f"Appended column: {title}")
        return column

    def setup_ip_column(self, factory, list_item):
        """Set up the IP address column."""
        logger.debug("Setting up IP address column")
        label = Gtk.Label()
        list_item.set_child(label)

    def bind_ip_column(self, factory, list_item):
        """Bind data to the IP address column."""
        logger.debug("Binding data to IP address column")
        label = list_item.get_child()
        obj = list_item.get_item()
        logger.debug(f"Setting IP label text: {obj.ip}")
        label.set_text(obj.ip)

    def setup_hostname_column(self, factory, list_item):
        """Set up the hostname column."""
        logger.debug("Setting up hostname column")
        label = Gtk.Label()
        list_item.set_child(label)

    def bind_hostname_column(self, factory, list_item):
        """Bind data to the hostname column."""
        logger.debug("Binding data to hostname column")
        label = list_item.get_child()
        obj = list_item.get_item()
        logger.debug(f"Setting hostname label text: {obj.hostname}")
        label.set_text(obj.hostname)

    # Store methods
    def populate_store(self, store):
        """Populate the store with data from the hosts file."""
        logger.debug("Populating store with hosts file data")
        store.remove_all()  # Clear previous data
        try:
            with open(self.hfe.HOSTS_FILE, "r", encoding="utf-8") as hosts_file:
                for line in hosts_file:
                    line = line.strip()  # Remove leading/trailing whitespace
                    if not line or line.startswith("#"):
                        continue  # Skip empty lines and comments
                    line_parts = line.split(maxsplit=1)
                    ip = line_parts[0]
                    hostname = line_parts[1] if len(line_parts) > 1 else ""
                    # Lets add a filter to ignore things that could be in the
                    # hosts file that we don't want to display or edit as they
                    # are not related.
                    if (
                        ip in ["127.0.0.1", "::1", "255.255.255.255"]
                        or hostname is None
                        or any(
                            word in hostname.lower()
                            for word in ["container", "registry", "docker"]
                        )
                        or hostname.lower()
                        in [
                            "localhost",
                            "localhost.localdomain",
                            "localhost6",
                            "localhost6.localdomain6",
                        ]
                    ):
                        continue

                    logger.debug(f"Appending to store: IP={ip}, Hostname={hostname}")
                    obj = DataObject(ip, hostname)
                    store.append(obj)
        except FileNotFoundError as e:
            logger.error(f"Error reading {self.hfe.HOSTS_FILE}: {e}")
            sys.exit(1)

    # Event handlers
    def on_entry_domain_activate(self, entry):
        """Handle the Enter key press in the domain entry."""
        domain = entry.get_text()

        # Call on_get_ip_button_clicked to handle domain validation and further processing
        self.on_get_ip_button_clicked(self.button_add_ip, entry, self.textview_status)

    def on_get_ip_button_clicked(self, button, entry, textview_status):
        """Handle the Get IP button click."""
        logger.debug("Get IP button clicked")
        domain = entry.get_text()
        sanitized_domain = self.akl.sanitize_domain(domain, textview_status)

        textview_status.set_margin_top(12)
        text_buffer = textview_status.get_buffer()
        text_buffer.set_text("")  # Clear the text buffer

        try:
            print(sanitized_domain)
            if sanitized_domain and re.match(
                r"^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", sanitized_domain
            ):
                staging_ip = self.ns.get_akamai_staging_ip(
                    sanitized_domain, textview_status
                )
                if staging_ip:
                    self.hfe.update_hosts_file_content(
                        staging_ip, sanitized_domain, False, textview_status
                    )
                    self.populate_store(self.store)

                    # Clear the domain entry text
                    entry.set_text("")
                else:
                    self.akl.print_to_textview(
                        textview_status,
                        f"Error: Failed to get Akamai Staging IP for {sanitized_domain}",
                    )
            else:
                self.akl.print_to_textview(
                    textview_status, "Invalid domain. Please enter a valid domain."
                )
        except Exception as e:
            self.akl.print_to_textview(
                textview_status,
                f"Error: {e}",
            )

    def on_delete_button_clicked(self, button, column_view_entries):
        """Handle the Delete button click."""
        selected_item = self.selection_model.get_selected_item()
        if not selected_item:
            self.akl.print_to_textview(
                self.textview_status, "No entry selected for deletion."
            )
            return

        entry = f"{selected_item.ip} {selected_item.hostname}"
        logger.debug(f"Deleting entry: {entry}")
        removed_entry = self.hfe.remove_hosts_entry(entry)
        self.populate_store(self.store)

        # Clear the text buffer of textview_status
        text_buffer = self.textview_status.get_buffer()
        text_buffer.set_text("")  # Clear the text buffer

        # Update the status label with a message indicating the removed entry
        self.akl.print_to_textview(self.textview_status, f"{removed_entry}")


class DataObject(GObject.Object):
    """Data object for storing IP and hostname entries."""

    ip = GObject.Property(type=str)
    hostname = GObject.Property(type=str)

    def __init__(self, ip, hostname):
        super().__init__()
        self.ip = ip
        self.hostname = hostname
