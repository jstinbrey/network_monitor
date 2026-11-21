"""Tests for Step 7.6: watch mode turns successive scans into events, and presence rows into uptime."""
import dataclasses

import pytest

from netmonitor import config, models, services, store
from netmonitor.core import pinger, watch
from netmonitor.models import Device

NETWORK = "192.168.1.0/24 via rr"
ROUTER = Device(ip="192.168.1.1", mac="00-1a-2b-00-00-01", hostname="Gateway", is_gateway=True)
PHONE = Device(ip="192.168.1.5", mac="00-1a-2b-00-00-05", hostname="phone")
LAPTOP = Device(ip="192.168.1.30", mac="00-1a-2b-00-00-30", hostname="laptop")


def test_watch_state():
    state, known = watch.WatchState(), {"aa", "gw"}
    assert state.update({"aa": ".2", "gw": ".1"}, known, "gw") == []                 # the first check only records
    assert state.update({"gw": ".1"}, known, "gw") == []                             # one miss: phones sleep
    assert state.update({"gw": ".1"}, known, "gw") == [("offline", "aa", ".2")]      # two misses: offline
    assert state.update({"aa": ".9", "gw": ".1", "new": ".5"}, known, "gw") == \
        [("back-online", "aa", ".9"), ("new-device", "new", ".5")]
    assert state.update({"aa": ".9", "new": ".5", "gw2": ".1"}, known, "gw2") == \
        [("gateway-mac-changed", "gw2", None), ("new-device", "gw2", ".1")]


def test_uptime_pct():
    assert watch.uptime_pct([]) is None
    assert watch.uptime_pct([("t1", True), ("t2", True), ("t3", False), ("t4", True)]) == 75.0


@pytest.fixture
def tick(tmp_path, monkeypatch):
    """tick(*devices, router_ms=2.0): one watch check on a fake network that finds those devices."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(services, "_user", models.User("admin", models.ADMIN))
    monkeypatch.setattr(services, "_network_id", lambda info, macs=None: NETWORK)
    monkeypatch.setattr(services.netinfo, "get_network_info", lambda: None)
    monkeypatch.setattr(services, "_watch", watch.WatchState())

    def run(*devices, router_ms=2.0):
        def scan():
            found = [dataclasses.replace(d) for d in devices]
            store.save_scan(found, NETWORK)
            return found

        def ping(ip, count):
            result = pinger.build_result(ip, count, [router_ms] * count)
            store.save_ping(result, NETWORK)
            return result
        monkeypatch.setattr(services, "scan", scan)
        monkeypatch.setattr(services, "run_ping", ping)
        return [(e.kind, e.severity, e.ip, e.detail) for e in services.watch_tick()]
    return run


def test_a_watched_network_reports_joins_departures_and_a_slow_router(tick):
    assert tick(ROUTER, PHONE) == []                                     # first check: the phone and router are known
    [joined] = tick(ROUTER, PHONE, LAPTOP)
    assert joined[:3] == ("new-device", "warning", LAPTOP.ip) and joined[3].startswith("New device joined: laptop, ")
    assert tick(ROUTER, LAPTOP) == []                                    # the phone missed one check
    offline, spike = tick(ROUTER, LAPTOP, router_ms=80.0)                # 30 earlier router replies make a baseline
    assert offline[:3] == ("offline", "warning", PHONE.ip) and offline[3].startswith("Went offline: phone, ")
    assert spike == ("spike", "warning", ROUTER.ip, "The router answered in 80 ms against a usual 2.0 ms.")

    phone = services.device_detail(PHONE.ip)                             # up, up, down, down
    assert [up for _, up in phone.presence] == [True, True, False, False] and phone.uptime_pct == 50.0
    assert services.device_detail(LAPTOP.ip).presence == []              # not known, so not tracked
    assert [e.kind for e in services.events()] == ["spike", "offline", "new-device"]   # stored, newest first


def test_only_an_admin_can_watch(monkeypatch):
    monkeypatch.setattr(services, "_user", models.User("bob", models.USER))
    with pytest.raises(PermissionError):
        services.start_watch()
