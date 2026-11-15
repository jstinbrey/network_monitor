"""Tests for core/discovery.py (Feature 1: finding devices)."""
import ipaddress

from netmonitor.core import discovery, pinger

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