#!/usr/bin/env python3
import sys
import os

# Get the real path of the script (resolving symlinks)
script_dir = os.path.dirname(os.path.realpath(__file__))

# Add the src directory to the python path
sys.path.insert(0, os.path.join(script_dir, 'src'))

if __name__ == "__main__":
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    import main
    
    app = main.SimpleNotes_GTK()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()
