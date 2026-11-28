"""Tests for services._network_id: how one network is told apart from another with the same range."""
import pytest

from netmonitor import config, services, store
from netmonitor.core import pinger
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


def test_traceroute_hostname_resolution_uses_the_selected_family(monkeypatch):
    def resolve(hostname, port, family, socket_type):
        assert hostname == "sample.test" and family == services.socket.AF_INET6
        return [(family, socket_type, 0, "", ("fe80::1", 0, 0, 15))]

    monkeypatch.setattr(services.socket, "getaddrinfo", resolve)
    assert services._trace_address("sample.test", 6) == "fe80::1%15"
    with pytest.raises(ValueError, match="switch the address family"):
        services._trace_address("::1", 4)


@pytest.mark.parametrize("changed_network", [True, False])
def test_ping_rejects_a_network_or_device_swap_before_saving(tmp_path, monkeypatch, changed_network):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "checks.db")
    ip, network = "192.168.1.9", "home"
    snapshots = iter((services._Network(INFO, network, {ip: "aa"}),
                      services._Network(INFO, "away" if changed_network else network, {ip: "bb"})))
    monkeypatch.setattr(services, "_network_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(pinger, "ping", lambda ip, count: pinger.build_result(ip, count, [1.0] * count))

    with pytest.raises(RuntimeError, match="network changed" if changed_network else "device at .* changed"):
        services.run_ping(ip)
    for key in ("home", "away"):
        assert store.get_pings(ip, key, owner="mac:aa") == []
        assert store.get_pings(ip, key, owner="mac:bb") == []
