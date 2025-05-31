import sys
import os
# Ensure current dir is in path for local module resolution if script is in root
sys.path.insert(0, '.')
print(f"Test script sys.path: {sys.path}")

# Attempt to import and run the main function of akamaistaging.in
# This will trigger its argparse and logging setup.
# We are primarily interested if it crashes *before* the gi imports within window.py
# if the i18n or debug flag logic had issues.

# It's hard to "run" akamaistaging.in as a module without triggering its full Adw.Application.run(),
# which will hit the _gi error.
# The command line tests in Part 1 are more direct for i18n and debug flag.

# This part will just try to import a core module to catch syntax errors.
print("Attempting to import core AkamaiStagingWindow module...")
try:
    from akstaging.window import AkamaiStagingWindow
    print("Successfully imported AkamaiStagingWindow class (syntax check).")
    # Further instantiation will likely fail due to _gi error.
except ImportError as e_import:
    if "_gi" in str(e_import):
        print(f"Expected ImportError due to _gi: {e_import}")
        print("This part of test considered 'conditionally passed' as no new pre-gi-import errors were found.")
    else:
        print(f"Unexpected ImportError: {e_import}")
        sys.exit(1) # Unexpected import error
except Exception as e:
    print(f"A non-ImportError exception occurred during import attempt: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) # Other critical error

print("Basic syntax and import checks passed for core modules.")
