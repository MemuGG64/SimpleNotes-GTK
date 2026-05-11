import gi
import time
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from ui_helpers import UIHelpers

class ToDoStyler:
    def __init__(self, todo_listbox, todo_sw, container, on_change_cb, on_save_cb):
        self.active_box = todo_listbox
        self.sw = todo_sw
        self.on_change = on_change_cb
        self.on_save = on_save_cb
        self.drag_row = None

        self.completed_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.completed_box.show()
        self.expander = Gtk.Expander(label="")
        self.expander.add(self.completed_box)
        container.pack_start(self.expander, False, False, 0)
        self.update_checked_count()

    def update_checked_count(self):
        completed = len(self.completed_box.get_children())
        if completed > 0:
            self.expander.set_label(f"  {completed} checked")
            self.expander.show()
        else:
            self.expander.hide()

    def clear_all(self):
        for r in list(self.active_box.get_children()):
            self.active_box.remove(r)
        for r in list(self.completed_box.get_children()):
            self.completed_box.remove(r)

    def get_all_items(self):
        items = []
        for i, r in enumerate(self.active_box.get_children()):
            items.append({
                "dateCreated": getattr(r, 'ts', int(time.time() * 1000)),
                "id": i + 1,
                "isDone": False,
                "title": r.ent.get_text()
            })
        offset = len(items)
        for i, r in enumerate(self.completed_box.get_children()):
            items.append({
                "dateCreated": getattr(r, 'ts', int(time.time() * 1000)),
                "id": offset + i + 1,
                "isDone": True,
                "title": r.ent.get_text()
            })
        return items

    def get_state_items(self):
        items = []
        for r in self.active_box.get_children():
            items.append({"done": False, "txt": r.ent.get_text(), "ts": r.ts})
        for r in self.completed_box.get_children():
            items.append({"done": True, "txt": r.ent.get_text(), "ts": r.ts})
        return items

    def show_all(self):
        self.active_box.show_all()
        self.completed_box.show_all()

    def add_todo(self, txt="", done=False, d_c=None, index=-1):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.get_style_context().add_class('t-box')
        hb = Gtk.EventBox()
        hb.add(Gtk.Label(label="⣿", margin_start=5, margin_end=5))

        chk = Gtk.CheckButton(active=done, focus_on_click=False)
        chk.connect("toggled", lambda c: self._on_check_toggled(c, row))

        ent = Gtk.Entry(text=txt, hexpand=True)
        ent.connect("changed", lambda e: self.on_change())

        def on_key(e, ev):
            if ev.keyval == Gdk.KEY_Return:
                if row.get_parent() == self.completed_box:
                    idx = -1
                else:
                    idx = row.get_index() + 1
                GLib.idle_add(lambda: self.add_todo(index=idx).grab_focus())
                return True
            if ev.keyval == Gdk.KEY_BackSpace and not e.get_text():
                parent = row.get_parent()
                if not parent:
                    return False
                idx = row.get_index()
                if idx > 0:
                    pr = parent.get_row_at_index(idx - 1)
                    if pr:
                        pr.ent.grab_focus()
                parent.remove(row)
                self.on_change()
                self.on_save()
                self.update_checked_count()
                return True
            return False

        ent.connect("key-press-event", on_key)
        del_b = UIHelpers.create_btn(
            "edit-delete-symbolic",
            cb=lambda x: [row.get_parent().remove(row) if row.get_parent() else None,
                          self.on_change(), self.on_save(),
                          self.update_checked_count()])
        del_b.set_relief(Gtk.ReliefStyle.NONE)
        for w in (hb, chk, ent, del_b):
            box.pack_start(w, w == ent, w == ent, 0)
        row.add(box)
        row.ts, row.chk, row.ent, row.box = d_c, chk, ent, box

        target = self.completed_box if done else self.active_box
        if done:
            row.get_style_context().add_class('done')
        if index == -1:
            target.add(row)
        else:
            target.insert(row, index)

        tgt = Gtk.TargetEntry.new("ROW", Gtk.TargetFlags.SAME_APP, 0)
        hb.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [tgt],
                           Gdk.DragAction.MOVE)
        hb.connect("drag-begin",
                    lambda w, c: setattr(self, 'drag_row', row))
        hb.connect("drag-data-get",
                    lambda w, c, d, i, t: d.set(
                        Gdk.Atom.intern("ROW", False), 8, b""))
        row.drag_dest_set(Gtk.DestDefaults.ALL, [tgt], Gdk.DragAction.MOVE)
        row.connect("drag-motion", self.d_motion, row)
        row.connect("drag-leave", self.d_clean)
        row.connect("drag-data-received", self.d_drop, row)

        row.show_all()
        self.update_checked_count()
        if target == self.active_box and (index == -1
            or index >= len(target.get_children()) - 1):
            GLib.idle_add(self.scroll_to_bottom)
        return ent

    def _on_check_toggled(self, chk, row):
        if chk.get_active():
            self.active_box.remove(row)
            self.completed_box.add(row)
            row.get_style_context().add_class('done')
        else:
            self.completed_box.remove(row)
            self.active_box.add(row)
            row.get_style_context().remove_class('done')
        self.on_change()
        self.on_save()
        self.update_checked_count()

    def scroll_to_bottom(self):
        adj = self.sw.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    def d_clean(self, widget, *args):
        parent = widget.get_parent()
        if parent:
            parent.drag_unhighlight_row()

    def d_motion(self, w, c, x, y, t, t_row):
        if self.drag_row == t_row:
            return False
        lb = t_row.get_parent()
        if lb:
            lb.drag_highlight_row(t_row)
        Gdk.drag_status(c, Gdk.DragAction.MOVE, t)
        return True

    def d_drop(self, w, c, x, y, d, i, t, t_row):
        lb = t_row.get_parent()
        if lb:
            lb.drag_unhighlight_row()
        if self.drag_row and self.drag_row != t_row:
            t_idx = t_row.get_index()
            if y > t_row.get_allocated_height() / 2:
                t_idx += 1
            curr_idx = self.drag_row.get_index()
            if curr_idx < t_idx:
                t_idx -= 1
            parent = self.drag_row.get_parent()
            if parent:
                parent.remove(self.drag_row)
                parent.insert(self.drag_row, t_idx)
            Gtk.drag_finish(c, True, False, t)
            self.on_change()
            self.on_save()
            self.update_checked_count()
        else:
            Gtk.drag_finish(c, False, False, t)
