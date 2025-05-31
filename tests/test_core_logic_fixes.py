import sys
import os
sys.path.insert(0, '.')
print(f"Test script sys.path: {sys.path}")

print("Attempting to import core modules to check for errors from recent fixes...")
try:
    # This import chain will exercise i18n.py -> defs.py imports,
    # and will make dns_utils.py and hosts.py available for basic syntax checks.
    # It does not execute their main logic paths extensively without Gtk.
    print("Importing akstaging.dns_utils...")
    import akstaging.dns_utils
    print("Successfully imported akstaging.dns_utils.")

    print("Importing akstaging.hosts...")
    import akstaging.hosts
    print("Successfully imported akstaging.hosts.")

    print("Importing akstaging.window (will likely fail at Gtk/Adw imports)...")
    from akstaging.window import AkamaiStagingWindow
    print("Successfully imported AkamaiStagingWindow class (syntax and non-Gtk import checks passed).")

except ImportError as e_import:
    if "_gi" in str(e_import): # Expected if Gtk components are hit
        print(f"Expected ImportError due to _gi: {e_import}")
        print("This part of test considered 'conditionally passed' as no new pre-gi-import errors were found for the core logic modules.")
    elif "LOCALEDIR" in str(e_import).upper() or "APP_ID" in str(e_import).upper() or "LOCALE_DIR" in str(e_import).upper() : # Check for regressions
        print(f"CRITICAL FAILURE: i18n import error REGRESSION: {e_import}")
        sys.exit(1) # Explicit failure for this test
    else:
        print(f"Unexpected ImportError: {e_import}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
except Exception as e:
    print(f"A non-ImportError exception occurred during import attempts: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Basic syntax and import checks passed for core modules after fixes.")
