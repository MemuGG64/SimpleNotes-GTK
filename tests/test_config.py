import os
import json
import tempfile
from simplenotes_gtk.config import ConfigManager


def test_defaults():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    c = ConfigManager(path)
    os.unlink(path)
    assert c.get("view") == "list"
    assert c.get("autosave") == "30"
    assert c.get("sort") == "text_first"
    assert c.get("binds")["save"] == "<Primary>s"


def test_set_and_get():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    c = ConfigManager(path)
    c.set("view", "tree")
    assert c.get("view") == "tree"
    c2 = ConfigManager(path)
    assert c2.get("view") == "tree"
    os.unlink(path)


def test_update():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    c = ConfigManager(path)
    c.update({"width": 800, "height": 600})
    assert c.get("width") == 800
    assert c.get("height") == 600
    c2 = ConfigManager(path)
    assert c2.get("width") == 800
    os.unlink(path)


def test_notes_dir():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    c = ConfigManager(path)
    assert c.notes_dir == os.path.expanduser("~/Documents/SimpleNotes-GTK")
    os.unlink(path)


def test_settings_file_default():
    c = ConfigManager("/tmp/_sng_test_nonexistent.json")
    assert c.get("view") == "list"
    c.set("view", "tree")
    assert c.get("view") == "tree"
    os.unlink("/tmp/_sng_test_nonexistent.json")


def test_binds_partial_override():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump({"binds": {"save": "<Primary><Shift>s"}}, f)
        path = f.name
    c = ConfigManager(path)
    assert c.get("binds")["save"] == "<Primary><Shift>s"
    assert c.get("binds")["undo"] == "<Primary>z"
    assert c.get("binds")["switch_note"] == "<Primary>bar"
    os.unlink(path)
