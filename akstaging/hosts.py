# hosts.py
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
import sys
from akstaging.aklib import AkamaiLib


class HostsFileEdit:
    HOSTS_FILE = "/etc/hosts"

    def remove_hosts_entry(self, entry):
        """
        Removes the specified entry from the /etc/hosts file.

        Args:
            entry (str): The entry to be removed.

        Returns:
            str: A message indicating the success of the operation.

        Raises:
            FileNotFoundError: If the /etc/hosts file is not found.
            Exception: If there is an error removing the entry.
        """
        try:
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as hosts_file:
                lines = hosts_file.readlines()

            lines = [line for line in lines if entry not in line]

            with open(self.HOSTS_FILE, "w", encoding="utf-8") as hosts_file:
                hosts_file.writelines(lines)

            return f"Removed /etc/hosts entry for: {entry}"
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Error reading {self.HOSTS_FILE}: {e}") from e
        except IOError as e:
            raise IOError(f"Error removing /etc/hosts entry: {e}") from e

    def on_delete_hosts_entry(self, entry):
        """
        Removes the specified entry from the /etc/hosts file.

        Args:
            entry (str): The entry to be removed.

        Returns:
            str: A message indicating the success of the operation.

        Raises:
            FileNotFoundError: If the /etc/hosts file is not found.
            Exception: If there is an error removing the entry.
        """
        try:
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as hosts_file:
                lines = hosts_file.readlines()

            lines = [line for line in lines if entry not in line]

            with open(self.HOSTS_FILE, "w", encoding="utf-8") as hosts_file:
                hosts_file.writelines(lines)

            return f"Removed /etc/hosts entry for: {entry}"
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Error reading {self.HOSTS_FILE}: {e}") from e
        except IOError as e:
            raise IOError(f"Error removing /etc/hosts entry: {e}") from e

    def update_hosts_file_content(self,
                                  staging_ip,
                                  sanitized_domain,
                                  delete,
                                  status_label):
        """
        Updates the content of the /etc/hosts file.

        Args:
            staging_ip (str): The staging IP to be added or deleted.
            sanitized_domain (str): The sanitized domain.
            delete (bool): True to delete the entry, False to add the entry.
            status_label: The textview widget to print messages to.
        """
        existing_ip = self.get_existing_ip_for_domain(sanitized_domain)

        # Check if the obtained IP is different from the existing IP
        if existing_ip != staging_ip:
            try:
                with open(
                    self.HOSTS_FILE, "a" if not delete else "r", encoding="utf-8"
                ) as hosts_file:
                    if delete:
                        lines = hosts_file.readlines()
                        lines = [line for line in lines if sanitized_domain not in line]
                        hosts_file.seek(0)
                        hosts_file.writelines(lines)
                        hosts_file.truncate()
                    else:
                        hosts_file.write(f"{staging_ip} {sanitized_domain}\n")

                message = f"{'Deleted' if delete else 'Added'} {sanitized_domain} {staging_ip} to /etc/hosts"
                AkamaiLib.print_to_textview(self, status_label, message)
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"Error reading/writing {self.HOSTS_FILE}: {e}"
                ) from e
        else:
            message = "The obtained IP is the same as the existing IP for {sanitized_domain}. Not updating."
            AkamaiLib.print_to_textview(self, status_label, message)

    def get_existing_ip_for_domain(self, sanitized_domain):
        """
        Retrieves the existing IP address for the given domain from the /etc/hosts file.

        Args:
            sanitized_domain (str): The sanitized domain.

        Returns:
            str: The existing IP address if found, otherwise None.
        """
        try:
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as hosts_file:
                for line in hosts_file:
                    line_parts = line.split()
                    if len(line_parts) >= 2:
                        ip, hostname = line_parts[0], " ".join(line_parts[1:])
                        if hostname == sanitized_domain:
                            return ip
        except FileNotFoundError as e:
            print(f"Error reading {self.HOSTS_FILE}: {e}")
            sys.exit(1)
        return None

