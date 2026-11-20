"""Tests for services._network_id: how one network is told apart from another with the same range."""
from netmonitor import services
from netmonitor.models import NetworkInfo

INFO = NetworkInfo(hostname="pc", local_ip="192.168.1.20", netmask="255.255.255.0", cidr="192.168.1.0/24",
                   first_host="192.168.1.1", last_host="192.168.1.254", gateway="192.168.1.1", host_count=254)
ROUTER_MAC = "aa-bb-cc-dd-ee-ff"


def test_network_id_is_the_range_plus_the_gateway_mac():
    assert services._network_id(INFO, {"192.168.1.1": ROUTER_MAC}) == "192.168.1.0/24 via aa-bb-cc-dd-ee-ff"


def test_gateway_missing_from_arp_is_pinged_once_then_read_again(monkeypatch):
    pinged = []
    monkeypatch.setattr(services.pinger, "is_alive", pinged.append)
    monkeypatch.setattr(services.discovery, "read_arp", lambda local_ip, network: {"192.168.1.1": ROUTER_MAC})
    assert services._network_id(INFO, {}) == "192.168.1.0/24 via aa-bb-cc-dd-ee-ff"
    assert pinged == ["192.168.1.1"]


def test_no_gateway_still_gives_an_id(monkeypatch):
    monkeypatch.setattr(services.pinger, "is_alive", lambda ip: False)
    monkeypatch.setattr(services.discovery, "read_arp", lambda local_ip, network: {})
    assert services._network_id(INFO, {}) == "192.168.1.0/24 via no gateway"