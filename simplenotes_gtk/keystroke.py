import re
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib


class KeyStroke:
    def __init__(self, text_view, note_styler, config_manager, callbacks):
        self.text_view = text_view
        self.note_styler = note_styler
        self.config = config_manager
        self.cb = callbacks

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape and self.cb["get_stack_child"]() == "settings":
            self.cb["show_note_view"]()
            return True

        s_note_bind = self.config.get("binds").get("switch_note", "")
        if s_note_bind:
            k, m = Gtk.accelerator_parse(s_note_bind)
            mod_mask = Gtk.accelerator_get_default_mod_mask()
            if event.keyval == k and (event.state & mod_mask) == (m & mod_mask):
                GLib.idle_add(self.cb["switch_to_last_note"])
                return True
            if k == Gdk.KEY_Tab and event.keyval == Gdk.KEY_ISO_Left_Tab and (event.state & mod_mask) == (m & mod_mask):
                GLib.idle_add(self.cb["switch_to_last_note"])
                return True

        if widget == self.text_view and self.cb["get_stack_child"]() == "text":
            if event.keyval == Gdk.KEY_Return:
                buf = widget.get_buffer()
                it = buf.get_iter_at_mark(buf.get_insert())
                line_iter = it.copy()
                line_iter.set_line_offset(0)
                m = re.match(r'^(\s*([*\-]\s*)?)', buf.get_text(line_iter, it, False))
                if m and m.group(1):
                    GLib.idle_add(lambda: buf.insert_at_cursor(m.group(1)))
            elif event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_BackSpace, Gdk.KEY_Delete):
                buf = widget.get_buffer()
                it = buf.get_iter_at_mark(buf.get_insert())
                offset = it.get_offset()
                text = buf.get_text(*buf.get_bounds(), True)
                img_p = r'!\[([^\]|]*)(?:\|(\d+))?\]\(([^\)]+)\)'
                lnk_p = r'\[([^\]]+)\]\(([^\)]+)\)'
                best = None
                by_end = event.keyval == Gdk.KEY_BackSpace
                for pat in [img_p, lnk_p]:
                    for m in re.finditer(pat, text):
                        ms, me = m.span()
                        if by_end:
                            if ms <= offset <= me:
                                best = (ms, me)
                                break
                            if me < offset + 2 and (best is None or me > best[1]):
                                best = (ms, me)
                        else:
                            if ms <= offset <= me:
                                best = (ms, me)
                                break
                            if ms > offset - 2 and (best is None or ms < best[0]):
                                best = (ms, me)
                    if best and best[0] <= offset <= best[1]:
                        break
                if best:
                    self.note_styler.is_rendering = True
                    s = buf.get_iter_at_offset(best[0])
                    e = buf.get_iter_at_offset(best[1])
                    buf.delete(s, e)
                    self.note_styler.is_rendering = False
                    self.note_styler.apply_markdown()
                    return True
        return False
