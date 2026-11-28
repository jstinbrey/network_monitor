"""Tests for core/discovery.py (Feature 1: finding devices)."""
import ipaddress

from netmonitor.core import discovery, pinger
from netmonitor.models import Device

NETWORK = ipaddress.ip_network("192.168.1.0/24")

ARP = """
Interface: 192.168.56.1 --- 0x9
  Internet Address      Physical Address      Type
  192.168.56.255        ff-ff-ff-ff-ff-ff     static

Interface: 192.168.1.37 --- 0x12
  Internet Address      Physical Address      Type
  192.168.1.1           A4-2B-B0-11-22-33     dynamic
  192.168.1.20          5c-e9-1e-aa-bb-cc     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
"""


def test_arp_keeps_only_real_neighbours_of_this_adapter():
    assert discovery.parse_arp(ARP, "192.168.1.37", NETWORK) == {
        "192.168.1.1": "a4-2b-b0-11-22-33",
        "192.168.1.20": "5c-e9-1e-aa-bb-cc",
    }


def test_arp_empty_output():
    assert discovery.parse_arp("No ARP Entries Found.", "192.168.1.37", NETWORK) == {}


def test_sweep_returns_hosts_that_reply(monkeypatch):
    monkeypatch.setattr(pinger, "is_alive", lambda ip: ip.endswith((".1", ".20")))
    progress = []
    alive = discovery.sweep(["192.168.1.1", "192.168.1.5", "192.168.1.20"],
                            lambda done, total: progress.append((done, total)))
    assert alive == {"192.168.1.1", "192.168.1.20"}
    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_ipv6_neighbors_are_scoped_and_merged_by_mac():
    output = """
Interface 15: Wi-Fi
fe80::1          02-10-20-30-40-50  Reachable (Router)
2001:db8::50     02-10-20-30-40-50  Stale
fe80::2          02-10-20-30-40-51  Delay
fe80::3          00-00-00-00-00-00  Unreachable
ff02::1          33-33-00-00-00-01  Permanent
"""
    neighbours = discovery.parse_ipv6_neighbours(output)
    assert neighbours == {"fe80::1%15": "02-10-20-30-40-50", "2001:db8::50": "02-10-20-30-40-50",
                          "fe80::2%15": "02-10-20-30-40-51"}
    gateway = Device("192.168.1.1", "02:10:20:30:40:50", "Gateway")
    merged, only_ipv6 = discovery.merge_ipv6([gateway], neighbours)
    assert merged.ip == gateway.ip and merged.ipv6_addresses == ("fe80::1%15", "2001:db8::50")
    assert only_ipv6.ip == "fe80::2%15" and not gateway.ipv6_addresses
