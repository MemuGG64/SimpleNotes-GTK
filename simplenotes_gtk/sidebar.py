import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango
from .dialogs import UIHelpers


class Sidebar:
    def __init__(self, file_ops, config_manager, search_entry, callbacks):
        self.file_ops = file_ops
        self.config = config_manager
        self.search_entry = search_entry
        self.cb = callbacks

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.pack_start(self.search_entry, False, False, 0)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)

        ls_scroll = Gtk.ScrolledWindow(min_content_width=200)
        self.listbox = Gtk.ListBox()
        self.listbox.connect("button-press-event", self._on_click)
        self.listbox.connect("key-press-event", self._pass_wm_keys)
        ls_scroll.add(self.listbox)

        tr_scroll = Gtk.ScrolledWindow()
        self.tree = Gtk.TreeView(model=Gtk.TreeStore(str, str, str), headers_visible=False)
        self.tree.connect("key-press-event", self._pass_wm_keys)
        col = Gtk.TreeViewColumn()
        rnd_i = Gtk.CellRendererPixbuf()
        rnd_t = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END)
        col.pack_start(rnd_i, False)
        col.add_attribute(rnd_i, "icon-name", 0)
        col.pack_start(rnd_t, True)
        col.add_attribute(rnd_t, "text", 1)
        self.tree.append_column(col)
        self.tree.connect("button-press-event", self._on_click)
        tr_scroll.add(self.tree)

        self.stack.add_named(ls_scroll, "list")
        self.stack.add_named(tr_scroll, "tree")
        self.stack.set_visible_child_name(self.config.get("view"))
        self.box.pack_start(self.stack, True, True, 0)

    def refresh(self):
        for r in list(self.listbox.get_children()):
            self.listbox.remove(r)
        store = self.tree.get_model()
        store.clear()

        files, all_fol = self.file_ops.list_files(self.search_entry.get_text())
        sm = self.config.get("sort")
        files.sort(key=lambda t: (
            "0_" if (sm == "text_first" and not t["is_todo"]) or (sm == "lists_first" and t["is_todo"])
            else "1_") + t["name"].lower()
        )
        new_fo = [f for f in self.config.get("fol_order") if f in all_fol]
        for f in all_fol:
            if f not in new_fo:
                new_fo.append(f)
        if new_fo != self.config.get("fol_order"):
            self.config.set("fol_order", new_fo)

        def _ico(name): return UIHelpers.make_icon(name, self.config.get("symbolic_icons", True))

        def add_grp(title, items, icon, tree_p=None):
            if not items and icon in ("bookmark-new-symbolic", "folder-symbolic"):
                return
            hdr = Gtk.Box(spacing=6, margin=10)
            hdr.pack_start(_ico(icon), False, False, 0)
            hdr.pack_start(Gtk.Label(label=f"<b>{title}</b>", use_markup=True, xalign=0), True, True, 0)
            row = Gtk.ListBoxRow(selectable=False)
            row.add(hdr)
            row.fol_name = title
            self.listbox.add(row)
            t_it = store.append(tree_p, [icon, title, ""]) if tree_p is None else tree_p
            for item in items:
                p, n, is_t = item["path"], item["name"], item["is_todo"]
                icn = "emblem-ok-symbolic" if is_t else "text-x-generic-symbolic"
                b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, border_width=5)
                b.pack_start(_ico(icn), False, False, 0)
                b.pack_start(Gtk.Label(label=n, xalign=0, ellipsize=Pango.EllipsizeMode.END), True, True, 0)
                if p in self.config.get("pinned"):
                    b.pack_end(_ico("bookmark-new-symbolic"), False, False, 0)
                lr = Gtk.ListBoxRow()
                lr.add(b)
                lr.filepath = p
                self.listbox.add(lr)
                store.append(t_it, [icn, n, p])

        pinned_p = self.config.get("pinned")
        add_grp("Pinned", [f for f in files if f["path"] in pinned_p], "bookmark-new-symbolic")
        add_grp("Root", [f for f in files if f["path"] not in pinned_p and f["folder"] == "Root"], "folder-symbolic")
        if self.config.get("folders"):
            for fol in self.config.get("fol_order"):
                items = [f for f in files if f["path"] not in pinned_p and f["folder"] == fol]
                if items:
                    add_grp(fol, items, "folder-symbolic")
        else:
            add_grp("Notes", [f for f in files if f["path"] not in pinned_p], "folder-symbolic")
        self.listbox.show_all()
        self.tree.expand_all()

    @staticmethod
    def _pass_wm_keys(widget, event):
        if event.state & Gdk.ModifierType.SUPER_MASK and event.keyval in (
            Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down
        ):
            return True
        return False

    def _on_click(self, widget, event):
        if event.button == 1:
            self._left_click(widget, event)
        elif event.button == 3:
            self._right_click(widget, event)

    def _left_click(self, widget, event):
        if isinstance(widget, Gtk.TreeView):
            path_info = widget.get_path_at_pos(int(event.x), int(event.y))
            if not path_info:
                return
            path, col, x, y = path_info
            model = widget.get_model()
            if not path:
                return
            filepath = model[path][2]
            if filepath:
                if filepath != self.cb["get_current_path"]():
                    self.cb["open_file"](filepath)
                elif self.cb["is_settings_visible"]():
                    self.cb["show_note_view"]()
            else:
                if widget.row_expanded(path):
                    widget.collapse_row(path)
                else:
                    widget.expand_row(path, False)
        elif isinstance(widget, Gtk.ListBox):
            r = widget.get_row_at_y(int(event.y))
            if not r or not hasattr(r, 'filepath'):
                return
            if r.filepath != self.cb["get_current_path"]():
                self.cb["open_file"](r.filepath)
            elif self.cb["is_settings_visible"]():
                self.cb["show_note_view"]()

    def _right_click(self, widget, event):
        r_path = r_fol = None
        if isinstance(widget, Gtk.TreeView):
            path_info = widget.get_path_at_pos(int(event.x), int(event.y))
            if path_info:
                path, col, x, y = path_info
                model = widget.get_model()
                r_path = model[path][2]
                if not r_path:
                    r_fol = model[path][1]
        else:
            r = widget.get_row_at_y(int(event.y))
            if not r:
                return
            r_path = getattr(r, 'filepath', None)
            r_fol = getattr(r, 'fol_name', None)

        m = Gtk.Menu()
        if r_path:
            mi1 = Gtk.MenuItem(label="Rename")
            mi1.connect("activate", lambda _: self.cb["rename_file"](r_path))
            m.append(mi1)

            mi_move = Gtk.MenuItem(label="Move to Folder")
            mi_move.connect("activate", lambda _: self.cb["move_note"](r_path))
            m.append(mi_move)

            m_ext = Gtk.Menu()
            mi_ext = Gtk.MenuItem(label="Save As / Format")
            for ext in [".txt", ".md", ".json"]:
                if not r_path.endswith(ext):
                    mi = Gtk.MenuItem(label=f"Convert to {ext}")
                    mi.connect("activate", lambda _, e=ext, p=r_path: self.cb["change_ext"](p, e))
                    m_ext.append(mi)
            if m_ext.get_children():
                mi_ext.set_submenu(m_ext)
                m.append(mi_ext)

            mi2 = Gtk.MenuItem(label="Delete")
            mi2.connect("activate", lambda _: self.cb["delete_note"](path_override=r_path))
            m.append(mi2)

        elif r_fol and r_fol not in ["Root", "Notes", "Pinned", ""]:
            mi1 = Gtk.MenuItem(label="Rename")
            mi1.connect("activate", lambda _: self.cb["rename_folder"](r_fol))
            m.append(mi1)

            mi2 = Gtk.MenuItem(label="Delete")
            mi2.connect("activate", lambda _: self.cb["delete_folder"](r_fol))
            m.append(mi2)

            if not isinstance(widget, Gtk.TreeView):
                m.append(Gtk.SeparatorMenuItem())
                for lbl, step in [("Move Up", -1), ("Move Down", 1)]:
                    mi = Gtk.MenuItem(label=lbl)
                    mi.connect("activate", lambda _, s=step: self.cb["reorder_fol"](r_fol, s))
                    m.append(mi)

        if m.get_children():
            m.show_all()
            m.popup_at_pointer(event)

    def toggle(self, window, pos_x, pos_y, w, h):
        if self.box.get_visible():
            self.box.hide()
        else:
            self.box.show()

    def set_view_mode(self, mode):
        self.stack.set_visible_child_name(mode)
