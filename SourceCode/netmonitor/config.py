"""Central settings: file locations, timeouts, pool sizes, and alert thresholds.

Every tunable number in the application lives here so that the behaviour of
the scanner, the ping tests, and the security rules can be changed (and cited
in the documentation) from a single place.
"""
import os
import sys
from pathlib import Path

# --- Version ----------------------------------------------------------------
# 0.<phase>.<fix> while the build plan runs; 1.0.0 is the submitted build.
# Pushing the tag v + VERSION builds NetMonitor.exe and publishes it (README.md, "Making a release").
VERSION = "0.8.0"

# --- File locations -------------------------------------------------------
FROZEN = getattr(sys, "frozen", False)                 # True when running as NetMonitor.exe (PyInstaller)
BASE_DIR = Path(__file__).resolve().parent.parent      # the SourceCode/ folder
# The .exe keeps its history and reports in AppData: a newer version, unzipped to a new folder, still finds them.
DATA_DIR = Path(os.environ["LOCALAPPDATA"]) / "NetMonitor" if FROZEN else BASE_DIR
DB_PATH = DATA_DIR / "data" / "netmonitor.db"          # SQLite history
OUTPUT_DIR = DATA_DIR / "output"                       # generated reports
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
OUI_PATH = Path(__file__).resolve().parent / "resources" / "oui.csv"   # IEEE MAC vendor registry

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
ECG_WINDOW = 60             # continuous ping: replies on screen (about one per second)
ECG_MIN_TOP_MS = 5          # continuous ping: the chart's top until a reply is slower; LAN replies are under 1 ms
LOG_MAX_LINES = 500         # older lines of the Ping log are deleted

# --- Feature 2 extension: traceroute --------------------------------------
TRACE_MAX_HOPS = 15         # tracert -h: give up after this many routers
TRACE_TIMEOUT_MS = 500      # tracert -w: wait per probe
TRACE_JUMP_MS = 30          # a lasting rise in latency above this at one hop is flagged

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

# --- Diagnosis ------------------------------------------------------------
DIAG_PINGS = 10             # pings to the router and to each internet target
INTERNET_TARGETS = ("1.1.1.1", "8.8.8.8")   # Cloudflare and Google: both answer ping and DNS
DNS_TEST_NAME = "example.com"
DNS_TIMEOUT_S = 2
GATEWAY_SLOW_MS = 50        # a router this slow to answer means a poor Wi-Fi or LAN link
INTERNET_SLOW_MS = 150
DNS_SLOW_MS = 300

# --- Bandwidth --------------------------------------------------------------
BW_SAMPLE_MS = 1000
BW_SUSTAIN_S = 10           # seconds above a limit before it alerts
BW_SAVE_EVERY_S = 10
BW_WINDOW_S = 120           # seconds shown in the chart

# --- Baseline: a host judged against its own history --------------------------
BASELINE_MIN_SAMPLES = 30   # replies needed before a host has a baseline
BASELINE_WINDOW = 300       # most recent replies used
SPIKE_SIGMAS = 3            # a reply above mean + 3 standard deviations is a spike...
SPIKE_FLOOR_MS = 20         # ...and also at least this far above the mean

# --- Wi-Fi ------------------------------------------------------------------
WIFI_WEAK_PCT = 40          # signal below this is weak

# --- Watch mode ---------------------------------------------------------------
WATCH_DEFAULT_MIN = 5       # minutes between checks
WATCH_MISSES = 2            # checks a device may miss before it counts as offline (phones sleep)

# Settings an administrator can change in Admin > Settings. Bandwidth limits: 0 = no limit.
SETTING_DEFAULTS = {"bw_down_mbps": 0, "bw_up_mbps": 0, "bw_daily_gb": 0, "watch_min": WATCH_DEFAULT_MIN}
SETTING_MINIMUMS = {"watch_min": 1}   # every other setting may be 0

# --- Window ---------------------------------------------------------------
APP_TITLE = "NetMonitor"
WINDOW_SIZE = "1180x720"
MIN_WINDOW_SIZE = (1000, 640)
LIVE_REFRESH_S = 30
ALIAS_MAX_LEN = 40          # longer device names are cut