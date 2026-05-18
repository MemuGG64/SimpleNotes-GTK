from simplenotes_gtk.chrono import StateManager


def test_push_and_get():
    sm = StateManager()
    assert sm.push_state("/a", "hello")
    assert sm.get_current_state("/a") == "hello"


def test_undo():
    sm = StateManager()
    sm.push_state("/a", "v1")
    sm.push_state("/a", "v2")
    assert sm.undo("/a") == "v1"


def test_redo():
    sm = StateManager()
    sm.push_state("/a", "v1")
    sm.push_state("/a", "v2")
    sm.undo("/a")
    assert sm.redo("/a") == "v2"


def test_undo_at_boundary():
    sm = StateManager()
    assert sm.undo("/a") is None
    sm.push_state("/a", "v1")
    assert sm.undo("/a") is None


def test_redo_at_boundary():
    sm = StateManager()
    sm.push_state("/a", "v1")
    assert sm.redo("/a") is None


def test_no_duplicate_push():
    sm = StateManager()
    assert sm.push_state("/a", "same")
    assert not sm.push_state("/a", "same")


def test_truncate_on_new_push():
    sm = StateManager()
    sm.push_state("/a", "v1")
    sm.push_state("/a", "v2")
    sm.push_state("/a", "v3")
    sm.undo("/a")
    sm.push_state("/a", "v2b")
    assert sm.undo("/a") == "v2"
    assert sm.redo("/a") == "v2b"
    assert sm.redo("/a") is None


def test_max_history():
    sm = StateManager(max_history=3)
    for i in range(5):
        sm.push_state("/a", f"v{i}")
    assert sm.get_current_state("/a") == "v4"
    assert sm.undo("/a") == "v3"
    assert sm.undo("/a") == "v2"
    assert sm.undo("/a") is None


def test_multiple_paths():
    sm = StateManager()
    sm.push_state("/a", "a1")
    sm.push_state("/b", "b1")
    sm.push_state("/a", "a2")
    assert sm.get_current_state("/a") == "a2"
    assert sm.get_current_state("/b") == "b1"
    assert sm.undo("/a") == "a1"
    assert sm.undo("/b") is None


def test_clear_history():
    sm = StateManager()
    sm.push_state("/a", "v1")
    sm.push_state("/a", "v2")
    sm.clear_history("/a")
    assert sm.get_current_state("/a") is None
    assert sm.undo("/a") is None


def test_rename_path():
    sm = StateManager()
    sm.push_state("/old", "data")
    sm.rename_path("/old", "/new")
    assert sm.get_current_state("/old") is None
    assert sm.get_current_state("/new") == "data"
    assert sm.undo("/new") is None
    assert sm.undo("/old") is None


def test_empty_path_returns_false():
    sm = StateManager()
    assert not sm.push_state("", "data")
    assert not sm.push_state(None, "data")


def test_get_current_state_empty():
    sm = StateManager()
    assert sm.get_current_state("/x") is None
