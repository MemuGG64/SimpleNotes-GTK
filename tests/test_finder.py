import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from simplenotes_gtk.finder import find_substrings, find_offsets, InNoteSearch


def test_find_substrings_empty_query():
    assert find_substrings(["buy milk", "walk dog"], "") == []


def test_find_substrings_case_insensitive():
    assert find_substrings(["Buy Milk", "walk Dog", "milk crate"], "MILK") == [0, 2]


def test_find_substrings_no_match():
    assert find_substrings(["buy milk", "walk dog"], "eggs") == []


def test_find_substrings_empty_list():
    assert find_substrings([], "milk") == []


def test_find_offsets_empty_query():
    assert find_offsets("hello world", "") == []


def test_find_offsets_single():
    assert find_offsets("hello hello", "llo") == [(2, 5), (8, 11)]


def test_find_offsets_case_insensitive():
    assert find_offsets("AaA", "aa") == [(0, 2)]


def test_find_offsets_overlapping_is_non_overlapping():
    assert find_offsets("aaaa", "aa") == [(0, 2), (2, 4)]


def test_find_offsets_no_match():
    assert find_offsets("hello", "xyz") == []


def _make_note_search(text, hidden_span=None):
    buf = Gtk.TextBuffer()
    buf.set_text(text)
    hidden = buf.create_tag("hidden", invisible=True)
    if hidden_span:
        buf.apply_tag(hidden,
                      buf.get_iter_at_offset(hidden_span[0]),
                      buf.get_iter_at_offset(hidden_span[1]))
    query = {"value": ""}
    ns = InNoteSearch({
        'get_query': lambda: query["value"],
        'get_stack_child': lambda: "text",
        'get_buffer': lambda: buf,
        'get_hidden_tag': lambda: hidden,
        'get_selection_color': lambda: "#35a854",
        'scroll_to_mark': lambda: None,
    })
    return ns, buf, query


def test_in_note_text_matches_all():
    ns, buf, query = _make_note_search("Hello world hello")
    query["value"] = "hello"
    ns.highlight()
    assert ns.matches == [(0, 5), (12, 17)]


def test_in_note_skips_hidden_spans():
    ns, buf, query = _make_note_search("foo ![x](secret) foo", hidden_span=(4, 17))
    query["value"] = "foo"
    ns.highlight()
    assert ns.matches == [(0, 3), (17, 20)]


def test_in_note_empty_query_clears():
    ns, buf, query = _make_note_search("Hello world hello")
    query["value"] = "hello"
    ns.highlight()
    assert len(ns.matches) == 2
    query["value"] = ""
    ns.highlight()
    assert ns.matches == []


def test_in_note_case_insensitive():
    ns, buf, query = _make_note_search("A B A")
    query["value"] = "a"
    ns.highlight()
    assert ns.matches == [(0, 1), (4, 5)]


def test_in_note_step_cycles():
    ns, buf, query = _make_note_search("aaa")
    query["value"] = "a"
    ns.highlight()
    ns.step(1)
    assert ns.idx == 0
    ns.step(1)
    assert ns.idx == 1
    ns.step(-1)
    assert ns.idx == 0
