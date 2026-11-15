"""Feature 2 (Connectivity Testing): ICMP echo request/reply via the windows ping command."""

import ipaddress
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from netmonitor import config, models
from netmonitor.models import PingResult

NO_WINDOW = subprocess.CREATE_NO_WINDOW # otherwise every ping  flashes a console window
_RTT = re.compile(r"time([=<])\s*(\d+(?:\.\d+)?)\s*ms", re.I)

def validate_ip(text: str) -> str:
    """Return a clean IPv4 string, or raise ValueError for anything else."""
    return str(ipaddress.IPv4Address(text.strip()))

def parse_rtts(output: str) -> list[float]:
    """Reply times in ms. Only lines with a time count; "times<1ms" becomes 0.5"""
    return [0.5 if sign == "<" else float (ms) for sign, ms in _RTT.findall(output)]

def build_result(ip: str, sent: int, rtts: list[float], raw_lines=None) -> PingResult:
    """Turn the reply times of one test into a PingResult with loss and status."""
    received = len(rtts)
    avg = sum (rtts) / received if received else None
    if not received:
        status = models.OFFLINE
    elif received < sent or avg > config.LATENCY_WARN_MS:
        status = models.DEGRADED
    else:
        status = models.ONLINE
    return PingResult(
        ip=ip, sent=sent, received=received,
        loss_pct=round((sent - received) / sent * 100, 1),
        rtts_ms=rtts,
        min_ms=min(rtts, default=None),
        avg_ms=round(avg, 1) if received else None,
        max_ms=max(rtts, default=None),
        status=status,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        raw_lines=raw_lines or [],
    )

def _run(ip: str, count: int, timeout_ms: int) -> str:
    """Run ping and return its text output ("" if it hangs)."""
    try:
        return subprocess.run(
            ["ping", "-n", str(count), "-w", str(timeout_ms), ip], # a list, never shell=True
            capture_output=True, text=True, creationflags=NO_WINDOW, timeout=count * (timeout_ms / 1000 + 1) + 2,).stdout
    except subprocess.TimeoutExpired:
        return ""

def ping(ip: str, count=config.PING_COUNT, timeout_ms=config.PING_TIMEOUT_MS) -> PingResult:
    """Ping one host. Raises ValueError if ip is not valid IPv4 address."""
    ip = validate_ip(ip)
    output = _run(ip, count, timeout_ms)
    lines = [l.strip() for l in output.splitlines() if l.strip().startswith(("Reply", "Request"))]
    # The OS summary is ignored: Windows counts "Destination host unreachable" as received.
    return build_result(ip, count, parse_rtts(output), lines)

def is_alive(ip: str, count=config.PING_COUNT, timeout_ms=config.SWEEP_TIMEOUT_MS) -> bool:
    """ One echo request; True if a reply came back. Used by network scan."""
    return bool(parse_rtts(_run(ip, 1, timeout_ms=timeout_ms)))

def ping_many(ips: list[str], count=config.PING_COUNT) -> list[PingResult]:
    """Ping several host in parallel; results come back in the same order."""
    with ThreadPoolExecutor(max_workers=config.PING_MANY_WORKERS) as pool:
        return list(pool.map(lambda ip: ping(ip, count), ips))