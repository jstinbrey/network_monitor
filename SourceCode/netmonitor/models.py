"""Records passed between the core modules, services, storage, and the GUI.

All times are in milliseconds. Timestamps are ISO 8601 strings produced by
``datetime.now().isoformat(timespec="seconds")``.
"""
from dataclasses import dataclass, field

# --- Device / ping status values ------------------------------------------
ONLINE = "online"        # replies received, no loss, latency within threshold
DEGRADED = "degraded"    # some loss, or average latency above the threshold
NO_ICMP = "no-icmp"      # no ping reply but the host answers ARP: it is up
OFFLINE = "offline"      # no ping reply and no ARP entry
NO_DATA = "no-data"      # the host has never been pinged

# --- Account roles ----------------------------------------------------------
ADMIN = "admin"          # can scan, manage accounts and change settings
USER = "user"            # can look at results and run ping tests

STATUS_LABELS = {
    ONLINE: "Online",
    DEGRADED: "Degraded",
    NO_ICMP: "No ICMP reply (host up)",
    OFFLINE: "Offline",
    NO_DATA: "No data",
}


@dataclass
class User:
    """A signed-in account and what it may do."""
    username: str
    role: str                    # ADMIN or USER

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN


@dataclass
class NetworkInfo:
    """Feature 1: how this PC is addressed on the local network."""
    hostname: str
    local_ip: str
    netmask: str
    cidr: str                    # network range, e.g. "192.168.1.0/24"
    first_host: str
    last_host: str
    gateway: str | None
    host_count: int              # usable host addresses in the range
    mask_assumed: bool = False   # True when the netmask could not be read
    truncated: bool = False      # True when a larger network was cut to /24


@dataclass
class Device:
    """Feature 1: one active device found on the network."""
    ip: str
    mac: str | None = None
    hostname: str = "Unknown"
    alias: str = ""              # a name the admin gave the device; shown instead of hostname
    replied_icmp: bool = False   # answered the ping sweep
    is_self: bool = False        # this PC
    is_gateway: bool = False     # the default gateway (router)
    known: bool = True           # False when its MAC is not in the baseline
    first_seen: str = ""
    last_seen: str = ""
    vendor: str = ""             # maker, from the MAC; worked out each time it is loaded, never stored


@dataclass
class Hop:
    """Traceroute: one router on the path, with the reply times of its three probes."""
    number: int
    times_ms: list[float | None]   # None: that probe got no reply
    address: str | None            # None when every probe timed out

    @property
    def loss_pct(self) -> float:
        return round(self.times_ms.count(None) / len(self.times_ms) * 100, 1)

    @property
    def avg_ms(self) -> float | None:
        replies = [t for t in self.times_ms if t is not None]
        return round(sum(replies) / len(replies), 1) if replies else None


@dataclass
class PingResult:
    """Feature 2: the outcome of one connectivity test against one host."""
    ip: str
    sent: int
    received: int
    loss_pct: float
    rtts_ms: list[float] = field(default_factory=list)   # one per reply
    min_ms: float | None = None
    avg_ms: float | None = None
    max_ms: float | None = None
    status: str = OFFLINE
    method: str = "icmp"         # "icmp" (ping) or "tcp" (handshake timing)
    timestamp: str = ""
    raw_lines: list[str] = field(default_factory=list)   # shown in the Ping log


@dataclass
class HostStats:
    """Feature 3: statistics for one host across all stored ping results."""
    ip: str
    hostname: str
    samples: int                 # replies received across all runs
    avg_ms: float | None
    max_ms: float | None
    min_ms: float | None
    jitter_ms: float | None
    loss_pct: float | None
    status: str


@dataclass
class DeviceDetail:
    """Everything the device panel shows, gathered in one service call."""
    device: Device
    stats: HostStats
    history: list[PingResult] = field(default_factory=list)   # the last 10 tests, oldest first
    open_ports: list[dict] | None = None                      # the latest port check; None: never checked
    presence: list[tuple[str, bool]] = field(default_factory=list)   # watch-mode checks in the last 24 h: (at, up)
    uptime_pct: float | None = None                            # up checks / all checks; None: never watched


@dataclass
class NetworkSummary:
    """Feature 3: network-wide performance summary."""
    devices: int
    reachable: int
    unreachable: int
    network_avg_ms: float | None
    best_host: str | None
    worst_host: str | None
    health_score: int            # 0 to 100


@dataclass
class Recommendation:
    """Feature 5: one piece of security or connectivity advice."""
    severity: str                # "critical", "warning", or "info"
    category: str
    host: str | None
    title: str
    detail: str
    action: str


@dataclass
class DiagnosisStep:
    """Diagnosis: one layer tested."""
    name: str                    # "Adapter", "Router", "Internet" or "DNS"
    ok: bool | None              # True: it answered; None: not tested
    detail: str                  # e.g. "3.2 ms"


@dataclass
class Measurements:
    """Diagnosis input: what was measured, layer by layer. None: not measured, or no answer."""
    local_ip: str | None = None
    gateway: HostStats | None = None         # DIAG_PINGS pings to the router
    internet: HostStats | None = None        # the better of the two internet targets
    dns_server: str | None = None            # the first DNS server Windows uses
    dns_ms: float | None = None              # its answer time
    dns_public_ms: float | None = None       # 1.1.1.1's answer time, for comparison
    wifi: "WifiInfo | None" = None           # the Wi-Fi link; None when wired or unknown


@dataclass
class Verdict:
    """Diagnosis result: where the problem is, the numbers that show it, and what to do."""
    status: str                  # "good", "warn" or "bad" (the theme.TAG_COLORS keys)
    where: str                   # "This PC", "Wi-Fi / LAN", "Router", "ISP", "DNS" or "None"
    headline: str
    evidence: list[str]          # every line quotes measured numbers, so it can be checked
    action: str
    layer: str                   # OSI layer(s), e.g. "1–2", "3", "7"


@dataclass
class Event:
    """Something that happened while NetMonitor ran, shown in the alert bar and kept in the events table."""
    id: int | None               # None until stored
    at: str
    kind: str                    # "bandwidth"; later steps add more
    severity: str                # "critical", "warning" or "info", as for a Recommendation
    ip: str | None               # the device it is about, if any: View opens its panel
    mac: str | None
    detail: str
    dismissed: bool = False


@dataclass
class WifiInfo:
    """This PC's Wi-Fi link, from `netsh wlan show interfaces`."""
    ssid: str
    band: str                    # "2.4 GHz", "5 GHz" or "6 GHz"
    channel: int
    radio: str                   # "802.11ax" and so on
    auth: str                    # "WPA2-Personal", "WPA3-Personal", "Open" ...
    cipher: str                  # "CCMP" (AES), "TKIP", "WEP" or "None"
    rx_mbps: float               # link rates the adapter agreed with the router, not measured throughput
    tx_mbps: float
    signal_pct: int
    rssi_dbm: int

    @property
    def quality(self) -> str:
        return ("Excellent" if self.signal_pct >= 80 else "Good" if self.signal_pct >= 60
                else "Fair" if self.signal_pct >= 40 else "Weak")


@dataclass
class BandwidthSample:
    """Bandwidth monitor: this PC's traffic over the last second."""
    down_mbps: float
    up_mbps: float
    today_bytes: int             # received + sent today, saved and not yet saved
    alerts: list[str] = field(default_factory=list)   # limits just passed, to store as events
