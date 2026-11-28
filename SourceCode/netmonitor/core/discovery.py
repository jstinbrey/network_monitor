"""Feature 1 (Discovery): find active devices with a ping sweep plus ARP table."""

import ipaddress
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from dataclasses import replace
from datetime import datetime

from netmonitor import config
from netmonitor.core import netinfo, pinger
from netmonitor.models import Device, NetworkInfo

# "Interface: 192.168.1.37 --- 0x12" starts each adapter's block in `arp -a`.
_INTERFACE = re.compile(r"^\S.*?(\d+\.\d+\.\d+\.\d+)\s+---\s+0x", re.M)
# "  192.168.1.1    a4-2b-b0-11-22-33    dynamic"
_ROW = re.compile(r"^\s+(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s", re.M)
_IPV6_INTERFACE = re.compile(r"^\s*\S+\s+(\d+)\s*:", re.M)
_MAC = re.compile(r"[0-9a-f]{2}(?:-[0-9a-f]{2}){5}", re.I)

def parse_arp(output: str, local_ip: str, network) -> dict[str, str]:
    """{ip: mac} of real neighbours on the adapter that owns local_ip.

    Drops other adapters, addresses outside the network, the broadcast
    address, and multicast entries, which are not devices.
    """
    parts = _INTERFACE.split(output)  # ['', ip1, block1, ip2, block2, ...]
    found = {}
    for interface_ip, block in zip(parts[1::2], parts[2::2]):
        if interface_ip != local_ip:
            continue
        for ip, mac in _ROW.findall(block):
            address = ipaddress.ip_address(ip)
            if address in network and address != network.broadcast_address \
                    and not mac.lower().startswith(("ff-ff", "01-00-5e")):
                found[ip] = mac.lower()
    return found


def read_arp(local_ip: str, network) -> dict[str, str]:
    """Run `arp -a` and return this network's {ip: mac} entries."""
    output = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                            timeout=10, creationflags=pinger.NO_WINDOW).stdout
    return parse_arp(output, local_ip, network)


def parse_ipv6_neighbours(output: str) -> dict[str, str]:
    """Read the selected Windows adapter's cache and preserve link-local scopes."""
    interface = _IPV6_INTERFACE.search(output)
    found = {}
    for line in output.splitlines():
        columns = line.split()
        if len(columns) < 3 or columns[2] not in {"Reachable", "Stale", "Delay", "Probe", "Permanent"}:
            continue
        ip, mac = columns[0], columns[1].lower()
        if not _MAC.fullmatch(mac) or mac == "00-00-00-00-00-00" or int(mac[:2], 16) & 1:
            continue
        try:
            address = ipaddress.IPv6Address(ip)
        except ValueError:
            continue
        if address.is_multicast or address.is_unspecified or address.is_loopback:
            continue
        if address.is_link_local and not address.scope_id:
            if not interface:
                continue
            ip = f"{address}%{interface[1]}"
        else:
            ip = str(address)
        found[ip] = mac
    return found


def read_ipv6_neighbours(local_ip: str) -> dict[str, str]:
    """Read IPv6 neighbors on the active LAN adapter. This does not send probes."""
    adapter = netinfo.get_adapter(local_ip)
    if not adapter:
        return {}
    try:
        result = subprocess.run(["netsh", "interface", "ipv6", "show", "neighbors", f"interface={adapter}"],
                                capture_output=True, text=True, timeout=5, creationflags=netinfo.NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return parse_ipv6_neighbours(result.stdout) if result.returncode == 0 else {}


def merge_ipv6(devices: list[Device], neighbours: dict[str, str]) -> list[Device]:
    """Attach IPv6 addresses by MAC without counting the same device again."""
    by_mac = {}
    for ip, mac in neighbours.items():
        by_mac.setdefault(mac, []).append(ip)
    merged = []
    for device in devices:
        mac = (device.mac or "").replace(":", "-").lower()
        addresses = by_mac.pop(mac, ())
        merged.append(replace(device, ipv6_addresses=tuple(addresses)) if addresses else device)
    merged.extend(Device(ips[0], mac, "IPv6 neighbor", ipv6_addresses=tuple(ips)) for mac, ips in by_mac.items())
    return merged


def sweep(targets: list[str], on_progress=None) -> set[str]:
    """Ping every target once, in parallel. Returns the IPs that replied.

    on_progress(done, total) is called from this thread, not the UI thread.
    """
    alive = set()
    with ThreadPoolExecutor(max_workers=config.SWEEP_WORKERS) as pool:
        futures = {pool.submit(pinger.is_alive, ip): ip for ip in targets}
        for done, future in enumerate(as_completed(futures), start=1):
            if future.result():
                alive.add(futures[future])
            if on_progress:
                on_progress(done, len(targets))
    return alive


def _lookup(ip: str) -> str:
    """Reverse DNS for one IP. Windows echoes the IP back when the host has no name."""
    try:
        name = socket.gethostbyaddr(ip)[0]
    except OSError:
        return "Unknown"
    return "Unknown" if name == ip else name


def resolve_hostnames(ips: list[str]) -> dict[str, str]:
    """Reverse DNS for each IP; "Unknown" when there is no name or it is too slow."""
    pool = ThreadPoolExecutor(max_workers=32)
    futures = {ip: pool.submit(_lookup, ip) for ip in ips}
    wait(futures.values(), timeout=config.HOSTNAME_TIMEOUT_S)
    pool.shutdown(wait=False, cancel_futures=True)  # gethostbyaddr has no timeout of its own
    return {ip: f.result() if f.done() and not f.cancelled() else "Unknown" for ip, f in futures.items()}


def discover(info: NetworkInfo, on_progress=None) -> list[Device]:
    """Scan the network and return every active device, sorted by IP."""
    network = ipaddress.ip_network(info.cidr)
    alive = sweep(netinfo.scan_targets(info), on_progress)
    macs = read_arp(info.local_ip, network)  # after the sweep: the pings filled the ARP cache
    macs[info.local_ip] = netinfo.get_mac(info.local_ip)
    alive.add(info.local_ip)

    ips = sorted(alive | macs.keys(), key=ipaddress.ip_address)
    names = resolve_hostnames([ip for ip in ips if ip != info.local_ip])
    names[info.local_ip] = info.hostname
    if names.get(info.gateway) == "Unknown":
        names[info.gateway] = "Gateway"

    now = datetime.now().isoformat(timespec="seconds")
    # A device with a MAC but no ping reply is up and blocking ICMP.
    return [Device(ip=ip, mac=macs.get(ip), hostname=names[ip], replied_icmp=ip in alive,
                   is_self=ip == info.local_ip, is_gateway=ip == info.gateway,
                   first_seen=now, last_seen=now)
            for ip in ips]
