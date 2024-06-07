# window.py
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
import re
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Gio, Adw, GObject, GLib
import sys
import logging

from akstaging.aklib import AkamaiLib as akl
from akstaging.dns_utils import DNSUtils as ns
from akstaging.hosts import HostsFileEdit as hfe
from akstaging.defs import VERSION, COPYRIGHT, APP_NAME

# Load and register the resource bundle
resource_path = "/usr/local/share/akamaistaging/akamaistaging.gresource"
try:
    resource = Gio.Resource.load(resource_path)
    Gio.resources_register(resource)
except GLib.Error as e:
    logging.error(f"Failed to load resource: {e}")
    sys.exit(1)

# Load CSS styles from the resource bundle
style_provider = Gtk.CssProvider()
style_provider.load_from_resource("/com/github/mclellac/AkamaiStaging/gtk/window.css")

# Apply the CSS to the default screen
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(), style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/github/mclellac/AkamaiStaging/gtk/window.ui")
class AkamaiStagingWindow(Adw.ApplicationWindow):
    __gtype_name__ = "AkamaiStagingWindow"

    button_add_ip: Gtk.Button = Gtk.Template.Child()
    button_delete: Gtk.Button = Gtk.Template.Child()
    column_view_entries: Gtk.ColumnView = Gtk.Template.Child()
    textview_status: Gtk.TextView = Gtk.Template.Child()
    entry_domain: Gtk.Entry = Gtk.Template.Child()

    def __init__(self, application=None):
        super().__init__(application=application)
        logger.debug("Initializing AkamaiStagingWindow")

        self._verify_ui_elements()
        self._initialize_helpers()
        self._initialize_ui_actions()
        self._initialize_store()
        self.create_column_view_columns()
        self._connect_signals()

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
        #self.create_action("preferences", self.on_preferences_action)

    def _initialize_store(self):
        """Initialize the data store for the column view."""
        self.store = Gio.ListStore.new(DataObject)
        self.selection_model = Gtk.SingleSelection(model=self.store)
        self.column_view_entries.set_model(self.selection_model)

    def _connect_signals(self):
        """Connect UI signals to their respective handlers."""
        self.button_add_ip.connect(
            "clicked",
            lambda btn: self.on_get_ip_button_clicked(
                btn, self.entry_domain, self.textview_status
            ),
        )
        self.button_delete.connect(
            "clicked",
            lambda btn: self.on_delete_button_clicked(btn, self.column_view_entries),
        )

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
        """Handle the Preferences action."""
        logger.info("Preferences action activated")

    def create_action(self, name, callback, shortcuts=None):
        """Create and register a new action."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.get_application().add_action(action)
        if shortcuts:
            self.get_application().set_accels_for_action(f"app.{name}", shortcuts)

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
        """Helper method to create and append a column."""
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
                    logger.debug(f"Appending to store: IP={ip}, Hostname={hostname}")
                    obj = DataObject(ip, hostname)
                    store.append(obj)
        except FileNotFoundError as e:
            logger.error(f"Error reading {self.hfe.HOSTS_FILE}: {e}")
            sys.exit(1)

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
            if sanitized_domain and re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', sanitized_domain):
                staging_ip = self.ns.get_akamai_staging_ip(sanitized_domain, textview_status)
                if staging_ip:
                    self.hfe.update_hosts_file_content(
                        staging_ip, sanitized_domain, False, textview_status
                    )
                    self.populate_store(self.store)
                    self.akl.print_to_textview(
                        textview_status,
                        f"Added Akamai Staging IP for {sanitized_domain} as {staging_ip}",
                    )
                else:
                    self.akl.print_to_textview(
                        textview_status,
                        f"Error: Failed to get Akamai Staging IP for {sanitized_domain}",
                    )
            else:
                self.akl.print_to_textview(
                    textview_status,
                    "Invalid domain. Please enter a valid domain."
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
            self.textview_status.set_text("No entry selected for deletion.")
            return

        entry = f"{selected_item.ip} {selected_item.hostname}"
        logger.debug(f"Deleting entry: {entry}")
        self.hfe.remove_hosts_entry(entry)
        removed_entry = self.hfe.remove_hosts_entry(entry)
        self.populate_store(self.store)

        # Clear the text buffer of textview_status
        text_buffer = self.textview_status.get_buffer()
        text_buffer.set_text("")  # Clear the text buffer

        # Update the status label with a message indicating the removed entry
        self.textview_status.set_text(f"{removed_entry}")

class DataObject(GObject.Object):
    """Data object for storing IP and hostname entries."""

    ip = GObject.Property(type=str)
    hostname = GObject.Property(type=str)

    def __init__(self, ip, hostname):
        super().__init__()
        self.ip = ip
        self.hostname = hostname

