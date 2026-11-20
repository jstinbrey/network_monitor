"""Tests for Step 5.4: the data behind the device panel."""
import pytest

from netmonitor import config, models, services, store
from netmonitor.core import pinger
from netmonitor.gui.widgets.device_panel import verdict
from netmonitor.models import Device, HostStats

NETWORK = "192.168.1.0/24 via aa"
PHONE = Device(ip="192.168.1.5", mac="cc", hostname="phone")


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """An empty database on a fixed network, with an admin signed in."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(services, "_network_id", lambda info, macs=None: NETWORK)
    monkeypatch.setattr(services.netinfo, "get_network_info", lambda: None)
    monkeypatch.setattr(services, "_user", models.User("admin", models.ADMIN))


def test_a_device_never_pinged_has_no_data_and_no_history():
    store.save_scan([PHONE], NETWORK)
    detail = services.device_detail(PHONE.ip)
    assert detail.device.hostname == "phone"
    assert detail.stats.status == models.NO_DATA and detail.history == []


def test_the_history_is_the_last_ten_tests_even_for_a_host_never_scanned():
    for rtt in range(12):
        store.save_ping(pinger.build_result("192.168.1.9", 4, [float(rtt)]), NETWORK)
    assert [r.avg_ms for r in services.device_detail("192.168.1.9").history] == [float(n) for n in range(2, 12)]


def test_a_name_survives_a_rescan_and_shows_in_the_statistics():
    store.save_scan([PHONE], NETWORK)
    assert services.set_alias(PHONE.ip, "  Mum's phone ").device.alias == "Mum's phone"
    store.save_scan([PHONE], NETWORK)
    assert services.stats()[0].hostname == "Mum's phone"


def test_a_user_cannot_rename():
    services._user = models.User("bob", models.USER)
    with pytest.raises(PermissionError):
        services.set_alias(PHONE.ip, "x")


@pytest.mark.parametrize("status, avg, loss, expected", [
    (models.ONLINE, 12.0, 0.0, "Online  ·  normal latency"),
    (models.DEGRADED, 150.0, 25.0, "Degraded  ·  high latency  ·  25% packet loss"),
    (models.NO_DATA, None, None, "No data"),
])
def test_verdict(status, avg, loss, expected):
    assert verdict(HostStats("192.168.1.5", "phone", 4, avg, avg, avg, None, loss, status)) == expected
