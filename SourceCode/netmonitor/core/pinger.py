"""Feature 2 (Connectivity Testing): ICMP echo request/reply through the Windows ping command."""
import ipaddress
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from netmonitor import config, models
from netmonitor.core import statistics
from netmonitor.models import PingResult

NO_WINDOW = subprocess.CREATE_NO_WINDOW   # otherwise every ping flashes a console window
_RTT = re.compile(r"time([=<])\s*(\d+(?:\.\d+)?)\s*ms", re.I)
_LOST = ("Request timed out", "Reply from", "General failure", "PING: transmit failed",
         "Destination host unreachable")


def validate_ip(text: str) -> str:
    """Return a clean IPv4 string, or raise ValueError for anything else."""
    return str(ipaddress.IPv4Address(text.strip()))


def parse_rtts(output: str) -> list[float]:
    """Reply times in ms. Only lines with a time count; "time<1ms" becomes 0.5."""
    return [0.5 if sign == "<" else float(ms) for sign, ms in _RTT.findall(output)]


def build_result(ip: str, sent: int, rtts: list[float], raw_lines=None) -> PingResult:
    """Turn the reply times of one test into a PingResult with loss and status."""
    received = len(rtts)
    avg = sum(rtts) / received if received else None
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


_children = set()                         # every ping -n still running, so stop_children can end it


def _run(ip: str, count: int, timeout_ms: int) -> str:
    """Run ping and return its text output ("" if it hangs). Raises RuntimeError if stop_children ended it."""
    process = subprocess.Popen(["ping", "-n", str(count), "-w", str(timeout_ms), ip],   # a list, never shell=True
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                               creationflags=NO_WINDOW)
    _children.add(process)
    try:
        output = process.communicate(timeout=count * (timeout_ms / 1000 + 1) + 2)[0]
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        output = ""
    finally:
        _children.discard(process)
    if getattr(process, "stopped", False):   # cut short: its partial output must not be stored as loss
        raise RuntimeError("Stopped.")
    return output


def stop_children():
    """End every ping -n still running (window closed, or signed out); each caller gets RuntimeError."""
    for process in list(_children):
        process.stopped = True
        process.kill()


def ping(ip: str, count=config.PING_COUNT, timeout_ms=config.PING_TIMEOUT_MS) -> PingResult:
    """Ping one host. Raises ValueError if ip is not a valid IPv4 address."""
    ip = validate_ip(ip)
    output = _run(ip, count, timeout_ms)
    lines = [l.strip() for l in output.splitlines() if l.strip().startswith(("Reply", "Request"))]
    # The OS summary is ignored: Windows counts "Destination host unreachable" as received.
    return build_result(ip, count, parse_rtts(output), lines)


def is_alive(ip: str, timeout_ms=config.SWEEP_TIMEOUT_MS) -> bool:
    """One echo request; True if a reply came back. Used by the network scan."""
    return bool(parse_rtts(_run(ip, 1, timeout_ms)))


def ping_many(ips: list[str], count=config.PING_COUNT) -> list[PingResult]:
    """Ping several hosts in parallel; results come back in the same order."""
    with ThreadPoolExecutor(max_workers=config.PING_MANY_WORKERS) as pool:
        return list(pool.map(lambda ip: ping(ip, count), ips))


# --- Continuous ping (ping -t) ------------------------------------------------
def parse_reply(line: str) -> tuple[bool, float | None]:
    """(is_echo_line, rtt_ms) for one line of ping output; rtt_ms is None for a lost reply.
    "Reply from …: Destination host unreachable." has no time, so it counts as lost."""
    found = _RTT.search(line)
    if found:
        return True, 0.5 if found.group(1) == "<" else float(found.group(2))
    return line.startswith(_LOST), None


class ContinuousPing:
    """`ping -t ip` in a child process. on_reply(rtt_ms or None, line) is called from a reader thread."""

    def __init__(self, ip: str, on_reply, timeout_ms=config.PING_TIMEOUT_MS):
        self.ip = validate_ip(ip)
        self.on_reply = on_reply
        self.process = subprocess.Popen(["ping", "-t", "-w", str(timeout_ms), self.ip],
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, creationflags=NO_WINDOW)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:          # ends when the process is terminated
            is_echo, rtt = parse_reply(line.strip())
            if is_echo:
                self.on_reply(rtt, line.strip())

    def stop(self):
        """End the child process. Safe to call twice."""
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)


class PingSession:
    """The running totals of one continuous ping. Pure: each reply is handed to add(), so it is easy to test."""

    def __init__(self, ip: str):
        self.ip = ip
        self.rtts = []                    # one per echo request; None for a lost reply
        self.history = []                 # the host's stored reply times (at most BASELINE_WINDOW), for the baseline
        self.spikes, self.last_spike = 0, False
        self.current_outage = 0           # lost replies in a row right now (about one per second)
        self.longest_outage, self.longest_outage_at = 0, None   # the longest run so far, and when it began
        self._outage_began = None

    def replies(self) -> list[float]:
        return [rtt for rtt in self.rtts if rtt is not None]

    def learned(self) -> int:
        """Replies the baseline is built from so far: stored ones plus this session's."""
        return len(self.history) + len(self.replies())

    def baseline(self) -> tuple[float, float] | None:
        """(mean, σ) of the host's last BASELINE_WINDOW replies, stored ones first; None while still learning."""
        return statistics.baseline(self.history + self.replies()[-config.BASELINE_WINDOW:])

    def add(self, rtt: float | None):
        base = self.baseline()            # a reply is judged against the replies before it
        self.last_spike = rtt is not None and base is not None and statistics.is_spike(rtt, base)
        self.spikes += self.last_spike
        self.rtts.append(rtt)
        if rtt is not None:
            self.current_outage = 0
            return
        if not self.current_outage:
            self._outage_began = datetime.now().strftime("%H:%M:%S")
        self.current_outage += 1
        if self.current_outage > self.longest_outage:
            self.longest_outage, self.longest_outage_at = self.current_outage, self._outage_began

    def result(self) -> PingResult:
        """The session so far as one ping test, so a stored session looks like any other."""
        return build_result(self.ip, len(self.rtts), self.replies())

    @property
    def jitter_ms(self) -> float | None:
        return statistics.host_stats(models.Device(ip=self.ip), [self.result()]).jitter_ms   # the Statistics formula

    def verdict(self) -> tuple[str, str]:
        """("good", "warn" or "bad", one sentence) to show when the session is stopped."""
        if not self.rtts:
            return "warn", "Stopped before the first reply."
        r, jitter = self.result(), self.jitter_ms
        if not r.received:
            return "bad", f"No replies from {self.ip} in {r.sent} pings: it is offline, or it blocks ping."
        outage = (f" Longest outage: {self.longest_outage} lost in a row (about {self.longest_outage} s) "
                  f"from {self.longest_outage_at}." if self.longest_outage else " No lost replies.")
        base = self.baseline()
        if self.spikes:
            outage += f" {self.spikes} slower than usual (usual {base[0]:.1f} ms)."
        slow = (r.loss_pct > config.LOSS_WARN_PCT or r.avg_ms > config.LATENCY_WARN_MS
                or (jitter or 0) > config.JITTER_WARN_MS)
        return ("warn" if slow else "good",
                f"{self.ip}: {r.received} of {r.sent} replies ({r.loss_pct:g}% lost), average {r.avg_ms:g} ms, "
                f"jitter {'-' if jitter is None else f'{jitter:g} ms'}.{outage}")