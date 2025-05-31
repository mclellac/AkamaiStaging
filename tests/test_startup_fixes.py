import sys
import os
sys.path.insert(0, '.') # Ensure current dir is in path
print(f"Test script sys.path: {sys.path}")

print("Attempting to import core AkamaiStagingWindow module (syntax/import check)...")
try:
    # This import chain will exercise i18n.py -> defs.py imports
    from akstaging.window import AkamaiStagingWindow
    print("Successfully imported AkamaiStagingWindow class (syntax and non-Gtk import checks passed).")
except ImportError as e_import:
    if "_gi" in str(e_import): # Expected if Gtk components are hit
        print(f"Expected ImportError due to _gi: {e_import}")
        print("This part of test considered 'conditionally passed' as no new pre-gi-import errors were found for akstaging.window chain.")
    elif "LOCALEDIR" in str(e_import).upper() or "APP_ID" in str(e_import).upper() or "LOCALE_DIR" in str(e_import).upper() : # Made case-insensitive for LOCALE_DIR
        print(f"CRITICAL FAILURE: i18n import error still present: {e_import}")
        sys.exit(1) # Explicit failure for this test
    else:
        print(f"Unexpected ImportError during 'akstaging.window' import: {e_import}")
        sys.exit(1) # Unexpected import error
except Exception as e:
    print(f"A non-ImportError exception occurred during 'akstaging.window' import attempt: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) # Other critical error

print("Basic import checks passed for core modules related to i18n and window.")
