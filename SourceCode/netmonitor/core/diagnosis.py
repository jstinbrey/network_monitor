"""Network diagnosis: find where a problem is by testing one layer at a time.

This PC (an address?), then the router (the local link), then the internet
beyond it, then DNS (names to addresses). The first layer that fails is where
the problem is. DNS is tested with a real query: a UDP request and response.
"""
import random
import socket
import struct
import subprocess
import time

from netmonitor import config
from netmonitor.core.pinger import NO_WINDOW
from netmonitor.models import HostStats, Measurements, Verdict

PUBLIC_DNS = config.INTERNET_TARGETS[0]             # 1.1.1.1 answers DNS too: the comparison server


def build_query(name: str, query_id: int) -> bytes:
    """A DNS query for name's A record (RFC 1035): a 12-byte header, then one question."""
    header = struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0)   # flags 0x0100 = recursion desired
    question = b"".join(bytes([len(part)]) + part.encode("ascii") for part in name.split(".")) + b"\0"
    return header + question + struct.pack(">HH", 1, 1)            # type A, class IN


def is_answer(reply: bytes, query_id: int) -> bool:
    """True when reply answers our query: the same ID, rcode 0 (no error) and at least one answer record."""
    if len(reply) < 12:
        return False
    reply_id, flags, _, answers = struct.unpack(">HHHH", reply[:8])
    return reply_id == query_id and flags & 0x000F == 0 and answers > 0


def dns_query(server: str, name=config.DNS_TEST_NAME, timeout_s=config.DNS_TIMEOUT_S) -> float | None:
    """Milliseconds until server answered, or None if it did not answer correctly."""
    query_id = random.randrange(65536)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout_s)
        start = time.perf_counter()
        try:
            sock.sendto(build_query(name, query_id), (server, 53))
            reply, _ = sock.recvfrom(512)
        except OSError:                      # timeout, or the port is closed
            return None
    elapsed = (time.perf_counter() - start) * 1000
    return round(elapsed, 1) if is_answer(reply, query_id) else None


def dns_servers(adapter: str) -> list[str]:
    """The DNS servers Windows uses on one adapter, e.g. ["192.168.1.1"]."""
    alias = adapter.replace("'", "''")         # quote safely inside the PowerShell string
    output = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-DnsClientServerAddress -AddressFamily IPv4 -InterfaceAlias '{alias}').ServerAddresses"],
        capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW).stdout
    return [line.strip() for line in output.splitlines() if line.strip()]


def describe(stats: HostStats) -> str:
    """"0% loss, 3.2 ms average, 0.8 ms jitter" for one pinged host."""
    parts = [f"{stats.loss_pct:g}% loss"]
    if stats.avg_ms is not None:
        parts.append(f"{stats.avg_ms:g} ms average")
    if stats.jitter_ms is not None:
        parts.append(f"{stats.jitter_ms:g} ms jitter")
    return ", ".join(parts)


def verdict(m: Measurements) -> Verdict:
    """Where the problem is. The rules go up the layers and the first one that matches wins."""
    gw, net = m.gateway, m.internet
    if m.local_ip is None:
        return Verdict("bad", "This PC", "Not connected to a network.", ["This PC has no IPv4 address."],
                       "Turn on Wi-Fi and join your network, or plug in the network cable.", "1–2")
    if m.local_ip.startswith("169.254."):
        return Verdict("bad", "Router", "Connected, but the router gave no address (DHCP failed).",
                       [f"This PC gave itself {m.local_ip}, the address Windows picks when no DHCP server answers."],
                       "Restart the router, then disconnect from the network and connect again.", "3")
    if gw is None or gw.loss_pct == 100:
        return Verdict("bad", "Wi-Fi / LAN", "This PC cannot reach the router.",
                       [f"Router {gw.ip}: all {config.DIAG_PINGS} pings lost." if gw else "No default gateway is set."],
                       "Move closer to the router or check the cable, then restart the router.", "1–2")
    router = f"Router {gw.ip}: {describe(gw)}."
    if gw.loss_pct > config.LOSS_WARN_PCT or gw.avg_ms > config.GATEWAY_SLOW_MS \
            or (gw.jitter_ms or 0) > config.JITTER_WARN_MS:
        return Verdict("warn", "Wi-Fi / LAN", "The link to your router is unstable.", [router],
                       "Move closer to the router or use a cable; other busy devices on the same Wi-Fi also slow it.",
                       "1–2")
    if net is None or net.loss_pct == 100:
        return Verdict("bad", "ISP", "Your router is fine, but the internet connection is down (ISP or modem).",
                       [router, f"{' and '.join(config.INTERNET_TARGETS)}: no replies."],
                       "Restart the modem and router; if the internet stays down, call your ISP.", "3")
    evidence = [router, f"Internet {net.ip}: {describe(net)}."]
    if net.loss_pct > config.LOSS_WARN_PCT or net.avg_ms > config.INTERNET_SLOW_MS:
        return Verdict("warn", "ISP", "The internet connection is slow beyond your router.", evidence,
                       "Trace the route to 1.1.1.1 to see where the delay starts; report it to your ISP.", "3")
    evidence += [f"DNS server {m.dns_server or '(none set)'}: "
                 + ("no answer." if m.dns_ms is None else f"answered in {m.dns_ms:g} ms."),
                 f"{PUBLIC_DNS}: " + ("no answer." if m.dns_public_ms is None else f"answered in {m.dns_public_ms:g} ms.")]
    if m.dns_ms is None and m.dns_public_ms is not None:
        return Verdict("bad", "DNS", f"DNS problem: your DNS server did not answer; {PUBLIC_DNS} did. "
                                     f"Change DNS to {PUBLIC_DNS}.", evidence,
                       f"In the adapter's IPv4 settings, set the preferred DNS server to {PUBLIC_DNS}.", "7")
    if m.dns_ms is None:
        return Verdict("bad", "DNS", "No DNS server answers; websites will not open by name.", evidence,
                       "Restart the router; if it continues, check whether a firewall blocks port 53.", "7")
    if m.dns_ms > config.DNS_SLOW_MS:
        return Verdict("warn", "DNS", f"DNS is slow ({m.dns_ms:g} ms); pages will start slowly.", evidence,
                       f"Set the preferred DNS server to {PUBLIC_DNS} in the adapter's IPv4 settings.", "7")
    return Verdict("good", "None", "Your network is healthy.", evidence, "No action needed.", "1–7")
