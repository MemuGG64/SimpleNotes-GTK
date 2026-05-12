import os
import json
import shutil
import time
from pathlib import Path
from gi.repository import Gio

class FileOperations:
    def __init__(self, config_manager):
        self.config = config_manager

    def get_notes_dir(self):
        return self.config.get("dir")

    def is_todo(self, filepath):
        try:
            with open(filepath, 'r') as f:
                return f.read(2).strip().startswith('[')
        except:
            return False

    def list_files(self, search_query=""):
        notes_dir = self.get_notes_dir()
        if not os.path.exists(notes_dir):
            return [], set()

        files = []
        all_folders = set()
        query = search_query.lower()

        for root, dirs, filenames in os.walk(notes_dir):
            folder_name = os.path.basename(root)
            if root != notes_dir:
                all_folders.add(folder_name)
            
            for f in [x for x in filenames if x.endswith(('.txt', '.json', '.md'))]:
                path = os.path.join(root, f)
                if not query or query in f.lower():
                    files.append({
                        "path": path,
                        "name": f,
                        "folder": folder_name if root != notes_dir else "Root",
                        "is_todo": self.is_todo(path)
                    })
        
        return files, all_folders

    def create_note(self, name, folder="Root", is_todo=False, extension=".txt"):
        target_dir = self.get_notes_dir()
        if folder and folder != "Root":
            target_dir = os.path.join(target_dir, folder)
        
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        # Ensure name doesn't already have the extension if user typed it
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
        # If new_name doesn't have extension, keep the old one
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
            # Try trashing first
            file = Gio.File.new_for_path(path)
            file.trash(None)
            return True, None
        except Exception as e:
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
        with open(path, 'w') as f:
            f.write(content)

    def save_todo_note(self, path, todo_items):
        with open(path, 'w') as f:
            json.dump(todo_items, f, separators=(',', ':'))

    def load_note_content(self, path):
        with open(path, 'r') as f:
            return f.read()
