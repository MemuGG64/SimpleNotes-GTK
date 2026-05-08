import os
import json
from pathlib import Path

class ConfigManager:
    DEFAULT_CONFIG = {
        "dir": os.path.expanduser("~/Documents/SimpleNotes-GTK"),
        "autosave": "30",
        "search": False,
        "sort": "text_first",
        "folders": True,
        "view": "list",
        "pinned": [],
        "fol_order": [],
        "width": 950,
        "height": 650,
        "binds": {
            "save": "<Primary>s",
            "undo": "<Primary>z",
            "redo": "<Primary>y",
            "n_txt": "<Primary>n",
            "n_todo": "<Primary>t",
            "find": "<Primary>f",
            "switch_note": "<Primary>bar"
        }
    }

    def __init__(self, settings_file=None):
        if settings_file is None:
            self.settings_file = os.path.expanduser("~/.config/sng_config.json")
        else:
            self.settings_file = settings_file
        
        self.conf = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    if "binds" in data:
                        self.conf["binds"].update(data.pop("binds"))
                    self.conf.update(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}")

    def save(self):
        try:
            Path(self.settings_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.conf, f, indent=4)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get(self, key):
        return self.conf.get(key)

    def set(self, key, val):
        self.conf[key] = val
        self.save()

    def update(self, data):
        self.conf.update(data)
        self.save()

    @property
    def notes_dir(self):
        return self.conf["dir"]
