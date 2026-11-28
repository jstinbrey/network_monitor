"""Selection and search data used by the Devices interface."""
from netmonitor import models
from netmonitor.gui.views.devices import device_status, matches


def test_device_search_matches_terms_across_columns_and_respects_filter():
    printer = models.Device("192.168.1.5", "a4:2b:00:00:00:01", "LaserPrinter", alias="Office printer",
                            vendor="Example Maker", known=False, replied_icmp=True)
    assert matches(printer, models.ONLINE, "New", "office MAKER .5")
    assert matches(printer, models.ONLINE, "All", "a4:2b")
    assert not matches(printer, models.ONLINE, "Issues", "office")
    assert not matches(printer, models.ONLINE, "New", "tablet")


def test_device_uses_discovery_until_it_has_a_ping_status():
    device = models.Device("192.168.1.5", replied_icmp=True)
    stats = models.HostStats(device.ip, "Printer", 0, None, None, None, None, None, models.NO_DATA)
    assert device_status(device, stats) == models.ONLINE
    stats.status = models.OFFLINE
    assert device_status(device, stats) == models.OFFLINE
