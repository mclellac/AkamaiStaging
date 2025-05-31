#!/usr/bin/env python3

import os
import sys
import traceback


def write_log_stderr(message: str):
    """Writes a message to sys.stderr, prefixed for this helper."""
    sys.stderr.write(f"[macOS Helper Log] {message}\n")

def adjust_python_path(logger_func):
    """
    Adjusts sys.path to include the site-packages directory relative to the script's prefix.
    This helps ensure that the 'akstaging' module can be imported if it's installed
    in a standard location relative to this helper script.
    """
    logger_func("adjust_python_path: Started.")
    initial_path_str = ":".join(sys.path)
    logger_func(f"adjust_python_path: Initial sys.path: {initial_path_str}")

    try:
        script_path = os.path.realpath(__file__)
        logger_func(f"adjust_python_path: Script path: {script_path}")

        # Determine prefix: e.g., PREFIX/libexec/akamaistaging/akstaging_macos_helper.py -> PREFIX
        prefix_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
        logger_func(f"adjust_python_path: Derived prefix_dir: {prefix_dir}")

        python_version_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
        # Common path structure for site-packages relative to prefix
        site_packages_path = os.path.join(prefix_dir, "lib", python_version_dir, "site-packages")
        logger_func(f"adjust_python_path: Constructed site-packages path: {site_packages_path}")

        if os.path.isdir(site_packages_path):
            if site_packages_path not in sys.path:
                sys.path.insert(0, site_packages_path)
                logger_func(f"adjust_python_path: ADDED to sys.path: {site_packages_path}")
            else:
                logger_func("adjust_python_path: Site-packages path already in sys.path.")

            # Test import
            try:
                import akstaging.hosts # Try importing a specific submodule
                logger_func("adjust_python_path: Test import of 'akstaging.hosts' successful.")
            except ModuleNotFoundError:
                logger_func("adjust_python_path: FAILED to import 'akstaging.hosts' after path adjustment.")
        else:
            logger_func("adjust_python_path: Constructed site-packages path is not a directory. Path not added. Check Python/install layout.")

    except Exception as e:
        logger_func(f"adjust_python_path: Error during path adjustment: {e}")
        # Traceback is already logged if logger_func is write_log_stderr and it includes it,
        # or can be added to the main exception handler if critical.

    final_path_str = ":".join(sys.path)
    logger_func(f"adjust_python_path: Finished. Final sys.path: {final_path_str}")

adjust_python_path(write_log_stderr)

try:
    from akstaging.hosts import HostsFileEdit
    from akstaging.status_codes import Status
    write_log_stderr("Import of akstaging.hosts.HostsFileEdit and akstaging.status_codes.Status successful.")
except ImportError as e:
    error_message = (
        f"ERROR_INTERNAL:Failed to import necessary modules. "
        f"Ensure 'akstaging' package is in PYTHONPATH. Error: {e}\n"
    )
    write_log_stderr(error_message)
    sys.stderr.write(f"Python sys.path: {sys.path}\n")
    sys.stderr.write(f"Current working directory: {os.getcwd()}\n")
    print(f"ERROR_INTERNAL:Failed to import modules in helper. Check stderr for details.")
    sys.exit(0)
except Exception as e_import_generic:
    write_log_stderr(f"CRITICAL: Unexpected error during initial module import: {e_import_generic}")
    # Main exception handler below will catch and log traceback if this occurs.
    print(f"ERROR_INTERNAL:Unexpected import error in helper. Check stderr.")
    sys.exit(0)

try:
    from akstaging.helper_cli import parse_common_arguments, handle_read_command
    write_log_stderr("Successfully imported shared CLI functions from akstaging.helper_cli.")
except ImportError as e_cli_import:
    write_log_stderr(f"CRITICAL: Failed to import from akstaging.helper_cli: {e_cli_import}")
    print(f"ERROR_INTERNAL:Failed to import helper_cli. Check stderr for details.")
    sys.exit(0)

def main():
    """Parses arguments and executes the requested hosts file operation for macOS."""
    args = parse_common_arguments()

    status: Status = Status.ERROR_INTERNAL
    message: str = "Operation not performed or failed in macOS helper."

    try:
        editor = HostsFileEdit()

        if args.command == "update":
            delete_bool = args.delete.lower() == 'true'
            status, message = editor._update_hosts_file_content_direct(args.ip, args.domain, delete=delete_bool)
            print(f"{status.name}:{message}")
            sys.exit(0)
        elif args.command == "remove":
            entry_to_remove = f"{args.ip} {args.domain}"
            status, message = editor._remove_hosts_entry_direct(entry_to_remove)
            print(f"{status.name}:{message}")
            sys.exit(0)
        elif args.command == "read":
            handle_read_command(write_log_stderr)

    except Exception as e_generic:
        status = Status.ERROR_INTERNAL
        # Print to stderr so osascript can capture it if stdout is exclusively for status:message
        sys.stderr.write(f"Error in akstaging_macos_helper: {e_generic}\n")
        sys.stderr.write(traceback.format_exc() + "\n")
        # Output the error status via the defined mechanism as well
        print(f"{status.name}:Unexpected error in macOS helper: {e_generic}")
        sys.exit(0)  # Still exit 0 as we've reported status via stdout


if __name__ == "__main__":
    main()
