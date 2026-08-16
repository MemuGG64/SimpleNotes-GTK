import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib


def find_substrings(texts, query):
    if not query:
        return []
    q = query.lower()
    return [i for i, t in enumerate(texts) if q in t.lower()]


def find_offsets(text, query):
    if not query:
        return []
    q = query.lower()
    t = text.lower()
    n = len(q)
    out = []
    start = 0
    while True:
        pos = t.find(q, start)
        if pos < 0:
            return out
        end = pos + n
        out.append((pos, end))
        start = end


class InNoteSearch:
    def __init__(self, callbacks):
        self.cb = callbacks
        self.matches = []
        self.idx = -1
        self._debounce = None
        self._match_tag = None

    def active(self):
        return bool(self.cb["get_query"]())

    def highlight(self):
        self._cancel_debounce()
        self.matches = []
        self.idx = -1
        if self.cb["get_stack_child"]() == "todo":
            self._search_todo()
        else:
            self._search_text()

    def on_content_changed(self):
        if self.active():
            self._cancel_debounce()
            self._debounce = GLib.timeout_add(200, self._run_debounced)

    def _run_debounced(self):
        self._debounce = None
        self.highlight()
        return False

    def step(self, d):
        if not self.matches:
            return
        self.idx = (self.idx + d) % len(self.matches)
        m = self.matches[self.idx]
        if self.cb["get_stack_child"]() == "todo":
            GLib.idle_add(m.ent.grab_focus)
        else:
            buf = self.cb["get_buffer"]()
            buf.place_cursor(buf.get_iter_at_offset(m[0]))
            self.cb["scroll_to_mark"]()

    def _search_text(self):
        query = self.cb["get_query"]()
        buf = self.cb["get_buffer"]()
        tag = self._get_match_tag(buf)
        buf.remove_tag(tag, buf.get_start_iter(), buf.get_end_iter())
        if not query:
            return
        hidden = self.cb["get_hidden_tag"]()
        for s_off, e_off in find_offsets(buf.get_text(*buf.get_bounds(), True), query):
            s = buf.get_iter_at_offset(s_off)
            e = buf.get_iter_at_offset(e_off)
            if s.has_tag(hidden) or e.has_tag(hidden):
                continue
            self.matches.append((s_off, e_off))
            buf.apply_tag(tag, s, e)

    def _search_todo(self):
        query = self.cb["get_query"]()
        styler = self.cb["get_todo_styler"]()
        rows = list(styler.active_box.get_children()) + list(styler.completed_box.get_children())
        for r in rows:
            r.get_style_context().remove_class("search-match")
        if not query:
            return
        for i in find_substrings([r.ent.get_text() for r in rows], query):
            self.matches.append(rows[i])
            rows[i].get_style_context().add_class("search-match")

    def _cancel_debounce(self):
        if self._debounce:
            GLib.source_remove(self._debounce)
            self._debounce = None

    def _get_match_tag(self, buf):
        if self._match_tag is None:
            self._match_tag = buf.create_tag("search_match", background=self.cb["get_selection_color"]())
        return self._match_tag
