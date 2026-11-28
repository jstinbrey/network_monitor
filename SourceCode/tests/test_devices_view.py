"""Selection and search data used by the Devices interface."""
from netmonitor import models
from netmonitor.gui.views.devices import matches


def test_device_search_matches_terms_across_columns_and_respects_filter():
    printer = models.Device("192.168.1.5", "a4:2b:00:00:00:01", "LaserPrinter", alias="Office printer",
                            vendor="Example Maker", known=False, replied_icmp=True)
    assert matches(printer, models.ONLINE, "New", "office MAKER .5")
    assert matches(printer, models.ONLINE, "All", "a4:2b")
    assert not matches(printer, models.ONLINE, "Issues", "office")
    assert not matches(printer, models.ONLINE, "New", "tablet")
