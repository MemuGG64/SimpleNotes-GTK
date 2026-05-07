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
        
        self.set_default_size(self.config_manager.get("width"), self.config_manager.get("height"))
        self.set_size_request(450, 350)
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

        hb.pack_start(UIHelpers.create_btn("sidebar-show-symbolic", "Toggle Sidebar", lambda _: self.sb_box.set_visible(not self.sb_box.get_visible())))
        
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
        self.file_listbox.connect("row-activated", lambda _, r: self.open_file(r.filepath) if hasattr(r, 'filepath') else None)
        self.file_listbox.connect("button-press-event", self.on_sb_click)
        ls_scroll.add(self.file_listbox)
        
        tr_scroll = Gtk.ScrolledWindow()
        self.file_tree = Gtk.TreeView(model=Gtk.TreeStore(str, str, str), headers_visible=False)
        col = Gtk.TreeViewColumn()
        rnd_i, rnd_t = Gtk.CellRendererText(), Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END)
        col.pack_start(rnd_i, False); col.add_attribute(rnd_i, "text", 0)
        col.pack_start(rnd_t, True); col.add_attribute(rnd_t, "text", 1)
        self.file_tree.append_column(col)
        self.file_tree.connect("row-activated", lambda tv, p, c: self.open_file(tv.get_model()[p][2]) if tv.get_model()[p][2] else None)
        tr_scroll.add(self.file_tree)

        self.sidebar_stack.add_named(ls_scroll, "list")
        self.sidebar_stack.add_named(tr_scroll, "tree")
        self.sidebar_stack.set_visible_child_name(self.config_manager.get("view"))
        self.sb_box.pack_start(self.sidebar_stack, True, True, 0)
        self.main_box.pack_start(self.sb_box, False, False, 0)

        # Main Stack Setup
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(Gtk.Label(label="Select or create a note"), "empty")
        
        self.text_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, left_margin=15, right_margin=15, top_margin=15)
        self.text_view.connect("key-press-event", self.on_key_press)
        self.tag_bold = self.text_view.get_buffer().create_tag("bold", weight=Pango.Weight.BOLD)
        self.text_view.get_buffer().connect("changed", self.queue_state)
        sw_txt = Gtk.ScrolledWindow(); sw_txt.add(self.text_view)
        self.stack.add_named(sw_txt, "text")

        td_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)
        self.todo_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        td_box.pack_start(self.todo_listbox, False, False, 0)
        add_task_btn = Gtk.Button(label="+ Add Task")
        add_task_btn.connect("clicked", lambda x: self.add_todo().grab_focus())
        td_box.pack_start(add_task_btn, False, False, 0)
        sw_td = Gtk.ScrolledWindow(); sw_td.add(td_box)
        self.stack.add_named(sw_td, "todo")

        self.setup_settings_ui()
        self.main_box.pack_start(self.stack, True, True, 0)
        self.reload_shortcuts()

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
        for a_id, d_n in [("save", "Save"), ("undo", "Undo"), ("redo", "Redo"), ("n_txt", "New Text"), ("n_todo", "New To-Do"), ("find", "Find")]:
            a_s = self.config_manager.get("binds").get(a_id, ""); k, m = Gtk.accelerator_parse(a_s) if a_s else (0,0)
            self.sc_store.append([a_id, d_n, a_s, k, m])
        sc_t = Gtk.TreeView(model=self.sc_store); sc_t.append_column(Gtk.TreeViewColumn("Action", Gtk.CellRendererText(), text=1))
        rnd_a = Gtk.CellRendererAccel(editable=True); rnd_a.connect("accel-edited", self.on_accel_edited); rnd_a.connect("accel-cleared", self.on_accel_cleared)
        sc_t.append_column(Gtk.TreeViewColumn("Shortcut", rnd_a, accel_key=3, accel_mods=4))
        b_sc.pack_start(sc_t, True, True, 0); nb.append_page(b_sc, Gtk.Label(label="Shortcuts"))
        self.stack.add_named(nb, "settings")

    def on_config_changed(self, key, val, refresh=False):
        self.config_manager.set(key, val)
        if refresh: self.refresh_sidebar()
        if key == "autosave": self.apply_autosave()
        if key == "view": self.sidebar_stack.set_visible_child_name(val)

    def reload_shortcuts(self):
        if hasattr(self, 'accel'): self.remove_accel_group(self.accel)
        self.accel = Gtk.AccelGroup(); self.add_accel_group(self.accel)
        for a_id, a_s in self.config_manager.get("binds").items():
            if not a_s: continue
            k, m = Gtk.accelerator_parse(a_s)
            if a_id == "save": self.save_btn.add_accelerator("clicked", self.accel, k, m, Gtk.AccelFlags.VISIBLE)
            else: self.accel.connect(k, m, Gtk.AccelFlags.VISIBLE, lambda _g, _w, _k, _m, a=a_id: self.exec_bind(a))

    def on_window_delete(self, *args):
        w, h = self.get_size(); self.config_manager.update({"width": w, "height": h})
        if self.config_manager.get("autosave") != "off": self.on_save()
        return False

    def exec_bind(self, a_id):
        actions = {"n_txt": lambda: self.create_file_dialog(False), "n_todo": lambda: self.create_file_dialog(True), 
                   "find": lambda: self.search_entry.grab_focus(), "undo": self.exec_undo, "redo": self.exec_redo}
        if a_id in actions: GLib.idle_add(actions[a_id]); return True
        return False

    def on_save(self, *args):
        if not self.current_path or not os.path.exists(self.current_path) or self.undoing: return
        if self.file_ops.is_todo(self.current_path):
            td = [{"dateCreated": getattr(r, 'ts', int(time.time()*1000)), "id": i+1, "isDone": r.chk.get_active(), "title": r.ent.get_text()} for i, r in enumerate(self.todo_listbox.get_children())]
            self.file_ops.save_todo_note(self.current_path, td)
        else:
            buf = self.text_view.get_buffer()
            self.file_ops.save_text_note(self.current_path, buf.get_text(*buf.get_bounds(), True))
        if args: self.refresh_sidebar()

    def add_todo(self, txt="", done=False, d_c=None, index=-1):
        row = Gtk.ListBoxRow(); box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); box.get_style_context().add_class('t-box')
        hb = Gtk.EventBox(); hb.add(Gtk.Label(label="⣿", margin_start=5, margin_end=5))
        chk = Gtk.CheckButton(active=done, focus_on_click=False)
        chk.connect("toggled", lambda c: [row.get_style_context().add_class('done') if c.get_active() else row.get_style_context().remove_class('done'), self.queue_state(), self.on_save()])
        ent = Gtk.Entry(text=txt, hexpand=True); ent.connect("changed", self.queue_state)
        ent.connect("activate", lambda e: GLib.idle_add(lambda: self.add_todo(index=row.get_index()+1).grab_focus()))
        del_b = UIHelpers.create_btn("edit-delete-symbolic", cb=lambda x: [self.todo_listbox.remove(row), self.queue_state(), self.on_save()])
        del_b.set_relief(Gtk.ReliefStyle.NONE); [box.pack_start(w, w == ent, w == ent, 0) for w in (hb, chk, ent, del_b)]
        eb = Gtk.EventBox(); eb.add(box); row.add(eb); row.ts, row.chk, row.ent, row.box = d_c, chk, ent, box
        if done: row.get_style_context().add_class('done')
        tgt = Gtk.TargetEntry.new("ROW", Gtk.TargetFlags.SAME_APP, 0); hb.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [tgt], Gdk.DragAction.MOVE)
        hb.connect("drag-begin", lambda w, c: setattr(self, 'drag_row', row)); eb.drag_dest_set(Gtk.DestDefaults.DROP, [tgt], Gdk.DragAction.MOVE)
        eb.connect("drag-motion", self.d_motion, row); eb.connect("drag-leave", self.d_clean); eb.connect("drag-data-received", self.d_drop, row)
        if index == -1: self.todo_listbox.add(row)
        else: self.todo_listbox.insert(row, index)
        self.todo_listbox.show_all(); return ent

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
                b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, border_width=5)
                b.pack_start(Gtk.Label(label=ico), False, False, 0); b.pack_start(Gtk.Label(label=n, xalign=0, ellipsize=Pango.EllipsizeMode.END), True, True, 0)
                if p in self.config_manager.get("pinned"): b.pack_end(Gtk.Label(label="📌"), False, False, 0)
                lr = Gtk.ListBoxRow(); lr.add(b); lr.filepath = p; self.file_listbox.add(lr); store.append(t_it, [ico, n, p])

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
        if event.button == 3:
            r = self.file_listbox.get_row_at_y(int(event.y))
            if not r: return
            m = Gtk.Menu()
            if hasattr(r, 'filepath'):
                mi1 = Gtk.MenuItem(label="Rename"); mi1.connect("activate", lambda _: self.rename_file_dialog(r.filepath)); m.append(mi1)
                mi_move = Gtk.MenuItem(label="Move to Folder"); mi_move.connect("activate", lambda _: self.move_note_dialog(r.filepath)); m.append(mi_move)
                mi2 = Gtk.MenuItem(label="Delete"); mi2.connect("activate", lambda _: self.on_delete(path_override=r.filepath)); m.append(mi2)
            elif hasattr(r, 'fol_name') and r.fol_name not in ["Root", "Notes", "Pinned", ""]:
                mi1 = Gtk.MenuItem(label="Rename"); mi1.connect("activate", lambda _: self.rename_folder_dialog(r.fol_name)); m.append(mi1)
                mi2 = Gtk.MenuItem(label="Delete"); mi2.connect("activate", lambda _: self.delete_folder_dialog(r.fol_name)); m.append(mi2)
                m.append(Gtk.SeparatorMenuItem())
                for lbl, step in [("Move Up", -1), ("Move Down", 1)]:
                    mi = Gtk.MenuItem(label=lbl); mi.connect("activate", lambda _, s=step: self.reorder_fol(r.fol_name, s)); m.append(mi)
            if m.get_children(): m.show_all(); m.popup_at_pointer(event)

    def open_file(self, path):
        if self.current_path: self.on_save()
        self.undoing, self.current_path = True, path
        self.pin_btn.set_active(path in self.config_manager.get("pinned"))
        if self.file_ops.is_todo(path):
            self.stack.set_visible_child_name("todo"); [self.todo_listbox.remove(r) for r in self.todo_listbox.get_children()]
            try:
                for i in json.loads(self.file_ops.load_note_content(path)): self.add_todo(i.get("title", ""), i.get("isDone", False), i.get("dateCreated"))
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
                fo = self.config_manager.get("fol_order"); (fo.__setitem__(fo.index(old), n) if old in fo else None); self.config_manager.set("fol_order", fo)
                self.state_manager.rename_path(op, np); self.refresh_sidebar()

    def delete_folder_dialog(self, fol):
        if UIHelpers.confirm(self, f"Delete folder '{fol}' and ALL notes?"):
            fp = os.path.join(self.config_manager.get("dir"), fol); success, err = self.file_ops.delete_folder(fol)
            if success:
                self.config_manager.set("pinned", [x for x in self.config_manager.get("pinned") if not x.startswith(fp + '/')])
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
        
        cb = Gtk.ComboBoxText.new_with_entry(); cb.append_text("Root")
        if self.config_manager.get("folders"):
            try:
                for f in os.scandir(self.config_manager.get("dir")):
                    if f.is_dir() and not f.name.startswith('.'): cb.append_text(f.name)
            except: pass
        cb.set_active(0); area.pack_start(cb, True, True, 5)
        
        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK and ent.get_text().strip():
            name = ent.get_text().strip()
            folder = cb.get_child().get_text().strip()
            path, err = self.file_ops.create_note(name, folder, is_todo)
            if path: self.open_file(path); self.refresh_sidebar()
        dlg.destroy()

    def rename_file_dialog(self, p):
        n = UIHelpers.get_text_input(self, "New Name:", os.path.basename(p).replace(".txt",""))
        if n:
            np, err = self.file_ops.rename_note(p, n)
            if np:
                if self.current_path == p: self.current_path = np
                self.config_manager.set("pinned", [np if x==p else x for x in self.config_manager.get("pinned")])
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
                self.state_manager.rename_path(p, np); self.refresh_sidebar()
            elif err == "exists":
                UIHelpers.show_dialog(self, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, "Error", "A note with this name already exists in the target folder.").run()
        dlg.destroy()

    def on_delete(self, *args, path_override=None):
        target = path_override or self.current_path
        if target and UIHelpers.confirm(self, "Move to Trash?"):
            if self.file_ops.delete_note(target)[0]:
                p = self.config_manager.get("pinned"); (p.remove(target) if target in p else None); self.config_manager.set("pinned", p)
                if self.current_path == target: self.current_path = None; self.stack.set_visible_child_name("empty")
                self.state_manager.clear_history(target); self.refresh_sidebar()

    def apply_markdown(self):
        buf = self.text_view.get_buffer(); start, end = buf.get_bounds(); buf.remove_tag(self.tag_bold, start, end)
        cursor = buf.get_iter_at_offset(0)
        while not cursor.is_end():
            line_start = cursor.copy(); (cursor.forward_to_line_end() if not cursor.ends_line() else None)
            if buf.get_text(line_start, cursor, False).lstrip().startswith('#'): buf.apply_tag(self.tag_bold, line_start, cursor)
            (cursor.forward_line() if not cursor.is_end() else None)

    def on_key_press(self, widget, event):
        if self.stack.get_visible_child_name() == "text" and event.keyval == Gdk.KEY_Return:
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
        if self.file_ops.is_todo(self.current_path): return [{"done": r.chk.get_active(), "txt": r.ent.get_text(), "ts": r.ts} for r in self.todo_listbox.get_children()]
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
            for i in st: self.add_todo(i["txt"], i["done"], i.get("ts"))
        else: self.text_view.get_buffer().set_text(st)
        self.on_save()

    def d_clean(self, *args): [r.box.get_style_context().remove_class(c) for r in self.todo_listbox.get_children() for c in ('drag-top', 'drag-bottom')]

    def d_motion(self, w, c, x, y, t, t_row):
        if self.drag_row == t_row: return False
        self.d_clean(); idx = t_row.get_index(); is_top = y < w.get_allocation().height / 2
        nr = self.todo_listbox.get_row_at_index(idx + 1); (nr.box if nr and not is_top else t_row.box).get_style_context().add_class('drag-top' if is_top or nr else 'drag-bottom')
        Gdk.drag_status(c, Gdk.DragAction.MOVE, t); return True

    def d_drop(self, w, c, x, y, d, i, t, t_row):
        self.d_clean()
        if self.drag_row and self.drag_row != t_row:
            t_idx = t_row.get_index() + (1 if y >= w.get_allocation().height / 2 else 0)
            t_idx -= 1 if self.drag_row.get_index() < t_idx else 0
            self.todo_listbox.remove(self.drag_row); self.todo_listbox.insert(self.drag_row, t_idx); c.finish(True, False, t); self.queue_state(); self.on_save()
        else: c.finish(False, False, t)

    def apply_autosave(self):
        (GLib.source_remove(self.timer_id) if self.timer_id else None)
        v = self.config_manager.get("autosave"); (setattr(self, 'timer_id', GLib.timeout_add_seconds(int(v), lambda: self.on_save() or True)) if v.isdigit() else None)

if __name__ == "__main__":
    app = SimpleNotes_GTK(); app.connect("destroy", Gtk.main_quit); app.show_all(); Gtk.main()
