"""Dashboard presentation regressions for device names on the latency chart."""
from netmonitor.gui.views.dashboard import chart_device_labels
from netmonitor.models import HostStats, ONLINE


def test_chart_names_keep_their_suffix_and_fall_back_to_addresses_for_duplicates():
    names = ["Campus Lab Computer 01", "Campus Lab Computer 02", "Printer", "Printer"]
    stats = [HostStats(f"192.168.1.{i}", name, 4, 1, 1, 1, 0, 0, ONLINE) for i, name in enumerate(names, 1)]
    labels = chart_device_labels(stats)
    assert labels[0].endswith("01") and labels[1].endswith("02")
    assert labels[2:] == ["192.168.1.3", "192.168.1.4"]
