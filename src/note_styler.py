import gi
import re
import os
import time
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf

class NoteStylist:
    def __init__(self, text_view, file_ops):
        self.text_view = text_view
        self.file_ops = file_ops
        self.buffer = text_view.get_buffer()
        self.revealed_range = None
        self.is_rendering = False 
        self.setup_tags()

    def setup_tags(self):
        self.tag_bold = self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.tag_link = self.buffer.create_tag("link", foreground="#3584e4", underline=Pango.Underline.SINGLE)
        self.tag_hidden = self.buffer.create_tag("hidden", invisible=True)
        self.tag_image = self.buffer.create_tag("image_marker")
        # Special tag to identify pixbuf characters for easy removal
        self.tag_pixbuf = self.buffer.create_tag("pixbuf_marker")

    def apply_markdown(self):
        if self.is_rendering: return
        self.is_rendering = True
        
        try:
            # 0. Clear all rendering tags and pixbufs
            start, end = self.buffer.get_bounds()
            for tag in [self.tag_bold, self.tag_link, self.tag_hidden, self.tag_image]:
                self.buffer.remove_tag(tag, start, end)

            # Remove all pixbufs added by NoteStylist
            # We iterate backwards to maintain valid offsets while deleting
            it = self.buffer.get_start_iter()
            while True:
                # Find the next range with our pixbuf tag
                res = it.forward_to_tag_toggle(self.tag_pixbuf)
                if not res: break
                
                # If it's a start of the tag, get the end and delete
                if it.begins_tag(self.tag_pixbuf):
                    end_it = it.copy()
                    end_it.forward_to_tag_toggle(self.tag_pixbuf)
                    self.buffer.delete(it, end_it)
                    # it is now at the position of the deleted char
                else:
                    # Just keep moving
                    pass
                if it.is_end(): break

            # 1. Bold Headers
            cursor = self.buffer.get_iter_at_offset(0)
            while not cursor.is_end():
                line_start = cursor.copy()
                if not cursor.ends_line(): cursor.forward_to_line_end()
                line_text = self.buffer.get_text(line_start, cursor, False)
                if line_text.lstrip().startswith('#'):
                    self.buffer.apply_tag(self.tag_bold, line_start, cursor)
                if not cursor.is_end(): cursor.forward_line()

            # 2. Links and Images
            self.apply_links_and_images()
        finally:
            self.is_rendering = False

    def apply_links_and_images(self):
        # Text is now clean of old pixbufs
        text = self.buffer.get_text(*self.buffer.get_bounds(), True)
        img_pat = r'!\[([^\]|]*)(?:\|(\d+))?\]\(([^\)]+)\)'
        lnk_pat = r'\[([^\]]+)\]\(([^\)]+)\)'

        def is_revealed(s_off, e_off):
            if not self.revealed_range: return False
            rs, re_off = self.revealed_range
            return not (e_off <= rs or s_off >= re_off)

        all_matches = []
        for m in re.finditer(img_pat, text): all_matches.append(('img', m))
        for m in re.finditer(lnk_pat, text):
            if m.start() > 0 and text[m.start()-1] == '!': continue
            all_matches.append(('lnk', m))
        
        all_matches.sort(key=lambda x: x[1].start())

        # Since we removed pixbufs, the current text matches buffer offsets perfectly
        for m_type, match in all_matches:
            ms, me = match.span()
            s, e = self.buffer.get_iter_at_offset(ms), self.buffer.get_iter_at_offset(me)

            if is_revealed(ms, me):
                self.buffer.apply_tag(self.tag_link, s, e)
                continue

            if m_type == 'img':
                self.buffer.apply_tag(self.tag_hidden, s, e)
                width = int(match.group(2)) if match.group(2) else 250
                path = match.group(3)
                if os.path.exists(path):
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width, -1, True)
                        # Insert pixbuf and tag it so we can find it later
                        # insert_pixbuf inserts it BEFORE the iterator
                        self.buffer.insert_pixbuf(e, pixbuf)
                        
                        # Apply our removal tag to the pixbuf char
                        tag_s = e.copy()
                        tag_s.backward_char()
                        self.buffer.apply_tag(self.tag_pixbuf, tag_s, e)
                    except: pass
            else:
                g1_s, g1_e = match.start(1), match.end(1)
                self.buffer.apply_tag(self.tag_hidden, s, self.buffer.get_iter_at_offset(g1_s))
                self.buffer.apply_tag(self.tag_link, self.buffer.get_iter_at_offset(g1_s), self.buffer.get_iter_at_offset(g1_e))
                self.buffer.apply_tag(self.tag_hidden, self.buffer.get_iter_at_offset(g1_e), e)

    def handle_paste(self):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        image = clipboard.wait_for_image()
        if image:
            media_dir = os.path.join(self.file_ops.get_notes_dir(), ".media")
            os.makedirs(media_dir, exist_ok=True)
            path = os.path.join(media_dir, f"img_{int(time.time())}.png")
            image.savev(path, "png", [], [])
            self.insert_markdown(f"![image]({path})")
            return True

        text = clipboard.wait_for_text()
        if text and (text.startswith("http://") or text.startswith("https://")):
            res = self.buffer.get_selection_bounds()
            label = self.buffer.get_text(*res, False) if res else "link"
            if res: self.buffer.delete(*res)
            self.insert_markdown(f"[{label}]({text})")
            return True
        return False

    def insert_markdown(self, text):
        self.buffer.begin_user_action()
        self.buffer.insert_at_cursor(text + " ") 
        self.text_view.scroll_to_mark(self.buffer.get_insert(), 0, False, 0, 0)
        self.buffer.end_user_action()

    def get_markdown_at_iter(self, it):
        offset = it.get_offset()
        text = self.buffer.get_text(*self.buffer.get_bounds(), True)
        img_pat = r'!\[([^\]|]*)(?:\|(\d+))?\]\(([^\)]+)\)'
        lnk_pat = r'\[([^\]]+)\]\(([^\)]+)\)'
        for pat in [img_pat, lnk_pat]:
            for match in re.finditer(pat, text):
                if match.start() <= offset <= match.end():
                    return match.span()
        return None
