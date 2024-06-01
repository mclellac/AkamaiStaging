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
    A class that provides methods for interacting with DNS with the intention
    obtaining the the Akamai Staging IP for a given domain and IP spoofing the
    /etc/hosts file to direct the host computer to the Akamai Staging network.
    """

    DOMAIN_SUFFIX = ".ca"

    def is_valid_domain(self, domain, status_label):
        """
        Checks if the given domain is a valid domain.

        Args:
            domain (str): The domain to be checked.
            status_label: The textview widget to print messages to.

        Returns:
            str: The sanitized domain if it is valid, otherwise None.
        """
        # Check the domain and remove "http://" or "https:// or any paths"
        domain = domain.replace("http://", "").replace("https://", "")
        domain_parts = domain.split("/")
        sanitized_domain = domain_parts[0]

        # Print messages related to domain sanitization
        self.print_to_textview(
            status_label, f"Original domain {domain} modified to {sanitized_domain}"
        )

        # Check if the sanitized domain ends with ".ca"
        return (
            sanitized_domain if sanitized_domain.endswith(self.DOMAIN_SUFFIX) else None
        )

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


