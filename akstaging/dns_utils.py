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

from akstaging.aklib import AkamaiLib

class DNSUtils:

    CNAME_SUFFIX = "edgekey.net"


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
                        break
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
            Exception: If there is an error resolving the CNAME.
        """
        resolver = self.configure_dns_resolver()
        dns_server_ip = (
            resolver.nameservers[0] if resolver.nameservers else "Default system DNS"
        )
        AkamaiLib.print_to_textview(self,
                                    status_label,
                                    message="Using DNS server {dns_server_ip} to get the records.")

        try:
            answers = resolver.resolve(domain, "CNAME")
            cname = answers[0].target.to_text().strip(".")
            if not cname.endswith(self.CNAME_SUFFIX):
                raise ValueError(
                    f"Invalid CNAME for {domain}. Must end with {self.CNAME_SUFFIX}"
                )
            AkamaiLib.print_to_textview(self,
                                        status_label,
                                        message="Retrieved CNAME {cname} when looking up {domain}")
            return cname
        except (
            dns.resolver.NoNameservers,
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.exception.DNSException,
        ) as e:
            raise dns.exception.DNSException(f"Error resolving CNAME for {domain}. Exception: {e}") from e

    def get_akamai_staging_ip(self, sanitized_domain, status_label):
        """
        Retrieves the Akamai staging IP for the given domain.

        Args:
            sanitized_domain (str): The sanitized domain.
            output_textview: The textview widget to print messages to.

        Returns:
            str: The Akamai staging IP.

        Raises:
            Exception: If there is an error getting the staging IP.
        """
        try:
            # Correct the reference to get_akamai_cname
            cname = self.get_akamai_cname(sanitized_domain, status_label)
            modified_cname = f"{cname[:-4]}-staging.net"
            staging_ip = self.resolve_ip_address(modified_cname)
            message = f"Obtained the Akamai staging IP {staging_ip} when looking up {modified_cname}"
            AkamaiLib.print_to_textview(self, status_label, message)
            return staging_ip
        except (
            dns.resolver.NoNameservers,
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.exception.DNSException,
        ) as e:
            raise type(e)(f"Error getting staging IP for {sanitized_domain} -> {e}") from e


    def resolve_ip_address(self, hostname):
        """
        Resolves the IP address for the given hostname.

        Args:
            hostname (str): The hostname to resolve.

        Returns:
            str: The resolved IP address.

        Raises:
            Exception: If there is an error resolving the IP address.
        """
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror as e:
            raise socket.gaierror(f"Error resolving IP address for {hostname}: {e}") from e

