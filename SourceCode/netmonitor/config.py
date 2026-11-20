"""Central settings: file locations, timeouts, pool sizes, and alert thresholds.

Every tunable number in the application lives here so that the behaviour of
the scanner, the ping tests, and the security rules can be changed (and cited
in the documentation) from a single place.
"""
from pathlib import Path

# --- File locations -------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent      # the SourceCode/ folder
DB_PATH = BASE_DIR / "data" / "netmonitor.db"          # SQLite history
OUTPUT_DIR = BASE_DIR / "output"                       # generated reports
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# --- Feature 1: network discovery -----------------------------------------
SWEEP_WORKERS = 64          # parallel pings during a scan
SWEEP_TIMEOUT_MS = 500      # how long to wait for each host during a scan
MAX_PREFIX = 24             # never sweep more than a /24 (254 hosts)
HOSTNAME_TIMEOUT_S = 2      # total time allowed for reverse DNS lookups

# --- Feature 2: connectivity testing --------------------------------------
PING_COUNT = 4              # echo requests per test
PING_TIMEOUT_MS = 1000      # wait per echo request
PING_MANY_WORKERS = 16      # parallel hosts in a batch ping
TCP_TIMEOUT_S = 3           # must exceed 2 s: Windows reports a refused
                            # connection only after retrying for about 2 s

# --- Features 3 and 5: thresholds -----------------------------------------
LATENCY_WARN_MS = 100       # average latency above this is "degraded"
LOSS_WARN_PCT = 5           # packet loss above this is "weak connectivity"
JITTER_WARN_MS = 30         # jitter above this hurts voice and video
GATEWAY_LOSS_WARN_PCT = 25  # gateway loss at or above this is "unstable"

# --- Feature 5 bonus: port check ------------------------------------------
PORT_TIMEOUT_S = 0.5
COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 53: "DNS", 80: "HTTP",
    139: "NetBIOS", 443: "HTTPS", 445: "SMB", 3389: "RDP", 8080: "HTTP-alt",
}
RISKY_PORTS = {21, 23, 445, 3389}   # unencrypted or commonly attacked services

# --- Accounts and roles ---------------------------------------------------
AUTH_ITERATIONS = 600_000   # PBKDF2-SHA256 rounds (OWASP guidance); about 0.2 s on this PC
PASSWORD_MIN_LEN = 8
LOGIN_MAX_FAILURES = 5      # wrong passwords in a row before sign-in pauses
LOGIN_LOCK_S = 30

# --- Window ---------------------------------------------------------------
APP_TITLE = "NetMonitor"
WINDOW_SIZE = "1180x720"
MIN_WINDOW_SIZE = (1000, 640)
LIVE_REFRESH_S = 30
ALIAS_MAX_LEN = 40          # longer device names are cut