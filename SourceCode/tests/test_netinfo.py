"""Tests for core/netinfo.py (Feature 1: local addressing)."""
from conftest import FIXTURES

from netmonitor.core import netinfo
from netmonitor.models import NetworkInfo


def read(name):
    return (FIXTURES / name).read_text()


# --- network range --------------------------------------------------------

def test_slash24_range():
    network, truncated = netinfo.get_network("192.168.1.37", "255.255.255.0")
    hosts = list(network.hosts())
    assert str(network) == "192.168.1.0/24"
    assert len(hosts) == 254
    assert str(hosts[0]) == "192.168.1.1"
    assert str(hosts[-1]) == "192.168.1.254"
    assert truncated is False


def test_small_hotspot_range():
    network, truncated = netinfo.get_network("172.20.10.3", "255.255.255.240")
    assert str(network) == "172.20.10.0/28"
    assert len(list(network.hosts())) == 14
    assert truncated is False


def test_large_network_is_cut_to_slash24():
    network, truncated = netinfo.get_network("10.5.7.200", "255.255.0.0")
    assert str(network) == "10.5.7.0/24"
    assert truncated is True


# --- default gateway ------------------------------------------------------

def test_gateway_from_route_table():
    assert netinfo.parse_default_gateway(read("route_print.txt"), "192.168.1.37") == "192.168.1.1"


def test_gateway_prefers_route_of_local_interface():
    output = read("route_print_two_adapters.txt")
    assert netinfo.parse_default_gateway(output, "192.168.1.37") == "192.168.1.1"
    assert netinfo.parse_default_gateway(output, "10.0.0.25") == "10.0.0.1"


def test_gateway_falls_back_to_lowest_metric():
    output = read("route_print_two_adapters.txt")
    assert netinfo.parse_default_gateway(output, "172.16.0.9") == "10.0.0.1"


def test_no_default_route():
    assert netinfo.parse_default_gateway("Active Routes:\n  None\n", "192.168.1.37") is None


# --- scan targets ---------------------------------------------------------

def test_scan_targets_exclude_this_pc():
    info = NetworkInfo("pc", "192.168.1.37", "255.255.255.0", "192.168.1.0/24",
                       "192.168.1.1", "192.168.1.254", "192.168.1.1", 254)
    targets = netinfo.scan_targets(info)
    assert len(targets) == 253
    assert "192.168.1.37" not in targets
    assert "192.168.1.1" in targets


# --- assembling NetworkInfo (OS calls replaced with fixed values) ---------

def test_network_info_assembled(monkeypatch):
    monkeypatch.setattr(netinfo, "get_local_ip", lambda: "192.168.1.37")
    monkeypatch.setattr(netinfo, "get_netmask", lambda ip: "255.255.255.0")
    monkeypatch.setattr(netinfo, "get_gateway", lambda ip: "192.168.1.1")
    info = netinfo.get_network_info()
    assert info.cidr == "192.168.1.0/24"
    assert info.host_count == 254
    assert info.gateway == "192.168.1.1"
    assert info.mask_assumed is False


def test_network_info_assumes_mask_when_unreadable(monkeypatch):
    monkeypatch.setattr(netinfo, "get_local_ip", lambda: "192.168.1.37")
    monkeypatch.setattr(netinfo, "get_netmask", lambda ip: None)
    monkeypatch.setattr(netinfo, "get_gateway", lambda ip: None)
    info = netinfo.get_network_info()
    assert info.netmask == "255.255.255.0"
    assert info.mask_assumed is True
    assert info.gateway is None


def test_network_info_without_connection(monkeypatch):
    monkeypatch.setattr(netinfo, "get_local_ip", lambda: None)
    try:
        netinfo.get_network_info()
    except RuntimeError as error:
        assert "Not connected" in str(error)
    else:
        raise AssertionError("expected RuntimeError")
