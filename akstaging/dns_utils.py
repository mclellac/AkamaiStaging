# dns_utils.py
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
import socket
import dns.exception
import dns.resolver
from gi.repository import Gtk

class AkamaiLib:
    """
    A class that provides methods for interacting with DNS with the intention
    of obtaining the Akamai Staging IP for a given domain and IP spoofing the
    /etc/hosts file to direct the host computer to the Akamai Staging network.
    """

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


class DNSUtils:

    CNAME_SUFFIXES = ["edgesuite.net", "edgekey.net"]

    def configure_dns_resolver(self, dns_server=None):
        """
        Configures and returns a DNS resolver.

        Args:
            dns_server (str, optional): The DNS server to be used. Defaults to None.

        Returns:
            dns.resolver.Resolver: The configured DNS resolver.
        """
        resolver = dns.resolver.Resolver(configure=False)
        if dns_server:
            resolver.nameservers = [dns_server]
        else:
            self.configure_default_dns(resolver)
        return resolver

    def configure_default_dns(self, resolver):
        """
        Configures the default DNS server for the resolver.

        Args:
            resolver (dns.resolver.Resolver): The resolver to be configured.

        Raises:
            FileNotFoundError: If the /etc/resolv.conf file is not found.
        """
        try:
            with open("/etc/resolv.conf", "r", encoding="utf-8") as resolv_conf:
                for line in resolv_conf:
                    if line.startswith("nameserver"):
                        resolver.nameservers.append(line.split()[1])
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Error reading /etc/resolv.conf: {e}") from e

    def get_akamai_cname(self, domain, status_label):
        """
        Retrieves the CNAME record for the given domain.

        Args:
            domain (str): The domain to retrieve the CNAME for.
            status_label: The textview widget to print messages to.

        Returns:
            str: The CNAME record.

        Raises:
            ValueError: If the CNAME does not match Akamai's expected suffixes.
            dns.exception.DNSException: If there is an error resolving the CNAME.
        """
        resolver = self.configure_dns_resolver()
        dns_server_ip = resolver.nameservers[0] if resolver.nameservers else "Default system DNS"
        AkamaiLib().print_to_textview(status_label, f"Using DNS server {dns_server_ip} to get the records.")

        try:
            answers = resolver.resolve(domain, "CNAME")
            cname = answers[0].target.to_text().strip(".")
            if not any(cname.endswith(suffix) for suffix in self.CNAME_SUFFIXES):
                raise ValueError(f"Invalid CNAME for {domain}. Must end with one of {self.CNAME_SUFFIXES}")
            AkamaiLib().print_to_textview(status_label, f"Retrieved CNAME {cname} when looking up {domain}")
            return cname
        except dns.resolver.NoAnswer:
            AkamaiLib().print_to_textview(status_label, f"The DNS response does not contain a CNAME record for {domain}.")
            raise dns.exception.DNSException(f"The DNS response does not contain a CNAME record for {domain}.")
        except (dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.exception.DNSException) as e:
            AkamaiLib().print_to_textview(status_label, f"Error resolving CNAME for {domain}. Exception: {e}")
            raise dns.exception.DNSException(f"Error resolving CNAME for {domain}. Exception: {e}") from e

    def get_akamai_staging_ip(self, sanitized_domain, status_label):
        """
        Retrieves the Akamai staging IP for the given domain.

        Args:
            sanitized_domain (str): The sanitized domain.
            status_label: The textview widget to print messages to.

        Returns:
            str: The Akamai staging IP.

        Raises:
            dns.exception.DNSException: If there is an error getting the staging IP.
        """
        try:
            cname = self.get_akamai_cname(sanitized_domain, status_label)
            modified_cname = f"{cname[:-4]}-staging.net"
            staging_ip = self.resolve_ip_address(modified_cname)
            AkamaiLib().print_to_textview(status_label, f"Obtained the Akamai staging IP {staging_ip} when looking up {modified_cname}")
            return staging_ip
        except (dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException, ValueError) as e:
            AkamaiLib().print_to_textview(status_label, f"Error getting staging IP for {sanitized_domain} -> {e}")
            raise dns.exception.DNSException(f"Error getting staging IP for {sanitized_domain} -> {e}") from e

    def resolve_ip_address(self, hostname):
        """
        Resolves the IP address for the given hostname.

        Args:
            hostname (str): The hostname to resolve.

        Returns:
            str: The resolved IP address.

        Raises:
            socket.gaierror: If there is an error resolving the IP address.
        """
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror as e:
            raise socket.gaierror(f"Error resolving IP address for {hostname}: {e}") from e

