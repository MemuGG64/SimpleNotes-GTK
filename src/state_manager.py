import time

class StateManager:
    def __init__(self, max_history=50):
        self.max_history = max_history
        self.hist = {}    # {path: [state1, state2, ...]}
        self.h_idx = {}   # {path: current_index}

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
        
        # Don't push if state hasn't changed
        if h and 0 <= idx < len(h) and h[idx] == state:
            return False
            
        # If we are in the middle of history and push a new state, truncate forward
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
