"""Tests for Step 7.1: events (alerts) stored per network, newest first, and dismissed."""
from netmonitor import config, services, store
from netmonitor.models import Event


def event(detail, ip=None):
    return Event(None, "2026-11-21T10:00:00", "bandwidth", "warning", ip, None, detail)


def test_newest_first_per_network_and_dismissed_ones_stay_listed(tmp_path):
    db = tmp_path / "t.db"
    first = store.add_event("home", event("first"), db)
    store.add_event("home", event("second", "192.168.1.5"), db)
    store.add_event("cafe", event("elsewhere"), db)
    store.dismiss_event(first, db)
    listed = store.get_events("home", path=db)
    assert [(e.detail, e.dismissed) for e in listed] == [("second", False), ("first", True)]
    assert listed[0].ip == "192.168.1.5"
    assert [e.detail for e in store.get_events("home", limit=1, path=db)] == ["second"]


def test_record_event_stores_it_for_this_network(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(services, "_network_id", lambda info: "home")
    monkeypatch.setattr(services.netinfo, "get_network_info", lambda: None)
    recorded = services.record_event("bandwidth", "warning", None, None, "Download above the limit.")
    assert recorded.id and services.events() == [recorded]
    services.dismiss(recorded.id)
    assert services.events()[0].dismissed
