# akstaging/window.py
import logging
import os
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

SETTINGS_ID = "com.github.mclellac.AkamaiStaging"

# Load and register the resource bundle
resource_path = RESOURCE_PATH
try:
    resource = Gio.Resource.load(resource_path)
    Gio.resources_register(resource)
except GLib.Error as e:
    logging.error("Failed to load resource: %s", e)
    sys.exit(1)

# Load CSS styles from the resource bundle
style_provider = Gtk.CssProvider()

class DataObject(GObject.Object):
    """
    A GObject class to represent a host entry (IP address and hostname).

    This object is used to store data for entries displayed in the Gtk.ColumnView.

    Properties:
        ip (str): The IP address of the host entry.
        hostname (str): The hostname(s) associated with the IP address.
    """
    ip = GObject.Property(type=str, nick="IP Address", blurb="The IP address of the host entry.")
    hostname = GObject.Property(type=str, nick="Hostname", blurb="The hostname(s) associated with the IP address.")

    def __init__(self, ip: str, hostname: str):
        """
        Initializes a DataObject instance.

        Args:
            ip: The IP address for this host entry.
            hostname: The hostname(s) for this host entry.
        """
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

    def __init__(self, application=None):
        """
        Initializes the Akamai Staging main application window.

        Sets up UI elements, initializes helper classes, connects signals,
        loads settings, and applies theme and font scaling.

        Args:
            application: The Adw.Application instance this window belongs to.
        """
        super().__init__(application=application)
        logger.debug("Initializing AkamaiStagingWindow")

        self.font_css_provider = None
        self._item_to_delete = None
        self.edit_ip_entry_row = None
        self.edit_hostname_entry_row = None

        self._verify_ui_elements()
        self._initialize_helpers()
        self._initialize_ui_actions()
        self._initialize_store()
        self.create_column_view_columns()
        self._connect_signals()
        # Set button_add_ip as the default widget for the window.
        # This allows Enter key press in entry_domain to trigger this button.
        if self.button_add_ip:
            self.set_default_widget(self.button_add_ip)
        self.set_size_request(700, 650)

        self.settings = Gio.Settings.new(SETTINGS_ID)
        self.apply_theme()
        self.apply_font_scaling()
        logger.debug("AkamaiStagingWindow initialized.")

    def apply_font_scaling(self, scale_factor=None):
        """
        Applies a font scaling factor to the entire application using a dynamic CSS provider.

        If `scale_factor` is provided, it's used directly. Otherwise, the factor is
        retrieved from GSettings ('font-scale' key). A CSS provider is added to the
        default display to scale fonts globally. If an existing custom font provider
        was set by this method, it's removed before applying the new one. If the
        scale factor is effectively 1.0, any existing custom provider is removed,
        restoring the default font sizes.

        Args:
            scale_factor (float, optional): The font scaling factor to apply (e.g., 1.2 for 120%).
                                            Defaults to None, which means it's read from GSettings.
        """
        if scale_factor is None:
            scale_factor = self.settings.get_double('font-scale')

        logger.info("Applying font scale factor: %s", scale_factor)

        display = Gdk.Display.get_default()
        if display is None:
            logger.error("Cannot get GDK Display to apply font scaling.")
            return

        if self.font_css_provider is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self.font_css_provider)
            self.font_css_provider = None
            logger.debug("Removed existing font CSS provider.")

        if abs(scale_factor - 1.0) > 0.01:
            self.font_css_provider = Gtk.CssProvider()
            css_data = f"* {{ font-size: {scale_factor}rem; }}"
            self.font_css_provider.load_from_data(css_data.encode())
            Gtk.StyleContext.add_provider_for_display(
                display, self.font_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
            logger.debug("Applied new font CSS provider with scale: %s", scale_factor)
        else:
            logger.debug("Font scale is default (1.0), no custom CSS provider applied.")

    # Initialization methods
    def _verify_ui_elements(self):
        """
        Verifies that all critical UI elements defined in the Gtk.Template are correctly loaded.

        This method asserts that each of the following UI elements, which are expected
        to be children of the AkamaiStagingWindow, are not None:
        - button_add_ip (Gtk.Button)
        - button_delete (Gtk.Button)
        - button_edit_host (Gtk.Button)
        - column_view_entries (Gtk.ColumnView)
        - textview_status (Gtk.TextView)
        - entry_domain (Adw.EntryRow)
        - toast_overlay (Adw.ToastOverlay)
        - search_entry_hosts (Gtk.SearchEntry)
        - hosts_view_switcher (Adw.ViewSwitcher)
        - scrolled_window_hosts_list (Gtk.ScrolledWindow)
        - empty_hosts_status_page (Adw.StatusPage)

        If any of these elements are not found, an AssertionError is raised,
        indicating a problem with the UI template or its loading.
        """
        assert self.button_add_ip is not None, "button_add_ip is not loaded"
        assert self.button_delete is not None, "button_delete is not loaded"
        assert self.button_edit_host is not None, "button_edit_host is not loaded"
        assert self.column_view_entries is not None, "column_view_entries is not loaded"
        assert self.textview_status is not None, "textview_status is not loaded"
        assert self.entry_domain is not None, "entry_domain is not loaded"
        assert self.toast_overlay is not None, "toast_overlay is not loaded"
        assert self.search_entry_hosts is not None, "search_entry_hosts is not loaded"
        assert self.hosts_view_switcher is not None, "hosts_view_switcher is not loaded"
        assert self.scrolled_window_hosts_list is not None, "scrolled_window_hosts_list is not loaded"
        assert self.empty_hosts_status_page is not None, "empty_hosts_status_page is not loaded"

    def _initialize_helpers(self):
        """
        Initializes instances of helper classes.

        This includes:
        - `HostsFileEdit` for interacting with the system's hosts file.
        - `DNSUtils` for performing DNS lookups.
        """
        self.hosts_editor = hfe()
        self.ns = ns()

    def _initialize_ui_actions(self):
        """
        Initializes application-wide and window-specific actions.

        This sets up actions for common operations like 'quit', 'about',
        and 'preferences', making them available for menus or keyboard shortcuts.
        """
        self.create_action("quit", lambda *_: self.quit(), ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("preferences", self.on_preferences_action)

    def _initialize_store(self):
        """
        Initializes the Gio.ListStore and the Gtk.ColumnView's model chain.

        This sets up the data store (`Gio.ListStore` for `DataObject` instances)
        and the necessary models for filtering (`Gtk.FilterListModel`),
        sorting (`Gtk.SortListModel`), and selection (`Gtk.SingleSelection`)
        to be used by the `column_view_entries`.
        """
        self.store = Gio.ListStore.new(DataObject)

        # Model chain: ListStore -> FilterListModel -> SortListModel -> SingleSelection
        self.filter_model = Gtk.FilterListModel.new(model=self.store, filter=None)
        self.sort_model = Gtk.SortListModel.new(model=self.filter_model, sorter=None)
        self.selection_model = Gtk.SingleSelection(model=self.sort_model)

        self.column_view_entries.set_model(self.selection_model)

        self.hosts_custom_filter = None
        self._update_hosts_view_visibility()

    def _connect_signals(self):
        """
        Connects UI element signals to their respective handler methods.

        This includes signals for:
        - Domain entry activation (`Adw.EntryRow.apply`).
        - Add IP button click (`Gtk.Button.clicked`).
        - Search entry changes (`Gtk.SearchEntry.search-changed`).
        - Delete button click.
        - Edit host button click.
        """
        self.entry_domain.connect("apply", self.on_entry_domain_activate)
        self.button_add_ip.connect("clicked", self._handle_add_ip_clicked)

        if hasattr(self, 'search_entry_hosts') and self.search_entry_hosts:
            self.search_entry_hosts.connect("search-changed", self._on_search_changed)
        else:
            logger.warning("search_entry_hosts UI element not found or not defined in template. Search will not be active.")

        self.button_delete.connect(
            "clicked",
            lambda btn: self.on_delete_button_clicked(btn)
        )
        self.button_edit_host.connect("clicked", self.on_edit_host_button_clicked)

    def _handle_add_ip_clicked(self, _button: Gtk.Button):
        """
        Handles the 'clicked' signal for the 'Add IP' button.

        This method simply calls `on_get_ip_button_clicked` to process
        the domain entered by the user.

        Args:
            _button: The Gtk.Button that emitted the signal.
        """
        self.on_get_ip_button_clicked()

    # Action methods
    def create_action(self, name: str, callback: callable, shortcuts: list[str] | None = None):
        """
        Creates a Gio.SimpleAction, connects it to a callback, and adds it to the application.

        Optionally, keyboard shortcuts (accelerators) can be set for the action.

        Args:
            name: The name of the action (e.g., "quit", "about").
            callback: The function to call when the action is activated.
            shortcuts: A list of shortcut strings (e.g., ["<primary>q"]). Defaults to None.
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.get_application().add_action(action)
        if shortcuts:
            self.get_application().set_accels_for_action(f"app.{name}", shortcuts)

    def on_about_action(self, _widget: Gio.SimpleAction, _param: GLib.Variant | None):
        """
        Handles the 'about' action activation.

        Displays the application's About dialog.

        Args:
            _widget: The Gio.SimpleAction that was activated.
            _param: Optional parameter for the action (not used here).
        """
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

    def on_preferences_action(self, _widget: Gio.SimpleAction, _param: GLib.Variant | None):
        """
        Handles the 'preferences' action activation.

        Displays the application's Preferences window.

        Args:
            _widget: The Gio.SimpleAction that was activated.
            _param: Optional parameter for the action (not used here).
        """
        logger.info("Preferences action activated")
        preferences_window = Preferences(parent_window=self)
        preferences_window.present()

    def apply_theme(self):
        """
        Applies the color scheme (theme) based on the 'theme' GSettings key.

        Reads the 'theme' setting ('light', 'dark', or 'system') and updates
        the Adwaita style manager accordingly.
        """
        style_manager = Adw.StyleManager.get_for_display(self.get_display())
        theme_str = self.settings.get_string('theme')
        if theme_str == 'dark':
            style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        elif theme_str == 'light':
            style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
        else: # 'system' or any other fallback
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        logger.info("Applied theme: %s", theme_str)

    def do_activate(self):
        """
        Handles activation of the application (e.g., when launched).

        If a window for the application already exists, it is presented.
        Otherwise, a new AkamaiStagingWindow is created and presented.
        This method is typically connected to the 'activate' signal of the Adw.Application.
        """
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
        """
        Creates and configures the columns for the Gtk.ColumnView.

        This method sets up two columns: "IP Address" and "Hostname".
        It defines Gtk.SignalListItemFactory for each column to set up and bind
        data from DataObject instances in the store. Sorters are also configured
        for each column. Finally, it populates the store with initial data.
        """
        logger.debug("Creating column view columns")
        ip_factory = Gtk.SignalListItemFactory()
        ip_factory.connect("setup", self._setup_column_cell, "ip")
        ip_factory.connect("bind", self._bind_column_cell_data, "ip")
        ip_column = Gtk.ColumnViewColumn(title=_("IP Address"), factory=ip_factory)
        ip_sorter = Gtk.StringSorter.new(expression=Gtk.PropertyExpression.new(DataObject, None, "ip"))
        ip_sorter.set_ignore_case(True)
        ip_column.set_sorter(ip_sorter)
        ip_column.set_expand(True)
        self.column_view_entries.append_column(ip_column)

        hostname_factory = Gtk.SignalListItemFactory()
        hostname_factory.connect("setup", self._setup_column_cell, "hostname")
        hostname_factory.connect("bind", self._bind_column_cell_data, "hostname")
        hostname_column = Gtk.ColumnViewColumn(title=_("Hostname"), factory=hostname_factory)
        hostname_sorter = Gtk.StringSorter.new(expression=Gtk.PropertyExpression.new(DataObject, None, "hostname"))
        hostname_sorter.set_ignore_case(True)
        hostname_column.set_sorter(hostname_sorter)
        hostname_column.set_expand(True)
        self.column_view_entries.append_column(hostname_column)

        self.populate_store(self.store)
        self._update_hosts_view_visibility() # Initial check after populating

    def _setup_column_cell(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, _column_type: str):
        """
        Sets up the widget (a Gtk.Label) for a cell in the Gtk.ColumnView.
        This method is connected to the 'setup' signal of a Gtk.SignalListItemFactory.

        Args:
            _factory: The factory that emitted the signal.
            list_item: The Gtk.ListItem to set up.
            _column_type: A string indicating which column this cell belongs to (unused here,
                          but part of the factory signal).
        """
        label = Gtk.Label()
        list_item.set_child(label)

    def _bind_column_cell_data(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, column_type: str):
        """
        Binds data from a DataObject to the Gtk.Label in a Gtk.ColumnView cell.
        This method is connected to the 'bind' signal of a Gtk.SignalListItemFactory.

        Args:
            _factory: The factory that emitted the signal.
            list_item: The Gtk.ListItem whose child Gtk.Label needs data.
            column_type: A string ("ip" or "hostname") indicating which data field to bind.
        """
        label = list_item.get_child()
        obj = list_item.get_item() # This is a DataObject
        if column_type == "ip":
            label.set_text(obj.ip)
        elif column_type == "hostname":
            label.set_text(obj.hostname)

    # Store methods
    def populate_store(self, store: Gio.ListStore):
        """
        Populates the Gio.ListStore with entries from the system's hosts file.

        It reads the hosts file using `HostsFileEdit.read_hosts_file_content_privileged`,
        parses each relevant line, creates DataObject instances, and appends them
        to the provided `store`. Common localhost, broadcast, and container-related
        entries are filtered out. If reading the hosts file fails, an error message
        is printed to the status text view.

        Args:
            store: The Gio.ListStore to populate.
        """
        logger.debug("Populating store using privileged hosts file read.")
        store.remove_all()

        status, file_content = self.hosts_editor.read_hosts_file_content_privileged()

        if status == Status.SUCCESS:
            logger.info("Successfully read hosts file content via helper.")
            lines = file_content

            for line_content_str in lines:
                line = line_content_str.strip()
                if not line or line.startswith("#"):
                    continue

                # Handle potential comments at the end of active lines
                line_parts_raw = line.split("#", 1)[0].strip().split(maxsplit=1)
                if len(line_parts_raw) < 2:
                    continue

                ip = line_parts_raw[0]
                # The rest of the line can contain multiple hostnames
                hostname_segment = line_parts_raw[1]
                # Split hostname_segment by whitespace to handle multiple hostnames on one line,
                # but only take the first one for display in this UI's current structure,
                # or adjust DataObject and UI to handle multiple hostnames per IP if desired.
                # For now, let's assume we take all hostnames on the line as a single "hostname" string for the list.
                # Or, if the original intent was one primary hostname per entry:
                # first_hostname = hostname_segment.split()[0]
                # For now, keep it as is: hostname is the full segment after IP (and before #)
                hostname = hostname_segment

                # Filter out common localhost, broadcast, and container/registry related entries
                if (ip in ["127.0.0.1", "::1", "255.255.255.255"] or
                        any(word in hostname.lower() for word in ["container", "registry", "docker"]) or
                        hostname.lower() in [
                            "localhost", "localhost.localdomain", "localhost6",
                            "localhost6.localdomain6", "ip6-localhost", "ip6-loopback",
                            "ip6-localnet", "ip6-mcastprefix", "ip6-allnodes",
                            "ip6-allrouters", "ip6-allhosts"
                        ]):
                    continue
                logger.debug("Appending to store: IP=%s, Hostname=%s", ip, hostname)
                obj = DataObject(ip, hostname)
                store.append(obj)

        else: # Read has failed
            error_message = file_content
            logger.error("Failed to read hosts file via helper. Status: %s. Message: %s", status.name if hasattr(status,'name') else status, error_message)
            display_error = _("Error loading hosts entries: {error_detail}").format(error_detail=error_message)
            print_to_textview(self.textview_status, display_error)
        self._update_hosts_view_visibility()

    # View Visibility Method
    def _update_hosts_view_visibility(self):
        """
        Manages the visibility of the hosts list versus an 'empty' state page.

        If the `sort_model` (which reflects filtered data) contains no items,
        it hides the `scrolled_window_hosts_list` and shows the
        `empty_hosts_status_page`. Otherwise, it shows the list and hides
        the empty state page. This ensures a user-friendly message is displayed
        when no hosts entries are visible (either due to an empty hosts file
        or active filtering).
        """
        if self.sort_model and self.sort_model.get_n_items() == 0:
            self.scrolled_window_hosts_list.hide()
            self.empty_hosts_status_page.show()
            logger.debug("Switched to empty_state view.")
        else:
            self.empty_hosts_status_page.hide()
            self.scrolled_window_hosts_list.show()
            logger.debug("Switched to hosts_list view.")


    # Search and Filter methods
    def _hosts_filter_func(self, item: DataObject, search_entry_widget: Gtk.SearchEntry | None = None) -> bool:
        """
        Filter function for the Gtk.FilterListModel connected to the hosts list.

        It checks if the `item` (a DataObject) matches the current search text
        entered in `search_entry_widget` (or `self.search_entry_hosts` if not provided).
        The search is case-insensitive and checks against both the IP and hostname
        fields of the DataObject.

        Args:
            item: The DataObject instance to check.
            search_entry_widget: The Gtk.SearchEntry providing the text. If None,
                                 `self.search_entry_hosts` is used.

        Returns:
            True if the item should be visible (matches search or search is empty),
            False otherwise.
        """
        if search_entry_widget is None:
             search_entry_widget = self.search_entry_hosts

        search_text = search_entry_widget.get_text().strip().lower()
        if not search_text:
            return True

        if not isinstance(item, DataObject):
            return True

        if search_text in item.ip.lower():
            return True
        if search_text in item.hostname.lower():
            return True

        return False

    def _on_search_changed(self, search_entry: Gtk.SearchEntry):
        """
        Handles the 'search-changed' signal from the `search_entry_hosts`.

        It ensures a Gtk.CustomFilter using `_hosts_filter_func` is set on the
        `filter_model`. Then, it signals that the filter conditions have changed,
        triggering a re-filter of the list. Finally, it updates the visibility
        of the hosts list or empty state page based on the filter results.

        Args:
            search_entry: The Gtk.SearchEntry that emitted the signal.
        """
        if self.hosts_custom_filter is None:
            self.hosts_custom_filter = Gtk.CustomFilter.new(self._hosts_filter_func, self.search_entry_hosts)
            self.filter_model.set_filter(self.hosts_custom_filter)

        self.hosts_custom_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_hosts_view_visibility()

    # Event handlers
    def on_entry_domain_activate(self, _entry: Adw.EntryRow):
        """
        Handles the 'apply' signal from the domain entry row (e.g., when Enter is pressed).
        Triggers the same action as clicking the 'Add IP' button.

        Args:
            _entry: The Adw.EntryRow that emitted the signal.
        """
        self.on_get_ip_button_clicked()

    def _validate_domain_input(self, domain_input: str) -> tuple[bool, str, str]:
        """
        Sanitizes and validates a domain name input string.

        The domain is first sanitized (e.g., whitespace stripped, http(s):// prefix removed).
        Then, it's validated against a basic regex for domain structure.
        A notice is printed to the status view if sanitization changed the input.

        Args:
            domain_input: The raw domain string from the user.

        Returns:
            A tuple (is_valid, sanitized_domain, error_message):
            - is_valid (bool): True if the sanitized domain is considered valid, False otherwise.
            - sanitized_domain (str): The domain after sanitization.
            - error_message (str): An error message if invalid, empty otherwise.
        """
        sanitized_domain = sanitize_domain(domain_input)
        if domain_input != sanitized_domain:
            notice = _("Notice: Input '{domain_input}' sanitized to '{sanitized_domain}'.\n").format(
                domain_input=domain_input, sanitized_domain=sanitized_domain
            )
            print_to_textview(self.textview_status, notice)

        if not (sanitized_domain and re.match(r"^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", sanitized_domain)):
            error_message = _("Invalid domain format. Please enter a valid domain (e.g., www.example.com).")
            return False, sanitized_domain, error_message
        return True, sanitized_domain, ""

    def _perform_staging_ip_lookup(self, domain_to_lookup: str) -> tuple[str | None, str | None, str]:
        """
        Performs a DNS lookup to find the Akamai staging IP address for a given domain.

        It uses `DNSUtils.get_akamai_staging_ip` to resolve the domain.
        Handles potential DNS exceptions and returns structured results.

        Args:
            domain_to_lookup: The domain name for which to find the staging IP.

        Returns:
            A tuple (staging_ip, staging_cname, error_message):
            - staging_ip (str | None): The resolved Akamai staging IP address, or None if not found/error.
            - staging_cname (str | None): The CNAME record pointing to the Akamai staging network,
                                          if available, otherwise None.
            - error_message (str): A descriptive error message if the lookup fails or no IP is found,
                                   empty string on success.
        """
        staging_cname_from_lookup: str | None = None
        try:
            staging_ip, staging_cname_from_lookup = self.ns.get_akamai_staging_ip(domain_to_lookup)
            if not staging_ip:
                error_message = _("Could not determine Akamai staging IP for {domain}.").format(domain=domain_to_lookup)
                return None, staging_cname_from_lookup, error_message
            return staging_ip, staging_cname_from_lookup, ""
        except (DNSException, DNSTimeout, gaierror) as e_dns:
            logger.error("DNS lookup failed for %s: %s", domain_to_lookup, e_dns)
            error_message = _("DNS lookup failed for {domain}: {error}").format(domain=domain_to_lookup, error=e_dns)
            return None, staging_cname_from_lookup, error_message

    def _get_toast_message_for_add_status(self, status: Status, domain_to_add: str) -> str:
        """
        Generates a user-friendly toast message based on the status of an add/update operation.

        Args:
            status: The `Status` enum member representing the outcome of the operation.
            domain_to_add: The domain name that was being added/updated.

        Returns:
            A localized string suitable for displaying in a toast notification.
        """
        toast_message = ""
        match status:
            case Status.SUCCESS:
                toast_message = _("Host '{domain}' added.").format(domain=domain_to_add)
            case Status.ALREADY_EXISTS:
                toast_message = _("Host '{domain}' already configured.").format(domain=domain_to_add)
            case Status.USER_CANCELLED:
                toast_message = _("Operation cancelled by user.")
            case Status.ERROR_PERMISSION:
                toast_message = _("Permission error occurred.")
            case Status.ERROR_IO:
                toast_message = _("File I/O error occurred.")
            case Status.ERROR_NOT_FOUND:
                toast_message = _("Hosts file not found.")
            case Status.ERROR_UNSUPPORTED_FLATPAK:
                toast_message = _("Feature unavailable in Flatpak.")
            case _: # Covers ERROR_INTERNAL or any other unexpected status
                toast_message = _("Failed to add host '{domain}'.").format(domain=domain_to_add)
        return toast_message

    def _update_hosts_and_ui(self, staging_ip: str, domain_to_add: str):
        """
        Attempts to update the system hosts file with the new entry and refreshes the UI.

        Calls `HostsFileEdit.update_hosts_file_content` to add the `staging_ip` and
        `domain_to_add`. Prints the outcome to the status text view.
        Generates and displays a toast message. If successful, it repopulates the
        hosts list store and clears the domain entry field.

        Args:
            staging_ip: The staging IP address to add.
            domain_to_add: The domain name to associate with the IP.
        """
        status, message_hosts = self.hosts_editor.update_hosts_file_content(
            staging_ip, domain_to_add, delete=False
        )
        logger.debug("update_hosts_file_content result: Status=%s, Message=%s", status, message_hosts)
        print_to_textview(self.textview_status, message_hosts)

        toast_message = self._get_toast_message_for_add_status(status, domain_to_add)

        if status == Status.SUCCESS:
            self.populate_store(self.store) # This will call _update_hosts_view_visibility
            self.entry_domain.set_text("")

        self.show_toast(toast_message)

    def on_get_ip_button_clicked(self):
        """
        Handles the "Get Staging IP & Add to Hosts" button click event.

        It retrieves the domain from the input field, validates it, performs a DNS
        lookup for the Akamai staging IP, and then attempts to update the hosts file
        and UI with the new entry. Feedback is provided to the user via the status
        text view and toast messages throughout the process.
        """
        logger.debug("Entering on_get_ip_button_clicked with entry: %s", self.entry_domain.get_text())
        self.textview_status.get_buffer().set_text("")

        domain_input = self.entry_domain.get_text()
        is_valid, sanitized_domain, error_msg = self._validate_domain_input(domain_input)

        if not is_valid:
            print_to_textview(self.textview_status, error_msg)
            self.show_toast(_("Invalid domain format entered."))
            return

        staging_ip, resolved_staging_cname, error_msg = self._perform_staging_ip_lookup(sanitized_domain)
        if not staging_ip:
            print_to_textview(self.textview_status, error_msg) # error_msg might already contain staging_cname if available
            self.show_toast(error_msg)
            return

        if resolved_staging_cname:
            status_msg_ip = _("Found staging IP {ip} for Akamai Staging domain {staging_cname} (derived from {original_domain}). Attempting to add to hosts file...").format(
                ip=staging_ip, staging_cname=resolved_staging_cname, original_domain=sanitized_domain
            )
        else:
            status_msg_ip = _("Found staging IP {ip} for {original_domain}. Attempting to add to hosts file...").format(
                ip=staging_ip, original_domain=sanitized_domain
            )
        print_to_textview(self.textview_status, status_msg_ip)

        try:
            self._update_hosts_and_ui(staging_ip, sanitized_domain)
        except Exception as e_generic:
            err_msg = _("Failed to process staging request for {domain}: {error}").format(domain=sanitized_domain, error=e_generic)
            logger.error(err_msg, exc_info=True)
            print_to_textview(self.textview_status, err_msg)
            self.show_toast(_("Failed to process staging request."))


    def on_delete_button_clicked(self, _button: Gtk.Button):
        """
        Handles the "Delete" button click event for removing a selected host entry.

        If an entry is selected in the `column_view_entries`, it displays a
        confirmation dialog. If confirmed, the entry is removed from the hosts file
        and the UI is updated.

        Args:
            _button: The Gtk.Button that emitted the signal.
        """
        logger.debug("Entering on_delete_button_clicked")
        selected_item = self.selection_model.get_selected_item()
        if not selected_item:
            self.show_toast(_("No entry selected for deletion."))
            print_to_textview(self.textview_status, _("No entry selected for deletion."))
            return

        self._item_to_delete = selected_item
        entry_display = f"{selected_item.ip} {selected_item.hostname}"

        dialog = Adw.MessageDialog.new(
            self.get_root(),
            _("Confirm Deletion"),
            _("Are you sure you want to delete the selected entry:\n'{entry}'?").format(entry=entry_display),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_confirmation_response)
        dialog.present()

    def _on_delete_confirmation_response(self, dialog: Adw.MessageDialog, response_id: str):
        """
        Handles the response from the delete confirmation dialog.

        If the user confirms deletion ("delete" response), it proceeds to remove the
        host entry using `HostsFileEdit.remove_hosts_entry`. Updates the UI
        (status view, toast, and hosts list) based on the outcome.

        Args:
            dialog: The Adw.MessageDialog that emitted the signal.
            response_id: The ID of the response (e.g., "delete", "cancel").
        """
        if response_id == "delete":
            self.textview_status.get_buffer().set_text("")
            logger.info("Deletion confirmed by user.")
            selected_item = getattr(self, '_item_to_delete', None)
            if not selected_item:
                logger.error("No item was identified for deletion after confirmation dialog.")
                err_msg_no_item = _("Error: No item was identified for deletion.")
                print_to_textview(self.textview_status, err_msg_no_item)
                self.show_toast(_("Error: No item identified for deletion."))
                return

            entry_to_remove = f"{selected_item.ip} {selected_item.hostname}"
            logger.debug("Proceeding with deletion of entry: %s", entry_to_remove)

            status, message_hosts = self.hosts_editor.remove_hosts_entry(entry_to_remove)
            logger.debug("remove_hosts_entry result: Status=%s, Message=%s", status, message_hosts)
            print_to_textview(self.textview_status, message_hosts)

            toast_message = self._get_toast_message_for_delete_status(status, entry_to_remove)

            if status == Status.SUCCESS:
                self.populate_store(self.store) # This will call _update_hosts_view_visibility

            self.show_toast(toast_message)
        else:
            self.textview_status.get_buffer().set_text("")
            logger.info("Deletion cancelled by user.")
            print_to_textview(self.textview_status, _("Deletion cancelled."))
            self.show_toast(_("Deletion cancelled."))

        if hasattr(self, '_item_to_delete'):
            del self._item_to_delete

    def _get_toast_message_for_delete_status(self, status: Status, entry_to_remove: str) -> str:
        """
        Generates a user-friendly toast message for a delete operation outcome.

        Args:
            status: The `Status` enum member representing the outcome.
            entry_to_remove: The string representation of the entry that was
                             attempted to be removed (e.g., "IP_ADDRESS HOSTNAME").

        Returns:
            A localized string suitable for displaying in a toast notification.
        """
        toast_message = ""
        match status:
            case Status.SUCCESS:
                toast_message = _("Host '{entry}' removed.").format(entry=entry_to_remove)
            case Status.ERROR_NOT_FOUND | Status.ALREADY_EXISTS: # ALREADY_EXISTS here means "was already not there"
                toast_message = _("Host '{entry}' not found.").format(entry=entry_to_remove)
            case Status.USER_CANCELLED:
                toast_message = _("Operation cancelled by user.")
            case Status.ERROR_PERMISSION:
                toast_message = _("Permission error during removal.")
            case Status.ERROR_IO:
                toast_message = _("File I/O error during removal.")
            case Status.ERROR_UNSUPPORTED_FLATPAK:
                toast_message = _("Feature unavailable in Flatpak.")
            case _: # Covers ERROR_INTERNAL or any other unexpected status
                toast_message = _("Failed to remove '{entry}'.").format(entry=entry_to_remove)
        return toast_message

    def _get_toast_message_for_edit_remove_status(self, status: Status, old_entry_str: str) -> str:
        """
        Generates a toast message for the removal part of an edit operation.

        This is used when an existing entry is being replaced (edited), and this function
        specifically provides feedback on the attempt to remove the old version of the entry.

        Args:
            status: The `Status` enum member of the removal attempt.
            old_entry_str: The string representation of the old entry being removed.

        Returns:
            A localized string for toast notification.
        """
        toast_msg = ""
        match status:
            case Status.USER_CANCELLED: toast_msg = _("Removal of old entry '{entry}' cancelled by user.").format(entry=old_entry_str)
            case Status.ERROR_PERMISSION: toast_msg = _("Permission error removing old entry '{entry}'.").format(entry=old_entry_str)
            case Status.ERROR_IO: toast_msg = _("I/O error removing old entry '{entry}'.").format(entry=old_entry_str)
            case Status.ERROR_UNSUPPORTED_FLATPAK: toast_msg = _("Feature unavailable in Flatpak. Cannot remove old entry '{entry}'.").format(entry=old_entry_str)
            case _: toast_msg = _("Failed to remove old entry '{entry}'. Edit aborted.").format(entry=old_entry_str)
        return toast_msg

    def _get_toast_message_for_edit_add_status(self, status: Status, new_ip: str, new_hostname: str) -> str:
        """
        Generates a toast message for the addition part of an edit operation.

        This is used when an existing entry is being replaced (edited), and this function
        provides feedback on the attempt to add the new version of the entry.

        Args:
            status: The `Status` enum member of the addition attempt.
            new_ip: The new IP address being added.
            new_hostname: The new hostname being added.

        Returns:
            A localized string for toast notification.
        """
        final_toast_msg = ""
        match status:
            case Status.SUCCESS:
                final_toast_msg = _("Host entry updated to '{ip} {hostname}'.").format(ip=new_ip, hostname=new_hostname)
            case Status.ALREADY_EXISTS:
                final_toast_msg = _("Host entry '{ip} {hostname}' already configured.").format(ip=new_ip, hostname=new_hostname)
            case Status.USER_CANCELLED: final_toast_msg = _("Save operation cancelled by user.")
            case Status.ERROR_PERMISSION: final_toast_msg = _("Permission error saving changes.")
            case Status.ERROR_IO: final_toast_msg = _("I/O error saving changes.")
            case Status.ERROR_UNSUPPORTED_FLATPAK: final_toast_msg = _("Feature unavailable in Flatpak.")
            case _: final_toast_msg = _("Failed to save changes for '{hostname}'.").format(hostname=new_hostname)
        return final_toast_msg

    def on_edit_host_button_clicked(self, _button: Gtk.Button):
        """
        Handles the "Edit" button click event for modifying a selected host entry.

        If an entry is selected, it opens a dialog (`Adw.MessageDialog`) pre-filled
        with the selected entry's IP and hostname, allowing the user to modify them.

        Args:
            _button: The Gtk.Button that emitted the signal.
        """
        logger.debug("Entering on_edit_host_button_clicked")
        selected_item = self.selection_model.get_selected_item()
        if not selected_item:
            self.show_toast(_("No entry selected to edit."))
            print_to_textview(self.textview_status, _("No entry selected to edit."))
            return

        logger.debug("Editing entry: IP=%s, Hostname=%s", selected_item.ip, selected_item.hostname)

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Edit Host Entry"),
            body=_("Modify the IP address and/or hostname.")
        )

        self.edit_ip_entry_row = Adw.EntryRow(title=_("IP Address"))
        self.edit_ip_entry_row.set_text(selected_item.ip)

        self.edit_hostname_entry_row = Adw.EntryRow(title=_("Hostname"))
        self.edit_hostname_entry_row.set_text(selected_item.hostname)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content_box.append(self.edit_ip_entry_row)
        content_box.append(self.edit_hostname_entry_row)

        dialog.set_extra_child(content_box)

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("save", _("Save Changes"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        dialog.connect("response", self._on_edit_dialog_response, selected_item)
        dialog.present()

    def _handle_save_edit(self, original_item: DataObject, new_ip: str, new_hostname: str) -> None:
        """
        Handles the core logic for saving an edited host entry.

        This involves:
        1. Removing the `original_item` from the hosts file.
        2. If removal is successful (or if the item was already not found),
           adding the new entry (`new_ip`, `new_hostname`) to the hosts file.
        UI updates (status view, toast, list store) are performed based on outcomes.

        Args:
            original_item: The DataObject representing the entry before edits.
            new_ip: The new IP address string.
            new_hostname: The new hostname string.
        """
        logger.info(
            "Attempting to change '%s %s' to '%s %s'",
            original_item.ip, original_item.hostname, new_ip, new_hostname
        )
        print_to_textview(
            self.textview_status,
            _("Attempting to change '{old_ip} {old_hostname}' to '{new_ip} {new_hostname}'...").format(
                old_ip=original_item.ip, old_hostname=original_item.hostname,
                new_ip=new_ip, new_hostname=new_hostname
            )
        )

        old_entry_str = f"{original_item.ip} {original_item.hostname}"
        print_to_textview(self.textview_status, _("Removing old entry: {entry}...").format(entry=old_entry_str))
        remove_status, remove_message_text = self.hosts_editor.remove_hosts_entry(old_entry_str)
        logger.debug("remove_hosts_entry (for edit) result: Status=%s, Message=%s", remove_status, remove_message_text)
        print_to_textview(self.textview_status, remove_message_text)

        if remove_status not in [Status.SUCCESS, Status.ERROR_NOT_FOUND, Status.ALREADY_EXISTS]:
            # ERROR_NOT_FOUND and ALREADY_EXISTS (meaning it wasn't there to be removed) are acceptable for the first step.
            print_to_textview(self.textview_status, _("Failed to remove old entry '{entry}'. Edit operation aborted.").format(entry=old_entry_str))
            toast_msg = self._get_toast_message_for_edit_remove_status(remove_status, old_entry_str)
            self.show_toast(toast_msg)
            return

        print_to_textview(self.textview_status, _("Adding new/updated entry: {ip} {hostname}...").format(ip=new_ip, hostname=new_hostname))
        add_status, add_message_text = self.hosts_editor.update_hosts_file_content(new_ip, new_hostname, delete=False)
        logger.debug("update_hosts_file_content (for edit) result: Status=%s, Message=%s", add_status, add_message_text)
        print_to_textview(self.textview_status, add_message_text)

        final_toast_msg = self._get_toast_message_for_edit_add_status(add_status, new_ip, new_hostname)
        self.show_toast(final_toast_msg)

        if add_status == Status.SUCCESS:
            self.populate_store(self.store) # This will call _update_hosts_view_visibility

    def _on_edit_dialog_response(self, dialog: Adw.MessageDialog, response_id: str, original_item: DataObject):
        """
        Handles the response from the edit host entry dialog.

        If the "save" response is received, it retrieves the new IP and hostname,
        validates them (non-empty, actual change), and then calls `_handle_save_edit`
        to apply the changes. If "cancel" is received, it shows a cancellation message.
        Cleans up dialog-specific properties afterwards.

        Args:
            dialog: The Adw.MessageDialog that emitted the signal.
            response_id: The ID of the response (e.g., "save", "cancel").
            original_item: The DataObject representing the item being edited.
        """
        if response_id == "save":
            self.textview_status.get_buffer().set_text("")
            new_ip = self.edit_ip_entry_row.get_text().strip()
            new_hostname = self.edit_hostname_entry_row.get_text().strip()

            if not (new_ip and new_hostname):
                err_msg_empty = _("Error: IP address and hostname cannot be empty.")
                print_to_textview(self.textview_status, err_msg_empty)
                self.show_toast(_("IP and hostname cannot be empty."))
            elif original_item.ip == new_ip and original_item.hostname == new_hostname:
                no_change_msg = _("No changes detected.")
                print_to_textview(self.textview_status, no_change_msg)
                self.show_toast(no_change_msg)
            else:
                self._handle_save_edit(original_item, new_ip, new_hostname)

        elif response_id == "cancel":
            self.textview_status.get_buffer().set_text("")
            cancel_msg = _("Edit operation cancelled by user.")
            print_to_textview(self.textview_status, cancel_msg)
            self.show_toast(_("Edit operation cancelled."))

        dialog.close()
        if hasattr(self, 'edit_ip_entry_row'):
            del self.edit_ip_entry_row
        if hasattr(self, 'edit_hostname_entry_row'):
            del self.edit_hostname_entry_row

    def show_toast(self, message: str, timeout: int = 3):
        """
        Displays a toast notification at the bottom of the window.

        The message is automatically shortened with an ellipsis if it exceeds
        a certain length to fit neatly in the toast.

        Args:
            message: The message string to display in the toast.
            timeout: The duration (in seconds) for which the toast should be visible.
                     Defaults to 3 seconds.
        """
        logger.info("Displaying toast: '%s' (timeout: %ss)", message, timeout)
        if self.toast_overlay:
            display_message = str(message) if message is not None else "An unspecified event occurred."

            # Heuristic to shorten very long messages for toast
            if len(display_message) > 100:  # Max length for toast display
                shortened = display_message[:100]
                last_space = shortened.rfind(' ')
                last_period = shortened.rfind('.')
                last_comma = shortened.rfind(',')
                # Try to cut at a natural break point if one is found reasonably far in
                cut_off_point = max(last_space, last_period, last_comma)
                if cut_off_point > 50: # Ensure we don't cut too early
                    display_message = shortened[:cut_off_point] + "..."
                else:  # Default to hard truncation if no suitable break point
                    display_message = shortened[:97] + "..."

            toast = Adw.Toast(title=display_message, timeout=timeout)
            toast.connect("dismissed", lambda t, *args: logger.info("Toast '%s' dismissed.", t.get_title())) # pylint: disable=unused-argument
            self.toast_overlay.add_toast(toast)
        else:
            logger.warning("ToastOverlay not available, cannot show toast.")
