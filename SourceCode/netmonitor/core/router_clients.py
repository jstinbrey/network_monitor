"""Read a copied router Wi-Fi client table without contacting the router."""
import ipaddress
import re
from dataclasses import dataclass, replace

from netmonitor.models import Device

_MAC = re.compile(r"(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])", re.I)


@dataclass(frozen=True)
class Client:
    mac: str
    ssid: str
    ip: str | None


@dataclass(frozen=True)
class Snapshot:
    network: str
    captured_at: str
    clients: tuple[Client, ...]


def _ipv4(text):
    try:
        address = ipaddress.IPv4Address(text)
    except ValueError:
        return None
    if address.is_multicast or address.is_unspecified or address.is_loopback or int(address) == 0xffffffff:
        return None
    return str(address)


def read_table(text: str) -> tuple[Client, ...]:
    """Read ID, SSID, MAC and IP cells copied as browser text."""
    clients = {}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = _MAC.search(line)
        if not match:
            continue
        mac = match[0].replace(":", "-").lower()
        prefix = line[:match.start()].strip(" \t,|")
        ssid = re.sub(r"^\d+(?:[\s,|]+|$)", "", prefix).strip('"')
        suffix = line[match.end():].strip(" \t,|")
        address = _ipv4(re.split(r"[\s,|]+", suffix, maxsplit=1)[0])
        if not suffix and index + 1 < len(lines):
            address = _ipv4(lines[index + 1].strip())
        if not ssid and not prefix and index > 0:
            previous = lines[index - 1].strip()
            if previous and not previous.isdecimal() and not _MAC.search(previous) and not _ipv4(previous):
                ssid = previous
        if mac not in clients or address:
            clients[mac] = Client(mac, ssid[:32], address)
    if not clients:
        raise ValueError("No client rows found. Copy the Wi-Fi client table with its MAC addresses.")
    return tuple(clients.values())


def add_to_map(devices: list[Device], clients: tuple[Client, ...]) -> list[Device]:
    """Keep PC discovery and add router clients with usable IPv4 addresses to the map."""
    by_ip = {device.ip: device for device in devices}
    by_mac = {device.mac.replace(":", "-").lower(): device for device in devices if device.mac}
    for client in clients:
        known = by_mac.get(client.mac)
        if known:
            by_ip[known.ip] = replace(known, router_ssid=client.ssid)
        elif client.ip and client.ip not in by_ip:
            by_ip[client.ip] = Device(client.ip, client.mac, "Router client", router_ssid=client.ssid, router_only=True)
    return list(by_ip.values())
