"""Watch mode: real-time monitoring by polling.

Every few minutes the network is scanned again and compared with the previous scan. The
interval is a trade-off: a shorter one notices a change sooner but adds more ping and ARP
traffic. Pure logic here; services.watch_tick does the scanning and storing.
"""
from netmonitor import config

SEVERITY = {"gateway-mac-changed": "critical", "new-device": "warning", "offline": "warning", "back-online": "info"}


class WatchState:
    """Remembers the previous check and turns the next one into events."""

    def __init__(self, misses_allowed=config.WATCH_MISSES):
        self.misses_allowed = misses_allowed
        self.present = {}            # mac -> ip of devices considered up
        self.misses = {}             # mac -> checks missed in a row
        self.gateway_mac = None
        self.first = True            # the first check only records; it reports nothing

    def update(self, seen: dict[str, str], known: set[str], gateway_mac: str | None) -> list[tuple]:
        """seen: {mac: ip} found now. Returns (kind, mac, ip) tuples."""
        events = []
        if self.gateway_mac and gateway_mac and gateway_mac != self.gateway_mac:
            events.append(("gateway-mac-changed", gateway_mac, None))
        self.gateway_mac = gateway_mac or self.gateway_mac
        for mac, ip in seen.items():
            self.misses.pop(mac, None)
            if mac not in self.present and not self.first:
                events.append(("new-device" if mac not in known else "back-online", mac, ip))
            self.present[mac] = ip
        for mac in [m for m in self.present if m not in seen]:
            self.misses[mac] = self.misses.get(mac, 0) + 1
            if self.misses[mac] >= self.misses_allowed:     # phones sleep: one miss is not "offline"
                events.append(("offline", mac, self.present.pop(mac)))
                del self.misses[mac]
        self.first = False
        return events


def uptime_pct(presence: list[tuple[str, bool]]) -> float | None:
    """Share of watch checks that found the device up, in %; None when it was never watched."""
    if not presence:
        return None
    return round(sum(up for _, up in presence) / len(presence) * 100, 1)
