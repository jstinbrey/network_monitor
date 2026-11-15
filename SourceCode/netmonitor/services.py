"""The only module the GUI imports.

Every function here can block for seconds, so views call them through
gui.worker.run_async and never directly.
"""
import ipaddress

from netmonitor import config, models, store
from netmonitor.core import discovery, netinfo, pinger, statistics

validate_ip = pinger.validate_ip          # raises ValueError on bad input
network_info = netinfo.get_network_info   # Feature 1: local IP, range, gateway


def scan(on_progress=None):
    """Feature 1: find every active device on the local network and remember them."""
    info = netinfo.get_network_info()
    devices = discovery.discover(info, on_progress)
    store.save_scan(devices, info.cidr)
    return devices


def _record(results):
    """Save ping results. A host with no reply that still answers ARP is up but blocks ICMP."""
    info = netinfo.get_network_info()
    neighbours = discovery.read_arp(info.local_ip, ipaddress.ip_network(info.cidr))
    for result in results:
        if result.status == models.OFFLINE and result.ip in neighbours:
            result.status = models.NO_ICMP
        store.save_ping(result)
    return results


def run_ping(ip, count=config.PING_COUNT):
    """Feature 2: ping one host and store the result."""
    return _record([pinger.ping(ip, count)])[0]


def run_ping_many(ips, count=config.PING_COUNT):
    """Feature 2: ping several hosts in parallel and store the results."""
    return _record(pinger.ping_many(ips, count))


def stats():
    """Feature 3: one row of statistics per device known on this network."""
    devices = store.get_devices(netinfo.get_network_info().cidr)
    # shortcut: ping history is keyed by IP only, so two networks that reuse the same
    # addresses share history; add a network column to pings if that becomes a problem.
    return [statistics.host_stats(device, store.get_pings(device.ip)) for device in devices]


def summary():
    """Feature 3: network-wide totals and health score."""
    return statistics.summary(stats())


def refresh_all():
    """Feature 3: ping every known device, then return fresh statistics."""
    run_ping_many([device.ip for device in store.get_devices(netinfo.get_network_info().cidr)])
    return stats()

def history(ip, limit=10):
    """Feature 3: the most recent ping tests of one host, oldest first, for the history chart."""
    return store.get_pings(ip)[-limit:]