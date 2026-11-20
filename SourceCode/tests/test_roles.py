"""Tests for Step 5.3: admin-only service calls and clearing one network's history."""
import pytest

from netmonitor import config, models, services, store
from netmonitor.core import pinger
from netmonitor.models import Device


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """An empty database, fast hashing, and nobody signed in."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "AUTH_ITERATIONS", 1_000)
    monkeypatch.setattr(services, "_user", None)


@pytest.mark.parametrize("call", [lambda: services.scan(), lambda: services.scan_and_refresh(),
                                  lambda: services.mark_known("192.168.1.5"), lambda: services.clear_history()])
def test_a_user_is_refused_before_anything_runs(call):
    services._user = models.User("bob", models.USER)
    with pytest.raises(PermissionError):
        call()


def test_clearing_one_network_keeps_the_others_and_the_accounts(monkeypatch):
    home, cafe = "192.168.1.0/24 via aa", "192.168.1.0/24 via bb"
    for network in (home, cafe):
        store.save_scan([Device(ip="192.168.1.5", mac="cc")], network)
        store.save_ping(pinger.build_result("192.168.1.5", 4, [2.0]), network)
    services.create_first_admin("admin", "adminpass", "adminpass")
    monkeypatch.setattr(services, "_network_id", lambda info: home)
    monkeypatch.setattr(services.netinfo, "get_network_info", lambda: None)

    assert services.clear_history() == home
    assert store.get_devices(home) == [] and store.get_pings("192.168.1.5", home) == []
    assert len(store.get_devices(cafe)) == 1 and len(store.get_pings("192.168.1.5", cafe)) == 1
    assert services.users() == [models.User("admin", models.ADMIN)]
