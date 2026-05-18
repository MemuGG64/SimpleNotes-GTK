import json
import logging
import threading
import urllib.request
import webbrowser
from gi.repository import GLib, Gtk

log = logging.getLogger(__name__)

VERSION = "1.3.0"
GITHUB_REPO = "MemuGG64/SimpleNotes-GTK"


class Updater:
    def __init__(self, parent_window):
        self.parent = parent_window

    def check(self):
        threading.Thread(target=self._fetch_latest, daemon=True).start()

    def _fetch_latest(self):
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"User-Agent": "SimpleNotes-GTK", "Accept": "application/vnd.github.v3+json"}
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            if tag and self._version_gt(tag, VERSION):
                url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
                GLib.idle_add(self._prompt, tag, url)
        except Exception as e:
            log.debug("Update check failed: %s", e)

    @staticmethod
    def _version_gt(a, b):
        try:
            va = tuple(int(x) for x in a.split("."))
            vb = tuple(int(x) for x in b.split("."))
            return va > vb
        except ValueError:
            return False

    def _prompt(self, latest, url):
        dlg = Gtk.MessageDialog(
            parent=self.parent, flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            message_format=f"Update available: v{VERSION} → v{latest}",
        )
        dlg.format_secondary_text("Download the new version?")
        if dlg.run() == Gtk.ResponseType.YES:
            webbrowser.open(url)
        dlg.destroy()
