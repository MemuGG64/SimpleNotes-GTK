import json
import logging
import os
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from gi.repository import GLib, Gtk

log = logging.getLogger(__name__)

VERSION = "1.3.1"
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
                deb_url = next(
                    (a["browser_download_url"] for a in data.get("assets", []) if a["name"].endswith(".deb")),
                    None
                )
                GLib.idle_add(self._prompt, tag, url, deb_url)
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

    def _can_install(self):
        if os.name == "darwin" or not sys.platform.startswith("linux"):
            return False
        try:
            subprocess.run(["pkexec", "--version"], capture_output=True, timeout=2)
            return True
        except Exception:
            return False

    def _prompt(self, latest, url, deb_url):
        can_install = deb_url is not None and self._can_install()

        dlg = Gtk.MessageDialog(
            parent=self.parent, flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            message_format=f"Update available: v{VERSION} → v{latest}",
        )
        if can_install:
            dlg.add_buttons("Install Now", 1, "Release Page", 2, "Later", Gtk.ResponseType.NO)
        else:
            dlg.add_buttons("Release Page", 2, "Later", Gtk.ResponseType.NO)
        resp = dlg.run()
        dlg.destroy()

        if resp == 1 and can_install:
            self._download_and_install(deb_url)
        elif resp == 2:
            webbrowser.open(url)

    def _download_and_install(self, deb_url):
        def do():
            dest = f"/tmp/simplenotes-gtk_latest.deb"
            try:
                urllib.request.urlretrieve(deb_url, dest)
                subprocess.run(["pkexec", "dpkg", "-i", dest], capture_output=True, timeout=120)
                os.unlink(dest)
                GLib.idle_add(self._prompt_restart)
            except Exception as e:
                log.error("Auto-install failed: %s", e)

        threading.Thread(target=do, daemon=True).start()

    def _prompt_restart(self):
        dlg = Gtk.MessageDialog(
            parent=self.parent, flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            message_format="Update installed. Restart now?",
        )
        if dlg.run() == Gtk.ResponseType.YES:
            os.execl(sys.executable, sys.executable, *sys.argv)
        dlg.destroy()
