# akstaging/dns_utils.py
import logging
import os
import dns.resolver
from dns.resolver import Resolver, NoNameservers, NXDOMAIN, Timeout as DNSTimeout
import dns.exception
import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio

logger = logging.getLogger(__name__)

SETTINGS_ID = "com.github.mclellac.AkamaiStaging"


class DNSUtils:
    """
    Utility class for performing DNS lookups, specifically for Akamai staging environments.
    """
    # Common Akamai CNAME suffixes used for constructing staging CNAMEs
    CNAME_SUFFIXES = [".edgesuite.net", ".edgekey.net", ".akamaiedge.net"]
    # Domains that identify a CNAME as being part of Akamai infrastructure
    AKAMAI_DOMAINS = ["edgesuite.net", "edgekey.net", "akamaiedge.net", "akamaihd.net"]


    def __init__(self):
        """
        Initializes the DNS utility class.
        The resolver instance will be determined dynamically by methods that use it,
        based on preferences.
        """
        pass

    def get_akamai_cname(self, domain: str, resolver_instance: dns.resolver.Resolver) -> str | None:
        """
        Resolves the CNAME for a given domain, expecting it to point to an Akamai staging domain.

        Args:
            domain: The domain to query.
            resolver_instance: The dns.resolver.Resolver instance to use for the query.

        Returns:
            The Akamai staging CNAME if found, otherwise None.
            Raises dns.exception.DNSException for various DNS errors.
        """
        try:
            answers = resolver_instance.resolve(domain, "CNAME")
            if answers:
                cname_target = answers[0].target.to_text(omit_final_dot=True)

                is_akamai_cname = False
                for akamai_domain in self.AKAMAI_DOMAINS:
                    if cname_target.endswith(akamai_domain):
                        is_akamai_cname = True
                        break
                
                if not is_akamai_cname:
                    logger.warning(
                        "Domain %s CNAME %s does not appear to be a recognized Akamai managed domain.",
                        domain, cname_target
                    )
                    raise dns.exception.DNSException(
                        f"CNAME {cname_target} for domain {domain} is not a recognized Akamai domain."
                    )
                
                logger.info("Found Akamai CNAME for %s: %s", domain, cname_target)
                return cname_target
            return None  # Should ideally not be reached if answers exist but are empty; NoAnswer would be raised.
        except dns.resolver.NXDOMAIN:
            logger.error("Domain %s not found (NXDOMAIN).", domain)
            raise
        except dns.resolver.NoAnswer:
            logger.warning("No CNAME record found for %s, but domain exists.", domain)
            raise
        except dns.resolver.NoNameservers:
            logger.error("No nameservers available to resolve %s.", domain)
            raise
        except dns.exception.Timeout:
            logger.error("DNS query timed out for %s.", domain)
            raise
        except dns.resolver.NoResolverConfiguration:
            logger.error("DNS resolver is not configured. Cannot resolve any domains.")
            raise
        except dns.exception.DNSException as e: # Catch-all for other dnspython errors
            logger.error("DNS lookup for %s failed with error: %s", domain, e)
            raise

    def get_akamai_staging_ip(self, domain: str) -> str | None:
        """
        Gets the Akamai staging IP address for a given domain.
        It first resolves the CNAME and then resolves the 'A' record of the CNAME.
        This method now respects custom DNS settings from the preferences file.

        Args:
            domain: The domain to query.

        Returns:
            tuple[str | None, str | None]: A tuple containing the staging IP address (or None if not found)
            and the resolved Akamai staging CNAME (or None if not determined).
            Raises dns.exception.DNSException for various DNS errors.
        """
        settings = Gio.Settings.new(SETTINGS_ID)
        custom_dns_enabled = settings.get_boolean('custom-dns-enabled')
        custom_dns_servers_str = settings.get_string('custom-dns-servers')

        resolver_instance = dns.resolver.get_default_resolver()

        if custom_dns_enabled and custom_dns_servers_str.strip():
            custom_servers = [s.strip() for s in custom_dns_servers_str.split(',') if s.strip()]
            if custom_servers:
                logger.info("Using custom DNS servers: %s", custom_servers)
                custom_resolver = Resolver(configure=False) # Do not configure from /etc/resolv.conf
                custom_resolver.nameservers = custom_servers
                resolver_instance = custom_resolver
            else:
                logger.warning("Custom DNS enabled but no servers configured or list is empty. Using system DNS.")
        else:
            logger.info("Using system DNS servers.")

        try:
            base_cname = self.get_akamai_cname(domain, resolver_instance)
            if not base_cname:
                logger.warning("Could not retrieve base CNAME for %s. Cannot determine staging IP.", domain)
                return None, None

            # Construct the staging CNAME.
            # Example: If base_cname is "example.com.edgesuite.net",
            # and "edgesuite.net" is an ak_domain,
            # customer_part becomes "example.com."
            # service_name becomes "edgesuite", tld becomes "net"
            # transformed_ak_domain becomes "edgesuite-staging.net"
            # staging_cname_to_resolve becomes "example.com.edgesuite-staging.net"
            staging_cname_to_resolve = None
            for ak_domain in self.AKAMAI_DOMAINS:
                if base_cname.endswith(ak_domain):
                    parts = ak_domain.split('.', 1)
                    if len(parts) == 2:
                        service_name, tld = parts
                        transformed_ak_domain = f"{service_name}-staging.{tld}"

                        customer_part = base_cname[:-len(ak_domain)]

                        # Defensively ensure customer_part ends with a dot if it's not empty
                        # and doesn't already end with one.
                        if customer_part and not customer_part.endswith('.'):
                            customer_part += '.'
                        # Handle a very unlikely edge case of customer_part becoming just ".."
                        # if base_cname was something like ".akamaiedge.net" and we stripped ".akamaiedge.net"
                        # This is more of a theoretical safeguard.
                        if customer_part == "..":
                             customer_part = "."

                        staging_cname_to_resolve = f"{customer_part}{transformed_ak_domain}"
                        logger.debug(f"Derived customer_part: '{customer_part}', transformed_ak_domain: '{transformed_ak_domain}', for base_cname: '{base_cname}' and ak_domain: '{ak_domain}'") # Added debug log
                        break

            if not staging_cname_to_resolve:
                logger.error(
                    "Base CNAME %s for domain %s does not end with a recognized Akamai domain pattern "
                    "from AKAMAI_DOMAINS or pattern is malformed. Cannot construct staging CNAME.",
                    base_cname, domain
                )
                return None, base_cname # Or None, None if base_cname is not useful here

            logger.info("Constructed staging CNAME for %s: %s", domain, staging_cname_to_resolve)
            
            answers = resolver_instance.resolve(staging_cname_to_resolve, "A")
            if answers:
                staging_ip = answers[0].address
                logger.info(
                    "Found Akamai staging IP for %s (via %s): %s",
                    domain, staging_cname_to_resolve, staging_ip
                )
                return staging_ip, staging_cname_to_resolve
            
            logger.warning("No A records found for staging CNAME %s (derived from %s).", staging_cname_to_resolve, domain)
            return None, staging_cname_to_resolve
        except NXDOMAIN as e: # Keep staging_cname_to_resolve context if available
            logger.error("DNS record not found (NXDOMAIN) for %s or its CNAMEs. Staging CNAME was: %s", domain, staging_cname_to_resolve if 'staging_cname_to_resolve' in locals() else "not determined")
            raise e
        except dns.resolver.NoAnswer as e: # Keep staging_cname_to_resolve context if available
            logger.warning("No A record found (NoAnswer) for %s or its CNAMEs. Staging CNAME was: %s", domain, staging_cname_to_resolve if 'staging_cname_to_resolve' in locals() else "not determined")
            raise e
        except NoNameservers as e:
            logger.error("No nameservers available to resolve %s.", domain)
            raise
        except DNSTimeout as e_timeout:
            logger.error("DNS query timed out for %s.", domain)
            raise e_timeout from None
        except dns.resolver.NoResolverConfiguration as e:
            logger.error("DNS resolver is not configured. Cannot resolve any domains.")
            raise e
        except dns.exception.DNSException as e: # General DNS exception
            logger.error("Staging IP lookup for %s failed: %s. Staging CNAME was: %s", domain, e, staging_cname_to_resolve if 'staging_cname_to_resolve' in locals() else "not determined")
            raise e
