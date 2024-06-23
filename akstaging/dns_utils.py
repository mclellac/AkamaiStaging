import socket
import dns.exception
import dns.resolver

from akstaging.aklib import AkamaiLib as akl
from gi.repository import Gtk

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

    def get_akamai_cname(self, domain, status_textview):
        """
        Retrieves the CNAME record for the given domain.

        Args:
            domain (str): The domain to retrieve the CNAME for.
            status_textview: The textview widget to print messages to.

        Returns:
            str: The CNAME record.

        Raises:
            ValueError: If the CNAME does not match Akamai's expected suffixes.
            dns.exception.DNSException: If there is an error resolving the CNAME.
        """
        resolver = self.configure_dns_resolver()
        dns_server_ip = resolver.nameservers[0] if resolver.nameservers else "Default system DNS"
        akl.print_to_textview(status_textview, f"Using DNS server {dns_server_ip} for record retrieval.")

        try:
            answers = resolver.resolve(domain, "CNAME")
            cname = answers[0].target.to_text().strip(".")
            if not any(cname.endswith(suffix) for suffix in self.CNAME_SUFFIXES):
                raise ValueError(f"Invalid CNAME for {domain}. Must end with one of {self.CNAME_SUFFIXES}")
            akl.print_to_textview(status_textview, f"Found {domain} CNAME'd to {cname}")
            return cname
        except dns.resolver.NoAnswer:
            akl.print_to_textview(status_textview, f"The DNS response does not contain a CNAME record for {domain}.")
            raise dns.exception.DNSException(f"The DNS response does not contain a CNAME record for {domain}.")
        except (dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.exception.DNSException) as e:
            akl.print_to_textview(status_textview, f"Error resolving CNAME for {domain}. Exception: {e}")
            raise dns.exception.DNSException(f"Error resolving CNAME for {domain}. Exception: {e}") from e

    def get_akamai_staging_ip(self, sanitized_domain, status_textview):
        """
        Retrieves the Akamai staging IP for the given domain.

        Args:
            sanitized_domain (str): The sanitized domain.
            status_textview: The textview widget to print messages to.

        Returns:
            str: The Akamai staging IP.

        Raises:
            dns.exception.DNSException: If there is an error getting the staging IP.
        """
        try:
            cname = self.get_akamai_cname(sanitized_domain, status_textview)
            modified_cname = f"{cname[:-4]}-staging.net"
            staging_ip = self.resolve_ip_address(modified_cname)
            akl.print_to_textview(status_textview, f"Acquired staging IP {staging_ip} for {modified_cname}")
            return staging_ip
        except (dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException, ValueError) as e:
            akl.print_to_textview(status_textview, f"Error getting staging IP for {sanitized_domain} -> {e}")
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

