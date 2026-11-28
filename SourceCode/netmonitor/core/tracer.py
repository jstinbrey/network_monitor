"""Feature 2 extension (Traceroute): the routers between this PC and a target, and where delay starts.

tracert sends probes with a growing TTL (time to live). The router that
lowers the TTL to 0 drops the probe and answers with ICMP Time Exceeded
(type 11), which reveals its address and the round-trip time: one hop at a time.
"""
import ipaddress
import re
import subprocess
import threading

from netmonitor import config
from netmonitor.core.pinger import NO_WINDOW
from netmonitor.models import Hop

# "  1    <1 ms     2 ms     1 ms  192.168.1.1"   and   "  3     *        *        *     Request timed out."
_HOP = re.compile(r"^\s*(\d+)\s+(<?\d+ ms|\*)\s+(<?\d+ ms|\*)\s+(<?\d+ ms|\*)\s+(\S+)")
CGNAT = ipaddress.ip_network("100.64.0.0/10")      # ISP shared address space; is_private is False for it


def parse_hop(line: str) -> Hop | None:
    """One line of tracert output as a Hop, or None for headers and blank lines."""
    found = _HOP.match(line)
    if not found:
        return None
    times = [None if t == "*" else 0.5 if t.startswith("<") else float(t.split()[0]) for t in found.group(2, 3, 4)]
    try:
        address = str(ipaddress.ip_address(found.group(5)))
    except ValueError:                       # "Request timed out."
        address = None
    return Hop(int(found.group(1)), times, address)


def segment(hop: Hop) -> str:
    """Which part of the path a hop is in. Private and CGNAT addresses after hop 1 belong to the ISP."""
    if hop.number == 1:
        return "your router"
    if hop.address is None:
        return "unknown"
    address = ipaddress.ip_address(hop.address)
    return "ISP access network" if address.is_private or address in CGNAT else "internet"


def analyse(hops: list[Hop], target: str) -> tuple[str, str]:
    """("good" or "warn", one plain sentence) saying whether the target was reached and where delay starts."""
    answered = [h for h in hops if h.avg_ms is not None]
    last_address = hops[-1].address if hops else None
    if not last_address or last_address.split("%", 1)[0] != target.split("%", 1)[0] or hops[-1].avg_ms is None:
        if not answered:
            return "warn", f"No router answered; {target} was not reached."
        last = answered[-1]
        return "warn", f"The route stops after hop {last.number} ({segment(last)}); {target} was not reached."
    final = hops[-1].avg_ms
    # A rise counts only if the target is still at least that slow: a rise that disappears later
    # is one router answering traceroute slowly, not delay on the path.
    lasting = [(round(later.avg_ms - earlier.avg_ms, 1), later) for earlier, later in zip(answered, answered[1:])
               if final >= later.avg_ms]
    rise, hop = max(lasting, key=lambda pair: pair[0], default=(0.0, None))
    if rise > config.TRACE_JUMP_MS:
        return "warn", f"Latency rises by {rise:g} ms at hop {hop.number} ({segment(hop)}) and stays high up to {target}."
    # Routers rate-limit their traceroute replies, so loss at a middle hop is not loss on the path.
    note = (" Lost replies at middle hops are routers limiting traceroute answers, not real loss."
            if any(h.loss_pct for h in hops[:-1]) and not hops[-1].loss_pct else "")
    hops_text = "1 hop" if len(hops) == 1 else f"{len(hops)} hops"
    return "good", f"{target} reached in {hops_text}, {final:g} ms. No hop adds a lasting delay.{note}"


class Traceroute:
    """tracert running in the background: on_hop(hop) as each hop arrives, on_done(hops) when it ends."""

    def __init__(self, ip: str, on_hop, on_done):
        self.ip, self.on_hop, self.on_done = ip, on_hop, on_done
        self.stopped = False
        self._process = None

    def start(self):
        # -d: no reverse DNS, which would make every hop slower. A list, never shell=True.
        family = "-6" if ":" in self.ip else "-4"
        self._process = subprocess.Popen(
            ["tracert", family, "-d", "-h", str(config.TRACE_MAX_HOPS), "-w", str(config.TRACE_TIMEOUT_MS), self.ip],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, creationflags=NO_WINDOW)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        hops = []
        for line in self._process.stdout:              # tracert prints each hop as soon as it is done
            hop = parse_hop(line)
            if hop:
                hops.append(hop)
                self.on_hop(hop)
        self._process.wait()
        self.on_done(hops)

    def stop(self):
        self.stopped = True
        self._process.kill()
