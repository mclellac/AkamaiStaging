# akstaging/i18n.py
import gettext
import locale
import sys


try:
    from akstaging.defs import APP_ID, LOCALE_DIR
except ImportError as e:
    print(f"CRITICAL: Could not import APP_ID/LOCALE_DIR from akstaging.defs for i18n setup: {e}", file=sys.stderr)
    APP_ID = "com.github.mclellac.AkamaiStaging.fallback"
    LOCALE_DIR = "/app/share/locale"

_translation_func = gettext.gettext

try:
    locale.setlocale(locale.LC_ALL, '')
    translation = gettext.translation(APP_ID, localedir=LOCALE_DIR, fallback=True)
    _translation_func = translation.gettext
except Exception as e:
    app_id_for_error_msg = APP_ID if 'APP_ID' in locals() else "undefined"
    locale_dir_for_error_msg = LOCALE_DIR if 'LOCALE_DIR' in locals() else "undefined"
    print(f"Error setting up gettext for APPID '{app_id_for_error_msg}' in LOCALE_DIR '{locale_dir_for_error_msg}': {e}", file=sys.stderr)

def get_translator():
    """Returns the configured translator instance."""
    return _translation_func
