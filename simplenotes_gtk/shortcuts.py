import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from .dialogs import UIHelpers


ACTIONS = [
    ("save", "Save"),
    ("undo", "Undo"),
    ("redo", "Redo"),
    ("n_txt", "New Text"),
    ("n_todo", "New To-Do"),
    ("find", "Find"),
    ("switch_note", "Quick Swap"),
]


class ShortcutManager:
    def __init__(self, window, config, save_btn, action_callbacks):
        self.window = window
        self.config = config
        self.save_btn = save_btn
        self.actions = action_callbacks
        self.accel = None
        self.sc_store = None

    def build_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, border_width=20)
        self.sc_store = Gtk.ListStore(str, str, str, int, int)

        for a_id, d_n in ACTIONS:
            a_s = self.config.get("binds").get(a_id, "")
            k, m = Gtk.accelerator_parse(a_s) if a_s else (0, 0)
            self.sc_store.append([a_id, d_n, a_s, k, m])

        tree = Gtk.TreeView(model=self.sc_store)
        tree.append_column(Gtk.TreeViewColumn("Action", Gtk.CellRendererText(), text=1))
        rnd_a = Gtk.CellRendererAccel(editable=True)
        rnd_a.connect("accel-edited", self._on_accel_edited)
        rnd_a.connect("accel-cleared", self._on_accel_cleared)
        tree.append_column(Gtk.TreeViewColumn("Shortcut", rnd_a, accel_key=3, accel_mods=4))
        box.pack_start(tree, True, True, 0)

        reset_btn = Gtk.Button(label="Reset to Defaults", margin_top=10)
        reset_btn.connect("clicked", self.reset)
        box.pack_start(reset_btn, False, False, 0)

        return box

    def exec_bind(self, a_id):
        if a_id in self.actions:
            GLib.idle_add(self.actions[a_id])
            return True
        return False

    def reload(self):
        if self.accel:
            self.window.remove_accel_group(self.accel)
        self.accel = Gtk.AccelGroup()
        self.window.add_accel_group(self.accel)

        for a_id, a_s in self.config.get("binds").items():
            if not a_s or a_id == "switch_note":
                continue
            k, m = Gtk.accelerator_parse(a_s)
            if a_id == "save":
                self.save_btn.add_accelerator("clicked", self.accel, k, m, Gtk.AccelFlags.VISIBLE)
            else:
                self.accel.connect(k, m, Gtk.AccelFlags.VISIBLE,
                                   lambda _g, _w, _k, _m, a=a_id: self.exec_bind(a))

    def reset(self, *args):
        if UIHelpers.confirm(self.window, "Reset all shortcuts to defaults?"):
            defaults = self.config.DEFAULT_CONFIG["binds"].copy()
            self.config.set("binds", defaults)
            self.reload()
            self._refresh_store()

    def _refresh_store(self):
        if not self.sc_store:
            return
        self.sc_store.clear()
        for a_id, d_n in ACTIONS:
            a_s = self.config.get("binds").get(a_id, "")
            k, m = Gtk.accelerator_parse(a_s) if a_s else (0, 0)
            self.sc_store.append([a_id, d_n, a_s, k, m])

    def _on_accel_edited(self, rnd, path, key, mods, hw):
        it = self.sc_store.get_iter(path)
        a_id, a_s = self.sc_store[it][0], Gtk.accelerator_name(key, mods)
        self.sc_store[it][2], self.sc_store[it][3], self.sc_store[it][4] = a_s, key, mods
        binds = self.config.get("binds")
        binds[a_id] = a_s
        self.config.set("binds", binds)
        self.reload()

    def _on_accel_cleared(self, rnd, path):
        it = self.sc_store.get_iter(path)
        self.sc_store[it][2], self.sc_store[it][3], self.sc_store[it][4] = "", 0, 0
        binds = self.config.get("binds")
        binds[self.sc_store[it][0]] = ""
        self.config.set("binds", binds)
        self.reload()
