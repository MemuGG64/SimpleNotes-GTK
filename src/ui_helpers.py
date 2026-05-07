import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class UIHelpers:
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
