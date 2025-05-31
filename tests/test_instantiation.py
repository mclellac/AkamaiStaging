import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio, GLib
import sys
import os

# Add current directory to path for local module imports
sys.path.insert(0, '.')

# Attempt to load the resource bundle.
# This is crucial. If this fails, the Gtk.Template will fail.
# Assuming the .gresource file is in the 'akstaging' directory for local testing.
gresource_file = "akstaging/akamaistaging.gresource"

if not os.path.exists(gresource_file):
    print(f"CRITICAL: Resource file '{gresource_file}' not found. "
          "This test cannot proceed meaningfully as UI components will not load. "
          "Ensure the project is built (e.g., with Meson) and the .gresource file is available.")
    sys.exit(1) # Exit, as the test is otherwise meaningless.

try:
    resource = Gio.Resource.load(gresource_file)
    Gio.resources_register(resource)
    print(f"Successfully loaded and registered resource: {gresource_file}")
except GLib.Error as e:
    print(f"Failed to load or register resource '{gresource_file}': {e}. "
          "This test cannot proceed meaningfully.")
    sys.exit(1)

# Now that resources are supposedly loaded, import the window class.
from akstaging.window import AkamaiStagingWindow

# Dummy Application class for the window
class DummyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

def main():
    app = DummyApp(application_id="com.github.mclellac.AkamaiStaging.Test")

    print("Attempting to instantiate AkamaiStagingWindow...")
    try:
        # The AkamaiStagingWindow constructor calls _verify_ui_elements internally.
        window = AkamaiStagingWindow(application=app)
        print("AkamaiStagingWindow instantiated successfully.")
        print("Startup error checks (Gtk-CRITICAL, Assertions in _verify_ui_elements) passed.")
    except Exception as e:
        print(f"Error during AkamaiStagingWindow instantiation: {e}")
        import traceback
        traceback.print_exc()
        print("Test FAILED.")
        sys.exit(1)

    print("Test PASSED.")

if __name__ == "__main__":
    main()
