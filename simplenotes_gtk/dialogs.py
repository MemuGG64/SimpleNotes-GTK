import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class UIHelpers:
    @staticmethod
    def make_icon(icon_name, symbolic=True):
        name = icon_name if symbolic else icon_name.removesuffix("-symbolic")
        return Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)

    @staticmethod
    def create_btn(icon_name, tip=None, cb=None):
        b = Gtk.Button()
        b.add(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
        if tip: b.set_tooltip_text(tip)
        if cb: b.connect("clicked", cb)
        return b

    @staticmethod
    def show_dialog(parent, msg_type, buttons, text, secondary_text=None):
        dlg = Gtk.MessageDialog(
            transient_for=parent,
            message_type=msg_type,
            buttons=buttons,
            text=text
        )
        if secondary_text:
            dlg.format_secondary_text(secondary_text)
        return dlg

    @staticmethod
    def get_text_input(parent, title, default_text=""):
        dlg = UIHelpers.show_dialog(parent, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, title)
        ent = Gtk.Entry(text=default_text)
        ent.set_activates_default(True)
        dlg.get_message_area().pack_start(ent, True, True, 5)
        dlg.set_default_response(Gtk.ResponseType.OK)
        dlg.show_all()
        response = dlg.run()
        text = ent.get_text().strip()
        dlg.destroy()
        if response == Gtk.ResponseType.OK:
            return text
        return None

    @staticmethod
    def confirm(parent, text, secondary=None, warn=True):
        m_type = Gtk.MessageType.WARNING if warn else Gtk.MessageType.QUESTION
        dlg = UIHelpers.show_dialog(parent, m_type, Gtk.ButtonsType.YES_NO, text, secondary)
        response = dlg.run()
        dlg.destroy()
        return response == Gtk.ResponseType.YES


def create_note(parent, config_manager, is_todo):
    dlg = UIHelpers.show_dialog(parent, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, "Create New Note")
    area = dlg.get_message_area()
    ent = Gtk.Entry(placeholder_text="Note Name")
    ent.set_activates_default(True)
    area.pack_start(ent, True, True, 5)

    box_opts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    cb_fol = Gtk.ComboBoxText.new_with_entry()
    cb_fol.append_text("Root")
    if config_manager.get("folders"):
        try:
            for f in os.scandir(config_manager.get("dir")):
                if f.is_dir() and not f.name.startswith('.'):
                    cb_fol.append_text(f.name)
        except OSError:
            pass
    cb_fol.set_active(0)
    box_opts.pack_start(cb_fol, True, True, 0)

    cb_ext = Gtk.ComboBoxText()
    for e in [".txt", ".md", ".json"]:
        cb_ext.append_text(e)
    cb_ext.set_active(0)
    box_opts.pack_start(cb_ext, False, False, 0)
    area.pack_start(box_opts, True, True, 5)

    dlg.show_all()
    if dlg.run() == Gtk.ResponseType.OK and ent.get_text().strip():
        name = ent.get_text().strip()
        folder = cb_fol.get_child().get_text().strip()
        ext = cb_ext.get_active_text()
        dlg.destroy()
        return name, folder, ext
    dlg.destroy()
    return None


def move_note(parent, config_manager):
    dlg = UIHelpers.show_dialog(parent, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, "Move Note to Folder")
    area = dlg.get_message_area()
    cb = Gtk.ComboBoxText.new_with_entry()
    cb.append_text("Root")
    if config_manager.get("folders"):
        try:
            for f in os.scandir(config_manager.get("dir")):
                if f.is_dir() and not f.name.startswith('.'):
                    cb.append_text(f.name)
        except OSError:
            pass
    cb.set_active(0)
    area.pack_start(cb, True, True, 5)
    dlg.show_all()
    if dlg.run() == Gtk.ResponseType.OK:
        folder = cb.get_child().get_text().strip()
        dlg.destroy()
        return folder
    dlg.destroy()
    return None


def confirm_folder(parent, config_manager, title):
    dlg = UIHelpers.show_dialog(parent, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, title)
    area = dlg.get_message_area()
    cb = Gtk.ComboBoxText.new_with_entry()
    cb.append_text("Root")
    if config_manager.get("folders"):
        try:
            for f in os.scandir(config_manager.get("dir")):
                if f.is_dir() and not f.name.startswith('.'):
                    cb.append_text(f.name)
        except OSError:
            pass
    cb.set_active(0)
    area.pack_start(cb, True, True, 5)
    dlg.show_all()
    if dlg.run() == Gtk.ResponseType.OK:
        folder = cb.get_child().get_text().strip()
        dlg.destroy()
        return folder
    dlg.destroy()
    return None
