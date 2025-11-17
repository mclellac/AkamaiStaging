import logging
import re
from socket import gaierror
import sys

from dns.exception import DNSException, Timeout as DNSTimeout
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from akstaging.aklib import sanitize_domain, print_to_textview
from akstaging.defs import APP_NAME, COPYRIGHT, RESOURCE_PATH, VERSION
from akstaging.dns_utils import DNSUtils as ns
from akstaging.hosts import HostsFileEdit as hfe
from akstaging.preferences import Preferences
from akstaging.status_codes import Status
from akstaging.i18n import get_translator

_ = get_translator()

# Load and register the resource bundle
resource_path = RESOURCE_PATH
try:
    resource = Gio.Resource.load(resource_path)
    Gio.resources_register(resource)
except GLib.Error as e:
    logging.error("Failed to load resource: %s", e)
    sys.exit(1)


class DataObject(GObject.Object):
    """A GObject class to represent a host entry."""
    ip = GObject.Property(type=str)
    hostname = GObject.Property(type=str)

    def __init__(self, ip: str, hostname: str):
        super().__init__()
        self.ip = ip
        self.hostname = hostname


logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/github/mclellac/AkamaiStaging/gtk/window.ui")
class AkamaiStagingWindow(Adw.ApplicationWindow):
    """Main application window for the Akamai Staging tool."""

    __gtype_name__ = "AkamaiStagingWindow"

    button_add_ip: Gtk.Button = Gtk.Template.Child()
    button_delete: Gtk.Button = Gtk.Template.Child()
    button_edit_host: Gtk.Button = Gtk.Template.Child()
    column_view_entries: Gtk.ColumnView = Gtk.Template.Child()
    textview_status: Gtk.TextView = Gtk.Template.Child()
    entry_domain: Adw.EntryRow = Gtk.Template.Child()
    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    search_entry_hosts: Gtk.SearchEntry = Gtk.Template.Child()
    hosts_view_switcher: Adw.ViewSwitcher = Gtk.Template.Child()
    scrolled_window_hosts_list: Gtk.ScrolledWindow = Gtk.Template.Child()
    empty_hosts_status_page: Adw.StatusPage = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initializes the Akamai Staging main application window."""
        super().__init__(**kwargs)
        logger.debug("Initializing AkamaiStagingWindow")

        self._item_to_delete = None
        self.edit_ip_entry_row = None
        self.edit_hostname_entry_row = None

        self._initialize_helpers()
        self._initialize_ui_actions()
        self._initialize_store()
        self.create_column_view_columns()
        self._connect_signals()

        if self.button_add_ip:
            self.set_default_widget(self.button_add_ip)

        logger.debug("AkamaiStagingWindow initialized.")

    def _initialize_helpers(self):
        """Initializes instances of helper classes."""
        self.hosts_editor = hfe()
        self.ns = ns()

    def _initialize_ui_actions(self):
        """Initializes application-wide and window-specific actions."""
        self.create_action("quit", lambda *_: self.get_application().quit(), ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("preferences", self.on_preferences_action)

    def _initialize_store(self):
        """Initializes the Gio.ListStore and the Gtk.ColumnView's model chain."""
        self.store = Gio.ListStore.new(DataObject)
        self.filter_model = Gtk.FilterListModel.new(model=self.store, filter=None)
        self.sort_model = Gtk.SortListModel.new(model=self.filter_model, sorter=None)
        self.selection_model = Gtk.SingleSelection(model=self.sort_model)
        self.column_view_entries.set_model(self.selection_model)
        self.hosts_custom_filter = None
        self._update_hosts_view_visibility()

    def _connect_signals(self):
        """Connects UI element signals to their respective handler methods."""
        self.entry_domain.connect("apply", self.on_entry_domain_activate)
        self.button_add_ip.connect("clicked", self._handle_add_ip_clicked)
        self.search_entry_hosts.connect("search-changed", self._on_search_changed)
        self.button_delete.connect("clicked", self.on_delete_button_clicked)
        self.button_edit_host.connect("clicked", self.on_edit_host_button_clicked)

    def _handle_add_ip_clicked(self, _button: Gtk.Button):
        """Handles the 'clicked' signal for the 'Add IP' button."""
        self.on_get_ip_button_clicked()

    def create_action(self, name: str, callback: callable, shortcuts: list[str] | None = None):
        """Creates a Gio.SimpleAction and connects it to a callback."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.get_application().add_action(action)
        if shortcuts:
            self.get_application().set_accels_for_action(f"app.{name}", shortcuts)

    def on_about_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None):
        """Handles the 'about' action activation."""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=APP_NAME,
            application_icon="com.github.mclellac.AkamaiStaging",
            developer_name="Carey McLelland",
            version=VERSION,
            website="https://github.com/mclellac/AkamaiStaging",
            issue_url="https://github.com/mclellac/AkamaiStaging/issues",
            developers=["Carey McLelland <careymclelland@gmail.com>"],
            copyright=COPYRIGHT,
            license_type=Gtk.License.GPL_3_0_ONLY,
        )
        about.present()

    def on_preferences_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None):
        """Handles the 'preferences' action activation."""
        preferences_window = Preferences(parent_window=self)
        preferences_window.present()

    def create_column_view_columns(self):
        """Creates and configures the columns for the Gtk.ColumnView."""
        ip_factory = Gtk.SignalListItemFactory()
        ip_factory.connect("setup", self._setup_column_cell)
        ip_factory.connect("bind", self._bind_column_cell_data, "ip")
        ip_column = Gtk.ColumnViewColumn(title=_("IP Address"), factory=ip_factory)
        ip_sorter = Gtk.StringSorter.new(expression=Gtk.PropertyExpression.new(DataObject, None, "ip"))
        ip_column.set_sorter(ip_sorter)
        ip_column.set_expand(True)
        self.column_view_entries.append_column(ip_column)

        hostname_factory = Gtk.SignalListItemFactory()
        hostname_factory.connect("setup", self._setup_column_cell)
        hostname_factory.connect("bind", self._bind_column_cell_data, "hostname")
        hostname_column = Gtk.ColumnViewColumn(title=_("Hostname"), factory=hostname_factory)
        hostname_sorter = Gtk.StringSorter.new(expression=Gtk.PropertyExpression.new(DataObject, None, "hostname"))
        hostname_column.set_sorter(hostname_sorter)
        hostname_column.set_expand(True)
        self.column_view_entries.append_column(hostname_column)

        self.populate_store(self.store)

    def _setup_column_cell(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
        """Sets up the widget (a Gtk.Label) for a cell in the ColumnView."""
        label = Gtk.Label(xalign=0)
        list_item.set_child(label)

    def _bind_column_cell_data(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, column_type: str):
        """Binds data from a DataObject to the Gtk.Label in a ColumnView cell."""
        label = list_item.get_child()
        obj = list_item.get_item()
        label.set_text(getattr(obj, column_type, ""))

    def populate_store(self, store: Gio.ListStore):
        """Populates the Gio.ListStore with entries from the system's hosts file."""
        logger.debug("Populating store from hosts file.")
        store.remove_all()
        status, file_content = self.hosts_editor.read_hosts_file_content_privileged()

        if status == Status.SUCCESS:
            for line in file_content:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith("#"):
                    continue
                parts = stripped_line.split("#", 1)[0].strip().split(maxsplit=1)
                if len(parts) < 2:
                    continue
                ip, hostname = parts
                if ip in ("127.0.0.1", "::1", "255.255.255.255") or "localhost" in hostname:
                    continue
                store.append(DataObject(ip, hostname))
        else:
            logger.error(f"Failed to read hosts file: {status.name} - {file_content}")
            print_to_textview(self.textview_status, _("Error loading hosts entries: {file_content}"))

        self._update_hosts_view_visibility()

    def _update_hosts_view_visibility(self):
        """Manages the visibility of the hosts list vs. an 'empty' state page."""
        is_empty = self.sort_model.get_n_items() == 0
        self.scrolled_window_hosts_list.set_visible(not is_empty)
        self.empty_hosts_status_page.set_visible(is_empty)

    def _hosts_filter_func(self, item: DataObject) -> bool:
        """Filter function for the Gtk.FilterListModel."""
        search_text = self.search_entry_hosts.get_text().strip().lower()
        if not search_text:
            return True
        return search_text in item.ip.lower() or search_text in item.hostname.lower()

    def _on_search_changed(self, _search_entry: Gtk.SearchEntry):
        """Handles the 'search-changed' signal from the search entry."""
        if self.hosts_custom_filter is None:
            self.hosts_custom_filter = Gtk.CustomFilter.new(self._hosts_filter_func)
            self.filter_model.set_filter(self.hosts_custom_filter)
        self.hosts_custom_filter.changed(Gtk.FilterChange.DIFFERENT)

    def on_entry_domain_activate(self, _entry: Adw.EntryRow):
        """Handles the 'apply' signal from the domain entry row."""
        self.on_get_ip_button_clicked()

    def _validate_domain_input(self, domain_input: str) -> tuple[bool, str, str]:
        """Sanitizes and validates a domain name input string."""
        sanitized_domain = sanitize_domain(domain_input)
        if domain_input != sanitized_domain:
            print_to_textview(self.textview_status, _("Notice: Input '{domain_input}' sanitized to '{sanitized_domain}'.\n").format(
                domain_input=domain_input, sanitized_domain=sanitized_domain
            ))
        if not re.match(r"^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", sanitized_domain):
            return False, sanitized_domain, _("Invalid domain format.")
        return True, sanitized_domain, ""

    def _perform_staging_ip_lookup(self, domain: str) -> tuple[str | None, str | None, str]:
        """Performs a DNS lookup to find the Akamai staging IP."""
        try:
            ip, cname = self.ns.get_akamai_staging_ip(domain)
            if not ip:
                return None, cname, _("Could not determine Akamai staging IP for {domain}.").format(domain=domain)
            return ip, cname, ""
        except (DNSException, DNSTimeout, gaierror) as e:
            logger.error(f"DNS lookup failed for {domain}: {e}")
            return None, None, _("DNS lookup failed for {domain}: {e}").format(domain=domain, e=e)

    def _update_hosts_and_ui(self, staging_ip: str, domain: str):
        """Updates the system hosts file and refreshes the UI."""
        status, message = self.hosts_editor.update_hosts_file_content(staging_ip, domain, delete=False)
        print_to_textview(self.textview_status, message)
        toast = self._get_toast_message_for_add_status(status, domain)
        if status == Status.SUCCESS:
            self.populate_store(self.store)
            self.entry_domain.set_text("")
        self.show_toast(toast)

    def on_get_ip_button_clicked(self):
        """Handles the 'Get Staging IP & Add to Hosts' button click."""
        self.textview_status.get_buffer().set_text("")
        is_valid, domain, err_msg = self._validate_domain_input(self.entry_domain.get_text())
        if not is_valid:
            print_to_textview(self.textview_status, err_msg)
            self.show_toast(_("Invalid domain format entered."))
            return

        ip, cname, err_msg = self._perform_staging_ip_lookup(domain)
        if not ip:
            print_to_textview(self.textview_status, err_msg)
            self.show_toast(err_msg)
            return

        status_msg = _("Found IP {ip} for {name}. Adding to hosts file...").format(
            ip=ip, name=cname or domain
        )
        print_to_textview(self.textview_status, status_msg)
        self._update_hosts_and_ui(ip, domain)

    def on_delete_button_clicked(self, _button: Gtk.Button):
        """Handles the 'Delete' button click event."""
        item = self.selection_model.get_selected_item()
        if not item:
            self.show_toast(_("No entry selected for deletion."))
            return
        self._item_to_delete = item
        entry_display = f"{item.ip} {item.hostname}"
        dialog = Adw.MessageDialog.new(self.get_root(), _("Confirm Deletion"),
                                       _("Delete the entry:\n'{entry}'?").format(entry=entry_display))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_delete_confirmation_response)
        dialog.present()

    def _on_delete_confirmation_response(self, _dialog: Adw.MessageDialog, response_id: str):
        """Handles the response from the delete confirmation dialog."""
        if response_id == "delete" and hasattr(self, "_item_to_delete"):
            item = self._item_to_delete
            entry = f"{item.ip} {item.hostname}"
            status, msg = self.hosts_editor.remove_hosts_entry(entry)
            print_to_textview(self.textview_status, msg)
            toast = self._get_toast_message_for_delete_status(status, entry)
            if status == Status.SUCCESS:
                self.populate_store(self.store)
            self.show_toast(toast)
        else:
            self.show_toast(_("Deletion cancelled."))
        if hasattr(self, "_item_to_delete"):
            del self._item_to_delete

    def on_edit_host_button_clicked(self, _button: Gtk.Button):
        """Handles the 'Edit' button click event."""
        item = self.selection_model.get_selected_item()
        if not item:
            self.show_toast(_("No entry selected to edit."))
            return

        dialog = Adw.MessageDialog(transient_for=self, heading=_("Edit Host Entry"))
        self.edit_ip_entry_row = Adw.EntryRow(title=_("IP Address"), text=item.ip)
        self.edit_hostname_entry_row = Adw.EntryRow(title=_("Hostname"), text=item.hostname)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.append(self.edit_ip_entry_row)
        content.append(self.edit_hostname_entry_row)
        dialog.set_extra_child(content)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("save", _("Save"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_edit_dialog_response, item)
        dialog.present()

    def _handle_save_edit(self, original_item: DataObject, new_ip: str, new_hostname: str):
        """Handles the logic for saving an edited host entry."""
        old_entry = f"{original_item.ip} {original_item.hostname}"
        remove_status, _ = self.hosts_editor.remove_hosts_entry(old_entry)

        if remove_status not in [Status.SUCCESS, Status.ERROR_NOT_FOUND]:
            self.show_toast(self._get_toast_message_for_edit_remove_status(remove_status, old_entry))
            return

        add_status, msg = self.hosts_editor.update_hosts_file_content(new_ip, new_hostname, delete=False)
        print_to_textview(self.textview_status, msg)
        self.show_toast(self._get_toast_message_for_edit_add_status(add_status, new_ip, new_hostname))
        if add_status == Status.SUCCESS:
            self.populate_store(self.store)

    def _on_edit_dialog_response(self, dialog: Adw.MessageDialog, response_id: str, item: DataObject):
        """Handles the response from the edit host entry dialog."""
        if response_id == "save":
            new_ip = self.edit_ip_entry_row.get_text().strip()
            new_hostname = self.edit_hostname_entry_row.get_text().strip()
            if not new_ip or not new_hostname:
                self.show_toast(_("IP and hostname cannot be empty."))
            elif item.ip == new_ip and item.hostname == new_hostname:
                self.show_toast(_("No changes detected."))
            else:
                self._handle_save_edit(item, new_ip, new_hostname)
        else:
            self.show_toast(_("Edit operation cancelled."))
        dialog.close()
        self.edit_ip_entry_row = self.edit_hostname_entry_row = None

    def _get_toast_message_for_add_status(self, status: Status, domain: str) -> str:
        """Generates a toast message for an add operation."""
        match status:
            case Status.SUCCESS: return _("Host '{domain}' added.").format(domain=domain)
            case Status.ALREADY_EXISTS: return _("Host '{domain}' already configured.").format(domain=domain)
            case _: return _("Failed to add host '{domain}'.").format(domain=domain)

    def _get_toast_message_for_delete_status(self, status: Status, entry: str) -> str:
        """Generates a toast message for a delete operation."""
        match status:
            case Status.SUCCESS: return _("Host '{entry}' removed.").format(entry=entry)
            case Status.ERROR_NOT_FOUND: return _("Host '{entry}' not found.").format(entry=entry)
            case _: return _("Failed to remove '{entry}'.").format(entry=entry)

    def _get_toast_message_for_edit_remove_status(self, status: Status, entry: str) -> str:
        """Generates a toast message for the removal part of an edit operation."""
        return _("Failed to remove old entry '{entry}'. Edit aborted.").format(entry=entry)

    def _get_toast_message_for_edit_add_status(self, status: Status, new_ip: str, new_hostname: str) -> str:
        """Generates a toast message for the addition part of an edit operation."""
        entry = f"{new_ip} {new_hostname}"
        match status:
            case Status.SUCCESS: return _("Host entry updated to '{entry}'.").format(entry=entry)
            case _: return _("Failed to save changes for '{entry}'.").format(entry=entry)

    def show_toast(self, message: str, timeout: int = 3):
        """Displays a toast notification."""
        if self.toast_overlay:
            self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=timeout))
