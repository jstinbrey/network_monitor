"""Tests for Step 8.1: the network map's layout, its filter, and the data behind it."""
from itertools import combinations
from math import dist

import pytest

from netmonitor import config, models, services, store
from netmonitor.core import pinger
from netmonitor.gui.views.map import keep
from netmonitor.gui.widgets.map_canvas import edge_style, map_positions, ring_layout
from netmonitor.models import Device, HostStats, NetworkInfo

NETWORK = "192.168.1.0/24 via aa"
GATEWAY = Device(ip="192.168.1.1", mac="aa", hostname="router", is_gateway=True)
PC = Device(ip="192.168.1.6", mac="bb", hostname="pc", is_self=True)
PHONE = Device(ip="192.168.1.5", mac="cc", hostname="phone", known=False)
TV = Device(ip="192.168.1.9", mac="dd", hostname="tv")


def stats(ip, avg, status=models.ONLINE):
    return HostStats(ip, "x", 4, avg, avg, avg, 1.0, 0.0 if avg else 100.0, status)


def test_ring_layout_starts_at_the_top_and_goes_clockwise():
    points = ring_layout(4, 0, 0, 100)
    assert points == [pytest.approx(p, abs=1e-9) for p in [(0, -100), (100, 0), (0, 100), (-100, 0)]]


def test_more_than_16_devices_go_on_a_second_ring():
    radii = [round((x * x + y * y) ** 0.5) for x, y in ring_layout(20, 0, 0, 100)]
    assert radii == [100] * 16 + [190] * 4


def test_dense_map_reserves_room_for_individual_nodes_at_the_minimum_window():
    width, height = 740, 300
    points = map_positions(18, width, height)
    assert all(18 <= x <= width - 18 and 18 <= y <= height - 18 for x, y in points)
    assert min(dist(a, b) for a, b in combinations(points, 2)) > 36


def test_edge_colour_follows_latency():
    assert edge_style(None) == (edge_style(stats("x", None))[0], (4, 4))          # no data: grey dashes
    assert [edge_style(stats("x", ms))[1] for ms in (5, 50, 500)] == ["", "", ""]
    assert len({edge_style(stats("x", ms))[0] for ms in (5, 50, 500)}) == 3       # green, amber, red


def test_the_filter_keeps_the_right_devices_and_always_the_gateway():
    devices = [GATEWAY, PC, PHONE, TV]
    host_stats = {"192.168.1.6": stats("192.168.1.6", 1.0), "192.168.1.5": stats("192.168.1.5", None, models.OFFLINE)}
    issues = {"192.168.1.9"}

    def ips(mode):
        return [d.ip for d in keep(devices, host_stats, issues, mode)]
    assert ips("All") == ["192.168.1.1", "192.168.1.6", "192.168.1.5", "192.168.1.9"]
    assert ips("Online") == ["192.168.1.1", "192.168.1.6"]                    # the TV was never pinged
    assert ips("New") == ["192.168.1.1", "192.168.1.5"]
    assert ips("Issues") == ["192.168.1.1", "192.168.1.9"]


def test_map_data_marks_risky_ports_and_shared_macs_only(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    info = NetworkInfo("pc", PC.ip, "255.255.255.0", "192.168.1.0/24", "192.168.1.1", "192.168.1.254",
                       GATEWAY.ip, 254)
    printer = Device(ip="192.168.1.20", mac="ee", hostname="printer")
    arp = {GATEWAY.ip: "aa", PHONE.ip: "cc", TV.ip: "dd", "192.168.1.10": "dd"}   # the TV's MAC answers for two IPs
    monkeypatch.setattr(services, "_live", lambda: (info, arp, NETWORK, [GATEWAY, PC, PHONE, TV, printer]))
    store.save_port_check(PC.ip, [{"port": 23, "service": "Telnet", "risk": "high"}], NETWORK)
    store.save_ping(pinger.build_result(GATEWAY.ip, 4, [2.0] * 4), NETWORK)
    store.save_ping(pinger.build_result(printer.ip, 4, []), NETWORK)            # asleep: red node, but no badge
    devices, host_stats, issues = services.map_data()
    assert len(devices) == 5 and host_stats[GATEWAY.ip].avg_ms == 2.0 and host_stats[printer.ip].status == models.OFFLINE
    assert issues == {PC.ip, TV.ip, "192.168.1.10"}                         # the new phone has its red ring instead
