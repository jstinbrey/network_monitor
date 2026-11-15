"""Feature 1 (Network Discovery): how this PC is addressed on the network.

Finds the local IPv4 address, its subnet mask, the network range in CIDR
notation, and the default gateway.

Networking concepts used here:
  * IPv4 addressing and subnet masks (which bits are network, which are host)
  * CIDR notation, e.g. 192.168.1.0/24
  * The default route (0.0.0.0/0) and its gateway, from the routing table
  * UDP sockets, used only to ask the OS which interface it would route from
"""
import ipaddress
import re
import socket
import subprocess

import psutil

from netmonitor import config
from netmonitor.models import NetworkInfo

# Stops Windows from flashing a console window for each command we run.
NO_WINDOW = subprocess.CREATE_NO_WINDOW

DEFAULT_MASK = "255.255.255.0"


def get_local_ip() -> str | None:
    """Return the IPv4 address of the adapter that routes to the internet.

    connect() on a UDP socket sends no packet. It only makes the operating
    system choose the outgoing interface for that destination, and
    getsockname() then returns that interface's address. Returns None when
    the PC is not connected to any network.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def get_netmask(ip: str) -> str | None:
    """Return the subnet mask of the adapter that owns `ip`, or None."""
    for addresses in psutil.net_if_addrs().values():
        for addr in addresses:
            if addr.family == socket.AF_INET and addr.address == ip:
                return addr.netmask
    return None


def get_mac(ip: str) -> str | None:
    """Return the MAC address of the adapter that owns `ip`, or None."""
    for addresses in psutil.net_if_addrs().values():
        if any(a.family == socket.AF_INET and a.address == ip for a in addresses):
            for addr in addresses:
                if addr.family == psutil.AF_LINK and addr.address:
                    return addr.address.lower()
    return None


def get_network(ip: str, mask: str) -> tuple[ipaddress.IPv4Network, bool]:
    """Return (network, truncated) for an address and its subnet mask.

    strict=False lets us pass a host address (192.168.1.37) and get back the
    network it belongs to (192.168.1.0/24). Networks larger than a /24 are
    cut down to the /24 that contains `ip`, so a scan never exceeds 254
    hosts; `truncated` is True when that happened.
    """
    network = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
    if network.prefixlen < config.MAX_PREFIX:
        return ipaddress.ip_network(f"{ip}/{config.MAX_PREFIX}", strict=False), True
    return network, False


# One row of the IPv4 route table:
#   Network Destination   Netmask    Gateway        Interface      Metric
#             0.0.0.0     0.0.0.0    192.168.1.1    192.168.1.37       35
# The row is entirely numeric, so it does not depend on the Windows language.
_DEFAULT_ROUTE = re.compile(
    r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+"
    r"(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s*$",
    re.MULTILINE,
)


def parse_default_gateway(route_output: str, local_ip: str) -> str | None:
    """Extract the default gateway from the output of `route print -4`.

    Prefers the default route that leaves through `local_ip`. If none
    matches, the route with the lowest metric wins, which is the one Windows
    itself would use.
    """
    routes = _DEFAULT_ROUTE.findall(route_output)
    if not routes:
        return None
    for gateway, interface, _metric in routes:
        if interface == local_ip:
            return gateway
    return min(routes, key=lambda route: int(route[2]))[0]


def get_gateway(local_ip: str) -> str | None:
    """Return the default gateway for this PC, or None if there is none."""
    try:
        output = subprocess.run(
            ["route", "print", "-4"],
            capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_default_gateway(output, local_ip)


def get_network_info() -> NetworkInfo:
    """Collect everything the Devices view shows about the local network.

    Raises RuntimeError when the PC has no network connection.
    """
    local_ip = get_local_ip()
    if local_ip is None:
        raise RuntimeError("Not connected to a network.")

    mask = get_netmask(local_ip)
    mask_assumed = mask is None
    if mask_assumed:
        mask = DEFAULT_MASK

    network, truncated = get_network(local_ip, mask)
    hosts = list(network.hosts())

    return NetworkInfo(
        hostname=socket.gethostname(),
        local_ip=local_ip,
        netmask=mask,
        cidr=str(network),
        first_host=str(hosts[0]),
        last_host=str(hosts[-1]),
        gateway=get_gateway(local_ip),
        host_count=len(hosts),
        mask_assumed=mask_assumed,
        truncated=truncated,
    )


def scan_targets(info: NetworkInfo) -> list[str]:
    """Every host address in the network range except this PC's own."""
    network = ipaddress.ip_network(info.cidr)
    return [str(host) for host in network.hosts() if str(host) != info.local_ip]
