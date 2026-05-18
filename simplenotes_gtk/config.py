import os
import json
import sys
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


def get_config_dir():
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/SimpleNotes-GTK")
    return os.path.expanduser("~/.config")


class ConfigManager:
    DEFAULT_CONFIG = {
        "dir": os.path.expanduser("~/Documents/SimpleNotes-GTK"),
        "autosave": "30",
        "search": False,
        "sort": "text_first",
        "folders": True,
        "view": "list",
        "pinned": [],
        "fol_order": [],
        "default_ext": ".txt",
        "symbolic_icons": True,
        "auto_update": True,
        "width": 950,
        "height": 650,
        "binds": {
            "save": "<Primary>s",
            "undo": "<Primary>z",
            "redo": "<Primary>y",
            "n_txt": "<Primary>n",
            "n_todo": "<Primary>t",
            "find": "<Primary>f",
            "switch_note": "<Primary>bar"
        }
    }

    def __init__(self, settings_file=None):
        if settings_file is None:
            self.settings_file = os.path.join(get_config_dir(), "sng_config.json")
        else:
            self.settings_file = settings_file
        self.conf = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    if "binds" in data:
                        self.conf["binds"].update(data.pop("binds"))
                    self.conf.update(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}")

    def save(self):
        try:
            Path(self.settings_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.conf, f, indent=4)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.conf.get(key, default)

    def set(self, key, val):
        self.conf[key] = val
        self.save()

    def update(self, data):
        self.conf.update(data)
        self.save()

    @property
    def notes_dir(self):
        return self.conf["dir"]

    def build_ui(self, callbacks):
        def add_opt(box, txt, desc, w, k=None, is_sw=False, ref=False):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            txt_b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            txt_b.pack_start(Gtk.Label(label=txt, use_markup=True, xalign=0), False, False, 0)
            txt_b.pack_start(Gtk.Label(label=f"<small>{desc}</small>", use_markup=True, xalign=0, opacity=0.7), False, False, 0)
            row.pack_start(txt_b, True, True, 0)
            row.pack_start(w, False, False, 0)
            box.pack_start(row, False, False, 10)
            if k:
                if is_sw:
                    w.set_active(self.get(k))
                    w.connect("notify::active", lambda s, p: callbacks["on_config_changed"](k, s.get_active(), ref))
                else:
                    w.set_active_id(self.get(k))
                    w.connect("changed", lambda c: callbacks["on_config_changed"](k, c.get_active_id(), ref))

        def _page(box):
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sw.add(box)
            return sw

        nb = Gtk.Notebook(border_width=10)

        b_gen = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, border_width=20)
        fc = Gtk.FileChooserButton(title="Select Folder", action=Gtk.FileChooserAction.SELECT_FOLDER)
        fc.set_current_folder(self.get("dir"))
        fc.connect("selection-changed", lambda c: callbacks["on_config_changed"]("dir", c.get_filename(), True) if c.get_filename() else None)
        add_opt(b_gen, "<b>Notes Directory:</b>", "Path where notes are stored.", fc)
        sw_is = Gtk.Switch()
        add_opt(b_gen, "Symbolic Icons:", "Use monochrome icons.", sw_is, "symbolic_icons", True, True)
        sw_au = Gtk.Switch()
        add_opt(b_gen, "Check for Updates:", "Automatically check GitHub for new versions.", sw_au, "auto_update", True, True)
        nb.append_page(_page(b_gen), Gtk.Label(label="General"))

        b_beh = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, border_width=20)
        cb_auto = Gtk.ComboBoxText()
        for k, v in [("off", "Off"), ("30", "30s"), ("60", "60s"), ("300", "5m")]:
            cb_auto.append(k, v)
        add_opt(b_beh, "Autosave:", "Save changes automatically.", cb_auto, "autosave")

        sw_s = Gtk.Switch()
        add_opt(b_beh, "Deep Search:", "Search inside notes.", sw_s, "search", True, True)
        cb_v = Gtk.ComboBoxText()
        for k, v in [("list", "Flat List"), ("tree", "Tree View")]:
            cb_v.append(k, v)
        add_opt(b_beh, "Sidebar Layout:", "View mode.", cb_v, "view")
        sw_f = Gtk.Switch()
        add_opt(b_beh, "Group by Folders:", "Show subdirectories.", sw_f, "folders", True, True)
        b_beh.pack_start(Gtk.Separator(), False, False, 5)

        cb_ext = Gtk.ComboBoxText()
        for k, v in [(".txt", "Text (.txt)"), (".md", "Markdown (.md)"), (".json", "Checklist (.json)")]:
            cb_ext.append(k, v)
        add_opt(b_beh, "<b>Default Format:</b>", "Extension for new notes.", cb_ext, "default_ext")

        conv_btn = Gtk.Button(label="Convert Folder to Default Format", margin_top=5)
        conv_btn.connect("clicked", lambda x: callbacks["convert_folder"]())
        b_beh.pack_start(conv_btn, False, False, 0)
        nb.append_page(_page(b_beh), Gtk.Label(label="Behavior"))

        return nb
