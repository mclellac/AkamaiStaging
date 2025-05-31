# akstaging/aklib.py
import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def sanitize_domain(domain: str) -> str:
    """
    Sanitizes the given domain by removing URL schemes and any paths.

    Args:
        domain (str): The domain to be sanitized.

    Returns:
        str: The sanitized domain.
    """
    sanitized_domain = (
        domain.replace("http://", "").replace("https://", "").split("/")[0]
    )
    return sanitized_domain


def print_to_textview(widget, message):
    """
    Prints a message to the specified widget.

    Args:
        widget (Gtk.TextView): The widget to print the message to.
        message (str): The message to be printed.

    Raises:
        ValueError: If the widget type is not supported.
    """
    if isinstance(widget, Gtk.TextView):
        text_buffer = widget.get_buffer()
        end_iter = text_buffer.get_end_iter()
        text_buffer.insert(end_iter, message + "\n")
    else:
        raise ValueError(f"Unsupported widget type: {type(widget)}")
