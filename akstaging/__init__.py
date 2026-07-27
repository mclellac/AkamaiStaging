VERBOSE = True
APP_NAME = "Akamai Staging"
APP_ID = "com.github.mclellac.AkamaiStaging"

import os
import sys
from typing import Any

_build_akstaging = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "akstaging"))
if os.path.exists(_build_akstaging) and _build_akstaging not in __path__:
    __path__.append(_build_akstaging)


def setup_gsettings_schema_dirs() -> None:
    """Configures GSETTINGS_SCHEMA_DIR and XDG_DATA_DIRS for macOS and custom install paths."""
    candidate_schema_dirs = [
        "/opt/homebrew/share/glib-2.0/schemas",
        "/usr/local/share/glib-2.0/schemas",
        "/usr/share/glib-2.0/schemas",
        os.path.expanduser("~/.local/share/glib-2.0/schemas"),
    ]
    candidate_xdg_dirs = [
        "/opt/homebrew/share",
        "/usr/local/share",
        "/usr/share",
        os.path.expanduser("~/.local/share"),
    ]

    try:
        from akstaging.defs import DATA_DIR

        if DATA_DIR:
            schema_path = os.path.join(DATA_DIR, "glib-2.0", "schemas")
            if schema_path not in candidate_schema_dirs:
                candidate_schema_dirs.insert(0, schema_path)
            if DATA_DIR not in candidate_xdg_dirs:
                candidate_xdg_dirs.insert(0, DATA_DIR)
    except Exception:
        pass

    # 1. Update GSETTINGS_SCHEMA_DIR
    valid_schema_dirs = [d for d in candidate_schema_dirs if os.path.isdir(d)]
    curr_schema_env = os.environ.get("GSETTINGS_SCHEMA_DIR", "")
    curr_schema_list = curr_schema_env.split(os.pathsep) if curr_schema_env else []
    for sdir in valid_schema_dirs:
        if sdir not in curr_schema_list:
            curr_schema_list.insert(0, sdir)
    if curr_schema_list:
        os.environ["GSETTINGS_SCHEMA_DIR"] = os.pathsep.join(curr_schema_list)

    # 2. Update XDG_DATA_DIRS
    valid_xdg_dirs = [d for d in candidate_xdg_dirs if os.path.isdir(d)]
    curr_xdg_env = os.environ.get("XDG_DATA_DIRS", "")
    curr_xdg_list = curr_xdg_env.split(os.pathsep) if curr_xdg_env else []
    for xdir in valid_xdg_dirs:
        if xdir not in curr_xdg_list:
            curr_xdg_list.append(xdir)
    if curr_xdg_list:
        os.environ["XDG_DATA_DIRS"] = os.pathsep.join(curr_xdg_list)


setup_gsettings_schema_dirs()


def get_gio_settings(settings_id: str) -> Any:
    """Retrieves a Gio.Settings object, with fallback schema source lookup if default lookup fails."""
    setup_gsettings_schema_dirs()
    from gi.repository import Gio

    try:
        return Gio.Settings.new(settings_id)
    except Exception:
        # Fallback: attempt to load schema source directly from candidate directories
        schema_dirs = os.environ.get("GSETTINGS_SCHEMA_DIR", "").split(os.pathsep)
        parent_source = Gio.SettingsSchemaSource.get_default()
        for sdir in schema_dirs:
            if sdir and os.path.isdir(sdir):
                try:
                    source = Gio.SettingsSchemaSource.new_from_directory(sdir, parent_source, False)
                    schema = source.lookup(settings_id, False)
                    if schema:
                        return Gio.Settings.new_full(schema, None, None)
                    parent_source = source
                except Exception:
                    pass
        raise
