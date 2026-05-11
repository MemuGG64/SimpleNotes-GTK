#!/usr/bin/env python3
import gi
import os
import json
import time
import re
from pathlib import Path

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio, Pango

# Local imports
from config import ConfigManager
from file_operations import FileOperations
from state_manager import StateManager
from ui_helpers import UIHelpers
from note_styler import NoteStylist

# Process identity
GLib.set_prgname('simplenotes-gtk')
GLib.set_application_name('SimpleNotes-GTK')

class SimpleNotes_GTK(Gtk.Window):
    def __init__(self):
        super().__init__(title="SimpleNotes-GTK")
        self.set_icon_name("accessories-text-editor")
        self.connect("delete-event", self.on_window_delete)

        # Initialize Managers
        self.config_manager = ConfigManager()
        self.file_ops = FileOperations(self.config_manager)
        self.state_manager = StateManager()
        
        self.load_styles()

        # UI State
        self.current_path = self.timer_id = self.drag_row = self.undo_timer = None
        self.undoing = False
        self.note_history = []
        
        self.set_default_size(self.config_manager.get("width"), self.config_manager.get("height"))
        self.set_size_request(300, 250)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.setup_ui()
        self.apply_autosave()
        self.refresh_sidebar()

    def load_styles(self):
        css = Gtk.CssProvider()
        style_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'styles.css')
        try:
            css.load_from_path(style_path)
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            print(f"Warning: Could not load CSS: {e}")

    def setup_ui(self):
        hb = Gtk.HeaderBar(show_close_button=True, title="SimpleNotes-GTK")
        self.set_titlebar(hb)

        hb.pack_start(UIHelpers.create_btn("sidebar-show-symbolic", "Toggle Sidebar", self.toggle_sidebar))
        
        add_btn = Gtk.MenuButton()
        add_btn.set_image(Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        pop = Gtk.Popover()
        pop.set_relative_to(add_btn)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, border_width=10)
        for lbl, is_t in [("New Text Note", False), ("New To-Do List", True)]:
            b = Gtk.Button(label=lbl, relief=Gtk.ReliefStyle.NONE)
            b.connect("clicked", lambda x, t=is_t: [pop.hide(), GLib.timeout_add(200, self.create_file_dialog, t)])
            vb.pack_start(b, False, False, 0)
        vb.show_all(); pop.add(vb); add_btn.set_popover(pop)

        self.save_btn = UIHelpers.create_btn("document-save-symbolic", "Save", self.on_save)
        self.pin_btn = Gtk.ToggleButton()
        self.pin_btn.add(Gtk.Image.new_from_icon_name("bookmark-new-symbolic", Gtk.IconSize.BUTTON))
        self.pin_btn.connect("toggled", self.on_pin)
        
        del_btn = UIHelpers.create_btn("user-trash-symbolic", "Delete Note", self.on_delete)
        set_btn = UIHelpers.create_btn("emblem-system-symbolic", "Settings", lambda x: [self.on_save(), self.stack.set_visible_child_name("settings")])
        
        for w in (add_btn, self.save_btn, self.pin_btn, del_btn): hb.pack_start(w)
        hb.pack_end(set_btn)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search...", margin=5)
        self.search_entry.connect("search-changed", lambda x: self.refresh_sidebar())

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL); self.add(self.main_box)
        self.sb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.sb_box.pack_start(self.search_entry, False, False, 0)
        
        # Sidebar Stack Setup
        self.sidebar_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        
        ls_scroll = Gtk.ScrolledWindow(min_content_width=200)
        self.file_listbox = Gtk.ListBox()
        self.file_listbox.connect("button-press-event", self.on_sb_click)
        ls_scroll.add(self.file_listbox)
        
        tr_scroll = Gtk.ScrolledWindow()
        self.file_tree = Gtk.TreeView(model=Gtk.TreeStore(str, str, str), headers_visible=False)
        col = Gtk.TreeViewColumn()
        rnd_i, rnd_t = Gtk.CellRendererText(), Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END)
        col.pack_start(rnd_i, False); col.add_attribute(rnd_i, "text", 0)
        col.pack_start(rnd_t, True); col.add_attribute(rnd_t, "text", 1)
        self.file_tree.append_column(col)
        self.file_tree.connect("button-press-event", self.on_sb_click)
        tr_scroll.add(self.file_tree)

        self.sidebar_stack.add_named(ls_scroll, "list")
        self.sidebar_stack.add_named(tr_scroll, "tree")
        self.sidebar_stack.set_visible_child_name(self.config_manager.get("view"))
        self.sb_box.pack_start(self.sidebar_stack, True, True, 0)

        # Main Stack Setup
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(Gtk.Label(label="Select or create a note"), "empty")
        
        self.text_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, left_margin=15, right_margin=15, top_margin=15)
        self.text_view.connect("key-press-event", self.on_key_press)
        self.text_view.connect("paste-clipboard", self.on_paste)
        self.text_view.connect("populate-popup", self.on_populate_popup)
        self.connect("key-press-event", self.on_key_press)
        
        self.note_styler = NoteStylist(self.text_view, self.file_ops)
        self.text_view.get_buffer().connect("changed", self.queue_state)
        self.text_view.get_buffer().connect("mark-set", self.on_cursor_moved)
        sw_txt = Gtk.ScrolledWindow(); sw_txt.add(self.text_view)
        self.stack.add_named(sw_txt, "text")

        td_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)
        self.todo_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        td_box.pack_start(self.todo_listbox, False, False, 0)
        
        self.add_task_btn = Gtk.Button(label="+ Add Task")
        self.add_task_btn.connect("clicked", lambda x: self.add_todo().grab_focus())
        td_box.pack_start(self.add_task_btn, False, False, 0)

        self.checked_expander = Gtk.Expander(label="0 checked items")
        self.checked_expander.set_margin_top(15)
        self.checked_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.checked_expander.add(self.checked_listbox)
        td_box.pack_start(self.checked_expander, False, False, 0)

        self.todo_sw = Gtk.ScrolledWindow(); self.todo_sw.add(td_box)
        self.stack.add_named(self.todo_sw, "todo")

        self.setup_settings_ui()
        
        # Revert: Sidebar LEFT (first), Note Area RIGHT (second)
        self.main_box.pack_start(self.sb_box, False, False, 0)
        self.main_box.pack_start(self.stack, True, True, 0)
        
        self.reload_shortcuts()

    def toggle_sidebar(self, *args):
        visible = self.sb_box.get_visible()
        w, h = self.get_size()
        pos_x, pos_y = self.get_position()
        
        if visible:
            sb_w = self.sb_box.get_allocated_width()
            self.last_sb_w = sb_w
            self.sb_box.hide()
            self.move(pos_x + sb_w, pos_y)
            self.resize(max(300, w - sb_w), h)
        else:
            self.sb_box.show()
            sb_w = getattr(self, 'last_sb_w', 250)
            self.move(pos_x - sb_w, pos_y)
            self.resize(w + sb_w, h)

    def setup_settings_ui(self):
        nb = Gtk.Notebook(border_width=10)
        def add_opt(box, txt, desc, w, k=None, is_sw=False, ref=False):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            txt_b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            txt_b.pack_start(Gtk.Label(label=txt, use_markup=True, xalign=0), False, False, 0)
            txt_b.pack_start(Gtk.Label(label=f"<small>{desc}</small>", use_markup=True, xalign=0, opacity=0.7), False, False, 0)
            row.pack_start(txt_b, True, True, 0); row.pack_start(w, False, False, 0); box.pack_start(row, False, False, 10)
            if k:
                if is_sw:
                    w.set_active(self.config_manager.get(k))
                    w.connect("notify::active", lambda s, p: self.on_config_changed(k, s.get_active(), ref))
                else:
                    w.set_active_id(self.config_manager.get(k))
                    w.connect("changed", lambda c: self.on_config_changed(k, c.get_active_id(), ref))

        b_gen = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, border_width=20)
        fc = Gtk.FileChooserButton(title="Select Folder", action=Gtk.FileChooserAction.SELECT_FOLDER)
        fc.set_current_folder(self.config_manager.get("dir"))
        fc.connect("selection-changed", lambda c: self.on_config_changed("dir", c.get_filename(), True) if c.get_filename() else None)
        add_opt(b_gen, "<b>Notes Directory:</b>", "Path where notes are stored.", fc)
        nb.append_page(b_gen, Gtk.Label(label="General"))

        b_beh = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, border_width=20)
        cb_auto = Gtk.ComboBoxText()
        for k, v in [("off", "Off"), ("30", "30s"), ("60", "60s"), ("300", "5m")]: cb_auto.append(k, v)
        add_opt(b_beh, "Autosave:", "Save changes automatically.", cb_auto, "autosave")
        
        sw_s = Gtk.Switch(); add_opt(b_beh, "Deep Search:", "Search inside notes.", sw_s, "search", True, True)
        cb_v = Gtk.ComboBoxText(); [cb_v.append(k, v) for k, v in [("list", "Flat List"), ("tree", "Tree View")]]
        add_opt(b_beh, "Sidebar Layout:", "View mode.", cb_v, "view")
        sw_f = Gtk.Switch(); add_opt(b_beh, "Group by Folders:", "Show subdirectories.", sw_f, "folders", True, True)
        nb.append_page(b_beh, Gtk.Label(label="Behavior"))

        b_sc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, border_width=20); self.sc_store = Gtk.ListStore(str, str, str, int, int)
        for a_id, d_n in [("save", "Save"), ("undo", "Undo"), ("redo", "Redo"), ("n_txt", "New Text"), ("n_todo", "New To-Do"), ("find", "Find"), ("switch_note", "Quick Swap")]:
            a_s = self.config_manager.get("binds").get(a_id, ""); k, m = Gtk.accelerator_parse(a_s) if a_s else (0,0)
            self.sc_store.append([a_id, d_n, a_s, k, m])
        sc_t = Gtk.TreeView(model=self.sc_store); sc_t.append_column(Gtk.TreeViewColumn("Action", Gtk.CellRendererText(), text=1))
        rnd_a = Gtk.CellRendererAccel(editable=True); rnd_a.connect("accel-edited", self.on_accel_edited); rnd_a.connect("accel-cleared", self.on_accel_cleared)
        sc_t.append_column(Gtk.TreeViewColumn("Shortcut", rnd_a, accel_key=3, accel_mods=4))
        b_sc.pack_start(sc_t, True, True, 0)
        
        reset_btn = Gtk.Button(label="Reset to Defaults", margin_top=10)
        reset_btn.connect("clicked", self.reset_shortcuts)
        b_sc.pack_start(reset_btn, False, False, 0)
        
        nb.append_page(b_sc, Gtk.Label(label="Shortcuts"))
        self.stack.add_named(nb, "settings")

    def reset_shortcuts(self, *args):
        if UIHelpers.confirm(self, "Reset all shortcuts to defaults?"):
            defaults = self.config_manager.DEFAULT_CONFIG["binds"].copy()
            self.config_manager.set("binds", defaults)
            self.reload_shortcuts()
            self.sc_store.clear()
            for a_id, d_n in [("save", "Save"), ("undo", "Undo"), ("redo", "Redo"), ("n_txt", "New Text"), ("n_todo", "New To-Do"), ("find", "Find"), ("switch_note", "Quick Swap")]:
                a_s = self.config_manager.get("binds").get(a_id, ""); k, m = Gtk.accelerator_parse(a_s) if a_s else (0,0)
                self.sc_store.append([a_id, d_n, a_s, k, m])

    def on_config_changed(self, key, val, refresh=False):
        self.config_manager.set(key, val)
        if refresh: self.refresh_sidebar()
        if key == "autosave": self.apply_autosave()
        if key == "view": self.sidebar_stack.set_visible_child_name(val)

    def reload_shortcuts(self):
        if hasattr(self, 'accel'): self.remove_accel_group(self.accel)
        self.accel = Gtk.AccelGroup(); self.add_accel_group(self.accel)
        for a_id, a_s in self.config_manager.get("binds").items():
            if not a_s or a_id == "switch_note": continue
            k, m = Gtk.accelerator_parse(a_s)
            if a_id == "save": self.save_btn.add_accelerator("clicked", self.accel, k, m, Gtk.AccelFlags.VISIBLE)
            else: self.accel.connect(k, m, Gtk.AccelFlags.VISIBLE, lambda _g, _w, _k, _m, a=a_id: self.exec_bind(a))

    def on_window_delete(self, *args):
        w, h = self.get_size(); self.config_manager.update({"width": w, "height": h})
        self.on_save()
        return False

    def exec_bind(self, a_id):
        actions = {"n_txt": lambda: self.create_file_dialog(False), "n_todo": lambda: self.create_file_dialog(True), 
                   "find": lambda: self.search_entry.grab_focus(), "undo": self.exec_undo, "redo": self.exec_redo,
                   "switch_note": self.switch_to_last_note}
        if a_id in actions: GLib.idle_add(actions[a_id]); return True
        return False

    def on_save(self, *args):
        if not self.current_path or not os.path.exists(self.current_path): return
        if self.file_ops.is_todo(self.current_path):
            all_rows = self.todo_listbox.get_children() + self.checked_listbox.get_children()
            td = [{"dateCreated": getattr(r, 'ts', int(time.time()*1000)), "id": getattr(r, 'todo_id', i+1), "isDone": r.chk.get_active(), "title": r.ent.get_text()} for i, r in enumerate(all_rows)]
            self.file_ops.save_todo_note(self.current_path, td)
        else:
            buf = self.text_view.get_buffer()
            self.file_ops.save_text_note(self.current_path, buf.get_text(*buf.get_bounds(), True))
        if args and args[0] is not self: self.refresh_sidebar()

    def update_checked_label(self):
        count = len(self.checked_listbox.get_children())
        self.checked_expander.set_label(f"{count} checked items")
        self.checked_expander.set_visible(count > 0)

    def move_todo_row(self, row, is_done):
        if is_done:
            row.get_style_context().add_class('done')
            if row.get_parent() == self.todo_listbox:
                self.todo_listbox.remove(row)
                self.checked_listbox.add(row)
        else:
            row.get_style_context().remove_class('done')
            if row.get_parent() == self.checked_listbox:
                self.checked_listbox.remove(row)
                self.todo_listbox.add(row)
        self.update_checked_label()

    def add_todo(self, txt="", done=False, d_c=None, index=-1, todo_id=None):
        row = Gtk.ListBoxRow(); box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); box.get_style_context().add_class('t-box')
        hb = Gtk.EventBox(); hb.add(Gtk.Label(label="⣿", margin_start=5, margin_end=5))
        
        chk = Gtk.CheckButton(active=done, focus_on_click=False)
        def on_toggled(c):
            self.move_todo_row(row, c.get_active())
            self.queue_state()
            self.on_save()
        chk.connect("toggled", on_toggled)

        ent = Gtk.Entry(text=txt, hexpand=True); ent.connect("changed", lambda e: self.queue_state())
        
        def on_key(e, ev):
            if ev.keyval == Gdk.KEY_Return:
                is_done_list = (row.get_parent() == self.checked_listbox)
                idx = row.get_index()
                GLib.idle_add(lambda: self.add_todo(index=idx+1, done=is_done_list).grab_focus())
                return True
            if ev.keyval == Gdk.KEY_BackSpace and not e.get_text():
                idx, parent = row.get_index(), row.get_parent()
                if idx > 0:
                    pr = parent.get_row_at_index(idx - 1)
                    if pr: pr.ent.grab_focus()
                parent.remove(row); self.update_checked_label(); self.queue_state(); self.on_save()
                return True
            return False
            
        ent.connect("key-press-event", on_key)
        del_b = UIHelpers.create_btn("edit-delete-symbolic", cb=lambda x: [row.get_parent().remove(row), self.update_checked_label(), self.queue_state(), self.on_save()])
        del_b.set_relief(Gtk.ReliefStyle.NONE); [box.pack_start(w, w == ent, w == ent, 0) for w in (hb, chk, ent, del_b)]
        row.add(box); row.ts, row.chk, row.ent, row.box, row.todo_id = d_c, chk, ent, box, todo_id
        
        if done:
            row.get_style_context().add_class('done')
            if index == -1: self.checked_listbox.add(row)
            else: self.checked_listbox.insert(row, index)
        else:
            if index == -1: self.todo_listbox.add(row)
            else: self.todo_listbox.insert(row, index)
        
        # DND Reordering
        tgt = Gtk.TargetEntry.new("ROW", Gtk.TargetFlags.SAME_APP, 0)
        hb.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [tgt], Gdk.DragAction.MOVE)
        hb.connect("drag-begin", lambda w, c: setattr(self, 'drag_row', row))
        hb.connect("drag-data-get", lambda w, c, d, i, t: d.set(Gdk.Atom.intern("ROW", False), 8, b""))
        row.drag_dest_set(Gtk.DestDefaults.ALL, [tgt], Gdk.DragAction.MOVE)
        row.connect("drag-motion", self.d_motion, row)
        row.connect("drag-leave", lambda *a: self.d_clean())
        row.connect("drag-data-received", self.d_drop, row)

        row.show_all()
        self.update_checked_label()
        if not done and (index == -1 or index >= len(self.todo_listbox.get_children()) - 1):
            GLib.idle_add(self.scroll_to_bottom)
        return ent

    def scroll_to_bottom(self):
        adj = self.todo_sw.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    def on_pin(self, btn):
        if not self.current_path: return
        p = self.config_manager.get("pinned")
        if btn.get_active(): (p.append(self.current_path) if self.current_path not in p else None)
        else: (p.remove(self.current_path) if self.current_path in p else None)
        self.config_manager.set("pinned", p); self.refresh_sidebar()

    def refresh_sidebar(self):
        [self.file_listbox.remove(r) for r in self.file_listbox.get_children()]; store = self.file_tree.get_model(); store.clear()
        files, all_fol = self.file_ops.list_files(self.search_entry.get_text())
        sm = self.config_manager.get("sort"); files.sort(key=lambda t: ("0_" if (sm == "text_first" and not t["is_todo"]) or (sm == "lists_first" and t["is_todo"]) else "1_") + t["name"].lower())
        fo = self.config_manager.get("fol_order"); [fo.append(f) for f in all_fol if f not in fo]
        self.config_manager.set("fol_order", [f for f in fo if f in all_fol])

        def add_grp(title, items, tree_p=None):
            if not items and title in ["📌 Pinned", "📁 Notes"]: return
            row = Gtk.ListBoxRow(selectable=False); row.add(Gtk.Label(label=f"<b>{title}</b>", use_markup=True, xalign=0, margin=10))
            row.fol_name = title.replace("📁 ", "").replace("📌 ", "").strip(); self.file_listbox.add(row)
            t_it = store.append(tree_p, [title[0], title[2:], ""]) if tree_p is None else tree_p
            for item in items:
                p, n, is_t = item["path"], item["name"], item["is_todo"]; ico = "☑" if is_t else "📄"
                display_name = n
                b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, border_width=5)
                b.pack_start(Gtk.Label(label=ico), False, False, 0); b.pack_start(Gtk.Label(label=display_name, xalign=0, ellipsize=Pango.EllipsizeMode.END), True, True, 0)
                if p in self.config_manager.get("pinned"): b.pack_end(Gtk.Label(label="📌"), False, False, 0)
                lr = Gtk.ListBoxRow(); lr.add(b); lr.filepath = p; self.file_listbox.add(lr); store.append(t_it, [ico, display_name, p])

        pinned_p = self.config_manager.get("pinned")
        add_grp("📌 Pinned", [f for f in files if f["path"] in pinned_p])
        add_grp("📁 Root", [f for f in files if f["path"] not in pinned_p and f["folder"] == "Root"])
        if self.config_manager.get("folders"):
            for fol in self.config_manager.get("fol_order"):
                items = [f for f in files if f["path"] not in pinned_p and f["folder"] == fol]
                if items: add_grp(f"📁 {fol}", items)
        else: add_grp("📁 Notes", [f for f in files if f["path"] not in pinned_p])
        self.file_listbox.show_all(); self.file_tree.expand_all()

    def on_sb_click(self, widget, event):
        if event.button == 1:
            if isinstance(widget, Gtk.TreeView):
                path_info = widget.get_path_at_pos(int(event.x), int(event.y))
                if path_info:
                    path, col, x, y = path_info
                    model = widget.get_model()
                    if path:
                        filepath = model[path][2]
                        if filepath: 
                            if filepath != self.current_path: self.open_file(filepath)
                        else:
                            if widget.row_expanded(path): widget.collapse_row(path)
                            else: widget.expand_row(path, False)
            elif isinstance(widget, Gtk.ListBox):
                r = widget.get_row_at_y(int(event.y))
                if r and hasattr(r, 'filepath') and r.filepath != self.current_path: 
                    self.open_file(r.filepath)
        
        elif event.button == 3:
            r_path = r_fol = None
            if isinstance(widget, Gtk.TreeView):
                path_info = widget.get_path_at_pos(int(event.x), int(event.y))
                if path_info:
                    path, col, x, y = path_info
                    model = widget.get_model()
                    r_path = model[path][2]
                    if not r_path: r_fol = model[path][1]
            else:
                r = widget.get_row_at_y(int(event.y))
                if not r: return
                r_path = getattr(r, 'filepath', None)
                r_fol = getattr(r, 'fol_name', None)

            m = Gtk.Menu()
            if r_path:
                mi1 = Gtk.MenuItem(label="Rename"); mi1.connect("activate", lambda _: self.rename_file_dialog(r_path)); m.append(mi1)
                mi_move = Gtk.MenuItem(label="Move to Folder"); mi_move.connect("activate", lambda _: self.move_note_dialog(r_path)); m.append(mi_move)
                
                m_ext = Gtk.Menu(); mi_ext = Gtk.MenuItem(label="Save As / Format")
                for ext in [".txt", ".md", ".json"]:
                    if not r_path.endswith(ext):
                        mi = Gtk.MenuItem(label=f"Convert to {ext}")
                        mi.connect("activate", lambda _, e=ext, p=r_path: self.on_change_ext(p, e))
                        m_ext.append(mi)
                if m_ext.get_children(): mi_ext.set_submenu(m_ext); m.append(mi_ext)

                mi2 = Gtk.MenuItem(label="Delete"); mi2.connect("activate", lambda _: self.on_delete(path_override=r_path)); m.append(mi2)
            elif r_fol and r_fol not in ["Root", "Notes", "Pinned", ""]:
                mi1 = Gtk.MenuItem(label="Rename"); mi1.connect("activate", lambda _: self.rename_folder_dialog(r_fol)); m.append(mi1)
                mi2 = Gtk.MenuItem(label="Delete"); mi2.connect("activate", lambda _: self.delete_folder_dialog(r_fol)); m.append(mi2)
                if not isinstance(widget, Gtk.TreeView):
                    m.append(Gtk.SeparatorMenuItem())
                    for lbl, step in [("Move Up", -1), ("Move Down", 1)]:
                        mi = Gtk.MenuItem(label=lbl); mi.connect("activate", lambda _, s=step: self.reorder_fol(r_fol, s)); m.append(mi)
            
            if m.get_children(): m.show_all(); m.popup_at_pointer(event)

    def on_change_ext(self, p, ext):
        np, err = self.file_ops.change_extension(p, ext)
        if np:
            if self.current_path == p: self.current_path = np
            self.config_manager.set("pinned", [np if x==p else x for x in self.config_manager.get("pinned")])
            self.note_history = [np if x==p else x for x in self.note_history]
            self.state_manager.rename_path(p, np); self.refresh_sidebar()

    def open_file(self, path):
        if self.current_path: self.on_save()
        self.undoing, self.current_path = True, path
        
        if path in self.note_history: self.note_history.remove(path)
        self.note_history.insert(0, path)
        if len(self.note_history) > 10: self.note_history.pop()

        self.pin_btn.set_active(path in self.config_manager.get("pinned"))
        self.note_styler.revealed_range = None
        if self.file_ops.is_todo(path):
            self.stack.set_visible_child_name("todo"); [self.todo_listbox.remove(r) for r in self.todo_listbox.get_children()]
            try:
                items = json.loads(self.file_ops.load_note_content(path))
                items.sort(key=lambda x: x.get('id', 0))
                for i in items: self.add_todo(i.get("title", ""), i.get("isDone", False), i.get("dateCreated"), todo_id=i.get("id"))
            except: pass
            self.todo_listbox.show_all()
        else:
            self.stack.set_visible_child_name("text"); self.text_view.get_buffer().set_text(self.file_ops.load_note_content(path))
        self.undoing = False; self.state_manager.push_state(path, self.get_state()); self.apply_markdown()

    def rename_folder_dialog(self, old):
        n = UIHelpers.get_text_input(self, f"Rename folder '{old}' to:", old)
        if n:
            op, np, err = self.file_ops.rename_folder(old, n)
            if not err:
                if self.current_path and self.current_path.startswith(op + '/'): self.current_path = self.current_path.replace(op, np, 1)
                self.config_manager.set("pinned", [x.replace(op, np, 1) if x.startswith(op + '/') else x for x in self.config_manager.get("pinned")])
                self.note_history = [x.replace(op, np, 1) if x.startswith(op + '/') else x for x in self.note_history]
                fo = self.config_manager.get("fol_order"); (fo.__setitem__(fo.index(old), n) if old in fo else None); self.config_manager.set("fol_order", fo)
                self.state_manager.rename_path(op, np); self.refresh_sidebar()

    def delete_folder_dialog(self, fol):
        if UIHelpers.confirm(self, f"Delete folder '{fol}' and ALL notes?"):
            fp = os.path.join(self.config_manager.get("dir"), fol); success, err = self.file_ops.delete_folder(fol)
            if success:
                self.config_manager.set("pinned", [x for x in self.config_manager.get("pinned") if not x.startswith(fp + '/')])
                self.note_history = [x for x in self.note_history if not x.startswith(fp + '/')]
                if self.current_path and self.current_path.startswith(fp + '/'): self.current_path = None; self.stack.set_visible_child_name("empty")
                fo = self.config_manager.get("fol_order"); (fo.remove(fol) if fol in fo else None); self.config_manager.set("fol_order", fo); self.refresh_sidebar()

    def reorder_fol(self, fol, step):
        fo = self.config_manager.get("fol_order")
        if fol in fo:
            idx = fo.index(fol); n_idx = max(0, min(len(fo) - 1, idx + step)); fo.insert(n_idx, fo.pop(idx))
            self.config_manager.set("fol_order", fo); self.refresh_sidebar()

    def create_file_dialog(self, is_todo):
        dlg = UIHelpers.show_dialog(self, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, "Create New Note")
        area = dlg.get_message_area()
        ent = Gtk.Entry(placeholder_text="Note Name"); ent.set_activates_default(True)
        area.pack_start(ent, True, True, 5)
        box_opts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        cb_fol = Gtk.ComboBoxText.new_with_entry(); cb_fol.append_text("Root")
        if self.config_manager.get("folders"):
            try:
                for f in os.scandir(self.config_manager.get("dir")):
                    if f.is_dir() and not f.name.startswith('.'): cb_fol.append_text(f.name)
            except: pass
        cb_fol.set_active(0); box_opts.pack_start(cb_fol, True, True, 0)
        cb_ext = Gtk.ComboBoxText(); [cb_ext.append_text(e) for e in [".txt", ".md", ".json"]]
        cb_ext.set_active(0); box_opts.pack_start(cb_ext, False, False, 0)
        area.pack_start(box_opts, True, True, 5)
        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK and ent.get_text().strip():
            name = ent.get_text().strip()
            folder = cb_fol.get_child().get_text().strip()
            ext = cb_ext.get_active_text()
            path, err = self.file_ops.create_note(name, folder, is_todo, ext)
            if path: self.open_file(path); self.refresh_sidebar()
        dlg.destroy()

    def rename_file_dialog(self, p):
        n = UIHelpers.get_text_input(self, "New Name:", os.path.basename(p).replace(".txt",""))
        if n:
            np, err = self.file_ops.rename_note(p, n)
            if np:
                if self.current_path == p: self.current_path = np
                self.config_manager.set("pinned", [np if x==p else x for x in self.config_manager.get("pinned")])
                self.note_history = [np if x==p else x for x in self.note_history]
                self.state_manager.rename_path(p, np); self.refresh_sidebar()

    def move_note_dialog(self, p):
        dlg = UIHelpers.show_dialog(self, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, "Move Note to Folder")
        area = dlg.get_message_area()
        cb = Gtk.ComboBoxText.new_with_entry(); cb.append_text("Root")
        if self.config_manager.get("folders"):
            try:
                for f in os.scandir(self.config_manager.get("dir")):
                    if f.is_dir() and not f.name.startswith('.'): cb.append_text(f.name)
            except: pass
        cb.set_active(0); area.pack_start(cb, True, True, 5)
        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK:
            folder = cb.get_child().get_text().strip()
            np, err = self.file_ops.move_note(p, folder)
            if np:
                if self.current_path == p: self.current_path = np
                self.config_manager.set("pinned", [np if x==p else x for x in self.config_manager.get("pinned")])
                self.note_history = [np if x==p else x for x in self.note_history]
                self.state_manager.rename_path(p, np); self.refresh_sidebar()
            elif err == "exists":
                UIHelpers.show_dialog(self, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, "Error", "A note with this name already exists in the target folder.").run()
        dlg.destroy()

    def on_delete(self, *args, path_override=None):
        target = path_override or self.current_path
        if target and UIHelpers.confirm(self, "Move to Trash?"):
            if self.file_ops.delete_note(target)[0]:
                p = self.config_manager.get("pinned"); (p.remove(target) if target in p else None); self.config_manager.set("pinned", p)
                if target in self.note_history: self.note_history.remove(target)
                if self.current_path == target: self.current_path = None; self.stack.set_visible_child_name("empty")
                self.state_manager.clear_history(target); self.refresh_sidebar()

    def on_paste(self, widget):
        if self.note_styler.handle_paste():
            widget.stop_emission_by_name("paste-clipboard")

    def on_populate_popup(self, text_view, menu):
        it = text_view.get_buffer().get_iter_at_mark(text_view.get_buffer().get_insert())
        span = self.note_styler.get_markdown_at_iter(it)
        if span:
            sep = Gtk.SeparatorMenuItem(); sep.show(); menu.append(sep)
            mi = Gtk.MenuItem(label="Edit Markdown Source"); mi.show()
            mi.connect("activate", lambda _: self.reveal_markdown(span))
            menu.append(mi)

    def reveal_markdown(self, span):
        self.note_styler.revealed_range = span
        self.apply_markdown()

    def on_cursor_moved(self, buffer, iter, mark):
        if mark.get_name() == "insert" and self.note_styler.revealed_range:
            offset = iter.get_offset()
            rs, re = self.note_styler.revealed_range
            if offset < rs or offset > re:
                self.note_styler.revealed_range = None
                self.apply_markdown()

    def apply_markdown(self):
        self.note_styler.apply_markdown()

    def on_key_press(self, widget, event):
        s_note_bind = self.config_manager.get("binds").get("switch_note", "")
        if s_note_bind:
            k, m = Gtk.accelerator_parse(s_note_bind)
            mod_mask = Gtk.accelerator_get_default_mod_mask()
            if event.keyval == k and (event.state & mod_mask) == (m & mod_mask):
                if self.exec_bind("switch_note"): return True
            if k == Gdk.KEY_Tab and event.keyval == Gdk.KEY_ISO_Left_Tab and (event.state & mod_mask) == (m & mod_mask):
                if self.exec_bind("switch_note"): return True

        if widget == self.text_view and self.stack.get_visible_child_name() == "text" and event.keyval == Gdk.KEY_Return:
            buf = widget.get_buffer(); iter = buf.get_iter_at_mark(buf.get_insert()); line_iter = iter.copy(); line_iter.set_line_offset(0)
            match = re.match(r'^(\s*([*\-]\s*)?)', buf.get_text(line_iter, iter, False))
            if match and match.group(1): GLib.idle_add(lambda: buf.insert_at_cursor(match.group(1)))
        return False

    def on_accel_edited(self, rnd, path, key, mods, hw):
        it = self.sc_store.get_iter(path); a_id, a_s = self.sc_store[it][0], Gtk.accelerator_name(key, mods)
        self.sc_store[it][2], self.sc_store[it][3], self.sc_store[it][4] = a_s, key, mods
        b = self.config_manager.get("binds"); b[a_id] = a_s; self.config_manager.set("binds", b); self.reload_shortcuts()

    def on_accel_cleared(self, rnd, path):
        it = self.sc_store.get_iter(path); self.sc_store[it][2], self.sc_store[it][3], self.sc_store[it][4] = "", 0, 0
        b = self.config_manager.get("binds"); b[self.sc_store[it][0]] = ""; self.config_manager.set("binds", b); self.reload_shortcuts()

    def get_state(self):
        if not self.current_path: return None
        if self.file_ops.is_todo(self.current_path): return [{"done": r.chk.get_active(), "txt": r.ent.get_text(), "ts": r.ts, "id": getattr(r, 'todo_id', None)} for r in self.todo_listbox.get_children()]
        b = self.text_view.get_buffer(); return b.get_text(*b.get_bounds(), True)

    def queue_state(self, *args):
        if not self.undoing and self.current_path:
            self.apply_markdown(); (GLib.source_remove(self.undo_timer) if self.undo_timer else None)
            self.undo_timer = GLib.timeout_add(400, self.push_state)

    def push_state(self):
        self.undo_timer = None; self.state_manager.push_state(self.current_path, self.get_state()); return False

    def exec_undo(self):
        st = self.state_manager.undo(self.current_path)
        if st is not None: self.undoing = True; self.apply_state(st); self.undoing = False

    def exec_redo(self):
        st = self.state_manager.redo(self.current_path)
        if st is not None: self.undoing = True; self.apply_state(st); self.undoing = False

    def apply_state(self, st):
        if self.file_ops.is_todo(self.current_path):
            [self.todo_listbox.remove(r) for r in self.todo_listbox.get_children()]
            [self.checked_listbox.remove(r) for r in self.checked_listbox.get_children()]
            for i in st: self.add_todo(i["txt"], i["done"], i.get("ts"), todo_id=i.get("id"))
            self.update_checked_label()
        else: self.text_view.get_buffer().set_text(st)
        self.on_save()

    def d_clean(self, *args): self.todo_listbox.drag_unhighlight_row()

    def d_motion(self, w, c, x, y, t, t_row):
        if self.drag_row == t_row: return False
        self.todo_listbox.drag_highlight_row(t_row)
        Gdk.drag_status(c, Gdk.DragAction.MOVE, t); return True

    def d_drop(self, w, c, x, y, d, i, t, t_row):
        self.todo_listbox.drag_unhighlight_row()
        if self.drag_row and self.drag_row != t_row:
            t_idx = t_row.get_index()
            if y > t_row.get_allocated_height() / 2: t_idx += 1
            curr_idx = self.drag_row.get_index()
            if curr_idx < t_idx: t_idx -= 1
            parent = self.drag_row.get_parent()
            parent.remove(self.drag_row); parent.insert(self.drag_row, t_idx)
            Gtk.drag_finish(c, True, False, t); self.queue_state(); self.on_save()
        else: Gtk.drag_finish(c, False, False, t)

    def apply_autosave(self):
        (GLib.source_remove(self.timer_id) if self.timer_id else None)
        v = self.config_manager.get("autosave"); (setattr(self, 'timer_id', GLib.timeout_add_seconds(int(v), lambda: self.on_save() or True)) if v.isdigit() else None)

if __name__ == "__main__":
    app = SimpleNotes_GTK(); app.connect("destroy", Gtk.main_quit); app.show_all(); Gtk.main()
