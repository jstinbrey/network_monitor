"""Tests for Step 6.1: MAC vendor lookup and randomized MAC addresses."""
import pytest

from netmonitor import config
from netmonitor.core import advisor, vendor
from netmonitor.models import Device

TP_LINK = "TP-LINK TECHNOLOGIES CO.,LTD."


@pytest.fixture(autouse=True)
def registry(tmp_path, monkeypatch):
    """A one-row registry instead of the real 40,000-row file."""
    path = tmp_path / "oui.csv"
    path.write_text("Registry,Assignment,Organization Name,Organization Address\n"
                    f'MA-L,A42BB0,"{TP_LINK}","Shenzhen, CN"\n', encoding="utf-8")
    monkeypatch.setattr(config, "OUI_PATH", path)
    vendor._registry.cache_clear()
    yield
    vendor._registry.cache_clear()      # other tests must not see the fake registry


@pytest.mark.parametrize("mac, expected", [
    ("a4-2b-b0-11-22-33", TP_LINK),            # registered OUI
    ("da-a1-19-11-22-33", vendor.PRIVATE),     # second hex digit a = 1010: locally administered bit set
    ("00-11-22-33-44-55", "Unknown vendor"),   # universal, but not in the registry
    (None, "Unknown"),
])
def test_vendor(mac, expected):
    assert vendor.vendor(mac) == expected


def test_a_missing_registry_file_gives_unknown_vendor(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUI_PATH", tmp_path / "missing.csv")
    vendor._registry.cache_clear()
    assert vendor.vendor("a4-2b-b0-11-22-33") == "Unknown vendor"


@pytest.mark.parametrize("mac, says_randomized", [("da-a1-19-11-22-33", True), ("a4-2b-b0-11-22-33", False)])
def test_a_new_device_with_a_randomized_mac_is_explained(mac, says_randomized):
    new = Device(ip="192.168.1.50", hostname="phone", mac=mac, known=False)
    detail = advisor.recommend([new], [])[0].detail
    assert ("randomized MAC address" in detail) == says_randomized
