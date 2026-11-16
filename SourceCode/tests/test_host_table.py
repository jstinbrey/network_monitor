"""Tests for the table's column sorting (gui/widgets/host_table.py)."""
from netmonitor.gui.widgets.host_table import sort_key


def test_columns_sort_by_value_not_by_text():
    assert sorted(["192.168.1.10", "192.168.1.9"], key=sort_key) == ["192.168.1.9", "192.168.1.10"]
    assert sorted(["100 ms", "No data", "12.4 ms", "9 ms"], key=sort_key) == ["9 ms", "12.4 ms", "100 ms", "No data"]
    assert sorted(["25%", "5%", "100%"], key=sort_key) == ["5%", "25%", "100%"]
    assert sorted(["phone", "Gateway", ""], key=sort_key) == ["", "Gateway", "phone"]
