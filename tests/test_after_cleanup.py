import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio, GLib
import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG)

sys.path.insert(0, '.')
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
    sys.exit(1)
except Exception as e_gen_import:
    print(f"Unexpected error during import of AkamaiStagingWindow: {e_gen_import}")
    sys.exit(1)

class DummyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("DummyApp initialized.")

def main():
    print("main(): Creating DummyApp...")
    app = DummyApp(application_id="com.github.mclellac.AkamaiStaging.TestAfterCleanup")

    print("main(): Attempting to instantiate AkamaiStagingWindow...")
    try:
        window = AkamaiStagingWindow(application=app)
        print("main(): AkamaiStagingWindow instantiated successfully.")
        print("Test PASSED (Window Instantiated after comment cleanup and minor functional tweaks).")
    except Exception as e:
        print(f"main(): Error during AkamaiStagingWindow instantiation: {e}")
        import traceback
        traceback.print_exc()
        print("Test FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
