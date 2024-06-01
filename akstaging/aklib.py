# aklib.py
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
from gi.repository import Gtk

class AkamaiLib:
    """
    A class that provides methods for interacting with DNS to obtain the Akamai Staging IP
    for a given domain and to spoof the /etc/hosts file to direct the host computer to the Akamai Staging network.
    """

    def sanitize_domain(self, domain, status_label):
        """
        Sanitizes the given domain by removing URL schemes and any paths.

        Args:
            domain (str): The domain to be sanitized.
            status_label: The textview widget to print messages to.

        Returns:
            str: The sanitized domain.
        """
        # Remove URL schemes and any paths
        sanitized_domain = domain.replace("http://", "").replace("https://", "").split("/")[0]

        # Print messages related to domain sanitization
        self.print_to_textview(status_label, f"Original domain {domain} modified to {sanitized_domain}")

        return sanitized_domain

    def print_to_textview(self, widget, message):
        """
        Prints a message to the specified widget.

        Args:
            widget: The widget to print the message to.
            message (str): The message to be printed.

        Raises:
            ValueError: If the widget type is not supported.
        """
        if isinstance(widget, Gtk.TextView):
            buffer = widget.get_buffer()
            end_iter = buffer.get_end_iter()
            buffer.insert(end_iter, message + "\n")
        elif isinstance(widget, Gtk.Label):
            widget.set_text(message)
        else:
            raise ValueError(f"Unsupported widget type: {type(widget)}")

    def update_hosts_file(self, domain, ip_address):
        """
        Updates the /etc/hosts file to map the given domain to the specified IP address.

        Args:
            domain (str): The domain to be mapped.
            ip_address (str): The IP address to map the domain to.

        Raises:
            IOError: If there is an error accessing or modifying the /etc/hosts file.
        """
        hosts_line = f"{ip_address} {domain}\n"
        try:
            with open("/etc/hosts", "a", encoding="utf-8") as hosts_file:
                hosts_file.write(hosts_line)
        except IOError as e:
            raise IOError(f"Error updating /etc/hosts file: {e}") from e

    def remove_from_hosts_file(self, domain):
        """
        Removes the given domain entry from the /etc/hosts file.

        Args:
            domain (str): The domain to be removed.

        Raises:
            IOError: If there is an error accessing or modifying the /etc/hosts file.
        """
        try:
            with open("/etc/hosts", "r", encoding="utf-8") as hosts_file:
                lines = hosts_file.readlines()

            with open("/etc/hosts", "w", encoding="utf-8") as hosts_file:
                for line in lines:
                    if domain not in line:
                        hosts_file.write(line)
        except IOError as e:
            raise IOError(f"Error modifying /etc/hosts file: {e}") from e
