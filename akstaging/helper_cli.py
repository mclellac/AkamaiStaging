# akstaging/helper_cli.py
import argparse
import sys
from akstaging.hosts import HostsFileEdit
from akstaging.status_codes import Status

def parse_common_arguments():
    """Defines and parses common command-line arguments for helper scripts."""
    parser = argparse.ArgumentParser(description="Privileged helper for /etc/hosts manipulation.")
    parser.add_argument("command", choices=["update", "remove", "read"],
                        help="The operation to perform: 'update', 'remove', or 'read'.")
    parser.add_argument("--ip", type=str, required=False,
                        help="The IP address. Required for 'update' and 'remove' operations.")
    parser.add_argument("--domain", type=str, required=False,
                        help="The domain name. Required for 'update' and 'remove' operations.")
    parser.add_argument("--delete", type=str, default='false', choices=['true', 'false'],
                        help="For 'update' command: if 'true', remove entries for the domain. "
                             "If 'false', ensure domain maps to IP. Defaults to 'false'.")
    args = parser.parse_args()

    if args.command in ["update", "remove"]:
        if not args.ip:
            # Helpers print status:message to stdout and log to stderr
            sys.stderr.write("[Helper CLI Log] Error: Argument --ip is required for update/remove operations.\n")
            print(f"{Status.ERROR_INTERNAL.name}:Error: Argument --ip is required for update/remove.")
            sys.exit(0) # Helpers exit 0 after printing status:message
        if not args.domain:
            sys.stderr.write("[Helper CLI Log] Error: Argument --domain is required for update/remove operations.\n")
            print(f"{Status.ERROR_INTERNAL.name}:Error: Argument --domain is required for update/remove.")
            sys.exit(0)
    return args

def handle_read_command(log_func):
    """Handles the logic for the 'read' command."""
    log_func("Preparing to read hosts file via helper_cli.handle_read_command.")
    try:
        with open(HostsFileEdit.HOSTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        sys.stdout.write(content) # Write raw content to stdout
        sys.exit(0)
    except FileNotFoundError as e_fnf_read:
        log_func(f"FileNotFoundError reading hosts: {e_fnf_read}")
        print(f"{Status.ERROR_NOT_FOUND.name}:Error reading hosts file in helper: {e_fnf_read}")
        sys.exit(0)
    except PermissionError as e_perm_read: # Should not happen if helper is root
        log_func(f"PermissionError reading hosts: {e_perm_read}")
        print(f"{Status.ERROR_PERMISSION.name}:Permission error reading hosts file (helper should be root): {e_perm_read}")
        sys.exit(0)
    except Exception as e_generic_read:
        log_func(f"Exception reading hosts: {e_generic_read}")
        print(f"{Status.ERROR_INTERNAL.name}:Unexpected error reading hosts file: {e_generic_read}")
        sys.exit(0)
