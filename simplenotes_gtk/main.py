#!/usr/bin/env python3
import gi
import os
import json
import sys
import re
import webbrowser

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from .config import ConfigManager
from .file_operations import FileOperations
from .dialogs import UIHelpers
from .note_styler import NoteStylist
from .to_do_styler import ToDoStyler
from .updater import Updater
from . import dialogs
from .shortcuts import ShortcutManager
from .sidebar import Sidebar
from .keystroke import KeyStroke
from .chrono import Chrono


if sys.platform == "darwin":
    GLib.set_prgname('io.github.memugg64.SimpleNotesGTK')
    GLib.set_application_name('SimpleNotes-GTK')
else:
    GLib.set_prgname('simplenotes-gtk')
    GLib.set_application_name('SimpleNotes-GTK')


class SimpleNotes_GTK(Gtk.Window):
    def __init__(self):
        super().__init__(title="SimpleNotes-GTK")
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'SNG.png')
        if os.path.exists(icon_path):
            self.set_icon_from_file(icon_path)
        self.connect("delete-event", self.on_window_delete)

        self.config_manager = ConfigManager()
        self.file_ops = FileOperations(self.config_manager)
        self.updater = Updater(self)

        self.load_styles()

        self.current_path = self.timer_id = None
        self.note_history = []

        self.set_default_size(self.config_manager.get("width"), self.config_manager.get("height"))
        self.set_size_request(300, 250)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.setup_ui()
        self.shortcuts = ShortcutManager(
            self, self.config_manager, self.save_btn,
            {"n_txt": lambda: self.create_file_dialog(False),
             "n_todo": lambda: self.create_file_dialog(True),
             "find": lambda: self.search_entry.grab_focus(),
             "undo": self.chrono.undo,
             "redo": self.chrono.redo,
             "switch_note": self.switch_to_last_note}
        )
        self.settings_notebook.append_page(self.shortcuts.build_tab(), Gtk.Label(label="Shortcuts"))
        self.shortcuts.reload()
        self.apply_autosave()
        self.sidebar.refresh()
        self.sidebar.box.show()
        if self.config_manager.get("auto_update"):
            GLib.timeout_add(3000, self.updater.check)

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

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL); self.add(self.main_box)

        self.sidebar = Sidebar(self.file_ops, self.config_manager, self.search_entry, {
            'open_file': self.open_file,
            'show_note_view': self._show_note_view,
            'rename_file': self.rename_file_dialog,
            'move_note': self.move_note_dialog,
            'change_ext': self.on_change_ext,
            'delete_note': self.on_delete,
            'rename_folder': self.rename_folder_dialog,
            'delete_folder': self.delete_folder_dialog,
            'reorder_fol': self.reorder_fol,
            'get_current_path': lambda: self.current_path,
            'is_settings_visible': lambda: self.stack.get_visible_child_name() == "settings",
        })
        self.search_entry.connect("search-changed", lambda x: self.sidebar.refresh())

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hhomogeneous=True)
        self.stack.add_named(Gtk.Label(label="Select or create a note"), "empty")

        self.text_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, left_margin=15, right_margin=15, top_margin=15)
        self.text_view.connect("paste-clipboard", self.on_paste)
        self.text_view.connect("populate-popup", self.on_populate_popup)

        self.note_styler = NoteStylist(self.text_view, self.file_ops)
        self.keystroke = KeyStroke(self.text_view, self.note_styler, self.config_manager, {
            'show_note_view': self._show_note_view,
            'switch_to_last_note': self.switch_to_last_note,
            'get_stack_child': lambda: self.stack.get_visible_child_name(),
        })
        self.text_view.connect("key-press-event", self.keystroke.on_key_press)
        self.connect("key-press-event", self.keystroke.on_key_press)

        self.chrono = Chrono(self.file_ops, {
            'get_current_path': lambda: self.current_path,
            'get_state': self._get_note_state,
            'apply_state': self._apply_chrono_state,
            'on_save': self.on_save,
            'is_text_visible': lambda: self.stack.get_visible_child_name() == "text",
            'apply_markdown': self.note_styler.apply_markdown,
        })

        self.text_view.get_buffer().connect("changed", self.chrono.queue)
        self.text_view.get_buffer().connect("mark-set", self.on_cursor_moved)
        sw_txt = Gtk.ScrolledWindow(); sw_txt.add(self.text_view)
        self.stack.add_named(sw_txt, "text")

        td_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)
        self.todo_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        td_box.pack_start(self.todo_listbox, False, False, 0)

        self.todo_sw = Gtk.ScrolledWindow(); self.todo_sw.add(td_box)
        self.todo_styler = ToDoStyler(self.todo_listbox, self.todo_sw, td_box, self.chrono.queue, self.on_save)

        self.add_task_btn = Gtk.Button(label="+ Add Task")
        td_box.pack_start(self.add_task_btn, False, False, 0)
        self.add_task_btn.connect("clicked", lambda x: self.todo_styler.add_todo().grab_focus())
        self.stack.add_named(self.todo_sw, "todo")

        self.settings_notebook = self.config_manager.build_ui({
            'on_config_changed': self.on_config_changed,
            'convert_folder': self._convert_folder_dialog,
        })
        self.stack.add_named(self.settings_notebook, "settings")

        self.main_box.pack_start(self.sidebar.box, False, False, 0)
        self.main_box.pack_start(self.stack, True, True, 0)

    def toggle_sidebar(self, *args):
        w, h = self.get_size()
        pos_x, pos_y = self.get_position()
        self.sidebar.toggle(self, pos_x, pos_y, w, h)

    def on_config_changed(self, key, val, refresh=False):
        self.config_manager.set(key, val)
        if refresh:
            self.sidebar.refresh()
        if key == "autosave":
            self.apply_autosave()
        if key == "view":
            self.sidebar.set_view_mode(val)

    def on_window_delete(self, *args):
        w, h = self.get_size(); self.config_manager.update({"width": w, "height": h})
        self.on_save()
        return False

    def on_save(self, *args):
        if not self.current_path or not os.path.exists(self.current_path): return
        if self.file_ops.is_todo(self.current_path):
            td = self.todo_styler.get_all_items()
            self.file_ops.save_todo_note(self.current_path, td)
        else:
            buf = self.text_view.get_buffer()
            self.note_styler.is_rendering = True
            try:
                start, end = buf.get_bounds()
                buf.remove_tag(self.note_styler.tag_hidden, start, end)
                content = buf.get_text(*buf.get_bounds(), False).replace('\uFFFC', '')
                self.file_ops.save_text_note(self.current_path, content)
            finally:
                self.note_styler.is_rendering = False
                self.apply_markdown()
        if args and args[0] is not self: self.sidebar.refresh()

    def on_pin(self, btn):
        if not self.current_path: return
        p = list(self.config_manager.get("pinned"))
        if btn.get_active():
            if self.current_path not in p:
                p.append(self.current_path)
        else:
            if self.current_path in p:
                p.remove(self.current_path)
        self.config_manager.set("pinned", p); self.sidebar.refresh()

    def on_change_ext(self, p, ext):
        np, err = self.file_ops.change_extension(p, ext)
        if np:
            if self.current_path == p: self.current_path = np
            self.config_manager.set("pinned", [np if x==p else x for x in self.config_manager.get("pinned")])
            self.note_history = [np if x==p else x for x in self.note_history]
            self.chrono.rename_path(p, np); self.sidebar.refresh()

    def open_file(self, path):
        if self.current_path: self.on_save()
        self.chrono.undoing = True
        self.current_path = path

        if path in self.note_history: self.note_history.remove(path)
        self.note_history.insert(0, path)
        if len(self.note_history) > 10: self.note_history.pop()

        self.pin_btn.set_active(path in self.config_manager.get("pinned"))
        self.note_styler.revealed_range = None
        if self.file_ops.is_todo(path):
            self.stack.set_visible_child_name("todo")
            self.todo_styler.clear_all()
            try:
                for i in json.loads(self.file_ops.load_note_content(path)):
                    self.todo_styler.add_todo(i.get("title", ""), i.get("isDone", False), i.get("dateCreated"), i.get("id"))
            except Exception:
                pass
            self.todo_styler.update_checked_count()
            self.todo_styler.show_all()
        else:
            self.stack.set_visible_child_name("text"); self.text_view.get_buffer().set_text(self.file_ops.load_note_content(path))
        self.chrono.undoing = False; self.chrono.push_state(path, self.chrono.get_state()); self.apply_markdown()

    def _show_note_view(self):
        if self.current_path:
            self.stack.set_visible_child_name("todo" if self.file_ops.is_todo(self.current_path) else "text")
        else:
            self.stack.set_visible_child_name("empty")

    def switch_to_last_note(self):
        if len(self.note_history) >= 2:
            self.open_file(self.note_history[1])

    def rename_folder_dialog(self, old):
        n = UIHelpers.get_text_input(self, f"Rename folder '{old}' to:", old)
        if n:
            op, np, err = self.file_ops.rename_folder(old, n)
            if not err:
                if self.current_path and self.current_path.startswith(op + '/'): self.current_path = self.current_path.replace(op, np, 1)
                self.config_manager.set("pinned", [x.replace(op, np, 1) if x.startswith(op + '/') else x for x in self.config_manager.get("pinned")])
                self.note_history = [x.replace(op, np, 1) if x.startswith(op + '/') else x for x in self.note_history]
                fo = self.config_manager.get("fol_order"); (fo.__setitem__(fo.index(old), n) if old in fo else None); self.config_manager.set("fol_order", fo)
                self.chrono.rename_path(op, np); self.sidebar.refresh()

    def delete_folder_dialog(self, fol):
        if UIHelpers.confirm(self, f"Delete folder '{fol}' and ALL notes?"):
            fp = os.path.join(self.config_manager.get("dir"), fol); success, err = self.file_ops.delete_folder(fol)
            if success:
                self.config_manager.set("pinned", [x for x in self.config_manager.get("pinned") if not x.startswith(fp + '/')])
                self.note_history = [x for x in self.note_history if not x.startswith(fp + '/')]
                if self.current_path and self.current_path.startswith(fp + '/'): self.current_path = None; self.stack.set_visible_child_name("empty")
                fo = self.config_manager.get("fol_order"); (fo.remove(fol) if fol in fo else None); self.config_manager.set("fol_order", fo); self.sidebar.refresh()

    def reorder_fol(self, fol, step):
        fo = self.config_manager.get("fol_order")
        if fol in fo:
            idx = fo.index(fol); n_idx = max(0, min(len(fo) - 1, idx + step)); fo.insert(n_idx, fo.pop(idx))
            self.config_manager.set("fol_order", fo); self.sidebar.refresh()

    def create_file_dialog(self, is_todo):
        result = dialogs.create_note(self, self.config_manager, is_todo)
        if not result:
            return
        name, folder, ext = result
        path, err = self.file_ops.create_note(name, folder, is_todo, ext)
        if path:
            self.open_file(path)
            self.sidebar.refresh()

    def rename_file_dialog(self, p):
        n = UIHelpers.get_text_input(self, "New Name:", os.path.basename(p).replace(".txt",""))
        if n:
            np, err = self.file_ops.rename_note(p, n)
            if np:
                if self.current_path == p: self.current_path = np
                self.config_manager.set("pinned", [np if x==p else x for x in self.config_manager.get("pinned")])
                self.note_history = [np if x==p else x for x in self.note_history]
                self.chrono.rename_path(p, np); self.sidebar.refresh()

    def move_note_dialog(self, p):
        folder = dialogs.move_note(self, self.config_manager)
        if not folder:
            return
        np, err = self.file_ops.move_note(p, folder)
        if np:
            if self.current_path == p: self.current_path = np
            self.config_manager.set("pinned", [np if x==p else x for x in self.config_manager.get("pinned")])
            self.note_history = [np if x==p else x for x in self.note_history]
            self.chrono.rename_path(p, np); self.sidebar.refresh()
        elif err == "exists":
            UIHelpers.show_dialog(self, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK,
                "Error", "A note with this name already exists in the target folder.").run()

    def on_delete(self, *args, path_override=None):
        target = path_override or self.current_path
        if target and UIHelpers.confirm(self, "Move to Trash?"):
            if self.file_ops.delete_note(target)[0]:
                p = self.config_manager.get("pinned"); (p.remove(target) if target in p else None); self.config_manager.set("pinned", p)
                if target in self.note_history: self.note_history.remove(target)
                if self.current_path == target: self.current_path = None; self.stack.set_visible_child_name("empty")
                self.chrono.clear_history(target); self.sidebar.refresh()

    def on_paste(self, widget):
        if self.note_styler.handle_paste():
            widget.stop_emission_by_name("paste-clipboard")

    def _convert_folder_dialog(self):
        folder = dialogs.confirm_folder(self, self.config_manager, "Convert folder to default format")
        if not folder:
            return
        target = self.file_ops.default_extension()
        converted, err = self.file_ops.convert_folder(folder, target)
        if err:
            dlg = UIHelpers.show_dialog(self, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, "Error", err)
            dlg.run(); dlg.destroy()
        else:
            pinned = self.config_manager.get("pinned")
            n_hist = self.note_history
            for old, new in converted:
                pinned = [new if x == old else x for x in pinned]
                n_hist = [new if x == old else x for x in n_hist]
                if self.current_path == old:
                    self.current_path = new
            self.config_manager.set("pinned", pinned)
            self.note_history = n_hist
            msg = f"Converted {len(converted)} notes to {target}"
            dlg = UIHelpers.show_dialog(self, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, "Done", msg)
            dlg.run(); dlg.destroy()
            self.sidebar.refresh()

    def _get_url_at_iter(self, it):
        offset = it.get_offset()
        text = self.text_view.get_buffer().get_text(*self.text_view.get_buffer().get_bounds(), True)
        for match in re.finditer(r'\[([^\]]+)\]\(([^\)]+)\)', text):
            if match.start() <= offset <= match.end():
                return match.group(2)
        return None

    def on_populate_popup(self, text_view, menu):
        it = text_view.get_buffer().get_iter_at_mark(text_view.get_buffer().get_insert())
        span = self.note_styler.get_markdown_at_iter(it)
        added = False
        if span:
            sep = Gtk.SeparatorMenuItem(); sep.show(); menu.append(sep)
            mi = Gtk.MenuItem(label="Edit Markdown Source"); mi.show()
            mi.connect("activate", lambda _: self.reveal_markdown(span))
            menu.append(mi); added = True
        url = self._get_url_at_iter(it)
        if url:
            if not added:
                sep = Gtk.SeparatorMenuItem(); sep.show(); menu.append(sep)
            mi = Gtk.MenuItem(label="Go to"); mi.show()
            mi.connect("activate", lambda _: webbrowser.open(url))
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

    def _get_note_state(self):
        if not self.current_path:
            return None
        if self.file_ops.is_todo(self.current_path):
            return self.todo_styler.get_state_items()
        b = self.text_view.get_buffer()
        return b.get_text(*b.get_bounds(), True)

    def _apply_chrono_state(self, st):
        if self.file_ops.is_todo(self.current_path):
            self.todo_styler.clear_all()
            for i in st:
                self.todo_styler.add_todo(i["txt"], i["done"], i.get("ts"), i.get("tid"))
            self.todo_styler.update_checked_count()
        else:
            self.text_view.get_buffer().set_text(st)
        self.on_save()

    def apply_autosave(self):
        (GLib.source_remove(self.timer_id) if self.timer_id else None)
        v = self.config_manager.get("autosave"); (setattr(self, 'timer_id', GLib.timeout_add_seconds(int(v), lambda: self.on_save() or True)) if v.isdigit() else None)


if __name__ == "__main__":
    app = SimpleNotes_GTK(); app.connect("destroy", Gtk.main_quit); app.show_all(); Gtk.main()
