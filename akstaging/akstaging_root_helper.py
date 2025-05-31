#!/usr/bin/env python3

import sys
import os
import datetime
import traceback


LOG_FILE_PATH = "/tmp/akstaging_helper_debug.log"


def write_log(message):
    """Appends a message to the debug log file."""
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        # If logging fails, we can't do much, but don't crash the helper.
        pass


write_log("--- AkamaiStaging Root Helper Started ---")
write_log(f"CWD: {os.getcwd()}")
write_log(f"sys.executable: {sys.executable}")
write_log(f"sys.version: {sys.version.replace(chr(10), ' ')}")
write_log(f"Initial sys.path: {sys.path}")

def adjust_python_path(logger_func):
    """
    Adjusts sys.path to include the site-packages directory relative to the script's prefix.
    This helps ensure that the 'akstaging' module can be imported if it's installed
    in a standard location relative to this helper script (e.g., in a venv or system prefix).
    """
    logger_func("adjust_python_path: Started.")
    logger_func(f"adjust_python_path: Initial sys.path: {sys.path}")

    try:
        script_path = os.path.realpath(__file__)
        logger_func(f"adjust_python_path: Script path: {script_path}")

        prefix_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
        logger_func(f"adjust_python_path: Derived prefix_dir: {prefix_dir}")

        python_version_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages_path = os.path.join(prefix_dir, "lib", python_version_dir, "site-packages")
        logger_func(f"adjust_python_path: Constructed site-packages path: {site_packages_path}")

        if os.path.isdir(site_packages_path):
            if site_packages_path not in sys.path:
                sys.path.insert(0, site_packages_path)
                logger_func(f"adjust_python_path: ADDED to sys.path: {site_packages_path}")
            else:
                logger_func("adjust_python_path: Site-packages path already in sys.path.")

            try:
                import akstaging
                logger_func("adjust_python_path: Test import of 'akstaging' successful after path adjustment.")
            except ModuleNotFoundError:
                logger_func("adjust_python_path: FAILED to import 'akstaging' even after adding site-packages path.")
        else:
            logger_func("adjust_python_path: Constructed site-packages path is not a directory. Path not added.")

    except Exception as e:
        logger_func(f"adjust_python_path: Error during path adjustment: {e}")
        logger_func(f"adjust_python_path: Traceback: {traceback.format_exc()}")

    logger_func(f"adjust_python_path: Finished. Final sys.path: {sys.path}")

adjust_python_path(write_log)

write_log("Attempting to import akstaging modules...")
try:
    from akstaging.hosts import HostsFileEdit
    from akstaging.status_codes import Status
    write_log("Import of akstaging.hosts.HostsFileEdit and akstaging.status_codes.Status successful.")
except ModuleNotFoundError as e:
    write_log(f"CRITICAL: Failed to import akstaging modules. Error: {e}")
    write_log("Ensure the 'akstaging' package is installed correctly in Python's site-packages.")
    write_log(f"Current sys.path: {sys.path}")
    write_log(f"Traceback: {traceback.format_exc()}")
    # Directly use string literals for safety, as Status import has failed.
    print(f"ERROR_INTERNAL:CRITICAL: Failed to import akstaging modules in helper. Check logs.")
    sys.exit(0)
except Exception as e_import_generic:
    _error_message = f"CRITICAL: Unexpected error importing modules: {e_import_generic}. Check logs."
    write_log(_error_message)
    write_log(f"Traceback: {traceback.format_exc()}")
    # Directly use string literal for safety, as Status import might have failed
    _final_status_name_str = "ERROR_INTERNAL"
    _final_message_str_content = _error_message
    print(f"{_final_status_name_str}:{_final_message_str_content}")
    sys.exit(0)

try:
    from akstaging.helper_cli import parse_common_arguments, handle_read_command
    write_log("Successfully imported shared CLI functions from akstaging.helper_cli.")
except ImportError as e_cli_import:
    write_log(f"CRITICAL: Failed to import from akstaging.helper_cli: {e_cli_import}")
    print(f"ERROR_INTERNAL:Failed to import helper_cli. Check logs.")
    sys.exit(0)

def _print_status_and_exit(status_code: Status, message: any):
    """Ensures status_code is Status, message is string, then logs, prints, and exits."""
    final_message_str = str(message)

    if not isinstance(status_code, Status):
        write_log(f"CRITICAL: Invalid status_code type ({type(status_code)}) in _print_status_and_exit. Value: {status_code}")
        if not (status_code == Status.ERROR_INTERNAL and "Invalid status type" not in final_message_str):
            final_message_str = "Internal helper error: Invalid status type processed."
        status_code = Status.ERROR_INTERNAL
    
    status_name_to_log = status_code.name if isinstance(status_code, Status) else "UNKNOWN_STATUS_TYPE"
    write_log(f"To stdout: {status_name_to_log}:{final_message_str}") 
    
    print(f"{status_code.name}:{final_message_str}")
    sys.exit(0)


def main():
    """Parses arguments and executes the requested hosts file operation."""
    write_log("main(): Function started.")
    args = parse_common_arguments()
    write_log(f"main(): Parsed arguments via helper_cli: {args}")

    status_code: Status = Status.ERROR_INTERNAL
    message: str = "Operation not performed or failed in helper."

    try:
        editor = HostsFileEdit(logger_func=write_log)

        if args.command == "update":
            delete_bool = args.delete.lower() == 'true'
            write_log(
                f"main(): Preparing to call editor._update_hosts_file_content_direct with "
                f"ip='{args.ip}', domain='{args.domain}', delete={delete_bool}"
            )
            status_code, message = editor._update_hosts_file_content_direct(
                args.ip, args.domain, delete=delete_bool
            )
            write_log(
                f"main(): editor._update_hosts_file_content_direct returned: "
                f"status_code='{status_code.name if hasattr(status_code, 'name') else status_code}', message='{message}'"
            )
            _print_status_and_exit(status_code, message)
        elif args.command == "remove":
            entry_to_remove = f"{args.ip} {args.domain}"
            write_log(
                f"main(): Preparing to call editor._remove_hosts_entry_direct with entry='{entry_to_remove}'"
            )
            status_code, message = editor._remove_hosts_entry_direct(entry_to_remove)
            write_log(
                f"main(): editor._remove_hosts_entry_direct returned: "
                f"status_code='{status_code.name if hasattr(status_code, 'name') else status_code}', message='{message}'"
            )
            _print_status_and_exit(status_code, message)
        elif args.command == "read":
            handle_read_command(write_log)

    except FileNotFoundError as e_fnf:
        _message = f"Error accessing hosts file in helper: {e_fnf}"
    except PermissionError as e_perm:
        _message = f"Permission error in helper (should be root): {e_perm}"
        write_log(f"main(): {_message}")
        _print_status_and_exit(Status.ERROR_PERMISSION, _message)
    except ImportError as e_imp:
        _message = f"Critical import error in helper: {e_imp}"
        write_log(f"main(): {_message}\nTraceback: {traceback.format_exc()}")
        _print_status_and_exit(Status.ERROR_INTERNAL, _message)
    except Exception as e_generic:
        _message = f"Unexpected error in privileged helper: {e_generic}"
        write_log(f"main(): {_message}\nTraceback: {traceback.format_exc()}")
        _print_status_and_exit(Status.ERROR_INTERNAL, _message)
    finally:
        write_log("--- AkamaiStaging Root Helper Finished ---")


if __name__ == "__main__":
    write_log("__main__: Script execution started.")
    main()
    write_log("__main__: Script execution normally finished (or sys.exit called).")
