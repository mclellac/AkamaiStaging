# akstaging/i18n.py
import ctypes
import gettext
import locale
import os
import sys

try:
    from akstaging.defs import APP_ID, LOCALE_DIR
except ImportError as e:
    print(f"CRITICAL: Could not import APP_ID/LOCALE_DIR from akstaging.defs for i18n setup: {e}", file=sys.stderr)
    APP_ID = "com.github.mclellac.AkamaiStaging.fallback"
    LOCALE_DIR = "/usr/local/share/locale"

_current_translation = None
_translation_func = gettext.gettext


def set_language(lang_str: str = "system"):
    """Sets the active application language ('system', 'en', 'fr') across Python gettext and C GLib/GTK textdomains."""
    global _translation_func, _current_translation

    if lang_str == "en":
        os.environ["LANGUAGE"] = "en_US:en"
        os.environ["LC_ALL"] = "en_US.UTF-8"
        languages = ["en"]
        c_locales = [b"en_US.UTF-8", b"en_US.utf8", b"en"]
    elif lang_str == "fr":
        os.environ["LANGUAGE"] = "fr_CA:fr"
        os.environ["LC_ALL"] = "fr_CA.UTF-8"
        languages = ["fr", "fr_CA"]
        c_locales = [b"fr_CA.UTF-8", b"fr_CA.utf8", b"fr_FR.UTF-8", b"fr"]
    else:
        os.environ.pop("LANGUAGE", None)
        os.environ.pop("LC_ALL", None)
        languages = None
        c_locales = [b""]

    # Bind C GLib/GTK gettext textdomains so GtkBuilder template widgets translate properly
    search_dirs = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "po")),
        LOCALE_DIR,
    ]

    try:
        libc = ctypes.CDLL(None)
        # LC_ALL on POSIX/Linux is 6
        for c_loc in c_locales:
            try:
                res = libc.setlocale(6, c_loc)
                if res is not None:
                    break
            except Exception:
                continue

        bindtextdomain = libc.bindtextdomain
        bindtextdomain.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        for domain in ["akamaistaging", APP_ID]:
            for ldir in search_dirs:
                if os.path.exists(ldir):
                    bindtextdomain(domain.encode("utf-8"), ldir.encode("utf-8"))

        libc.textdomain(b"akamaistaging")
    except Exception as e:
        print(f"Warning: Could not bind C libc textdomain: {e}", file=sys.stderr)

    # Set Python gettext
    domains = ["akamaistaging", APP_ID]
    found_translation = None
    for domain in domains:
        for ldir in search_dirs:
            if os.path.exists(ldir):
                try:
                    t = gettext.translation(
                        domain, localedir=ldir, languages=languages, fallback=False if languages else True
                    )
                    if t:
                        found_translation = t
                        break
                except Exception:
                    continue
        if found_translation:
            break

    if not found_translation:
        try:
            found_translation = gettext.translation(
                "akamaistaging", localedir=LOCALE_DIR, languages=languages, fallback=True
            )
        except Exception:
            found_translation = gettext.NullTranslations()

    _current_translation = found_translation
    _translation_func = found_translation.gettext
    try:
        found_translation.install()
    except Exception:
        pass


try:
    try:
        locale.setlocale(locale.LC_ALL, "")
    except Exception:
        pass
    set_language("system")
except Exception as e:
    print(f"Error initializing i18n: {e}", file=sys.stderr)


def get_translator():
    """Returns the configured translator instance."""
    return lambda msg: _translation_func(msg)
