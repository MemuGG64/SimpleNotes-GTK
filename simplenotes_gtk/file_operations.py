import os
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from gi.repository import Gio

log = logging.getLogger(__name__)


def detect_checklist(content):
    if isinstance(content, str) and content.startswith("[{") and content.endswith("}]"):
        try:
            items = json.loads(content)
            return isinstance(items, list) and all(
                isinstance(i, dict) and "id" in i and "title" in i and "isDone" in i
                for i in items
            )
        except (json.JSONDecodeError, TypeError):
            pass
    return False


def serialize_checklist(tasks):
    return json.dumps(tasks, separators=(",", ":"))


class FileOperations:
    def __init__(self, config_manager):
        self.config = config_manager

    def get_notes_dir(self):
        return self.config.get("dir")

    def is_todo(self, filepath):
        if filepath.endswith('.json'):
            return True
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return detect_checklist(f.read())
        except Exception as e:
            log.debug("is_todo error %s: %s", filepath, e)
            return False

    def list_files(self, search_query=""):
        notes_dir = self.get_notes_dir()
        if not os.path.exists(notes_dir):
            return [], set()

        files = []
        all_folders = set()
        query = search_query.lower()
        deep = self.config.get("search")

        for root, _, filenames in os.walk(notes_dir):
            folder_name = os.path.basename(root)
            if root != notes_dir:
                all_folders.add(folder_name)

            for f in [x for x in filenames if x.endswith(('.txt', '.json', '.md'))]:
                path = os.path.join(root, f)
                name_match = not query or query in f.lower()
                content = None

                if not name_match:
                    if not deep:
                        continue
                    try:
                        with open(path, 'r', encoding='utf-8') as fh:
                            content = fh.read()
                        if query not in content.lower():
                            continue
                    except OSError:
                        continue

                is_todo = f.endswith('.json')
                if not is_todo:
                    if content is not None:
                        is_todo = detect_checklist(content)
                    else:
                        is_todo = self.is_todo(path)

                files.append({
                    "path": path,
                    "name": f,
                    "folder": folder_name if root != notes_dir else "Root",
                    "is_todo": is_todo
                })

        return files, all_folders

    def create_note(self, name, folder="Root", is_todo=False, extension=".txt"):
        target_dir = self.get_notes_dir()
        if folder and folder != "Root":
            target_dir = os.path.join(target_dir, folder)

        Path(target_dir).mkdir(parents=True, exist_ok=True)
        if not any(name.endswith(ext) for ext in ['.txt', '.json', '.md']):
            name += extension
        path = os.path.join(target_dir, name)

        if os.path.exists(path):
            return None, "exists"

        content = "[]" if is_todo else ""
        try:
            with open(path, 'w') as f:
                f.write(content)
            return path, None
        except Exception as e:
            return None, str(e)

    def rename_note(self, old_path, new_name):
        if not any(new_name.endswith(ext) for ext in ['.txt', '.json', '.md']):
            new_name += os.path.splitext(old_path)[1]
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        try:
            os.rename(old_path, new_path)
            return new_path, None
        except Exception as e:
            return None, str(e)

    def change_extension(self, path, new_ext):
        new_path = os.path.splitext(path)[0] + new_ext
        if os.path.exists(new_path):
            return None, "exists"
        try:
            os.rename(path, new_path)
            return new_path, None
        except Exception as e:
            return None, str(e)

    def move_note(self, old_path, target_folder):
        target_dir = self.get_notes_dir()
        if target_folder and target_folder != "Root":
            target_dir = os.path.join(target_dir, target_folder)

        Path(target_dir).mkdir(parents=True, exist_ok=True)
        new_path = os.path.join(target_dir, os.path.basename(old_path))

        if os.path.exists(new_path):
            return None, "exists"

        try:
            os.rename(old_path, new_path)
            return new_path, None
        except Exception as e:
            return None, str(e)

    def delete_note(self, path):
        try:
            if sys.platform == "darwin":
                escaped = path.replace('"', '\\"')
                result = subprocess.run(
                    ["osascript", "-e",
                     f'tell app "Finder" to delete (POSIX file "{escaped}" as alias)'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    return True, None
            file = Gio.File.new_for_path(path)
            file.trash(None)
            return True, None
        except Exception:
            try:
                os.remove(path)
                return True, None
            except Exception as e2:
                return False, str(e2)

    def rename_folder(self, old_folder_name, new_folder_name):
        old_path = os.path.join(self.get_notes_dir(), old_folder_name)
        new_path = os.path.join(self.get_notes_dir(), new_folder_name)
        try:
            os.rename(old_path, new_path)
            return old_path, new_path, None
        except Exception as e:
            return None, None, str(e)

    def delete_folder(self, folder_name):
        path = os.path.join(self.get_notes_dir(), folder_name)
        try:
            shutil.rmtree(path)
            return True, None
        except Exception as e:
            return False, str(e)

    def save_text_note(self, path, content):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError as e:
            log.error("save_text_note %s: %s", path, e)

    def save_todo_note(self, path, todo_items):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(serialize_checklist(todo_items))
        except OSError as e:
            log.error("save_todo_note %s: %s", path, e)

    def load_note_content(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except OSError as e:
            log.error("load_note_content %s: %s", path, e)
            return ""

    def default_extension(self):
        return self.config.get("default_ext", ".txt")

    def convert_folder(self, folder, target_ext):
        notes_dir = self.get_notes_dir()
        if folder == "Root":
            base = notes_dir
        else:
            base = os.path.join(notes_dir, folder)
        if not os.path.isdir(base):
            return [], f"Folder not found: {base}"

        converted = []
        for root, _, files in os.walk(base):
            for f in files:
                if not f.endswith(('.txt', '.json', '.md')):
                    continue
                old = os.path.join(root, f)
                old_ext = os.path.splitext(f)[1]
                if old_ext == target_ext:
                    continue
                new = os.path.splitext(old)[0] + target_ext
                if os.path.exists(new):
                    log.warning("convert_folder skip %s → %s (exists)", f, target_ext)
                    continue
                try:
                    os.rename(old, new)
                    converted.append((old, new))
                except OSError as e:
                    log.error("convert_folder error %s: %s", f, e)
        return converted, None
