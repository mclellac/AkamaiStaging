# akstaging/hosts.py
import os
import tempfile
import platform
import subprocess
import traceback
import akstaging
from akstaging.config import HELPER_EXECUTABLE_PATH, MACOS_HELPER_EXECUTABLE_PATH
from .status_codes import Status


class HostsFileEdit:
    """
    Manages operations on the system's hosts file (`/etc/hosts`),
    including adding, updating, and removing host entries.
    """

    HOSTS_FILE = "/etc/hosts"
    OSASCRIPT_ERROR_LOG = "/tmp/akamai_staging_osascript_error.log"

    _MODULE_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(akstaging.__file__)))

    def __init__(self, logger_func=None):
        """
        Initializes HostsFileEdit.

        Args:
            logger_func: An optional function to use for logging. If provided,
                         debug messages from this class will be passed to this function.
        """
        self.logger_func = logger_func
        self.is_flatpak = os.path.exists("/.flatpak-info") or "FLATPAK_ID" in os.environ
        if self.is_flatpak:
            self._log_debug("Running in a Flatpak environment.")

        self._log_debug(f"HELPER_EXECUTABLE_PATH='{HELPER_EXECUTABLE_PATH}'")
        self._log_debug(f"MACOS_HELPER_EXECUTABLE_PATH='{MACOS_HELPER_EXECUTABLE_PATH}'")
        self._log_debug(f"HOSTS_FILE path used: '{self.HOSTS_FILE}'")

    def _write_lines_to_hosts_file(self, lines_to_write: list[str]) -> tuple[Status, str]:
        """
        Atomically writes lines to the configured hosts file.

        This method creates a temporary file, writes the given lines to it,
        applies the original hosts file's permissions and ownership (or defaults
        if the file doesn't exist), and then replaces the original hosts file
        with the temporary file.

        Args:
            lines_to_write: A list of strings, where each string is a line
                            to be written to the hosts file.

        Returns:
            A tuple (Status, message):
            - Status: A Status enum member indicating success or the type of error.
            - message: A descriptive message about the operation's outcome.
        """
        temp_file_descriptor, temp_file_path = -1, None
        original_mode, original_uid, original_gid = None, None, None

        try:
            try:
                stat_info = os.stat(self.HOSTS_FILE)
                original_mode = stat_info.st_mode
                original_uid = stat_info.st_uid
                original_gid = stat_info.st_gid
                self._log_debug(
                    f"Original '{self.HOSTS_FILE}' metadata: mode={oct(original_mode)}, uid={original_uid}, gid={original_gid}"
                )
            except FileNotFoundError:
                self._log_debug(
                    f"'{self.HOSTS_FILE}' not found. New file will be created with default root perms (0o644, uid 0, gid 0)."
                )
                original_uid, original_gid = 0, 0  # Default root ownership
                original_mode = 0o644  # Default for /etc/hosts if created new.

            hosts_dir = os.path.dirname(self.HOSTS_FILE)
            temp_file_descriptor, temp_file_path = tempfile.mkstemp(dir=hosts_dir, text=True)

            self._log_debug(
                f"Atomically writing {len(lines_to_write)} lines to '{self.HOSTS_FILE}' via temp file '{temp_file_path}'"
            )

            with os.fdopen(temp_file_descriptor, "w", encoding="utf-8") as tmp_f:
                tmp_f.writelines(lines_to_write)
            temp_file_descriptor = -1  # fdopen took ownership and closed it.

            self._log_debug(
                f"Applying metadata to temp file '{temp_file_path}': mode={oct(original_mode)}, uid={original_uid}, gid={original_gid}"
            )
            try:
                os.chown(temp_file_path, original_uid, original_gid)
                os.chmod(temp_file_path, original_mode)
            except OSError as e_meta:
                self._log_debug(
                    f"CRITICAL: Error applying metadata (chown/chmod) to temp file '{temp_file_path}': {e_meta}. File permissions might be incorrect."
                )
                return (
                    Status.ERROR_IO,
                    f"Failed to set correct permissions/ownership on temp hosts file: {e_meta}",
                )

            os.replace(temp_file_path, self.HOSTS_FILE)
            self._log_debug(
                f"Successfully replaced '{self.HOSTS_FILE}' with temporary file '{temp_file_path}'."
            )
            temp_file_path = None  # Mark as successfully moved.
            return Status.SUCCESS, f"Successfully updated '{self.HOSTS_FILE}'."

        except PermissionError as e_perm:
            self._log_debug(f"PermissionError during atomic write to '{self.HOSTS_FILE}': {e_perm}")
            return (
                Status.ERROR_PERMISSION,
                f"Permission denied during update of '{self.HOSTS_FILE}'.",
            )
        except IOError as e_io:
            self._log_debug(f"IOError during atomic write to '{self.HOSTS_FILE}': {e_io}")
            return Status.ERROR_IO, f"I/O error updating '{self.HOSTS_FILE}': {e_io}"
        except Exception as e_generic:
            self._log_debug(
                f"Unexpected error during atomic write to '{self.HOSTS_FILE}': {e_generic} (Traceback: {traceback.format_exc()})"
            )
            return (
                Status.ERROR_INTERNAL,
                f"Unexpected error updating '{self.HOSTS_FILE}': {e_generic}",
            )
        finally:
            if temp_file_descriptor != -1:
                try:
                    os.close(temp_file_descriptor)
                except OSError as e_close:
                    self._log_debug(f"Error closing temp_file_descriptor: {e_close}")
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    self._log_debug(f"Successfully removed temporary file: {temp_file_path}")
                except OSError as e_cleanup:
                    self._log_debug(f"Error removing temporary file {temp_file_path}: {e_cleanup}")

    def _log_debug(self, message_text: str):
        """
        Internal helper for debug logging. Uses self.logger_func if available.

        Args:
            message_text: The text to log.
        """
        if hasattr(self, "logger_func") and self.logger_func is not None:
            self.logger_func(f"[HostsFileEdit] {message_text}")

    def _parse_hosts_line(
        self, line_content: str
    ) -> tuple[str | None, list[str], list[str], str | None]:
        """
        Parses a single line from a hosts file into its components.

        Args:
            line_content: The raw string content of a single line from the hosts file.

        Returns:
            A tuple containing four elements:
            - ip_address (str | None): The IP address found on the line. None if the line
              is empty, a comment, or does not start with a parsable IP address.
            - original_hostnames (list[str]): A list of hostnames as they originally
              appeared on the line. Empty if no hostnames are found or if ip_address is None.
            - normalized_hostnames (list[str]): A list of hostnames, converted to lowercase.
              Empty if no hostnames are found or if ip_address is None.
            - comment_text (str | None): Any trailing comment text found on the line after
              a '#' character. If the entire line is a comment (starts with '#'),
              this will contain the full line. If the line is empty or cannot be parsed
              into an IP/hostname structure but is not a comment, this might contain
              the original unparsable line content to ensure its preservation.
              None if there's no comment and the line is empty.
        """
        stripped_line = line_content.strip()
        if not stripped_line:
            return None, [], [], None
        if stripped_line.startswith("#"):
            return None, [], [], stripped_line

        line_before_comment = stripped_line.split("#", 1)[0].strip()
        trailing_comment_text = ""
        if "#" in stripped_line:
            trailing_comment_text = stripped_line.split("#", 1)[1]

        if not line_before_comment:
            return None, [], [], stripped_line

        parts = line_before_comment.split()
        if not parts or len(parts) < 2:
            # Treat as unparsable for IP/hostname structure, return it as if it were a comment line to preserve it
            self._log_debug(f"Could not parse line into IP and hostnames: '{line_content.strip()}'")
            return None, [], [], line_content.strip()

        ip_address = parts[0]
        original_hostnames = parts[1:]
        normalized_hostnames = [h.lower() for h in original_hostnames]

        return ip_address, original_hostnames, normalized_hostnames, trailing_comment_text

    def _process_line_for_removal(
        self, line_content: str, ip_to_remove: str, domain_to_remove_lower: str
    ) -> tuple[str | None, bool]:
        """
        Processes a single line from the hosts file for a removal operation.

        It checks if the line contains the specified IP address and domain. If a match
        is found, it modifies the line to remove the domain or marks the entire line
        for removal if it's the only domain associated with the IP on that line.

        Args:
            line_content: The content of the line to process.
            ip_to_remove: The IP address of the host entry to remove.
            domain_to_remove_lower: The lowercase domain name to remove.

        Returns:
            A tuple (new_line_content, entry_removed):
            - new_line_content (str | None): The modified line content. If the entire
              line is to be removed, this is None. If the line is a comment or empty,
              it's returned as is (or a slightly normalized version for unparsable lines).
            - entry_removed (bool): True if the specified IP/domain entry was found
              and removed from this line, False otherwise.
        """
        parsed_ip, parsed_original_hostnames, parsed_normalized_hostnames, parsed_comment_text = (
            self._parse_hosts_line(line_content)
        )

        if parsed_ip is None:  # Comment, empty, or unparsable line
            return (
                parsed_comment_text + "\n"
            ) if parsed_comment_text and not parsed_comment_text.startswith(
                "#"
            ) and parsed_comment_text.strip() else line_content, False

        if parsed_ip == ip_to_remove and domain_to_remove_lower in parsed_normalized_hostnames:
            self._log_debug(
                f"  MATCH FOUND for removal: IP '{parsed_ip}', Domain '{domain_to_remove_lower}' in line: '{line_content.strip()}'"
            )
            remaining_hostnames = [
                parsed_original_hostnames[i]
                for i, norm_host in enumerate(parsed_normalized_hostnames)
                if norm_host != domain_to_remove_lower
            ]
            if remaining_hostnames:
                new_line_parts = [parsed_ip] + remaining_hostnames
                new_line = " ".join(new_line_parts)
                if parsed_comment_text is not None:
                    new_line += (
                        " #" + parsed_comment_text
                        if not parsed_comment_text.startswith("#")
                        else " " + parsed_comment_text
                    )
                self._log_debug(f"    REWRITING LINE (for removal) as: '{new_line.strip()}'")
                return new_line.strip() + "\n", True
            else:  # Domain was the only one on this line for this IP
                self._log_debug(
                    f"    REMOVING ENTIRE LINE (for removal) as it only contained '{domain_to_remove_lower}' for IP '{parsed_ip}'."
                )
                return None, True  # Remove line completely
        else:
            if parsed_ip == ip_to_remove:
                self._log_debug(
                    f" IP '{parsed_ip}' matches but domain '{domain_to_remove_lower}' not found in this line's domains: {parsed_original_hostnames}. Keeping original line."
                )
            return line_content, False  # No change to this line

    def _remove_hosts_entry_direct(self, entry_to_remove: str) -> tuple[Status, str]:
        """
        Directly removes an IP-domain pair from the configured hosts file.

        This method reads the hosts file, identifies the line(s) containing the
        specified IP address and domain, and removes the domain. If the domain is
        the only one associated with an IP on a line, the entire line for that
        IP is removed. It then writes the modified content back to the hosts file.

        This method does NOT handle PermissionError itself; that is managed by
        the calling `_execute_operation` method for privilege escalation.

        Args:
            entry_to_remove: A string containing the IP address and domain to remove,
                             separated by whitespace (e.g., "1.2.3.4 example.com").

        Returns:
            A tuple (Status, message):
            - Status: A Status enum member indicating success, if the entry was not found,
                      or the type of error encountered.
            - message: A descriptive message about the operation's outcome.
        """
        self._log_debug(f"Attempting to remove entry '{entry_to_remove}' from '{self.HOSTS_FILE}'")
        original_lines: list[str] = []

        try:
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as hosts_file:
                original_lines = hosts_file.readlines()
        except FileNotFoundError:
            return Status.ERROR_NOT_FOUND, f"Error reading '{self.HOSTS_FILE}': File not found."
        except PermissionError:
            return Status.ERROR_PERMISSION, f"Permission denied reading '{self.HOSTS_FILE}'."
        except IOError as e:
            return Status.ERROR_IO, f"I/O error reading '{self.HOSTS_FILE}': {e}"
        except Exception as e:  # pylint: disable=broad-except
            return Status.ERROR_INTERNAL, f"Unexpected error reading '{self.HOSTS_FILE}': {e}"

        ip_domain_parts = entry_to_remove.split(maxsplit=1)
        if len(ip_domain_parts) != 2:
            return (
                Status.ERROR_INTERNAL,
                f"Invalid format for entry_to_remove: '{entry_to_remove}'.",
            )
        ip_to_remove, domain_to_remove_original_case = ip_domain_parts
        domain_to_remove_lower = domain_to_remove_original_case.lower()

        lines_to_keep: list[str] = []
        entry_found_and_removed = False
        self._log_debug(
            f"Processing lines to remove IP='{ip_to_remove}' DOMAIN='{domain_to_remove_lower}' (original case: '{domain_to_remove_original_case}')"
        )

        for line_content in original_lines:
            modified_line, was_removed = self._process_line_for_removal(
                line_content, ip_to_remove, domain_to_remove_lower
            )
            if was_removed:
                entry_found_and_removed = True
            if modified_line is not None:
                lines_to_keep.append(modified_line)
            elif not was_removed and modified_line is None:
                lines_to_keep.append(line_content)

        if not entry_found_and_removed:
            status = Status.ALREADY_EXISTS  # Or NOT_FOUND
            message = (
                f"Entry '{entry_to_remove}' not found in '{self.HOSTS_FILE}'. No changes made."
            )
            self._log_debug(
                f"Entry '{entry_to_remove}' not found. No changes needed. Returning {status.name}."
            )
            return status, message

        self._log_debug(
            f"Attempting to write changes for removal of '{entry_to_remove}' using atomic write."
        )
        status, message = self._write_lines_to_hosts_file(lines_to_keep)

        if status == Status.SUCCESS:
            message = f"Successfully removed entry '{entry_to_remove}' from '{self.HOSTS_FILE}'."

        self._log_debug(
            f"_remove_hosts_entry_direct returning: Status={status.name if hasattr(status, 'name') else status}, Message='{message}'"
        )
        return status, message

    def _process_line_for_update(
        self,
        line_content: str,
        staging_ip: str,
        sanitized_domain: str,
        sanitized_domain_lower: str,
        delete_operation: bool,
    ) -> tuple[bool, str | None, bool]:
        """
        Processes a single line for an update or delete operation on a specific domain.

        For an update (add/modify):
        - If the domain is found with the correct IP, ensures casing is updated if necessary.
        - If the domain is found with an incorrect IP, it's removed from that line.
        - The goal is to ensure the domain only appears with the target staging_ip.

        For a delete:
        - If the domain is found on the line, it's removed. If it's the only domain
          for that IP on the line, the entire line is marked for removal.

        Args:
            line_content: The current line from the hosts file.
            staging_ip: The target IP address for the domain (for add/update operations).
            sanitized_domain: The canonical (original case) domain name.
            sanitized_domain_lower: The lowercase version of the domain name for matching.
            delete_operation: True if the domain should be deleted, False for add/update.

        Returns:
            A tuple (line_modified, new_line_content, domain_ip_correct):
            - line_modified (bool): True if the line's content was changed or if the
              line is marked for removal.
            - new_line_content (str | None): The modified line, or None to remove it.
              If not modified, this is the original line_content.
            - domain_ip_correct (bool): For add/update operations, True if the domain
              was found on this line with the correct `staging_ip`. Always False
              for delete operations or if the domain wasn't found with the correct IP.
        """
        parsed_ip, parsed_original_hostnames, parsed_normalized_hostnames, parsed_comment_text = (
            self._parse_hosts_line(line_content)
        )

        if parsed_ip is None:  # Comment, empty, or unparsable line
            original_line_to_keep = (
                line_content
                if (
                    parsed_comment_text is None
                    or parsed_comment_text.startswith("#")
                    or not parsed_comment_text.strip()
                )
                else parsed_comment_text + "\n"
            )
            return False, original_line_to_keep, False

        domain_found_on_this_line = sanitized_domain_lower in parsed_normalized_hostnames
        domain_is_correct_ip_for_update = False

        if not domain_found_on_this_line:
            return False, line_content, False

        self._log_debug(
            f"    Domain '{sanitized_domain_lower}' found on line (IP: '{parsed_ip}'): '{line_content.strip()}'"
        )

        if delete_operation:
            remaining_hostnames = [
                parsed_original_hostnames[i]
                for i, norm_host in enumerate(parsed_normalized_hostnames)
                if norm_host != sanitized_domain_lower
            ]
            if remaining_hostnames:
                new_line_parts = [parsed_ip] + remaining_hostnames
                new_line = " ".join(new_line_parts)
                if parsed_comment_text is not None:
                    new_line += (
                        " #" + parsed_comment_text
                        if not parsed_comment_text.startswith("#")
                        else " " + parsed_comment_text
                    )
                self._log_debug(f"    DELETE: Rewriting line as: '{new_line.strip()}'")
                return True, new_line.strip() + "\n", False
            else:
                self._log_debug(
                    f"    DELETE: Removing entire line as it only contained '{sanitized_domain_lower}' for IP '{parsed_ip}'."
                )
                return True, None, False
        else:  # Add/Update operation
            if parsed_ip == staging_ip:
                domain_is_correct_ip_for_update = True
                self._log_debug(
                    f"    UPDATE: Domain '{sanitized_domain_lower}' found with CORRECT IP '{staging_ip}'."
                )

                current_hostnames_on_line = []
                target_domain_present_original_case = False
                for hn_orig in parsed_original_hostnames:
                    if hn_orig.lower() == sanitized_domain_lower:
                        current_hostnames_on_line.append(sanitized_domain)
                        target_domain_present_original_case = True
                    else:
                        current_hostnames_on_line.append(hn_orig)

                if not target_domain_present_original_case:
                    current_hostnames_on_line.append(sanitized_domain)

                new_line_parts = [parsed_ip] + current_hostnames_on_line
                new_line = " ".join(new_line_parts)
                if parsed_comment_text is not None:
                    new_line += (
                        " #" + parsed_comment_text
                        if not parsed_comment_text.startswith("#")
                        else " " + parsed_comment_text
                    )

                line_changed = new_line.strip() != line_content.strip()
                if line_changed:
                    self._log_debug(
                        f"    UPDATE: Line with correct IP, content updated: '{new_line.strip()}'"
                    )
                return line_changed, new_line.strip() + "\n", domain_is_correct_ip_for_update
            else:
                self._log_debug(
                    f"    UPDATE: Domain '{sanitized_domain_lower}' found with INCORRECT IP '{parsed_ip}'. Will remove from this line."
                )
                remaining_hostnames = [
                    parsed_original_hostnames[i]
                    for i, norm_host in enumerate(parsed_normalized_hostnames)
                    if norm_host != sanitized_domain_lower
                ]
                if remaining_hostnames:
                    new_line_parts = [parsed_ip] + remaining_hostnames
                    new_line = " ".join(new_line_parts)
                    if parsed_comment_text is not None:
                        new_line += (
                            " #" + parsed_comment_text
                            if not parsed_comment_text.startswith("#")
                            else " " + parsed_comment_text
                        )
                    self._log_debug(
                        f"    UPDATE: Rewriting line (incorrect IP for target domain) as: '{new_line.strip()}'"
                    )
                    return True, new_line.strip() + "\n", False
                else:
                    self._log_debug(
                        f"    UPDATE: Removing entire line as it only contained '{sanitized_domain_lower}' with incorrect IP '{parsed_ip}'."
                    )
                    return True, None, False

    def _update_hosts_file_content_direct(
        self, staging_ip: str, sanitized_domain: str, delete: bool
    ) -> tuple[Status, str]:
        """
        Directly updates or removes a domain entry in the configured hosts file.

        This method handles the logic of ensuring a domain is associated with a specific
        IP address (add/update) or that a domain is removed entirely (delete).
        It reads the hosts file, processes each line to make necessary modifications,
        and then writes the changes back. If an add/update operation does not find
        the domain correctly configured, a new line for the entry is appended.

        This method does NOT handle PermissionError itself; that is managed by
        the calling `_execute_operation` method for privilege escalation.

        Args:
            staging_ip: The IP address to associate with the domain (for add/update).
            sanitized_domain: The domain name to update or remove.
            delete: If True, the domain is removed. If False, the domain is added/updated
                    to point to `staging_ip`.

        Returns:
            A tuple (Status, message):
            - Status: A Status enum member indicating success, if the entry already
                      existed as specified, or the type of error encountered.
            - message: A descriptive message about the operation's outcome.
        """
        sanitized_domain_lower = sanitized_domain.lower()
        self._log_debug(
            f"Args: ip='{staging_ip}', domain='{sanitized_domain_lower}' (original: '{sanitized_domain}'), delete={delete}, hosts_file='{self.HOSTS_FILE}'"
        )

        original_lines: list[str] = []
        try:
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as hosts_file:
                original_lines = hosts_file.readlines()
        except FileNotFoundError:
            return Status.ERROR_NOT_FOUND, f"Error reading '{self.HOSTS_FILE}': File not found."
        except PermissionError:
            return Status.ERROR_PERMISSION, f"Permission denied reading '{self.HOSTS_FILE}'."
        except IOError as e:
            return Status.ERROR_IO, f"I/O error reading '{self.HOSTS_FILE}': {e}"
        except Exception as e:  # pylint: disable=broad-except
            return Status.ERROR_INTERNAL, f"Unexpected error reading '{self.HOSTS_FILE}': {e}"

        lines_to_keep: list[str] = []
        made_change_to_file_content = False
        target_entry_correctly_exists = False

        self._log_debug(
            f"Processing {len(original_lines)} lines for domain '{sanitized_domain_lower}' with IP '{staging_ip}' (delete={delete})..."
        )
        for line_content in original_lines:
            line_modified, new_content, domain_ip_correct = self._process_line_for_update(
                line_content, staging_ip, sanitized_domain, sanitized_domain_lower, delete
            )
            if line_modified:
                made_change_to_file_content = True
            if new_content is not None:
                lines_to_keep.append(new_content)
            if domain_ip_correct and not delete:
                target_entry_correctly_exists = True

        self._log_debug(
            f"Line processing complete. made_change_to_file_content: {made_change_to_file_content}, target_entry_correctly_exists: {target_entry_correctly_exists}"
        )

        current_status: Status
        message: str

        if delete:
            if made_change_to_file_content:
                current_status = Status.SUCCESS
                message = (
                    f"Successfully removed entries for {sanitized_domain} from '{self.HOSTS_FILE}'."
                )
            else:
                current_status = Status.ALREADY_EXISTS
                message = f"No entry found for {sanitized_domain} in '{self.HOSTS_FILE}'. No changes made."
        else:  # Add or Update operation
            if not target_entry_correctly_exists:
                self._log_debug(
                    f"UPDATE: Target entry '{staging_ip} {sanitized_domain}' not found with correct IP or was removed. Adding/Re-adding."
                )
                new_entry_line = f"{staging_ip} {sanitized_domain.strip()}\n"
                lines_to_keep.append(new_entry_line)
                made_change_to_file_content = True
                current_status = Status.SUCCESS
                message = f"Updated '{self.HOSTS_FILE}': Set {sanitized_domain} to {staging_ip}."
            elif made_change_to_file_content:
                current_status = Status.SUCCESS
                message = f"Updated '{self.HOSTS_FILE}': Corrected entries for {sanitized_domain} to {staging_ip}."
            else:
                current_status = Status.ALREADY_EXISTS
                message = f"Entry {staging_ip} {sanitized_domain} already correctly configured in '{self.HOSTS_FILE}'."

        self._log_debug(f"Status after logic: {current_status.name}. Message: {message}")

        if made_change_to_file_content:
            self._log_debug("Writing changes to hosts file.")
            write_status, write_message = self._write_lines_to_hosts_file(lines_to_keep)
            if write_status != Status.SUCCESS:
                return write_status, write_message

        return current_status, message

    def _execute_operation(
        self, operation_func: callable, operation_type: str, op_kwargs: dict
    ) -> tuple[Status, str]:
        """
        Executes a host file write operation (update, remove), handling direct execution
        and attempting privilege escalation if a PermissionError occurs.

        Args:
            operation_func: The internal function to call for the direct operation
                            (e.g., `_update_hosts_file_content_direct`).
            operation_type: A string descriptor of the operation (e.g., "update", "remove")
                            used for logging and helper script arguments.
            op_kwargs: A dictionary of keyword arguments to pass to `operation_func`.

        Returns:
            A tuple (Status, message) from the operation_func or the escalation helper.
        """
        status, message = operation_func(**op_kwargs)

        if status == Status.ERROR_PERMISSION:
            self._log_debug(
                f"Direct operation '{operation_type}' failed with PermissionError. Attempting privilege escalation."
            )
            current_os = platform.system()
            if self.is_flatpak and current_os == "Linux":
                self._log_debug(
                    "Flatpak environment on Linux detected. Using flatpak-spawn for escalation."
                )
                return self._run_flatpak_spawn_pkexec(operation_type, **op_kwargs)
            if current_os == "Darwin":
                self._log_debug("macOS detected. Using osascript for escalation.")
                return self._run_macos_elevated(operation_type, **op_kwargs)
            if current_os == "Linux":
                self._log_debug("Linux (non-Flatpak) detected. Using pkexec for escalation.")
                return self._run_linux_elevated(operation_type, **op_kwargs)
            self._log_debug(f"Unsupported OS for privilege escalation: {current_os}")
            return (
                Status.ERROR_INTERNAL,
                f"Permission denied. Automated privilege escalation not supported on this OS ({current_os}).",
            )

        self._log_debug(
            f"Direct operation '{operation_type}' resulted in {status.name if hasattr(status, 'name') else status}. No escalation needed or possible for this status."
        )
        return status, message

    def remove_hosts_entry(self, entry_to_remove: str) -> tuple[Status, str]:
        """
        Removes an IP-domain pair from the system hosts file.

        This is a public method that wraps the internal removal logic, including
        privilege escalation if required.

        Args:
            entry_to_remove: A string in the format "IP_ADDRESS DOMAIN_NAME"
                             (e.g., "1.2.3.4 example.com") to be removed.

        Returns:
            A tuple (Status, message) indicating the outcome of the operation.
        """
        op_kwargs = {"entry_to_remove": entry_to_remove}
        return self._execute_operation(self._remove_hosts_entry_direct, "remove", op_kwargs)

    def update_hosts_file_content(
        self, staging_ip: str, sanitized_domain: str, delete: bool
    ) -> tuple[Status, str]:
        """
        Updates or deletes an entry in the system hosts file for a given domain.

        This is a public method that wraps the internal update/delete logic,
        including privilege escalation if required.

        Args:
            staging_ip: The IP address to set for the domain.
            sanitized_domain: The domain name to update or delete.
            delete: If True, the entry for `sanitized_domain` will be removed.
                    If False, `sanitized_domain` will be mapped to `staging_ip`.

        Returns:
            A tuple (Status, message) indicating the outcome of the operation.
        """
        op_kwargs = {
            "staging_ip": staging_ip,
            "sanitized_domain": sanitized_domain,
            "delete": delete,
        }
        return self._execute_operation(self._update_hosts_file_content_direct, "update", op_kwargs)

    def read_hosts_file_content(self) -> tuple[Status, str | list[str]]:
        """
        Reads the content of the system hosts file.

        It first attempts a direct read. If this fails due to a PermissionError,
        it then attempts to read the file using privileged helper scripts
        appropriate for the operating system.

        Returns:
            A tuple (Status, content_or_error_message):
            - Status: A Status enum member. SUCCESS if read is successful.
            - content_or_error_message (list[str] | str):
                - If successful (Status.SUCCESS): A list of strings, where each
                  string is a line from the hosts file (newlines stripped).
                - If failed: A string containing an error message.
        """
        self._log_debug(f"Attempting to read '{self.HOSTS_FILE}' directly.")
        try:
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as f:
                content_lines = f.read().splitlines(keepends=False)
            self._log_debug(
                f"Successfully read '{self.HOSTS_FILE}' directly ({len(content_lines)} lines)."
            )
            return Status.SUCCESS, content_lines
        except PermissionError:
            self._log_debug(
                f"Permission denied reading '{self.HOSTS_FILE}' directly. Falling back to privileged read."
            )
            return self.read_hosts_file_content_privileged()
        except FileNotFoundError:
            self._log_debug(f"'{self.HOSTS_FILE}' not found during direct read attempt.")
            return Status.ERROR_NOT_FOUND, f"Error reading '{self.HOSTS_FILE}': File not found."
        except IOError as e:
            self._log_debug(f"IOError during direct read of '{self.HOSTS_FILE}': {e}")
            return Status.ERROR_IO, f"I/O error reading '{self.HOSTS_FILE}' directly: {e}"
        except Exception as e:  # pylint: disable=broad-except
            self._log_debug(
                f"Unexpected error during direct read of '{self.HOSTS_FILE}': {e} (Traceback: {traceback.format_exc()})"
            )
            return (
                Status.ERROR_INTERNAL,
                f"Unexpected error reading '{self.HOSTS_FILE}' directly: {e}",
            )

    def _read_hosts_file_direct(self) -> tuple[Status, str | list[str]]:
        """
        Attempts to read the hosts file directly without privilege escalation.

        This is an internal helper primarily used by `read_hosts_file_content` and
        `read_hosts_file_content_privileged`.

        Returns:
            A tuple (Status, content_or_error_message):
            - Status: A Status enum member (SUCCESS, ERROR_PERMISSION, ERROR_NOT_FOUND, etc.).
            - content_or_error_message (list[str] | str):
                - If successful: A list of strings (lines from the hosts file).
                - If failed: An error message string.
        """
        self._log_debug(
            f"_read_hosts_file_direct: Attempting to read '{self.HOSTS_FILE}' directly."
        )
        try:
            euid = os.geteuid() if hasattr(os, "geteuid") else "N/A"
            self._log_debug(f"_read_hosts_file_direct: Effective UID: {euid}")
            if not os.path.exists(self.HOSTS_FILE):
                self._log_debug(
                    f"_read_hosts_file_direct: File '{self.HOSTS_FILE}' does not exist."
                )
                return Status.ERROR_NOT_FOUND, f"Error reading '{self.HOSTS_FILE}': File not found."
            if not os.access(self.HOSTS_FILE, os.R_OK):
                self._log_debug(
                    f"_read_hosts_file_direct: File '{self.HOSTS_FILE}' exists but is not readable (os.R_OK check failed)."
                )
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as f:
                content_lines = f.read().splitlines(keepends=False)
            self._log_debug(
                f"_read_hosts_file_direct: Successfully read '{self.HOSTS_FILE}' directly ({len(content_lines)} lines)."
            )
            return Status.SUCCESS, content_lines
        except PermissionError as e_perm:
            self._log_debug(
                f"_read_hosts_file_direct: Permission denied reading '{self.HOSTS_FILE}'. Error: {e_perm}"
            )
            return Status.ERROR_PERMISSION, f"Permission denied reading '{self.HOSTS_FILE}'."
        except FileNotFoundError as e_fnf:
            self._log_debug(
                f"_read_hosts_file_direct: File '{self.HOSTS_FILE}' not found during open. Error: {e_fnf}"
            )
            return Status.ERROR_NOT_FOUND, f"Error reading '{self.HOSTS_FILE}': File not found."
        except IOError as e_io:
            self._log_debug(
                f"_read_hosts_file_direct: IOError during direct read of '{self.HOSTS_FILE}': {e_io} (Traceback: {traceback.format_exc()})"
            )
            return Status.ERROR_IO, f"I/O error reading '{self.HOSTS_FILE}' directly: {e_io}"
        except Exception as e_generic:  # pylint: disable=broad-except
            self._log_debug(
                f"_read_hosts_file_direct: Unexpected error during direct read of '{self.HOSTS_FILE}': {e_generic} (Traceback: {traceback.format_exc()})"
            )
            return (
                Status.ERROR_INTERNAL,
                f"Unexpected error reading '{self.HOSTS_FILE}' directly: {e_generic}",
            )

    def read_hosts_file_content_privileged(self) -> tuple[Status, str | list[str]]:
        """
        Reads the content of the system's hosts file using privileged escalation if necessary.

        It first calls `_read_hosts_file_direct`. If that attempt fails with
        a permission error, this method proceeds to use OS-specific helper scripts
        (e.g., pkexec on Linux, osascript on macOS) to read the file with elevated
        privileges.

        Returns:
            A tuple (Status, content_or_error_message):
            - Status: A Status enum member. SUCCESS if read is successful.
            - content_or_error_message (list[str] | str):
                - If successful (Status.SUCCESS): A list of strings, where each
                  string is a line from the hosts file (newlines stripped), read via
                  the privileged helper.
                - If failed: A string containing an error message from the helper
                  or the escalation process.
        """
        self._log_debug("Attempting to read hosts file content (privileged method entry point).")
        direct_status, direct_content_or_error = self._read_hosts_file_direct()

        if direct_status == Status.SUCCESS:
            self._log_debug("Direct read successful. Skipping privileged escalation.")
            return direct_status, direct_content_or_error
        if direct_status == Status.ERROR_PERMISSION:
            self._log_debug(
                "Direct read failed due to permission error. Proceeding with privileged escalation."
            )
        else:
            self._log_debug(
                f"read_hosts_file_content_privileged: Direct read failed with {direct_status.name if hasattr(direct_status, 'name') else direct_status} ('{direct_content_or_error}'). Not attempting privileged escalation."
            )
            return direct_status, direct_content_or_error

        self._log_debug("Proceeding with privileged helper to read hosts file content.")
        current_os = platform.system()
        op_kwargs = {}
        raw_output_from_helper = ""
        status: Status = Status.ERROR_INTERNAL

        if self.is_flatpak and current_os == "Linux":
            self._log_debug("Flatpak on Linux: using flatpak-spawn for privileged read.")
            status, raw_output_from_helper = self._run_flatpak_spawn_pkexec("read", **op_kwargs)
        elif current_os == "Darwin":
            self._log_debug("macOS: using osascript for privileged read.")
            status, raw_output_from_helper = self._run_macos_elevated("read", **op_kwargs)
        elif current_os == "Linux":  # Non-Flatpak Linux
            self._log_debug("Linux (non-Flatpak): using pkexec for privileged read.")
            status, raw_output_from_helper = self._run_linux_elevated("read", **op_kwargs)
        else:
            self._log_debug(f"Unsupported OS for privileged read: {current_os}")
            return (
                Status.ERROR_INTERNAL,
                f"Privileged read not supported on this OS ({current_os}).",
            )

        if status == Status.SUCCESS:
            self._log_debug(
                f"Privileged read successful. Received {len(raw_output_from_helper)} bytes from helper."
            )
            return Status.SUCCESS, raw_output_from_helper.splitlines()
        self._log_debug(
            f"Privileged read failed. Status: {status.name if hasattr(status, 'name') else status}. Message: {raw_output_from_helper}"
        )
        return status, raw_output_from_helper

    def _build_macos_command_args(
        self, operation_type: str, **kwargs
    ) -> list[str] | tuple[Status, str]:
        """
        Builds the command arguments for the macOS helper script used with osascript.

        Args:
            operation_type: The operation to perform ("read", "update", "remove").
            **kwargs: Arguments specific to the operation type (e.g., ip, domain).

        Returns:
            A list of command arguments if successful, or a tuple (Status, error_message)
            if an error occurs (e.g., helper script not found, invalid arguments).
        """
        macos_helper_script_path = MACOS_HELPER_EXECUTABLE_PATH
        if not os.path.exists(macos_helper_script_path):
            return (
                Status.ERROR_INTERNAL,
                f"macOS helper script not found at configured path: {macos_helper_script_path}",
            )

        cmd_args = ["python3", macos_helper_script_path, operation_type]

        if operation_type == "update":
            staging_ip = kwargs.get("staging_ip")
            sanitized_domain = kwargs.get("sanitized_domain")
            delete_str = str(kwargs.get("delete", False)).lower()
            cmd_args.extend(
                ["--ip", staging_ip, "--domain", sanitized_domain, "--delete", delete_str]
            )
        elif operation_type == "remove":
            entry_to_remove = kwargs.get("entry_to_remove")
            parts = entry_to_remove.split(maxsplit=1)
            if len(parts) != 2:
                return (
                    Status.ERROR_INTERNAL,
                    "Invalid format for entry_to_remove for macOS helper (expected 'IP DOMAIN').",
                )
            ip_to_remove, domain_to_remove = parts
            cmd_args.extend(["--ip", ip_to_remove, "--domain", domain_to_remove])
        elif operation_type == "read":
            pass
        else:
            return (
                Status.ERROR_INTERNAL,
                f"Invalid operation type for macOS elevation: {operation_type}",
            )
        return cmd_args

    def _run_macos_elevated(self, operation_type: str, **kwargs) -> tuple[Status, str]:
        """
        Executes a hosts file operation on macOS with administrator privileges using osascript.

        It constructs a shell command to run the Python helper script (`macos_helper.py`)
        and executes it via AppleScript's "do shell script ... with administrator privileges".

        Args:
            operation_type: The type of operation ("read", "update", "remove").
            **kwargs: Arguments for the operation (e.g., ip, domain for "update").

        Returns:
            A tuple (Status, message_or_content):
            - Status: The outcome of the operation.
            - message_or_content: For "read" on success, the content of the hosts file as a string.
                                 For other operations or errors, a descriptive message.
        """
        cmd_args_or_error = self._build_macos_command_args(operation_type, **kwargs)
        if isinstance(cmd_args_or_error, tuple):
            return cmd_args_or_error

        cmd_args = cmd_args_or_error

        def sh_quote(s_val):
            return "'" + s_val.replace("'", "'\\''") + "'"

        shell_cmd_str = " ".join([sh_quote(arg) for arg in cmd_args])
        osascript_cmd_str = f'do shell script "{shell_cmd_str}" with administrator privileges'

        self._log_debug(f'Executing macOS osascript command: osascript -e "{osascript_cmd_str}"')
        try:
            process = subprocess.run(
                ["osascript", "-e", osascript_cmd_str],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            stdout_cleaned = process.stdout.strip()
            stderr_cleaned = process.stderr.strip()

            if process.returncode:
                error_details_str = (
                    stderr_cleaned
                    if stderr_cleaned
                    else f"osascript failed with exit code {process.returncode} and no stderr."
                )
                if (
                    "User cancelled" in error_details_str
                    or "(-128)" in error_details_str
                    or process.returncode == 1
                ):
                    op_details = kwargs.get(
                        "entry_to_remove", kwargs.get("sanitized_domain", "operation")
                    )
                    return Status.USER_CANCELLED, f"Operation cancelled by user for '{op_details}'."

                if ":" in stdout_cleaned:
                    status_name, message_str = stdout_cleaned.split(":", 1)
                    try:
                        status_code_val = Status[status_name]
                        full_message = (
                            f"osascript error ({error_details_str}) "
                            f"but helper provided status: {message_str}"
                        )
                        return status_code_val, full_message
                    except KeyError:
                        pass

                return (
                    Status.ERROR_INTERNAL,
                    f"Failed to perform '{operation_type}' via osascript: {error_details_str}",
                )

            if operation_type == "read":
                first_line_has_colon = (
                    ":" in stdout_cleaned.splitlines()[0] if stdout_cleaned else False
                )
                if not first_line_has_colon:
                    self._log_debug(
                        f"Helper 'read' successful, returning raw content ({len(stdout_cleaned)} bytes)."
                    )
                    return Status.SUCCESS, stdout_cleaned

            if ":" in stdout_cleaned:
                status_name, message_str = stdout_cleaned.split(":", 1)
                try:
                    status_code_val = Status[status_name]
                    return status_code_val, message_str
                except KeyError:
                    err_detail = f"macOS script returned unknown status: {stdout_cleaned}."
                    if stderr_cleaned:
                        err_detail += f" Stderr: {stderr_cleaned}"
                    return Status.ERROR_INTERNAL, err_detail
            if operation_type != "read":
                err_detail = f"macOS script returned malformed output for {operation_type}: {stdout_cleaned}."
                if stderr_cleaned:
                    err_detail += f" Stderr: {stderr_cleaned}"
                return Status.ERROR_INTERNAL, err_detail
            if not stdout_cleaned:
                self._log_debug("Helper 'read' successful, returning empty content.")
                return Status.SUCCESS, ""
            return (
                Status.ERROR_INTERNAL,
                f"Helper 'read' (macOS) returned unhandled non-empty output: {stdout_cleaned}",
            )

        except subprocess.TimeoutExpired:
            return (
                Status.ERROR_INTERNAL,
                f"Privileged operation timed out for '{operation_type}' on macOS.",
            )
        except FileNotFoundError:
            return (
                Status.ERROR_INTERNAL,
                "osascript command not found. Ensure it's installed and in PATH.",
            )
        except Exception as e_osascript:  # pylint: disable=broad-except
            return (
                Status.ERROR_INTERNAL,
                f"Exception executing osascript for {operation_type}: {e_osascript}",
            )

    def _build_linux_command(self, operation_type: str, **kwargs) -> list[str] | None:
        """
        Builds the command list for executing the Linux helper script via pkexec.

        Args:
            operation_type: The operation to perform ("read", "update", "remove").
            **kwargs: Arguments specific to the operation type.

        Returns:
            A list of command arguments for pkexec, or None if the operation_type is invalid.
        """
        helper_path = HELPER_EXECUTABLE_PATH
        cmd = ["pkexec", helper_path]

        if operation_type == "update":
            cmd.extend(
                [
                    "update",
                    "--ip",
                    kwargs.get("staging_ip"),
                    "--domain",
                    kwargs.get("sanitized_domain"),
                    "--delete",
                    str(kwargs.get("delete")).lower(),
                ]
            )
        elif operation_type == "remove":
            entry_to_remove = kwargs.get("entry_to_remove")
            parts = entry_to_remove.split(maxsplit=1)
            ip_to_remove = ""
            domain_to_remove = entry_to_remove
            if len(parts) == 2:
                ip_to_remove, domain_to_remove = parts
            cmd.extend(["remove", "--ip", ip_to_remove, "--domain", domain_to_remove])
        elif operation_type == "read":
            cmd.append("read")
        else:
            self._log_debug(
                f"Error: Invalid operation type for _build_linux_command: {operation_type}"
            )
            return None
        return cmd

    def _run_linux_elevated(self, operation_type: str, **kwargs) -> tuple[Status, str]:
        """
        Executes a hosts file operation on Linux with root privileges using pkexec.

        It constructs a command to run the Python helper script (`helper.py`) via `pkexec`.

        Args:
            operation_type: The type of operation ("read", "update", "remove").
            **kwargs: Arguments for the operation.

        Returns:
            A tuple (Status, message_or_content):
            - Status: The outcome of the operation.
            - message_or_content: For "read" on success, the content of the hosts file as a string.
                                 For other operations or errors, a descriptive message.
        """
        cmd = self._build_linux_command(operation_type, **kwargs)
        if cmd is None:
            return (
                Status.ERROR_INTERNAL,
                f"Error: Invalid operation type for Linux elevation: {operation_type}",
            )

        self._log_debug(f"Executing pkexec command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
            self._log_debug(f"pkexec raw returncode: {result.returncode}")
            self._log_debug(f"pkexec raw stdout: '{result.stdout.strip()}'")
            self._log_debug(f"pkexec raw stderr: '{result.stderr.strip()}'")
            output_str = result.stdout.strip()

            if result.returncode:
                error_details_str = (
                    result.stderr.strip() if result.stderr else "Unknown error from pkexec/helper."
                )
                op_details = kwargs.get(
                    "entry_to_remove", kwargs.get("sanitized_domain", "operation")
                )
                if (
                    "cancel" in error_details_str.lower()
                    or "authenticate" in error_details_str.lower()
                    or "authorization" in error_details_str.lower()
                ):
                    status_to_return = Status.USER_CANCELLED
                    message_to_return = (
                        f"Operation for '{op_details}' cancelled or "
                        f"authentication failed via pkexec: {error_details_str}"
                    )
                    self._log_debug(
                        f"Returning status: {status_to_return.name}, message: '{message_to_return}'"
                    )
                    return status_to_return, message_to_return

                status_to_return = Status.ERROR_INTERNAL
                message_to_return = (
                    f"Failed to perform '{operation_type}' for '{op_details}' "
                    f"with pkexec: {error_details_str}"
                )
                self._log_debug(
                    f"Returning status: {status_to_return.name}, message: '{message_to_return}'"
                )
                return status_to_return, message_to_return

            if operation_type == "read":
                first_line_has_colon = ":" in output_str.splitlines()[0] if output_str else False
                if not first_line_has_colon:
                    self._log_debug(
                        f"Helper 'read' successful, returning raw content ({len(output_str)} bytes)."
                    )
                    return Status.SUCCESS, output_str

            if ":" in output_str:
                status_name, message_str = output_str.split(":", 1)
                try:
                    status_code_val = Status[status_name]
                    self._log_debug(
                        f"Returning status: {status_code_val.name}, message: '{message_str}'"
                    )
                    return status_code_val, message_str
                except KeyError:
                    error_message_str = f"Linux helper script returned unknown status: {output_str}"
                    self._log_debug(f"Returning ERROR_INTERNAL, message: '{error_message_str}'")
                    return Status.ERROR_INTERNAL, error_message_str
            if operation_type != "read":
                error_message_str = f"Linux helper script returned malformed output for {operation_type}: {output_str}"
                self._log_debug(f"Returning ERROR_INTERNAL, message: '{error_message_str}'")
                return Status.ERROR_INTERNAL, error_message_str
            if not output_str:
                self._log_debug("Helper 'read' successful, returning empty content.")
                return Status.SUCCESS, ""
            return (
                Status.ERROR_INTERNAL,
                f"Linux helper 'read' returned unhandled non-empty output: {output_str}",
            )

        except subprocess.TimeoutExpired:
            error_message_str = f"Privileged operation timed out for '{operation_type}' on Linux."
            self._log_debug(f"Returning ERROR_INTERNAL, message: '{error_message_str}'")
            return Status.ERROR_INTERNAL, error_message_str
        except FileNotFoundError:
            error_message_str = (
                f"Failed to perform '{operation_type}': pkexec or "
                f"helper script ({helper_path}) not found."
            )
            self._log_debug(f"Returning ERROR_NOT_FOUND, message: '{error_message_str}'")
            return Status.ERROR_NOT_FOUND, error_message_str
        except Exception as e_pkexec:  # pylint: disable=broad-except
            error_message_str = f"Error executing pkexec for {operation_type}: {e_pkexec} (Traceback: {traceback.format_exc()})"
            self._log_debug(f"Returning ERROR_INTERNAL, message: '{error_message_str}'")
            return Status.ERROR_INTERNAL, error_message_str

    def _build_flatpak_command(self, operation_type: str, **kwargs) -> list[str] | None:
        """
        Builds the command list for executing the helper script via flatpak-spawn --host pkexec.

        Args:
            operation_type: The operation to perform ("read", "update", "remove").
            **kwargs: Arguments specific to the operation type.

        Returns:
            A list of command arguments for flatpak-spawn, or None if operation_type is invalid.
        """
        helper_path = HELPER_EXECUTABLE_PATH
        cmd = ["flatpak-spawn", "--host", "pkexec", helper_path]

        if operation_type == "update":
            cmd.extend(
                [
                    "update",
                    "--ip",
                    kwargs.get("staging_ip"),
                    "--domain",
                    kwargs.get("sanitized_domain"),
                    "--delete",
                    str(kwargs.get("delete")).lower(),
                ]
            )
        elif operation_type == "remove":
            entry_to_remove = kwargs.get("entry_to_remove")
            parts = entry_to_remove.split(maxsplit=1)
            ip_to_remove = ""
            domain_to_remove = entry_to_remove
            if len(parts) == 2:
                ip_to_remove, domain_to_remove = parts
            cmd.extend(["remove", "--ip", ip_to_remove, "--domain", domain_to_remove])
        elif operation_type == "read":
            cmd.append("read")
        else:
            self._log_debug(
                f"Error: Invalid operation type for _build_flatpak_command: {operation_type}"
            )
            return None
        return cmd

    def _run_flatpak_spawn_pkexec(self, operation_type: str, **kwargs) -> tuple[Status, str]:
        """
        Executes the helper script using 'flatpak-spawn --host pkexec' for privilege escalation
        in Linux Flatpak environments.

        Args:
            operation_type: The type of operation ("read", "update", "remove").
            **kwargs: Arguments for the operation.

        Returns:
            A tuple (Status, message_or_content):
            - Status: The outcome of the operation.
            - message_or_content: For "read" on success, the content of the hosts file as a string.
                                 For other operations or errors, a descriptive message.
        """
        cmd = self._build_flatpak_command(operation_type, **kwargs)
        if cmd is None:
            return (
                Status.ERROR_INTERNAL,
                f"Error: Invalid operation type for Flatpak pkexec elevation: {operation_type}",
            )

        self._log_debug(f"Executing flatpak-spawn command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=15)
            self._log_debug(f"flatpak-spawn raw returncode: {result.returncode}")
            self._log_debug(f"flatpak-spawn raw stdout: '{result.stdout.strip()}'")
            self._log_debug(f"flatpak-spawn raw stderr: '{result.stderr.strip()}'")
            output_str = result.stdout.strip()

            if result.returncode:
                error_details_str = (
                    result.stderr.strip()
                    if result.stderr
                    else "Unknown error from flatpak-spawn/pkexec/helper."
                )
                op_details = kwargs.get(
                    "entry_to_remove", kwargs.get("sanitized_domain", "operation")
                )
                if (
                    "cancel" in error_details_str.lower()
                    or "authenticate" in error_details_str.lower()
                    or "authorization" in error_details_str.lower()
                    or "org.freedesktop.PolicyKit1.Error.NotAuthorized" in error_details_str
                ):
                    status_to_return = Status.USER_CANCELLED
                    message_to_return = (
                        f"Operation for '{op_details}' cancelled or "
                        f"authentication failed via flatpak-spawn/pkexec: {error_details_str}"
                    )
                else:
                    status_to_return = Status.ERROR_INTERNAL
                    message_to_return = (
                        f"Failed to perform '{operation_type}' for '{op_details}' "
                        f"with flatpak-spawn/pkexec: {error_details_str}"
                    )
                self._log_debug(
                    f"Returning status: {status_to_return.name}, message: '{message_to_return}'"
                )
                return status_to_return, message_to_return

            if operation_type == "read":
                first_line_has_colon = ":" in output_str.splitlines()[0] if output_str else False
                if not first_line_has_colon:
                    self._log_debug(
                        f"Helper 'read' (via flatpak-spawn) successful, returning raw content ({len(output_str)} bytes)."
                    )
                    return Status.SUCCESS, output_str

            if ":" in output_str:
                status_name, message_str = output_str.split(":", 1)
                try:
                    status_code_val = Status[status_name]
                    self._log_debug(
                        f"Returning status from helper (via flatpak-spawn): {status_code_val.name}, message: '{message_str}'"
                    )
                    return status_code_val, message_str
                except KeyError:
                    error_message_str = (
                        f"Helper (via flatpak-spawn) returned unknown status: {output_str}"
                    )
                    self._log_debug(error_message_str)
                    return Status.ERROR_INTERNAL, error_message_str
            if operation_type != "read":
                error_message_str = f"Helper (via flatpak-spawn) returned malformed output for {operation_type}: {output_str}"
                self._log_debug(error_message_str)
                return Status.ERROR_INTERNAL, error_message_str
            if not output_str:
                self._log_debug(
                    "Helper 'read' (via flatpak-spawn) successful, returning empty content."
                )
                return Status.SUCCESS, ""
            return (
                Status.ERROR_INTERNAL,
                f"Helper 'read' (flatpak-spawn) returned unhandled non-empty output: {output_str}",
            )

        except subprocess.TimeoutExpired:
            error_message_str = (
                f"Privileged operation (via flatpak-spawn) timed out for '{operation_type}'."
            )
            self._log_debug(error_message_str)
            return Status.ERROR_INTERNAL, error_message_str
        except FileNotFoundError:
            error_message_str = "flatpak-spawn command not found. This method should only be called in a Flatpak environment."
            self._log_debug(error_message_str)
            return Status.ERROR_INTERNAL, error_message_str
        except Exception as e_fp_spawn:  # pylint: disable=broad-except
            error_message_str = f"Error executing flatpak-spawn for {operation_type}: {e_fp_spawn} (Traceback: {traceback.format_exc()})"
            self._log_debug(error_message_str)
            return Status.ERROR_INTERNAL, error_message_str

    def get_existing_ip_for_domain(self, sanitized_domain: str) -> str | None:
        """
        Reads the hosts file to find the IP address currently associated with a given domain.

        This method performs a direct read of the hosts file. It does not use
        privilege escalation. It should be used when a read is expected to succeed
        or when failure to read (e.g., due to permissions) should be handled by the caller.

        Args:
            sanitized_domain: The domain name to search for.

        Returns:
            The IP address (str) currently mapped to the domain in the hosts file.
            Returns None if the domain is not found or if the line is malformed.

        Raises:
            FileNotFoundError: If the hosts file cannot be found.
            PermissionError: If there's a permission issue reading the hosts file.
            IOError: For other I/O related issues.
            RuntimeError: For any other unexpected errors during the file read.
        """
        try:
            with open(self.HOSTS_FILE, "r", encoding="utf-8") as hosts_file:
                for line in hosts_file:
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith("#"):
                        continue

                    # Basic parsing: IP hostname [hostname...]
                    # This doesn't use _parse_hosts_line to keep it simple for read-only.
                    line_parts = stripped_line.split()
                    if len(line_parts) >= 2:
                        ip_address_in_line = line_parts[0]
                        # Check if the domain is one of the hostnames on this line
                        if sanitized_domain in line_parts[1:]:
                            return ip_address_in_line
            return None  # Domain not found
        except FileNotFoundError as e_fnf:
            # Re-raise with more context for clarity if needed, or let it propagate.
            raise FileNotFoundError(f"Error reading '{self.HOSTS_FILE}': {e_fnf}") from e_fnf
        except PermissionError as e_perm:
            raise PermissionError(
                f"Permission denied reading '{self.HOSTS_FILE}': {e_perm}"
            ) from e_perm
        except IOError as e_io:
            raise IOError(f"I/O error reading '{self.HOSTS_FILE}': {e_io}") from e_io
        except Exception as e_generic:  # pylint: disable=broad-except
            # Catching broad Exception is generally discouraged, but here it might
            # be for logging or converting to a custom app exception.
            # For now, re-raise as RuntimeError to signal an unexpected issue.
            raise RuntimeError(
                f"An unexpected error occurred while reading '{self.HOSTS_FILE}': {e_generic}"
            ) from e_generic


# Ensure a single newline at the end of the file
