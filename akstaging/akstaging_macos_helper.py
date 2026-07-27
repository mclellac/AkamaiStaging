#!/usr/bin/env python3

import os
import sys
import traceback


def write_log_stderr(message: str):
    """Writes a message to sys.stderr, prefixed for this helper."""
    sys.stderr.write(f"[macOS Helper Log] {message}\n")


def adjust_python_path(logger_func):
    """
    Adjusts sys.path to ensure 'akstaging' module can be imported across all install layouts and dev environments.
    """
    logger_func("adjust_python_path: Started.")

    candidate_paths = []

    try:
        import sysconfig

        purelib = sysconfig.get_path("purelib")
        if purelib and os.path.isdir(purelib):
            candidate_paths.append(purelib)
    except Exception as e:
        logger_func(f"adjust_python_path: Error getting sysconfig purelib: {e}")

    try:
        script_path = os.path.realpath(__file__)
        script_dir = os.path.dirname(script_path)

        # If helper is inside the akstaging package directory itself (e.g. repo layout)
        if os.path.exists(os.path.join(script_dir, "hosts.py")):
            parent_dir = os.path.dirname(script_dir)
            candidate_paths.append(parent_dir)

        # Derived prefix site-packages (e.g. PREFIX/libexec/akamaistaging -> PREFIX/lib/python3.X/site-packages)
        prefix_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
        python_version_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
        prefix_site_packages = os.path.join(prefix_dir, "lib", python_version_dir, "site-packages")
        if os.path.isdir(prefix_site_packages):
            candidate_paths.append(prefix_site_packages)

    except Exception as e:
        logger_func(f"adjust_python_path: Error analyzing script paths: {e}")

    for path_item in candidate_paths:
        if path_item not in sys.path:
            sys.path.insert(0, path_item)
            logger_func(f"adjust_python_path: ADDED to sys.path: {path_item}")

    try:
        import importlib

        importlib.import_module("akstaging.hosts")
        logger_func("adjust_python_path: Import of 'akstaging.hosts' successful.")
    except Exception as e_imp:
        logger_func(f"adjust_python_path: Test import failed: {e_imp}")


adjust_python_path(write_log_stderr)

try:
    from akstaging.hosts import HostsFileEdit
    from akstaging.status_codes import Status

    write_log_stderr("Import of akstaging.hosts.HostsFileEdit and akstaging.status_codes.Status successful.")
except ImportError as e:
    error_message = (
        f"ERROR_INTERNAL:Failed to import necessary modules. Ensure 'akstaging' package is in PYTHONPATH. Error: {e}\n"
    )
    write_log_stderr(error_message)
    sys.stderr.write(f"Python sys.path: {sys.path}\n")
    sys.stderr.write(f"Current working directory: {os.getcwd()}\n")
    print("ERROR_INTERNAL:Failed to import modules in helper. Check stderr for details.")
    sys.exit(0)
except Exception as e_import_generic:
    write_log_stderr(f"CRITICAL: Unexpected error during initial module import: {e_import_generic}")
    # Main exception handler below will catch and log traceback if this occurs.
    print("ERROR_INTERNAL:Unexpected import error in helper. Check stderr.")
    sys.exit(0)

try:
    from akstaging.helper_cli import handle_read_command, parse_common_arguments

    write_log_stderr("Successfully imported shared CLI functions from akstaging.helper_cli.")
except ImportError as e_cli_import:
    write_log_stderr(f"CRITICAL: Failed to import from akstaging.helper_cli: {e_cli_import}")
    print("ERROR_INTERNAL:Failed to import helper_cli. Check stderr for details.")
    sys.exit(0)


def main():
    """Parses arguments and executes the requested hosts file operation for macOS."""
    args = parse_common_arguments()

    status: Status = Status.ERROR_INTERNAL
    message: str = "Operation not performed or failed in macOS helper."

    try:
        editor = HostsFileEdit()

        if args.command == "update":
            delete_bool = args.delete.lower() == "true"
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
