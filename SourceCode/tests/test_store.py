"""Tests for store.py (SQLite storage). Each test uses its own temporary database."""
from netmonitor import store
from netmonitor.core import pinger
from netmonitor.models import Device

NET = "192.168.1.0/24"


def device(ip, mac, seen="2026-11-15T10:00:00"):
    return Device(ip=ip, mac=mac, hostname="pc", replied_icmp=True, first_seen=seen, last_seen=seen)


def test_devices_round_trip_sorted_by_ip(tmp_path):
    db = tmp_path / "t.db"
    store.save_scan([device("192.168.1.10", "aa"), device("192.168.1.9", "bb")], NET, db)
    assert store.get_devices(NET, db) == [device("192.168.1.9", "bb"), device("192.168.1.10", "aa")]
    assert store.get_devices("10.0.0.0/24", db) == []          # networks are kept apart


def test_first_scan_is_the_baseline_and_new_devices_are_flagged(tmp_path):
    db = tmp_path / "t.db"
    store.save_scan([device("192.168.1.1", "aa")], NET, db)
    store.save_scan([device("192.168.1.1", "aa"), device("192.168.1.50", "zz")], NET, db)
    known = {d.ip: d.known for d in store.get_devices(NET, db)}
    assert known == {"192.168.1.1": True, "192.168.1.50": False}

    store.mark_known("zz", NET, db)
    assert all(d.known for d in store.get_devices(NET, db))


def test_undo_confirmation_stays_on_the_original_network(tmp_path):
    db = tmp_path / "t.db"
    other_network = "10.0.0.0/24"
    router, new_device = device("192.168.1.1", "aa"), device("192.168.1.50", "zz")
    store.save_scan([router], NET, db)
    store.save_scan([router, new_device], NET, db)
    store.save_scan([device("10.0.0.50", "zz")], other_network, db)

    assert store.mark_known("zz", NET, db)
    assert not store.mark_known("zz", NET, db)
    store.unmark_known("zz", NET, db)
    store.save_scan([router, new_device], NET, db)

    assert [d.known for d in store.get_devices(NET, db)] == [True, False]
    assert store.get_devices(other_network, db)[0].known


def test_rescan_keeps_first_seen_and_devices_that_left(tmp_path):
    db = tmp_path / "t.db"
    store.save_scan([device("192.168.1.1", "aa"), device("192.168.1.7", "cc")], NET, db)
    store.save_scan([device("192.168.1.1", "aa", seen="2026-11-16T09:00:00")], NET, db)
    router, left = store.get_devices(NET, db)
    assert (router.first_seen, router.last_seen) == ("2026-11-15T10:00:00", "2026-11-16T09:00:00")
    assert left.ip == "192.168.1.7"


def test_ping_history_round_trip(tmp_path):
    db = tmp_path / "t.db"
    first = pinger.build_result("192.168.1.1", 4, [3.0, 0.5, 4.0])
    second = pinger.build_result("192.168.1.1", 4, [])
    store.save_ping(first, NET, db)
    store.save_ping(second, NET, db)
    assert store.get_pings("192.168.1.1", NET, db) == [first, second]
    assert store.get_pings("192.168.1.99", NET, db) == []


def test_networks_with_the_same_range_stay_separate(tmp_path):
    db = tmp_path / "t.db"
    home, cafe = "192.168.1.0/24 via aa-aa-aa-aa-aa-01", "192.168.1.0/24 via bb-bb-bb-bb-bb-02"
    store.save_scan([device("192.168.1.5", "aa")], home, db)
    store.save_scan([device("192.168.1.5", "cc")], cafe, db)
    assert [d.mac for d in store.get_devices(home, db)] == ["aa"]
    assert [d.mac for d in store.get_devices(cafe, db)] == ["cc"]

    result = pinger.build_result("192.168.1.5", 4, [2.0, 3.0])
    store.save_ping(result, home, db)
    assert store.get_pings("192.168.1.5", home, db) == [result]
    assert store.get_pings("192.168.1.5", cafe, db) == []      # same IP, other network: no history
