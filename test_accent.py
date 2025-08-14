#!/usr/bin/env python
import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class MinimalApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = Adw.ApplicationWindow(application=self)
            self.window.set_title("Accent Color Test")
            self.window.set_default_size(300, 200)

            # The button that should be accent-colored
            button = Gtk.Button(label="Test Button")
            button.set_css_classes(["suggested-action"])

            # CORRECTED: Use set_content() for Adw.ApplicationWindow
            self.window.set_content(button)

        self.window.present()


if __name__ == "__main__":
    app = MinimalApp(application_id="com.example.AccentTest")
    app.run(sys.argv)
