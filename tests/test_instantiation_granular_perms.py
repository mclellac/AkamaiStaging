import gi
# Attempt to set Gtk and Adw versions early, though the import error might precede this.
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio, GLib
import sys
import os
import logging

# Configure logging to see debug messages from hosts.py
logging.basicConfig(level=logging.DEBUG)
# Specifically enable debug logging for the 'akstaging.hosts' logger if it's named
# For now, basicConfig at DEBUG level should capture it if hosts.py uses standard logging.

# Add current directory to path for local module imports
sys.path.insert(0, '.')
print(f"Python sys.path: {sys.path}")

gresource_file = "akstaging/akamaistaging.gresource"

if not os.path.exists(gresource_file):
    print(f"CRITICAL: Resource file '{gresource_file}' not found. "
          "Ensure the project is built (e.g., with Meson) and the .gresource file is available.")
    sys.exit(1)

try:
    print(f"Attempting to load and register resource: {gresource_file}")
    resource = Gio.Resource.load(gresource_file)
    Gio.resources_register(resource)
    print(f"Successfully loaded and registered resource: {gresource_file}")
except GLib.Error as e:
    print(f"Failed to load or register resource '{gresource_file}': {e}. "
          "This test cannot proceed meaningfully.")
    sys.exit(1)
except Exception as e_res:
    print(f"Unexpected error loading resource '{gresource_file}': {e_res}")
    sys.exit(1)

print("Attempting to import AkamaiStagingWindow...")
try:
    from akstaging.window import AkamaiStagingWindow
    print("Successfully imported AkamaiStagingWindow.")
except ImportError as e_import:
    print(f"Failed to import AkamaiStagingWindow: {e_import}")
    print("This is likely due to the same 'gi._gi' import error as before.")
    sys.exit(1) # Exit if core import fails
except Exception as e_gen_import:
    print(f"Unexpected error during import of AkamaiStagingWindow: {e_gen_import}")
    sys.exit(1)


# Dummy Application class for the window
class DummyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("DummyApp initialized.")

def main():
    print("main(): Creating DummyApp...")
    app = DummyApp(application_id="com.github.mclellac.AkamaiStaging.TestGranularPerms")

    print("main(): Attempting to instantiate AkamaiStagingWindow...")
    try:
        # Instantiation will trigger _initialize_helpers (incl. hfe()),
        # then _initialize_store(), then populate_store(), which calls
        # self.hosts_editor.read_hosts_file_content_privileged()
        window = AkamaiStagingWindow(application=app)
        print("main(): AkamaiStagingWindow instantiated successfully.")
        print("main(): Startup error checks (Gtk-CRITICAL, Assertions in _verify_ui_elements) passed.")
        print("main(): The call to read_hosts_file_content_privileged within populate_store also completed without crashing.")
        # At this point, logs should indicate if direct read was attempted/succeeded/failed.
    except Exception as e:
        print(f"main(): Error during AkamaiStagingWindow instantiation: {e}")
        import traceback
        traceback.print_exc()
        print("Test FAILED.")
        sys.exit(1)

    print("Test PASSED (Window Instantiated). Check logs for read attempt details.")

if __name__ == "__main__":
    main()
