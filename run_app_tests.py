import os
import sys
import logging

# Setup PYTHONPATH to find akstaging modules from the build directory
# This script is in /app
module_base_dir = os.path.abspath(os.path.dirname(__file__)) # /app
sys.path.insert(0, module_base_dir)


# Configure basic logging for the test script
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger("AkamaiStagingTest")

# --- BEGIN Imports from AkamaiStaging ---
import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk, GLib

RESOURCE_PATH_FROM_DEFS = None
try:
    from akstaging.defs import RESOURCE_PATH as RESOURCE_PATH_FROM_DEFS
    logger.info(f"Test Script: Imported RESOURCE_PATH from akstaging.defs: {RESOURCE_PATH_FROM_DEFS}")
except ImportError:
    logger.warning("Test Script: Could not import RESOURCE_PATH from akstaging.defs.")

ABS_RESOURCE_PATH = os.path.join(module_base_dir, "build", "akstaging", "akamaistaging.gresource")
logger.info(f"Test Script: Attempting to load Gio resource from: {ABS_RESOURCE_PATH}")

try:
    resource = Gio.Resource.load(ABS_RESOURCE_PATH)
    Gio.resources_register(resource)
    logger.info("Test Script: Gio Resource loaded and registered successfully.")
except GLib.Error as e:
    logger.error(f"Test Script: Failed to load Gio resource from {ABS_RESOURCE_PATH}: {e}")
    # Attempt path relative to CWD if that fails (e.g. if CWD is /app/build)
    # This alternative logic might be needed if the script's CWD changes.
    # For `python /app/run_app_tests.py` run from /app, ABS_RESOURCE_PATH should be correct.
    # If it was run from /app/build, then "akstaging/akamaistaging.gresource" would be correct.
    # The current setup assumes CWD=/app for the `run_in_bash_session` execution of the script.
    sys.exit(1) 
except Exception as e_generic:
    logger.error(f"Test Script: Generic exception loading Gio resource: {e_generic}", exc_info=True)
    sys.exit(1)


from akstaging.window import AkamaiStagingWindow, DataObject
from akstaging.hosts import HostsFileEdit # To access HOSTS_FILE path for reading
# --- END Imports from AkamaiStaging ---

def read_hosts_file_content():
    try:
        with open(HostsFileEdit.HOSTS_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Hosts file not found at {HostsFileEdit.HOSTS_FILE}")
        return "HOSTS_FILE_NOT_FOUND"
    except Exception as e:
        logger.error(f"Error reading hosts file {HostsFileEdit.HOSTS_FILE}: {e}")
        return f"ERROR_READING_HOSTS_FILE: {e}"

def get_textview_status_content(window_instance):
    buffer = window_instance.textview_status.get_buffer()
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip()

def clear_hosts_file_for_test():
    logger.info(f"Clearing dummy hosts file for test: {HostsFileEdit.HOSTS_FILE}")
    content = (
        "127.0.0.1 localhost\n"
        "::1 localhost\n"
        "# Test comment\n"
    )
    try:
        with open(HostsFileEdit.HOSTS_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Hosts file at {HostsFileEdit.HOSTS_FILE} cleared with basic content.")
    except Exception as e:
        logger.error(f"Failed to clear hosts file {HostsFileEdit.HOSTS_FILE}: {e}")
        sys.exit(f"CRITICAL_SETUP_FAILURE: Could not clear hosts file: {e}")


def run_all_tests(app_instance):
    logger.info("Starting AkamaiStaging UI tests (simulated).")
    
    window = AkamaiStagingWindow(application=app_instance)

    logger.info("--- Test Case 1: Initial State ---")
    clear_hosts_file_for_test()
    window.populate_store(window.store) 
    initial_hosts_content = read_hosts_file_content()
    logger.info(f"Initial hosts content:\n{initial_hosts_content}")
    assert "example-staging.com" not in initial_hosts_content, "Initial state FAILED: example-staging.com found in hosts file."
    logger.info("Test Case 1 PASSED.")

    logger.info("--- Test Case 2: Add New Host (example-staging.com) ---")
    window.entry_domain.set_text("example-staging.com")
    window.on_get_ip_button_clicked(window.button_add_ip, window.entry_domain, window.textview_status)
    
    status_messages_tc2 = get_textview_status_content(window)
    hosts_content_tc2 = read_hosts_file_content()
    logger.info(f"TC2 Status Messages:\n{status_messages_tc2}")
    logger.info(f"TC2 Hosts Content:\n{hosts_content_tc2}")
    
    expected_msgs_tc2 = [
        "Found staging IP 1.2.3.4 for example-staging.com.",
        "Attempting to add to hosts file...",
        f"Updated {HostsFileEdit.HOSTS_FILE}: Set example-staging.com to 1.2.3.4."
    ]
    current_pos = 0
    for msg in expected_msgs_tc2:
        found_pos = status_messages_tc2.find(msg, current_pos)
        assert found_pos != -1, f"TC2 FAILED: Expected message '{msg}' not found in sequence. Full log:\n{status_messages_tc2}"
        current_pos = found_pos + len(msg)
    assert "1.2.3.4 example-staging.com" in hosts_content_tc2, "TC2 FAILED: Host entry '1.2.3.4 example-staging.com' not found."
    logger.info("Test Case 2 PASSED.")

    logger.info("--- Test Case 3: Add Existing Host (No Change) ---")
    window.entry_domain.set_text("example-staging.com")
    window.on_get_ip_button_clicked(window.button_add_ip, window.entry_domain, window.textview_status)
    
    status_messages_tc3 = get_textview_status_content(window)
    hosts_content_tc3 = read_hosts_file_content()
    logger.info(f"TC3 Status Messages:\n{status_messages_tc3}")
    
    expected_msgs_tc3 = [
        "Found staging IP 1.2.3.4 for example-staging.com.",
        "Attempting to add to hosts file...",
        f"Entry 1.2.3.4 example-staging.com already correctly configured in {HostsFileEdit.HOSTS_FILE}."
    ]
    current_pos = 0
    for msg in expected_msgs_tc3:
        found_pos = status_messages_tc3.find(msg, current_pos)
        assert found_pos != -1, f"TC3 FAILED: Expected message '{msg}' not found in sequence. Full log:\n{status_messages_tc3}"
        current_pos = found_pos + len(msg)
    assert hosts_content_tc3 == hosts_content_tc2, f"TC3 FAILED: Hosts file changed.\nExpected:\n{hosts_content_tc2}\nGot:\n{hosts_content_tc3}"
    logger.info("Test Case 3 PASSED.")

    logger.info("--- Test Case 4: Update Existing Host (example-staging.com from 0.0.0.0 to 1.2.3.4) ---")
    with open(HostsFileEdit.HOSTS_FILE, "w", encoding="utf-8") as f:
        f.write("127.0.0.1 localhost\n::1 localhost\n0.0.0.0 example-staging.com # Old entry\n")
    logger.info(f"TC4 Hosts file before update:\n{read_hosts_file_content()}")
    
    window.entry_domain.set_text("example-staging.com")
    window.on_get_ip_button_clicked(window.button_add_ip, window.entry_domain, window.textview_status)

    status_messages_tc4 = get_textview_status_content(window)
    hosts_content_tc4 = read_hosts_file_content()
    logger.info(f"TC4 Status Messages:\n{status_messages_tc4}")
    logger.info(f"TC4 Hosts Content:\n{hosts_content_tc4}")

    expected_msgs_tc4 = [
        "Found staging IP 1.2.3.4 for example-staging.com.",
        "Attempting to add to hosts file...",
        f"Updated {HostsFileEdit.HOSTS_FILE}: Set example-staging.com to 1.2.3.4."
    ]
    current_pos = 0
    for msg in expected_msgs_tc4:
        found_pos = status_messages_tc4.find(msg, current_pos)
        assert found_pos != -1, f"TC4 FAILED: Expected message '{msg}' not found in sequence. Full log:\n{status_messages_tc4}"
        current_pos = found_pos + len(msg)
    assert "1.2.3.4 example-staging.com" in hosts_content_tc4, "TC4 FAILED: Host entry not updated to 1.2.3.4."
    assert "0.0.0.0 example-staging.com" not in hosts_content_tc4, "TC4 FAILED: Old host entry 0.0.0.0 still present."
    logger.info("Test Case 4 PASSED.")

    logger.info("--- Test Case 5: Delete Host (example-staging.com) ---")
    clear_hosts_file_for_test() 
    with open(HostsFileEdit.HOSTS_FILE, "a", encoding="utf-8") as f:
        f.write("1.2.3.4 example-staging.com\n")
    window.populate_store(window.store) 
    
    selected_idx = -1
    for i in range(window.store.get_n_items()):
        item = window.store.get_item(i)
        hostname_in_store = item.hostname.split("#")[0].strip()
        if item.ip == "1.2.3.4" and hostname_in_store == "example-staging.com":
            selected_idx = i
            break
    assert selected_idx != -1, "TC5 Setup FAILED: Could not find '1.2.3.4 example-staging.com' in store to select."
    window.selection_model.select_item(selected_idx, True)
    
    window._item_to_delete = window.selection_model.get_selected_item()
    window._on_delete_confirmation_response(dialog=None, response_id="delete")

    status_messages_tc5 = get_textview_status_content(window)
    hosts_content_tc5 = read_hosts_file_content()
    logger.info(f"TC5 Status Messages:\n{status_messages_tc5}")
    logger.info(f"TC5 Hosts Content:\n{hosts_content_tc5}")
    
    expected_msg_tc5 = f"Successfully removed entries matching '1.2.3.4 example-staging.com' from {HostsFileEdit.HOSTS_FILE}."
    assert expected_msg_tc5 in status_messages_tc5, f"TC5 FAILED: Expected message '{expected_msg_tc5}' not found. Full log:\n{status_messages_tc5}"
    assert "1.2.3.4 example-staging.com" not in hosts_content_tc5, "TC5 FAILED: Host entry '1.2.3.4 example-staging.com' still present."
    logger.info("Test Case 5 PASSED.")

    logger.info("--- Test Case 6: Delete Non-Existent Host (example-staging.com) ---")
    assert "example-staging.com" not in read_hosts_file_content(), "TC6 Setup FAILED: example-staging.com found in hosts."
    
    # _item_to_delete should still hold the DataObject from the last successful deletion.
    # This simulates trying to delete the same logical entry again.
    if window._item_to_delete and window._item_to_delete.ip == "1.2.3.4" and window._item_to_delete.hostname.split("#")[0].strip() == "example-staging.com":
         logger.info(f"TC6: Simulating delete for already deleted item: {window._item_to_delete.ip} {window._item_to_delete.hostname.split('#')[0].strip()}")
         window._on_delete_confirmation_response(dialog=None, response_id="delete")
    else:
         # If _item_to_delete is not what we expect, this path of the test is flawed.
         # For this test, we want to ensure that calling delete on an entry that's
         # not in the hosts file (but might have been represented by a DataObject)
         # results in the correct "not found" message.
         logger.warning("TC6: _item_to_delete not as expected. Manually creating DataObject for test.")
         window._item_to_delete = DataObject("1.2.3.4", "example-staging.com") # Simulate it was selected
         window._on_delete_confirmation_response(dialog=None, response_id="delete")


    status_messages_tc6 = get_textview_status_content(window)
    hosts_content_tc6 = read_hosts_file_content()
    logger.info(f"TC6 Status Messages:\n{status_messages_tc6}")
    
    expected_msg_tc6 = f"Entry '1.2.3.4 example-staging.com' not found in {HostsFileEdit.HOSTS_FILE}. No changes made."
    assert expected_msg_tc6 in status_messages_tc6, f"TC6 FAILED: Expected message '{expected_msg_tc6}' not found. Full log:\n{status_messages_tc6}"
    assert hosts_content_tc6 == hosts_content_tc5, f"TC6 FAILED: Hosts file changed.\nExpected:\n{hosts_content_tc5}\nGot:\n{hosts_content_tc6}"
    logger.info("Test Case 6 PASSED.")

    logger.info("All simulated UI tests completed successfully.")
    app_instance.quit()

if __name__ == "__main__":
    logger.info("Test script __main__ started.")
    
    app = Adw.Application(application_id="com.github.mclellac.akamai.staging.testrunner.main")
    app.connect("activate", run_all_tests) # Pass the app instance to run_all_tests
    
    exit_status = app.run(sys.argv)
    
    if exit_status == 0:
        logger.info("Test script finished successfully (exit code 0).")
        print("TEST_SCRIPT_SUCCESS")
    else:
        logger.error(f"Test script finished with errors (exit code {exit_status}).")
        print(f"TEST_SCRIPT_FAILURE: Exit code {exit_status}")
    sys.exit(exit_status)
