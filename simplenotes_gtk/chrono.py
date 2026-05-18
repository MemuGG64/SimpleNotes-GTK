import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib


class StateManager:
    def __init__(self, max_history=50):
        self.max_history = max_history
        self.hist = {}
        self.h_idx = {}

    def get_current_state(self, path):
        h = self.hist.get(path, [])
        idx = self.h_idx.get(path, -1)
        if 0 <= idx < len(h):
            return h[idx]
        return None

    def push_state(self, path, state):
        if not path:
            return False
        h = self.hist.setdefault(path, [])
        idx = self.h_idx.setdefault(path, -1)
        if h and 0 <= idx < len(h) and h[idx] == state:
            return False
        if idx < len(h) - 1:
            del h[idx+1:]
        h.append(state)
        if len(h) > self.max_history:
            h.pop(0)
        self.h_idx[path] = len(h) - 1
        return True

    def undo(self, path):
        h = self.hist.get(path, [])
        idx = self.h_idx.get(path, -1)
        if not h or idx <= 0:
            return None
        self.h_idx[path] = idx - 1
        return h[idx - 1]

    def redo(self, path):
        h = self.hist.get(path, [])
        idx = self.h_idx.get(path, -1)
        if not h or idx >= len(h) - 1:
            return None
        self.h_idx[path] = idx + 1
        return h[idx + 1]

    def clear_history(self, path):
        if path in self.hist:
            del self.hist[path]
        if path in self.h_idx:
            del self.h_idx[path]

    def rename_path(self, old_path, new_path):
        if old_path in self.hist:
            self.hist[new_path] = self.hist.pop(old_path)
        if old_path in self.h_idx:
            self.h_idx[new_path] = self.h_idx.pop(old_path)


class Chrono(StateManager):
    def __init__(self, file_ops, callbacks, max_history=50):
        super().__init__(max_history)
        self.file_ops = file_ops
        self.cb = callbacks
        self.undo_timer = None
        self.undoing = False

    def queue(self, *args):
        if not self.undoing and self.cb["get_current_path"]():
            if self.cb["is_text_visible"]():
                self.cb["apply_markdown"]()
            if self.undo_timer:
                GLib.source_remove(self.undo_timer)
            self.undo_timer = GLib.timeout_add(400, self._push)

    def _push(self):
        self.undo_timer = None
        path = self.cb["get_current_path"]()
        self.push_state(path, self.cb["get_state"]())
        return False

    def undo(self):
        st = super().undo(self.cb["get_current_path"]())
        if st is not None:
            self.undoing = True
            self.cb["apply_state"](st)
            self.undoing = False

    def redo(self):
        st = super().redo(self.cb["get_current_path"]())
        if st is not None:
            self.undoing = True
            self.cb["apply_state"](st)
            self.undoing = False

    def get_state(self):
        return self.cb["get_state"]()
