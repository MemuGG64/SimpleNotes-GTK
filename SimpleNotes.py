#!/usr/bin/env python3
import logging
import sys

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

if __name__ == "__main__":
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
    except (ImportError, ValueError) as e:
        if sys.platform == "darwin":
            print("=" * 60)
            print("  SimpleNotes-GTK requires GTK3 and PyGObject.")
            print()
            print("  Install via Homebrew:")
            print("    brew install gtk+3 pygobject3")
            print()
            print("  Then run: python3 SimpleNotes.py")
            print("=" * 60)
        else:
            print(f"Error: GTK3 not available. {e}")
            print("Install: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0")
        sys.exit(1)

    from simplenotes_gtk.main import SimpleNotes_GTK

    app = SimpleNotes_GTK()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()
