import gi
# Attempt to set Gtk and Adw versions early.
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio, GLib
import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG) # Enable debug logging

sys.path.insert(0, '.') # Add current directory to path
print(f"Python sys.path: {sys.path}")

gresource_file = "akstaging/akamaistaging.gresource"

if not os.path.exists(gresource_file):
    print(f"CRITICAL: Resource file '{gresource_file}' not found.")
    sys.exit(1)

try:
    print(f"Attempting to load and register resource: {gresource_file}")
    resource = Gio.Resource.load(gresource_file)
    Gio.resources_register(resource)
    print(f"Successfully loaded and registered resource: {gresource_file}")
except GLib.Error as e:
    print(f"Failed to load or register resource '{gresource_file}': {e}.")
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
    print("This is likely due to the persistent 'gi._gi' import error.")
    sys.exit(1) # Exit if core import fails
except Exception as e_gen_import:
    print(f"Unexpected error during import of AkamaiStagingWindow: {e_gen_import}")
    sys.exit(1)

class DummyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("DummyApp initialized.")

def main():
    print("main(): Creating DummyApp...")
    app = DummyApp(application_id="com.github.mclellac.AkamaiStaging.TestUIRefactor")

    print("main(): Attempting to instantiate AkamaiStagingWindow...")
    try:
        window = AkamaiStagingWindow(application=app)
        print("main(): AkamaiStagingWindow instantiated successfully.")
        # Check if the newly re-added buttons are bound (they should be, as IDs were preserved)
        if not window.button_delete:
            print("ERROR: button_delete is not bound after UI changes.")
            sys.exit(1)
        if not window.button_edit_host:
            print("ERROR: button_edit_host is not bound after UI changes.")
            sys.exit(1)
        print("main(): button_delete and button_edit_host appear to be bound.")
        print("Test PASSED (Window Instantiated, basic checks for re-added buttons passed).")
    except Exception as e:
        print(f"main(): Error during AkamaiStagingWindow instantiation: {e}")
        import traceback
        traceback.print_exc()
        print("Test FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
