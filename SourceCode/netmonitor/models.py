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
