import os
import json
import tempfile
from simplenotes_gtk.file_operations import (
    detect_checklist,
    serialize_checklist,
    FileOperations,
)


class _StubConfig:
    def __init__(self, d):
        self._d = d
    def get(self, k, default=None):
        return self._d.get(k, default)


def test_detect_checklist_true():
    data = json.dumps([{"id": "1", "title": "a", "isDone": False}])
    assert detect_checklist(data)


def test_detect_checklist_false_string():
    assert not detect_checklist("just a note")


def test_detect_checklist_false_empty():
    assert not detect_checklist("")


def test_detect_checklist_false_malformed():
    assert not detect_checklist("{bad json")


def test_detect_checklist_false_not_list():
    data = json.dumps({"id": "1", "title": "a", "isDone": False})
    assert not detect_checklist(data)


def test_serialize_checklist():
    tasks = [{"id": "x", "title": "test", "isDone": True}]
    result = serialize_checklist(tasks)
    parsed = json.loads(result)
    assert parsed == tasks


def test_is_todo():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        path = os.path.join(tmp, "test.json")
        data = json.dumps([{"id": "1", "title": "x", "isDone": False}])
        with open(path, "w") as f:
            f.write(data)
        assert fo.is_todo(path)


def test_is_todo_plain_text():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        path = os.path.join(tmp, "note.txt")
        with open(path, "w") as f:
            f.write("hello world")
        assert not fo.is_todo(path)


def test_is_todo_nonexistent():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        assert not fo.is_todo("/nonexistent")


def test_is_todo_json_extension():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        path = os.path.join(tmp, "list.json")
        with open(path, "w") as f:
            f.write("not actually json")
        assert fo.is_todo(path)


def test_default_extension():
    cfg = _StubConfig({"default_ext": ".md"})
    fo = FileOperations(cfg)
    assert fo.default_extension() == ".md"


def test_default_extension_fallback():
    cfg = _StubConfig({})
    fo = FileOperations(cfg)
    assert fo.default_extension() == ".txt"


def test_create_text_note():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        path, err = fo.create_note("my note", folder="Root", is_todo=False, extension=".txt")
        assert path is not None
        assert err is None
        assert os.path.exists(path)
        assert path.endswith(".txt")
        with open(path) as f:
            assert f.read() == ""


def test_create_todo_note():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        path, err = fo.create_note("tasks", folder="Root", is_todo=True, extension=".json")
        assert path is not None
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
            assert isinstance(data, list)


def test_create_note_in_folder():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        path, err = fo.create_note("sub", folder="MyFolder", is_todo=False, extension=".md")
        assert path is not None
        assert "MyFolder" in path
        assert os.path.exists(os.path.join(tmp, "MyFolder"))


def test_list_files_empty():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        files, folders = fo.list_files()
        assert files == []
        assert folders == set()


def test_list_files_with_notes():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        fo.create_note("a", extension=".txt")
        fo.create_note("b", extension=".md")
        files, _ = fo.list_files()
        assert len(files) >= 2


def test_save_and_load_text():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p, _ = fo.create_note("save_test")
        fo.save_text_note(p, "hello world")
        content = fo.load_note_content(p)
        assert content == "hello world"


def test_save_todo_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p, _ = fo.create_note("todo_test", is_todo=True, extension=".json")
        items = [{"id": "x1", "title": "task1", "isDone": False}]
        fo.save_todo_note(p, items)
        content = fo.load_note_content(p)
        loaded = json.loads(content)
        assert loaded == items


def test_rename_note():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p, _ = fo.create_note("oldname")
        new_p, err = fo.rename_note(p, "newname")
        assert err is None
        assert new_p != p
        assert os.path.exists(new_p)
        assert not os.path.exists(p)


def test_delete_note():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p, _ = fo.create_note("delete_me")
        assert os.path.exists(p)
        success, _ = fo.delete_note(p)
        assert success
        assert not os.path.exists(p)


def test_change_extension():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p, _ = fo.create_note("ext_test", extension=".txt")
        new_p, err = fo.change_extension(p, ".md")
        assert err is None
        assert new_p.endswith(".md")
        assert os.path.exists(new_p)


def test_move_note():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p, _ = fo.create_note("movable")
        new_p, err = fo.move_note(p, "SubFolder")
        assert err is None
        assert "SubFolder" in new_p
        assert os.path.exists(new_p)


def test_rename_folder():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        fo.create_note("inside", folder="OldFolder")
        op, np, err = fo.rename_folder("OldFolder", "NewFolder")
        assert err is None
        assert os.path.exists(os.path.join(tmp, "NewFolder"))


def test_delete_folder():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        fo.create_note("inside", folder="DelMe")
        success, err = fo.delete_folder("DelMe")
        assert success
        assert not os.path.exists(os.path.join(tmp, "DelMe"))


def test_list_files_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        assert fo.list_files() == ([], set())


def test_convert_folder_root():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p1, _ = fo.create_note("a", extension=".txt")
        p2, _ = fo.create_note("b", extension=".md")
        converted, err = fo.convert_folder("Root", ".md")
        assert err is None
        assert len(converted) == 1
        assert converted[0] == (p1, os.path.splitext(p1)[0] + ".md")
        assert os.path.exists(converted[0][1])
        assert not os.path.exists(p1)


def test_convert_folder_subfolder():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p1, _ = fo.create_note("inside", folder="Sub", extension=".txt")
        converted, err = fo.convert_folder("Sub", ".md")
        assert err is None
        assert len(converted) == 1
        assert converted[0][0] == p1
        assert converted[0][1].endswith(".md")
        assert os.path.exists(converted[0][1])


def test_convert_folder_already_target():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        p1, _ = fo.create_note("a", extension=".md")
        converted, err = fo.convert_folder("Root", ".md")
        assert err is None
        assert len(converted) == 0


def test_convert_folder_nonexistent():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp})
        fo = FileOperations(cfg)
        converted, err = fo.convert_folder("NoSuchFolder", ".txt")
        assert err is not None
        assert converted == []


def test_list_files_deep_search():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _StubConfig({"dir": tmp, "search": True})
        fo = FileOperations(cfg)
        fo.create_note("aaa", extension=".txt")
        p2, _ = fo.create_note("bbb", extension=".txt")
        with open(p2, "w") as f:
            f.write("secret word")
        files, _ = fo.list_files("secret")
        assert len(files) == 1
        assert "bbb" in files[0]["name"]
