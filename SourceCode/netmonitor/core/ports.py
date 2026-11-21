"""Feature 5 bonus (Port Scanner): which common TCP services a device has open.

A TCP connect scan: a port is open when the three-way handshake completes.
Closed and filtered ports both fail within config.PORT_TIMEOUT_S.
Only check devices on a network you own or administer.
"""
import socket
from concurrent.futures import ThreadPoolExecutor

from netmonitor import config
from netmonitor.core import pinger


def check_ports(ip: str, ports: dict[int, str] = config.COMMON_PORTS) -> list[dict]:
    """[{"port", "service", "risk"}] for every port in ports that accepts a connection, in port order."""
    ip = pinger.validate_ip(ip)                     # never pass unchecked input to connect()

    def probe(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(config.PORT_TIMEOUT_S)
            return port if s.connect_ex((ip, port)) == 0 else None

    with ThreadPoolExecutor(max_workers=len(ports)) as pool:   # all ports at once: about 0.5 s in total
        open_ports = [port for port in pool.map(probe, sorted(ports)) if port]
    return [{"port": p, "service": ports[p], "risk": "high" if p in config.RISKY_PORTS else "normal"}
            for p in open_ports]
