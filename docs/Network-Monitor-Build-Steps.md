# Network Monitor: Step-by-Step Build Plan

Companion to `Network-Monitor-Implementation-Plan-v3.docx`. That document says **what** is built and why; this one says **how**, in the order to do it. Requirements, dates and point values come from the two course documents in this folder.

- **Target:** Windows 10/11, Python 3.11+ (3.13 is installed on this PC).
- **Submission:** Dec 4. **Feature freeze:** Nov 29. **Defense:** Dec 8–10.
- **Rule for every step:** do not start the next step until the current step's **Checkpoint** passes.

Code blocks marked **(checked)** were run on this PC: Phases 0–4 against real `ping`, `route print` and `arp -a` output on Nov 15; Phases 5–8 against real `ping -t`, `tracert`, `netsh wlan` output and DNS replies on Nov 20. Everything else is a design to implement and test, not finished code.

**Revision 3 (Nov 20).** Phases 0–4 are done and unchanged below. Phase 5 onward is rewritten for the fourteen features of plan v3. The old Phase 5 items either moved (port check → 6.3, polish → 8.3, PDF export → 8.4) or were cut (TCP latency mode; live refresh, replaced by watch mode). The old Phases 6 and 7 are now 9 and 10.

---

## Contents

| Phase | Dates | Result |
|---|---|---|
| [0. Setup](#phase-0-setup) | Nov 15 | Done |
| [1. Scan and ping](#phase-1-scan-and-ping-f1-f2) | Nov 15–16 | Done: F1 and F2 |
| [2. Storage and statistics](#phase-2-storage-and-statistics-f3) | — | Done: F3 |
| [3. Reports](#phase-3-reports-f4) | — | Done: F4 |
| [4. Security](#phase-4-security-recommendations-f5) | — | Done: F5 and the Dashboard |
| [5. Foundations](#phase-5-foundations) | Nov 20–21 | Network id, accounts and roles, device panel |
| [6. Conclusive diagnostics](#phase-6-conclusive-diagnostics) | Nov 22–24 | Vendor, ARP spoofing, port check, traceroute, diagnosis verdict |
| [7. Real-time monitoring](#phase-7-real-time-monitoring) | Nov 25–28 | Alerts, continuous ping with ECG, bandwidth limits, baseline, Wi-Fi, watch mode |
| [8. Map, polish, freeze](#phase-8-map-polish-freeze) | Nov 29 | Interactive map; feature freeze |
| [9. Test evidence](#phase-9-test-evidence) | Nov 30 | Everything Chapter 4 needs |
| [10. Packaging](#phase-10-packaging) | Dec 3 | The zip |

Dec 1–2 is the final report, Dec 3 the slides, video and zip (plan v3, section 12). Write 30 minutes of the report every day from Nov 21; this schedule has no slack.

---

## Ground rules

1. **Three layers, one direction.** `gui/` calls `services.py`; `services.py` calls `core/` and `store.py`. `core/` never imports Tkinter. `gui/` never runs `subprocess` or opens a socket.
2. **Nothing slow on the main thread.** Every service call from a view goes through `run_async`. Test by dragging the window while a scan runs; it must keep moving. (The one exception is the bandwidth sampler, which reads a counter in under a millisecond.)
3. **Tkinter is touched only from the main thread.** Worker threads put results on a queue; the main thread reads the queue.
4. **Test `core/` before wiring it to a view.** Each core step below has a pytest file. A parser that passes its fixtures will not surprise you in the demo.
5. **Save real command output as fixtures.** When `ping`, `arp -a`, `tracert` or `netsh` prints something new, save it under `tests/fixtures/` and add a test. Replace your SSID and BSSID with placeholders before committing a `netsh` fixture.
6. **Comment as you write.** The brief requires commented code. Each module gets a docstring naming its feature and protocol; each public function gets a docstring.
7. **Commit after every checkpoint.** A working state you can return to is worth more than any feature.
8. **Roles are checked twice.** Admin-only service functions call `require_admin()` first; views disable the same buttons for Users. The GUI check is for convenience; the services check is the real one.
9. **Every view ends in a verdict.** One sentence, coloured green, amber or red, that names the cause and the next action and quotes the numbers behind it.
10. **Every child process gets stopped.** `ping -t` and `tracert` handles are registered in services. Stop, sign-out and closing the window call `services.stop_all()`. After any test run, `tasklist /FI "IMAGENAME eq PING.EXE"` must find nothing.
11. **Background loops never overlap.** A watch tick does not start while the previous one runs.

---

## Phase 0: Setup

### Step 0.1: Create the folder tree

Use your real name now so packaging is only a zip later.

```
LASTNAME_FIRSTNAME_FINALPROJECT/
  README.txt
  SourceCode/
    main.py
    requirements.txt
    run.bat
    netmonitor/
      __init__.py
      config.py
      models.py
      store.py
      services.py
      core/
        __init__.py
        netinfo.py  discovery.py  pinger.py
        statistics.py  report_builder.py  advisor.py
      gui/
        __init__.py
        app.py  worker.py  theme.py
        views/     __init__.py + one file per view
        widgets/   __init__.py + host_table.py, latency_chart.py,
                   stat_card.py, recommendation_card.py
      templates/report.html
    tests/
      fixtures/
    output/
    data/
  Presentation/
  VideoDemo/
  Documentation/
    01_Proposal/ 02_ProgressReport/ 03_FinalReport/
    diagrams/ screenshots/ wireshark/
```

Create every `.py` file empty for now. `data/` holds the SQLite file; `output/` holds generated reports.

### Step 0.2: Virtual environment and packages

In PowerShell, inside `SourceCode/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install customtkinter matplotlib psutil jinja2 reportlab pytest
pip freeze > requirements.txt
```

If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

`pip freeze` pins the exact versions that work on your machine, including dependencies. That is what the grader installs.

Add a `.gitignore` with: `.venv/`, `__pycache__/`, `.pytest_cache/`, `output/*`, `data/*.db`, `build/`, `dist/`.

### Step 0.3: `config.py`

Every tunable number lives here so the report can cite one place.

```python
"""Central settings: timeouts, pool sizes, and alert thresholds."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # SourceCode/
DB_PATH = BASE_DIR / "data" / "netmonitor.db"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Discovery (F1)
SWEEP_WORKERS = 64          # parallel pings during a scan
SWEEP_TIMEOUT_MS = 500      # per-host wait during a scan
MAX_PREFIX = 24             # never sweep more than a /24 (254 hosts)
HOSTNAME_TIMEOUT_S = 2

# Ping (F2)
PING_COUNT = 4
PING_TIMEOUT_MS = 1000
PING_MANY_WORKERS = 16
TCP_TIMEOUT_S = 3           # must exceed 2 s, see Step 5.3

# Thresholds (F3, F5)
LATENCY_WARN_MS = 100
LOSS_WARN_PCT = 5
JITTER_WARN_MS = 30
GATEWAY_LOSS_WARN_PCT = 25

# Port check (F5 bonus)
PORT_TIMEOUT_S = 0.5
COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 53: "DNS", 80: "HTTP",
    139: "NetBIOS", 443: "HTTPS", 445: "SMB", 3389: "RDP", 8080: "HTTP-alt",
}
RISKY_PORTS = {21, 23, 445, 3389}

# Window
APP_TITLE = "NetMonitor"
WINDOW_SIZE = "1180x720"
LIVE_REFRESH_S = 30
```

### Step 0.4: `models.py`

Plain dataclasses shared by all layers. Times are milliseconds; timestamps are ISO strings from `datetime.now().isoformat(timespec="seconds")`.

```python
"""Records passed between core, services, store, and the GUI."""
from dataclasses import dataclass, field

# Device / ping status values
ONLINE = "online"
DEGRADED = "degraded"
NO_ICMP = "no-icmp"        # shown as "No ICMP reply (host up)"
OFFLINE = "offline"
NO_DATA = "no-data"

@dataclass
class NetworkInfo:
    hostname: str
    local_ip: str
    netmask: str
    cidr: str               # e.g. "192.168.1.0/24"
    first_host: str
    last_host: str
    gateway: str | None
    host_count: int
    mask_assumed: bool = False   # True when the netmask could not be read
    truncated: bool = False      # True when a larger network was cut to /24

@dataclass
class Device:
    ip: str
    mac: str | None = None
    hostname: str = "Unknown"
    replied_icmp: bool = False
    is_self: bool = False
    is_gateway: bool = False
    known: bool = True
    first_seen: str = ""
    last_seen: str = ""

@dataclass
class PingResult:
    ip: str
    sent: int
    received: int
    loss_pct: float
    rtts_ms: list[float] = field(default_factory=list)
    min_ms: float | None = None
    avg_ms: float | None = None
    max_ms: float | None = None
    status: str = OFFLINE
    method: str = "icmp"         # "icmp" or "tcp"
    timestamp: str = ""
    raw_lines: list[str] = field(default_factory=list)   # for the Ping log

@dataclass
class HostStats:
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
    devices: int
    reachable: int
    unreachable: int
    network_avg_ms: float | None
    best_host: str | None
    worst_host: str | None
    health_score: int

@dataclass
class Recommendation:
    severity: str                # "critical" | "warning" | "info"
    category: str
    host: str | None
    title: str
    detail: str
    action: str

@dataclass
class ReportMeta:
    id: int
    created_at: str
    format: str
    path: str
```

### Step 0.5: Make it run

`main.py`:

```python
"""Entry point: prepare storage, then open the main window."""
from netmonitor.gui.app import App

if __name__ == "__main__":
    App().mainloop()
```

`gui/app.py`, for now:

```python
import customtkinter as ctk
from netmonitor import config

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(config.APP_TITLE)
        self.geometry(config.WINDOW_SIZE)
```

`run.bat`:

```bat
@echo off
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python main.py
```

Add `tests/conftest.py` so pytest finds the package:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

**Checkpoint 0**
- [ ] `python main.py` opens an empty dark window titled NetMonitor.
- [ ] `pytest` runs and reports "no tests ran" without import errors.
- [ ] `run.bat` opens the same window by double-click.

---

## Phase 1: Scan and ping (F1, F2)

Goal for Nov 16: a scan lists real devices and a ping shows reply times and loss, without the window freezing. There is no database yet; services keep results in memory.

### Step 1.1: `core/netinfo.py` — local IP, mask, range, gateway

Concepts to name in the report: IPv4 addressing, subnet mask, CIDR, default gateway, UDP sockets.

```python
"""F1: local addressing. Finds this PC's IP, subnet mask, network range and gateway."""
import ipaddress, re, socket, subprocess
import psutil
from netmonitor import config
from netmonitor.models import NetworkInfo

NO_WINDOW = subprocess.CREATE_NO_WINDOW

def get_local_ip() -> str | None:
    """IP of the adapter that routes to the internet.

    connect() on a UDP socket sends no packet; it only makes the OS pick
    the outgoing interface, whose address getsockname() then returns.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None                      # no network
    finally:
        s.close()

def get_netmask(ip: str) -> str | None:
    """Subnet mask of the adapter that owns `ip`, from psutil."""
    for addrs in psutil.net_if_addrs().values():
        for a in addrs:
            if a.family == socket.AF_INET and a.address == ip:
                return a.netmask
    return None

_ROUTE = re.compile(
    r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s*$",
    re.M,
)

def parse_default_gateway(route_output: str, local_ip: str) -> str | None:
    """Gateway of the default route (0.0.0.0/0) from `route print -4`.

    Prefers the row whose interface is `local_ip`; otherwise the lowest metric.
    """
    rows = _ROUTE.findall(route_output)
    if not rows:
        return None
    for gw, iface, _ in rows:
        if iface == local_ip:
            return gw
    return min(rows, key=lambda r: int(r[2]))[0]

def get_gateway(local_ip: str) -> str | None:
    out = subprocess.run(["route", "print", "-4"], capture_output=True, text=True,
                         timeout=10, creationflags=NO_WINDOW).stdout
    return parse_default_gateway(out, local_ip)
```

The route regex and the psutil lookup are **(checked)**: on this PC they returned one default route and the mask `255.255.255.0`.

Then write `get_network_info() -> NetworkInfo`:

1. `ip = get_local_ip()`. If `None`, raise `RuntimeError("Not connected to a network")`; the view shows that message.
2. `mask = get_netmask(ip)`. If `None`, use `"255.255.255.0"` and set `mask_assumed=True`.
3. `net = ipaddress.ip_network(f"{ip}/{mask}", strict=False)`.
4. If `net.prefixlen < config.MAX_PREFIX`, replace it with `ipaddress.ip_network(f"{ip}/24", strict=False)` and set `truncated=True`.
5. `hosts = list(net.hosts())`; fill `first_host`, `last_host`, `host_count=len(hosts)`.
6. `hostname = socket.gethostname()`, `gateway = get_gateway(ip)`.

Keep a helper `scan_targets(info) -> list[str]` that returns the host addresses as strings, without the local IP.

**Tests — `tests/test_netinfo.py`**
- `ip_network("192.168.1.37/255.255.255.0", strict=False)` gives `192.168.1.0/24`, 254 hosts, first `.1`, last `.254`.
- Mask `255.255.255.240` gives 14 hosts.
- A `/16` input is truncated to the `/24` containing the IP, with `truncated=True`.
- `parse_default_gateway` on a saved fixture (`tests/fixtures/route_print.txt`, made with `route print -4 > ...`) returns your gateway.
- Fixture with no default route returns `None`.

### Step 1.2: `core/pinger.py` — ICMP ping and parsing

Concepts: ICMP echo request (type 8) and echo reply (type 0), round-trip time, packet loss, TTL, timeouts.

Windows output to handle:

```
Reply from 192.168.1.1: bytes=32 time=3ms TTL=64
Reply from 192.168.1.1: bytes=32 time<1ms TTL=64
Request timed out.
Reply from 192.168.1.37: Destination host unreachable.
```

The last line is a reply from **your own PC** saying it could not reach the target. Windows counts it as "Received" in its summary, so the summary is not used. Only lines with a `time` value count.

```python
"""F2: connectivity testing with the Windows ping command (ICMP echo)."""
import ipaddress, re, subprocess
from datetime import datetime
from netmonitor import config, models
from netmonitor.models import PingResult

NO_WINDOW = subprocess.CREATE_NO_WINDOW
_RTT = re.compile(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.I)

def validate_ip(text: str) -> str:
    """Return a clean IPv4 string or raise ValueError. Blocks command injection."""
    return str(ipaddress.IPv4Address(text.strip()))

def parse_rtts(output: str) -> list[float]:
    """Reply times in ms. `time<1ms` is recorded as 0.5."""
    rtts = []
    for line in output.splitlines():
        m = _RTT.search(line)
        if m:
            rtts.append(0.5 if "time<" in line.lower() else float(m.group(1)))
    return rtts

def build_result(ip, sent, rtts, method="icmp", raw_lines=None) -> PingResult:
    received = len(rtts)
    loss = (sent - received) / sent * 100 if sent else 100.0
    avg = sum(rtts) / received if received else None
    if received == 0:
        status = models.OFFLINE          # services may upgrade this to NO_ICMP
    elif loss > 0 or avg > config.LATENCY_WARN_MS:
        status = models.DEGRADED
    else:
        status = models.ONLINE
    return PingResult(
        ip=ip, sent=sent, received=received, loss_pct=round(loss, 1), rtts_ms=rtts,
        min_ms=min(rtts) if rtts else None,
        avg_ms=round(avg, 1) if rtts else None,
        max_ms=max(rtts) if rtts else None,
        status=status, method=method,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        raw_lines=raw_lines or [],
    )

def ping(ip: str, count=config.PING_COUNT, timeout_ms=config.PING_TIMEOUT_MS) -> PingResult:
    ip = validate_ip(ip)
    cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), ip]   # a list, never shell=True
    limit_s = count * (timeout_ms / 1000 + 1) + 2
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=limit_s,
                             creationflags=NO_WINDOW).stdout
    except subprocess.TimeoutExpired:
        out = ""
    lines = [l.strip() for l in out.splitlines()
             if l.strip().startswith(("Reply from", "Request timed out", "PING:", "General failure"))]
    return build_result(ip, count, parse_rtts(out), raw_lines=lines)
```

The regex is **(checked)** against real replies on this PC.

Also write:

- `is_alive(ip, timeout_ms) -> bool`: one ping (`-n 1`), returns `bool(parse_rtts(out))`. Used by the sweep; skips `build_result` to stay cheap.
- `ping_many(ips, count) -> list[PingResult]`: `ThreadPoolExecutor(max_workers=config.PING_MANY_WORKERS)` and `executor.map(lambda ip: ping(ip, count), ips)`.

`CREATE_NO_WINDOW` matters: without it a windowed app flashes a console for every ping.

**Tests — `tests/test_pinger.py`**

Save real output first: `ping -n 4 192.168.1.1 > tests\fixtures\ping_ok.txt`, and the same for an unused address (`ping_timeout.txt`). Hand-write `ping_sub1ms.txt`, `ping_mixed.txt` (two replies, two timeouts) and `ping_unreachable.txt` from the samples above.

- `parse_rtts` on each fixture returns the expected list; `[]` for timeout and unreachable.
- `time<1ms` gives `0.5`.
- `build_result("x", 4, [3, 5, 4])` gives 25% loss and status `degraded`.
- `build_result("x", 4, [])` gives 100% loss, `avg_ms is None`, status `offline`.
- `validate_ip("1.1.1.1; dir")`, `validate_ip("abc")` and `validate_ip("999.1.1.1")` raise `ValueError`.

### Step 1.3: `core/discovery.py` — sweep, ARP, hostnames

Concepts: ICMP sweep, ARP (maps IP to MAC on the local segment), reverse DNS.

**ARP parsing.** `arp -a` prints one block per adapter:

```
Interface: 192.168.1.37 --- 0x12
  Internet Address      Physical Address      Type
  192.168.1.1           a4-2b-b0-11-22-33     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
```

Keep only rows in the block for your local IP, inside the scanned network, that are not the network or broadcast address and not a broadcast or multicast MAC. Filtering by address rather than by the word `dynamic` keeps it independent of the Windows display language.

```python
_IFACE = re.compile(r"^\S.*?(\d+\.\d+\.\d+\.\d+)\s+---\s+0x", re.M)
_ROW = re.compile(r"^\s+(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s+\S+", re.M)

def parse_arp(output: str, local_ip: str, network) -> dict[str, str]:
    """{ip: mac} for real neighbours on the adapter that owns local_ip."""
    blocks = _IFACE.split(output)          # ['', ip1, block1, ip2, block2, ...]
    found = {}
    for iface_ip, block in zip(blocks[1::2], blocks[2::2]):
        if iface_ip != local_ip:
            continue
        for ip, mac in _ROW.findall(block):
            addr = ipaddress.ip_address(ip)
            mac = mac.lower()
            if addr not in network or addr in (network.network_address, network.broadcast_address):
                continue
            if mac == "ff-ff-ff-ff-ff-ff" or mac.startswith("01-00-5e"):
                continue
            found[ip] = mac
    return found
```

Both regexes are **(checked)**: on this PC they found 3 interface blocks and 21 rows.

**Sweep.**

```python
def sweep(targets: list[str], on_progress=None) -> set[str]:
    """Ping every target once in parallel; return the IPs that replied."""
    alive, done = set(), 0
    with ThreadPoolExecutor(max_workers=config.SWEEP_WORKERS) as pool:
        futures = {pool.submit(pinger.is_alive, ip, config.SWEEP_TIMEOUT_MS): ip for ip in targets}
        for fut in as_completed(futures):
            done += 1
            if fut.result():
                alive.add(futures[fut])
            if on_progress:
                on_progress(done, len(targets))    # called from this worker thread
    return alive
```

`on_progress` runs in the scanning thread, not the main thread. The view must not touch widgets inside it (Step 1.6 shows how).

**Hostnames.** `socket.gethostbyaddr` has no timeout and can block for seconds on Windows, so run lookups in their own pool and stop waiting after `HOSTNAME_TIMEOUT_S`:

```python
def resolve_hostnames(ips: list[str]) -> dict[str, str]:
    def lookup(ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except OSError:
            return "Unknown"
    pool = ThreadPoolExecutor(max_workers=32)
    futures = {ip: pool.submit(lookup, ip) for ip in ips}
    names = {}
    deadline = time.monotonic() + config.HOSTNAME_TIMEOUT_S
    for ip, fut in futures.items():
        try:
            names[ip] = fut.result(timeout=max(0, deadline - time.monotonic()))
        except TimeoutError:
            names[ip] = "Unknown"
    pool.shutdown(wait=False)      # do not wait for slow lookups
    return names
```

Import `TimeoutError` from `concurrent.futures` for Python 3.10 compatibility.

**`discover(info, on_progress) -> list[Device]`** puts it together:

1. `alive = sweep(netinfo.scan_targets(info), on_progress)`.
2. Run `arp -a` **after** the sweep (the pings populate the ARP cache) and `parse_arp` it.
3. Device IPs = `alive | arp.keys() | {info.local_ip}`.
4. Build a `Device` for each: `mac` from ARP, `replied_icmp = ip in alive`, `is_self`, `is_gateway`, timestamps now.
5. For this PC: `hostname = socket.gethostname()`, `replied_icmp = True`, and its MAC from `psutil.net_if_addrs()` (the `psutil.AF_LINK` entry of the same adapter).
6. `resolve_hostnames` for the rest; if the gateway comes back "Unknown", name it "Gateway".
7. Return sorted by `ipaddress.ip_address(d.ip)`.

A device with an ARP entry but no ping reply is **up but blocking ICMP**. That is the `no-icmp` status; do not show it as offline.

**Tests — `tests/test_discovery.py`**
- `parse_arp` on a fixture with two interfaces, a broadcast row, a multicast row and an address outside the subnet returns only the real neighbours of the right interface. Save yours with `arp -a > tests\fixtures\arp.txt`, then edit the addresses if you do not want real MACs in the submission.
- Empty output returns `{}`.
- `sweep` with `pinger.is_alive` monkeypatched to return `True` for two addresses returns exactly those two and calls `on_progress` once per target.

Live check from a Python prompt:

```python
from netmonitor.core import netinfo, discovery
info = netinfo.get_network_info(); print(info)
import time; t = time.time()
for d in discovery.discover(info): print(d.ip, d.mac, d.hostname, d.replied_icmp)
print(round(time.time() - t, 1), "s")
```

Record the time; target under 15 seconds. If it is slower, raise `SWEEP_WORKERS` to 128.

### Step 1.4: `services.py` — first version

```python
"""The only module the GUI imports. Each function may block; call via run_async."""
from netmonitor.core import netinfo, discovery, pinger

_devices: list = []          # replaced by store.py in Phase 2

def network_info():
    return netinfo.get_network_info()

def scan(on_progress=None):
    global _devices
    _devices = discovery.discover(netinfo.get_network_info(), on_progress)
    return _devices

def run_ping(ip, count=4, timeout_ms=1000):
    return pinger.ping(ip, count, timeout_ms)

def run_ping_many(ips, count=4):
    return pinger.ping_many(ips, count)
```

### Step 1.5: `gui/worker.py` — `run_async`

Worker threads never call Tkinter. They put a callback on a queue; the main thread drains the queue every 50 ms.

```python
"""Runs blocking service calls off the UI thread and returns results on it."""
import queue, threading

_results: queue.Queue = queue.Queue()

def run_async(fn, *args, on_done=None, on_error=None, **kwargs):
    """Run fn(*args, **kwargs) in a thread; call on_done(result) on the UI thread."""
    def task():
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:                     # reported to the view, not swallowed
            _results.put((on_error, exc))
        else:
            _results.put((on_done, result))
    threading.Thread(target=task, daemon=True).start()

def post(callback, value):
    """From any thread: have callback(value) run on the UI thread (progress updates)."""
    _results.put((callback, value))

def start_pump(root, interval_ms=50):
    """Call once from App.__init__. Drains the queue on the UI thread."""
    def pump():
        try:
            while True:
                callback, value = _results.get_nowait()
                if callback:
                    callback(value)
        except queue.Empty:
            pass
        root.after(interval_ms, pump)
    pump()
```

Every view passes an `on_error` that shows the message in a label. A failed call must never leave a button disabled.

### Step 1.6: App shell, theme, and the first two views

**`gui/theme.py`**: colour constants (`GREEN`, `AMBER`, `RED`, `BLUE`, `MUTED`), font tuples, and one function that styles `ttk.Treeview` to match dark mode:

```python
def style_treeview():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b",
                foreground="#e6e6e6", rowheight=28, borderwidth=0)
    s.configure("Treeview.Heading", background="#1f538d", foreground="white", relief="flat")
    s.map("Treeview", background=[("selected", "#1f538d")])
```

**`gui/app.py`**:

1. `ctk.set_appearance_mode("dark")`, `ctk.set_default_color_theme("blue")`, `theme.style_treeview()`, `worker.start_pump(self)`.
2. Grid: column 0 is a fixed-width sidebar `CTkFrame`; column 1 is the content area with `weight=1`.
3. Sidebar: app name label, then one `CTkButton` per view (Dashboard, Devices, Ping, Statistics, Reports, Security).
4. Create each view once as a `CTkFrame` in the same grid cell and keep them in `self.views: dict[str, CTkFrame]`.
5. `show(name, **kwargs)`: `self.views[name].tkraise()`, highlight the sidebar button, then call `view.on_show(**kwargs)` if it exists. `on_show` is how the Ping view receives an IP and how Statistics reloads.
6. Add only Devices and Ping now. Add the other buttons when their views exist.

**`gui/widgets/host_table.py`**: a `CTkFrame` wrapping a `ttk.Treeview` and a scrollbar, reused by Devices, Ping, and Statistics.

- `__init__(parent, columns: list[tuple[key, title, width]])`
- `set_rows(rows: list[dict])`: clear, then insert; use the IP as the item id.
- `selected() -> list[str]`: the selected IPs.
- Clicking a heading sorts by that column; a second click reverses. Sort the `ip` column with `ipaddress.ip_address` as the key, and numeric columns as floats with blanks last.
- `tag_configure("warn", foreground=AMBER)`, `"bad"` red, `"good"` green; `set_rows` accepts a `tag` per row.
- `selectmode="extended"` for multi-select.

**`gui/views/devices.py`**:

1. Top panel with labels: Hostname, Local IP, Subnet mask, Network range (`192.168.1.0/24 (192.168.1.1 – 192.168.1.254)`), Gateway, Usable hosts. If `mask_assumed` or `truncated`, add a muted note saying so. This panel is the "detect local IP" and "display network range" evidence.
2. A row with **Scan network** (`CTkButton`), a `CTkProgressBar`, and a label for `112 / 254`.
3. `HostTable` with columns IP, Hostname, MAC, Status, Tags.
4. **Ping selected** button and a status label for errors.

Scan handler:

```python
def _on_scan(self):
    self.scan_btn.configure(state="disabled")
    self.progress.set(0)
    run_async(services.scan,
              lambda done, total: worker.post(self._on_progress, (done, total)),
              on_done=self._on_scan_done, on_error=self._on_error)

def _on_progress(self, value):
    done, total = value
    self.progress.set(done / total)
    self.count_lbl.configure(text=f"{done} / {total}")
```

`_on_scan_done` fills the table and re-enables the button; `_on_error` shows the message and re-enables the button. Load the top panel in `on_show` with `run_async(services.network_info, ...)`.

Status text per device: "Online" if `replied_icmp`, otherwise "No ICMP reply (host up)". Tags: "This PC", "Gateway", "New".

Double-click a row: `self.app.show("Ping", ip=ip)`. **Ping selected**: `run_async(services.run_ping_many, ips, ...)`, then show the results in a second table or switch to the Ping view.

**`gui/views/ping.py`**:

1. Row: IP `CTkEntry`, count `CTkEntry` (default 4, clamp to 1–20), **Run ping** button.
2. `CTkTextbox` log, read-only (`state="disabled"` except while writing).
3. Result label, coloured by status.
4. `LatencyChart` (Step 1.7).
5. `on_show(ip=None)`: if given, put it in the entry.

Run handler: validate first so a bad IP never starts a thread.

```python
def _on_run(self):
    try:
        ip = pinger_validate(self.ip_entry.get())      # services.validate_ip wrapper
    except ValueError:
        self._show_error("Enter a valid IPv4 address, for example 192.168.1.1")
        return
    self.run_btn.configure(state="disabled")
    self._log(f"Pinging {ip} with {count} packets...")
    run_async(services.run_ping, ip, count, on_done=self._on_result, on_error=self._on_error)
```

Expose `validate_ip` through `services.py` so the view still imports only services.

`_on_result` writes `result.raw_lines` to the log, then the summary line: `Sent 4, Received 3, Lost 1 (25%) · min 2 ms · avg 3.3 ms · max 5 ms`. Colour: green `online`, amber `degraded` or `no-icmp`, red `offline`.

### Step 1.7: `gui/widgets/latency_chart.py`

Use `Figure` directly, never `pyplot`.

```python
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class LatencyChart(ctk.CTkFrame):
    def __init__(self, parent, title=""):
        super().__init__(parent)
        self.fig = Figure(figsize=(6, 2.4), dpi=100, facecolor="#2b2b2b")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.title = title

    def plot_bars(self, labels, values, ylabel="ms"):
        self.ax.clear()
        self.ax.bar(labels, values, color="#3b8ed0")
        self.ax.set_ylabel(ylabel); self.ax.set_title(self.title)
        # style axes for dark mode: facecolor, tick and label colours
        self.fig.tight_layout()
        self.canvas.draw_idle()
```

Add `plot_line(x, y)` for history later. For the Ping view, bars are replies 1..n; show a lost packet as a gap.

**Checkpoint 1 (end of Nov 16)**
- [ ] `pytest` passes for netinfo, pinger and discovery.
- [ ] Devices view shows the correct local IP, mask, range and gateway (compare with `ipconfig`).
- [ ] Scan fills the table with real devices; the progress bar moves; the window drags freely during the scan.
- [ ] Your phone appears after joining the Wi-Fi.
- [ ] Ping to the gateway logs each reply; ping to an unused address shows 100% loss in red.
- [ ] Typing `abc` shows the validation message and the button stays usable.
- [ ] Screenshots of both views saved to `Documentation/screenshots/` for the progress report.

**Nov 17:** write and submit the progress report from this state. Sample code: `parse_rtts` and `sweep`.

---

## Phase 2: Storage and statistics (F3)

### Step 2.1: `store.py` — SQLite

SQLite connections cannot be shared between threads by default, and services run in worker threads. Open a short-lived connection per call.

```python
"""SQLite persistence for devices, ping results, and generated reports."""
import json, sqlite3
from contextlib import contextmanager
from netmonitor import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    ip TEXT PRIMARY KEY, mac TEXT, hostname TEXT,
    replied_icmp INTEGER, is_self INTEGER, is_gateway INTEGER,
    known INTEGER, first_seen TEXT, last_seen TEXT, network TEXT
);
CREATE TABLE IF NOT EXISTS known_macs (network TEXT, mac TEXT, PRIMARY KEY (network, mac));
CREATE TABLE IF NOT EXISTS pings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, method TEXT,
    sent INTEGER, received INTEGER, loss_pct REAL,
    min_ms REAL, avg_ms REAL, max_ms REAL, rtts_json TEXT,
    status TEXT, timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_pings_ip ON pings(ip, timestamp);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, format TEXT, path TEXT
);
"""

@contextmanager
def connect(db_path=None):
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init(db_path=None):
    with connect(db_path) as c:
        c.executescript(SCHEMA)
```

Functions to write (each takes an optional `db_path` so tests use `tmp_path`):

| Function | Behaviour |
|---|---|
| `save_scan(devices, network)` | Replace the device list for `network` (the CIDR string). Keep the original `first_seen` for IPs already stored. Decide `known`: if `known_macs` has no rows for this network, insert every MAC (first scan is the baseline) and mark all known; otherwise `known = mac in known_macs`. Devices with no MAC are treated as known. |
| `get_devices(network=None)` | List of `Device`, sorted by IP numerically in Python. |
| `mark_known(mac, network)` | Insert into `known_macs`; set `known=1` on the device. |
| `save_ping(result)` | Insert one row; `rtts_json = json.dumps(result.rtts_ms)`. |
| `get_pings(ip, limit=None)` | Rows for a host, newest first, as `PingResult`. |
| `latest_ping(ip)` | Newest row or `None`. |
| `save_report(fmt, path)` / `get_reports()` | Report history, newest first. |

Call `store.init()` in `main.py` before creating the window. Write to the database once per scan, after the sweep finishes, never from the sweep's worker threads.

`network` matters: on the hotspot you will get a different device list than at home, and the known-device baseline must not mix them.

**Tests — `tests/test_store.py`** (all with `tmp_path / "t.db"`)
- Save two devices, read them back equal.
- First scan marks all known; a second scan with one new MAC marks only that one unknown; `mark_known` clears it.
- `first_seen` survives a rescan; `last_seen` updates.
- A saved `PingResult` round-trips, including the `rtts_ms` list.

### Step 2.2: Update `services.py`

- `scan`: after `discover`, `store.save_scan(devices, info.cidr)`, then return `store.get_devices(info.cidr)` so `known` is filled in.
- `run_ping` / `run_ping_many`: after pinging, **upgrade the status** and save:

```python
def _finalise(result):
    """A host with 100% loss that still has an ARP entry is up but drops ICMP."""
    if result.status == models.OFFLINE and discovery.has_arp_entry(result.ip):
        result.status = models.NO_ICMP
    store.save_ping(result)
    return result
```

`discovery.has_arp_entry(ip)` runs `arp -a` and checks the parsed table. For `run_ping_many`, read the ARP table once and reuse it for every result. This only works for addresses on your own subnet; a remote address such as 8.8.8.8 with 100% loss stays `offline`, which is correct.

Remove the in-memory `_devices` list.

### Step 2.3: `core/statistics.py`

Concepts: latency, jitter, packet loss, performance baseline.

Pure functions over lists of `PingResult`; no database access here, which keeps them easy to test.

```python
def host_stats(device, results) -> HostStats:
    """Aggregate every stored ICMP result for one host."""
    results = [r for r in results if r.method == "icmp"]
    if not results:
        return HostStats(device.ip, device.hostname, 0, None, None, None, None, None, models.NO_DATA)
    rtts = [t for r in sorted(results, key=lambda r: r.timestamp) for t in r.rtts_ms]
    sent = sum(r.sent for r in results)
    received = sum(r.received for r in results)
    loss = (sent - received) / sent * 100
    ...
```

- **Average / max / min:** over the flattened reply times; `None` if there are none.
- **Loss %:** total lost ÷ total sent across runs. 4/4 and 2/4 received is 2 lost of 8 = 25%.
- **Jitter:** mean of `abs(rtts[i] - rtts[i-1])`; `None` with fewer than two replies. For `[10, 14, 12]` it is `(4 + 2) / 2 = 3.0`.
- **Status:** take the status of the newest result (already upgraded to `no-icmp` where it applies).

`summary(stats) -> NetworkSummary`:

- `devices = len(stats)`
- `unreachable` = count with status `offline`; `reachable = devices - unreachable`. `no-icmp` and `no-data` count as reachable.
- `network_avg_ms` = mean of `avg_ms` over hosts that have one.
- `best_host` / `worst_host` = lowest / highest `avg_ms`.
- **Health score** (state this formula in Chapter 4):

```
score = 100
score -= 50 * (unreachable / devices)
score -= min(30, mean loss % of hosts that have replies)
if network_avg_ms > 50: score -= min(20, (network_avg_ms - 50) / 5)
score = max(0, round(score))
```

With zero devices, return a score of 0 and `None` for the averages.

`history(results, limit=50)`: list of `{timestamp, avg_ms, loss_pct}`, oldest first, for the chart.

Services: `stats()` loads devices and their pings from the store and calls `host_stats` for each; `summary()` calls `summary(stats())`; `history(ip)` reads that host's pings.

**Tests — `tests/test_statistics.py`**
- Known lists give the expected average, max, min, jitter.
- 4/4 + 2/4 gives 25.0% loss.
- No results gives status `no-data` and all `None`, with no exception.
- One reply gives `jitter_ms is None`.
- Health score for three hand-worked cases: all healthy (100); 1 of 4 offline (87.5 → 88, minus any loss term); average 150 ms (minus 20).
- `summary([])` does not raise.

### Step 2.4: `gui/views/statistics.py`

1. **Refresh all** button and a "Last updated" label.
2. `HostTable` with the five required columns first, in the brief's order and wording: **Hostname, IP Address, Average Latency, Maximum Latency, Packet Loss**; then Jitter, Samples, Status.
3. Format: `12.4 ms`, `25.0 %`, and `No data` for `None`. Never print `None` or `0` for missing data.
4. Row tags: red for `offline`, amber when loss > `LOSS_WARN_PCT` or average > `LATENCY_WARN_MS`.
5. Selecting a row loads `services.history(ip)` into a `LatencyChart.plot_line`.
6. `on_show`: reload from the store (fast, but still through `run_async`).

**Refresh all**: `run_async(services.refresh_all, ...)`, where `refresh_all` pings every stored device with `run_ping_many` and then returns `stats()`. Disable the button while it runs. With 15 devices and 16 workers this takes about 4 seconds.

Add the Statistics button to the sidebar.

**Checkpoint 2 (Nov 20)**
- [ ] `pytest` passes for store and statistics.
- [ ] Close and reopen the app: devices and statistics are still there.
- [ ] Statistics shows the five required columns with real values after Refresh all.
- [ ] A Windows PC with its firewall on shows "No ICMP reply (host up)", not offline.
- [ ] Turning a phone's Wi-Fi off and refreshing eventually shows it offline (its ARP entry must expire first; `arp -d *` in an administrator prompt clears it at once for the demo).
- [ ] Selecting a row draws its history.

---

## Phase 3: Reports (F4)

The brief requires four things in the report: **date and time, devices detected, ping results, network performance summary**. Recommendations are added in Phase 4.

### Step 3.1: `core/report_builder.py`

```python
@dataclass
class ReportData:
    generated_at: str
    info: NetworkInfo
    devices: list[Device]
    pings: list[PingResult]        # latest ICMP result per device
    stats: list[HostStats]
    summary: NetworkSummary
    recommendations: list[Recommendation]
```

`services.collect_report_data()` builds it from the store; `report_builder` only renders, so it can be tested with hand-made data.

**HTML** — `templates/report.html` rendered with Jinja2:

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape
env = Environment(loader=FileSystemLoader(config.TEMPLATE_DIR),
                  autoescape=select_autoescape(["html"]))
html = env.get_template("report.html").render(d=data)
```

Template sections, in this order:

1. Header: "Network Monitoring Report", generated date and time, hostname, local IP, network range, gateway.
2. **Devices detected**: count, then a table (IP, hostname, MAC, status).
3. **Ping results**: table (IP, hostname, sent, received, loss %, min, avg, max, time of test).
4. **Network performance summary**: devices, reachable, unreachable, network average latency, best host, worst host, health score.
5. **Security recommendations**: severity, title, action. Hidden with `{% if %}` when the list is empty.

Use inline CSS in a `<style>` block (no external files), a light background so it prints, and `{% if not d.devices %}<p>No devices found.</p>{% endif %}`.

**CSV** — `csv.writer` with `newline=""` and `encoding="utf-8-sig"` so Excel opens it correctly. First two lines: `Generated,<timestamp>` and `Network,<cidr>`; a blank line; then the header `Hostname,IP Address,Average Latency (ms),Maximum Latency (ms),Packet Loss (%),Status` and one row per device.

**PDF** — leave for Phase 5.

`build(data, fmt) -> Path`: make `OUTPUT_DIR`, write `report_YYYYMMDD_HHMMSS.<ext>`, return the path. `services.generate_report(fmt)` collects, builds, calls `store.save_report`, and returns a `ReportMeta`.

**Tests — `tests/test_report.py`** (write into `tmp_path` by passing an output directory)
- HTML contains the timestamp, every device IP, every ping row, and the health score.
- A hostname of `<script>` appears escaped.
- Zero devices renders "No devices found" without error.
- CSV has the expected header and one row per device.

### Step 3.2: `gui/views/reports.py`

1. `CTkSegmentedButton` with HTML, CSV (PDF added in Phase 5) and a **Generate report** button with a busy state.
2. A short line listing what the report contains.
3. `HostTable`-style list of past reports: date, format, file name.
4. **Open** (`os.startfile(path)`) and **Open folder** (`os.startfile(config.OUTPUT_DIR)`). If a listed file was deleted, show a message instead of raising.
5. If there are no devices yet, show "Run a scan first" and still allow generation.

**Checkpoint 3 (Nov 22)**
- [ ] `pytest` passes for reports.
- [ ] Generate HTML: it opens in the browser and shows all four required parts with real data.
- [ ] Generate CSV: it opens in Excel with correct columns.
- [ ] The report list survives a restart.

---

## Phase 4: Security recommendations (F5)

The brief's examples: **weak connectivity alerts, unreachable hosts, basic firewall recommendations, password security reminders**. All four must be visible.

### Step 4.1: `core/advisor.py`

Concepts: firewalls, ports and services, attack surface, wireless security.

Each rule is a function `(ctx) -> list[Recommendation]`. `ctx` is a small dataclass: `devices`, `stats` (dict by IP), `gateway_ip`, `open_ports` (dict IP → list of ports; empty until a port check runs).

```python
def rule_unreachable(ctx):
    out = []
    for d in ctx.devices:
        s = ctx.stats.get(d.ip)
        if s and s.status == models.OFFLINE and not d.is_gateway:
            out.append(Recommendation(
                "warning", "Connectivity", d.ip,
                f"{d.hostname} ({d.ip}) is unreachable",
                "The device did not answer any ping and has no ARP entry.",
                "Check its power and cable or Wi-Fi connection; it may have left the network."))
    return out

RULES = [rule_gateway_down, rule_risky_ports, rule_unreachable, rule_gateway_unstable,
         rule_weak_connectivity, rule_new_device, rule_high_jitter, rule_icmp_blocked,
         rule_firewall_reminder, rule_password_reminder]

_ORDER = {"critical": 0, "warning": 1, "info": 2}

def run_all(ctx):
    recs = [r for rule in RULES for r in rule(ctx)]
    return sorted(recs, key=lambda r: _ORDER[r.severity])    # stable: keeps rule order
```

| Rule | Trigger | Severity | Action text |
|---|---|---|---|
| `rule_gateway_down` | Gateway status `offline` | critical | The whole LAN loses its route out; restart or inspect the router. |
| `rule_risky_ports` | Any port in `RISKY_PORTS` open | critical | Close the service or block the port in the firewall; use SSH or SFTP instead of Telnet or FTP. |
| `rule_unreachable` | Non-gateway device `offline` | warning | Check power, cable or Wi-Fi. |
| `rule_gateway_unstable` | Gateway loss ≥ `GATEWAY_LOSS_WARN_PCT` or average > `LATENCY_WARN_MS` | warning | Every device is affected; check router load and Wi-Fi channel. |
| `rule_weak_connectivity` | Non-gateway host with replies and loss > `LOSS_WARN_PCT` or average > `LATENCY_WARN_MS` | warning | Check signal strength, interference, or a congested link. |
| `rule_new_device` | `known == False` | warning | Confirm it belongs on the network; change the Wi-Fi password if not. Note that phones with randomized MAC addresses can appear as new. |
| `rule_high_jitter` | Jitter > `JITTER_WARN_MS` | info | Expect poor voice and video quality. |
| `rule_icmp_blocked` | Status `no-icmp` | info | The device is up and its firewall drops ping; normal for Windows PCs. No action needed. |
| `rule_firewall_reminder` | Always | info | Keep the OS firewall on and block unused inbound ports. |
| `rule_password_reminder` | Always | info | Change the default router password; use WPA2 or WPA3 with a passphrase of 12 or more characters. |

The two gateway rules must not both fire, and gateway problems must not repeat as "weak connectivity" for the same host.

`services.recommendations()` builds the context from the store and returns `run_all(ctx)`. Keep port results in a module-level dict in services so they persist for the session. Now add recommendations to `collect_report_data`.

**Tests — `tests/test_advisor.py`**
- For every rule: one crafted context where it fires, one healthy context where it returns `[]`.
- Gateway offline gives exactly one critical item and no "unstable" or "weak" item for the gateway.
- `run_all` returns criticals before warnings before info.
- A healthy network returns exactly the two reminders.

### Step 4.2: `gui/widgets/recommendation_card.py` and `gui/views/security.py`

Card: a `CTkFrame` with a 4-pixel coloured strip on the left (red, amber, blue), a bold title, the host, the detail text, and the action prefixed "Recommended:". Use `wraplength` on labels so long text wraps.

View:

1. Summary row: `2 critical · 3 warnings · 4 info`.
2. `CTkScrollableFrame` holding the cards. On reload, destroy the old cards and build new ones.
3. `on_show` reloads through `run_async`.
4. For new devices, a **Mark as known** button on the card that calls `services.mark_known(mac)` and reloads.

**Checkpoint 4 (Nov 24)**
- [ ] `pytest` passes for advisor; the whole suite is green.
- [ ] Security view shows the firewall and password reminders on a healthy network.
- [ ] An offline device produces an "unreachable" warning; a slow or lossy one produces "weak connectivity".
- [ ] A device joining after the first scan is flagged as new; Mark as known clears it.
- [ ] The HTML report now includes the recommendations.

All five required features work at this point. Everything after this is bonus or polish.

---

## Phase 5: Foundations

Everything later builds on these four steps: the network id changes the database, roles decide which buttons each later step enables, and the device panel is where later actions are wired.

### Step 5.1: Clean-up, network identity, new tables

**Files:** `gui/views/devices.py`, `store.py`, `services.py`, `models.py`, `tests/test_store.py`.

1. **Remove the dead `on_show`.** `devices.py` defines `on_show` twice (lines 48 and 60). Python keeps the second definition, so delete the first one (the three lines starting at line 48).

2. **New tables.** Extend `SCHEMA` in `store.py` (still `CREATE TABLE IF NOT EXISTS`, so nothing else changes):

```python
DEVICE_COLUMNS = "network, ip, mac, hostname, alias, replied_icmp, is_self, is_gateway, known, first_seen, last_seen"
PING_COLUMNS = "network, ip, sent, received, loss_pct, rtts_ms, min_ms, avg_ms, max_ms, status, method, timestamp"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS devices ({DEVICE_COLUMNS}, PRIMARY KEY (network, ip));
CREATE TABLE IF NOT EXISTS known_macs (network, mac, PRIMARY KEY (network, mac));
CREATE TABLE IF NOT EXISTS pings (id INTEGER PRIMARY KEY, {PING_COLUMNS});
CREATE INDEX IF NOT EXISTS pings_by_ip ON pings (network, ip);
CREATE TABLE IF NOT EXISTS users (username PRIMARY KEY, salt BLOB, hash BLOB, role);
CREATE TABLE IF NOT EXISTS port_checks (network, ip, checked_at, open_ports, PRIMARY KEY (network, ip));
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, network, at, kind, severity, ip, mac, detail,
                                   dismissed DEFAULT 0);
CREATE TABLE IF NOT EXISTS presence (network, mac, at, up);
CREATE TABLE IF NOT EXISTS usage (day PRIMARY KEY, bytes_recv DEFAULT 0, bytes_sent DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings (key PRIMARY KEY, value);
"""
```

   `Device` gains `alias: str = ""`. The upsert in `save_scan` must **not** overwrite `alias` (leave it out of the `DO UPDATE SET` list, like `first_seen`).

3. **Network id.** In `services.py`:

```python
def _network_id(info=None) -> str:
    """CIDR plus the gateway's MAC, so two networks that both use 192.168.1.0/24 stay separate."""
    info = info or netinfo.get_network_info()
    network = ipaddress.ip_network(info.cidr)
    macs = discovery.read_arp(info.local_ip, network)
    if info.gateway and info.gateway not in macs:      # ARP cache may be empty right after connecting
        pinger.is_alive(info.gateway)
        macs = discovery.read_arp(info.local_ip, network)
    return f"{info.cidr} via {macs.get(info.gateway, 'no gateway')}"
```

   Use it everywhere a CIDR was used as the key: `scan`, `_devices`, `generate_report`, `mark_known`. `store.save_ping(result, network)` and `store.get_pings(ip, network)` take the id; `_record` passes it. `save_ping` adds `"network": network` to `asdict(result)`. `get_pings` must drop the `network` key before building `PingResult(**...)`, the way `get_devices` already drops it for `Device`. Delete the `# shortcut:` comment in `_stats`, because it no longer applies.

4. **Delete `data/netmonitor.db`.** The columns changed and the data is development data.

**Tests:** update the existing store tests to the new signatures; add one test where two networks with the same CIDR but different ids keep separate devices and separate pings.

### Step 5.2: `core/auth.py` and the users table

Concept: authentication (who you are) vs authorization (what you may do); salted, deliberately slow hashing.

`config.py`:

```python
# --- Accounts and roles -----------------------------------------------------
AUTH_ITERATIONS = 600_000     # PBKDF2-SHA256 rounds (OWASP guidance); about 0.2 s on this PC
PASSWORD_MIN_LEN = 8
LOGIN_MAX_FAILURES = 5        # wrong passwords in a row before sign-in pauses
LOGIN_LOCK_S = 30
ADMIN, USER = "admin", "user"
```

`core/auth.py` **(checked)**:

```python
"""Accounts: salted PBKDF2 password hashes. Passwords are never stored or logged as text."""
import hashlib
import hmac
import os

from netmonitor import config


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Return (salt, hash). A new random salt makes two equal passwords hash differently."""
    salt = salt or os.urandom(16)
    return salt, hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, config.AUTH_ITERATIONS)


def verify_password(password: str, salt: bytes, digest: bytes) -> bool:
    """compare_digest takes the same time wherever the bytes differ, so timing reveals nothing."""
    return hmac.compare_digest(hash_password(password, salt)[1], digest)


def check_new_password(username: str, password: str, confirm: str):
    """Raise ValueError with a message for the form if the new password is not acceptable."""
    ...  # at least PASSWORD_MIN_LEN, not equal to the username, matches confirm
```

`models.py`: `User(username: str, role: str)` with a property `is_admin`.

`store.py`: `add_user(username, salt, digest, role)`, `get_user(username)` (row or None), `list_users()`, `set_password(username, salt, digest)`, `set_role(username, role)`, `delete_user(username)`, `count_admins()`.

`services.py`:

```python
_user = None                      # the signed-in models.User
_failures, _locked_until = 0, 0.0

def needs_setup() -> bool: ...                  # True when the users table is empty
def create_first_admin(username, password, confirm) -> User: ...   # only while needs_setup()
def login(username, password) -> User:
    """Raises ValueError("Wrong username or password.") or ("Too many attempts. Wait N s.")."""
def logout(): ...                               # also calls stop_all() (Step 7.2)
def current_user() -> User | None: ...
def require_admin():
    if not (_user and _user.is_admin):
        raise PermissionError("Only an administrator can do this.")
```

Give the same message for an unknown username and a wrong password, so the form does not reveal which usernames exist.

User management (`users`, `add_user`, `reset_password`, `delete_user`, `set_role`) each call `require_admin()` first. `delete_user` and `set_role` refuse to remove the last admin.

**Tests (`tests/test_auth.py`):** round trip; wrong password fails; same password twice gives different hashes; `check_new_password` rejects short, equal-to-username and mismatched passwords; with a User signed in, `require_admin()` raises `PermissionError`; the last admin cannot be deleted; the sixth attempt inside 30 s is refused even with the right password. Point `config.DB_PATH` at `tmp_path` in a fixture, as the store tests already do.

### Step 5.3: Sign-in screen, roles in the window, Admin view

**`gui/views/login.py`:** a centred card. With no users it says "Create the administrator account" and shows username, password and confirm. Otherwise it shows username and password. Enter submits. Sign-in goes through `run_async` because hashing takes about 0.2 s. Errors appear in red under the form.

**`gui/app.py`** changes shape: the window starts with the login view; the sidebar and views are built only after sign-in, so a User's window never contains admin-only views.

```python
class App(ctk.CTk):
    def __init__(self):
        ...                                    # theme, pump, title, size as now
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.main = None
        self.login = LoginView(self, on_success=self.start)
        self.login.grid(row=0, column=0, columnspan=2, sticky="nsew")

    def start(self, user):
        """Build the top bar, sidebar and the views this user may open."""
        self.user = user
        self.login.grid_remove()
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        ...                                    # top bar: "Signed in as ... (Admin) · Sign out"
        views = VIEWS + ([("Admin", AdminView)] if user.is_admin else [])
        ...                                    # the existing sidebar loop, inside self.main

    @property
    def is_admin(self):
        return self.user.is_admin

    def sign_out(self):
        services.logout()                      # stops child processes and watch mode
        self.main.destroy()
        self.login.reset()
        self.login.grid()

    def close(self):
        services.stop_all()                    # no ping.exe or tracert.exe may outlive the window
        self.destroy()
```

Add `def stop_all(): pass` to services now so `close()` and `logout()` can call it. Step 7.2 fills it in.

**Admin-only buttons:** each view checks `self.app.is_admin` once when it is built. For a User the button is created with `state="disabled"` and its text ends in "(Admin)", for example "Scan network (Admin)". In services, add `require_admin()` as the first line of `scan`, `mark_known` and `scan_and_refresh`. The Dashboard's "Scan and refresh" becomes "Refresh" for a User and calls `refresh_all`.

**`gui/views/admin.py`:** a `CTkTabview` with two tabs.
- *Users*: a table of username and role, plus Add user (username, password, confirm, role), Reset password, Change role, Delete. Error messages come from services.
- *Settings*: entries for the bandwidth limits and the watch interval (both filled in later steps), Save, and **Clear history for this network** behind `tkinter.messagebox.askyesno`.

`store.get_settings()` returns a dict, and `services.settings()` merges it over the defaults in `config.py`, so a missing key always has a value.

**Checkpoint (R-1, R-2, R-3):** first run shows the setup form; an Admin sees Admin in the sidebar and enabled Scan; a User sees neither; five wrong passwords lock sign-in for 30 seconds.

### Step 5.4: Device panel

**`models.py`:**

```python
@dataclass
class DeviceDetail:
    """Everything the device panel shows, gathered in one service call."""
    device: Device
    stats: HostStats
    vendor: str = "Unknown"                 # Step 6.1
    history: list = field(default_factory=list)     # last 10 PingResults
    open_ports: list | None = None          # Step 6.3; None = never checked
    uptime_pct: float | None = None         # Step 7.6
    presence: list = field(default_factory=list)    # Step 7.6
```

`services.device_detail(ip)` fills what exists today; later steps fill the rest. `services.set_alias(ip, name)` (admin) stores the alias by network and MAC.

**`gui/widgets/device_panel.py`:** a `CTkToplevel` with:
1. A header with the name (alias if set), IP, MAC and tags, and under it the verdict line, coloured by status ("Online · normal latency").
2. Four stat tiles (average, maximum, loss, jitter), first and last seen, and the history as a `LatencyChart`.
3. An action row: **Ping** (result shown in the panel), **Mark as known** (Admin), **Rename** (Admin, `ctk.CTkInputDialog`). Later steps add Continuous ping, Traceroute and Check ports.
4. A `show(ip)` method that reloads through `run_async`.

In `app.py`:

```python
def open_device(self, ip):
    """One panel for the whole app: reuse it if it is open, otherwise create it."""
    if self.panel is None or not self.panel.winfo_exists():
        self.panel = DevicePanel(self, self)
    self.panel.show(ip)
    self.panel.lift()
    self.panel.focus()
```

**Wire every place a device appears:**
- Devices, Statistics and the Ping batch table: double-click a row → `app.open_device(row)`. The Devices view keeps **Ping selected** for batch pings.
- Security cards that have a host: an **Open device** button (give `RecommendationCard` an optional `on_open`).
- Dashboard bars: make bars clickable in `LatencyChart`.

```python
# in __init__, after the canvas is created and before the first plot():
self._bars, self._on_pick = [], None
self.canvas.mpl_connect("pick_event", self._picked)        # connect once; plot() only swaps the bars

def plot(self, labels, values, title, on_pick=None):
    self.axes.clear()
    self._bars = list(self.axes.bar(labels, values, color=theme.BLUE, picker=True))
    self._on_pick = on_pick
    ...                                                     # title, colours, draw_idle as now

def _picked(self, event):
    """A bar was clicked: tell the view its index in the plotted list."""
    if self._on_pick and event.artist in self._bars:
        self._on_pick(self._bars.index(event.artist))
```

The Dashboard passes `on_pick=lambda i: app.open_device(ips[i])`, where `ips` is the list it plotted, in the same order.

**Tests:** `device_detail` for a device with no pings returns `NO_DATA` stats and an empty history.

**Checkpoint 5 (Nov 21)**
- [ ] `pytest` green, including `test_auth.py` and the two-network store test.
- [ ] Admin and User windows differ as in the permissions table (plan v3, section 9).
- [ ] Double-clicking a device in Devices, Statistics and Ping, and clicking a Dashboard bar, opens the same panel.

---

## Phase 6: Conclusive diagnostics

### Step 6.1: MAC vendor and randomized MAC (`core/vendor.py`)

Concept: the IEEE OUI registry; the universal/local bit of a MAC address.

1. Download `https://standards-oui.ieee.org/oui/oui.csv` once and save it as `netmonitor/resources/oui.csv`. Its columns are `Registry, Assignment, Organization Name, Organization Address`; `Assignment` is six hex digits.
2. `config.OUI_PATH = Path(__file__).resolve().parent / "resources" / "oui.csv"`.

```python
"""Feature 1 extension: who made a device, from the first three bytes of its MAC address."""
import csv
from functools import cache

from netmonitor import config

PRIVATE = "Private (randomized MAC)"


@cache                                      # read the 30,000-row file once, on first use
def _registry() -> dict[str, str]:
    try:
        with open(config.OUI_PATH, newline="", encoding="utf-8", errors="replace") as file:
            return {row["Assignment"].upper(): row["Organization Name"] for row in csv.DictReader(file)}
    except FileNotFoundError:
        return {}


def is_randomized(mac: str) -> bool:
    """True when the locally administered bit (0x02) of the first byte is set. (checked)"""
    return bool(int(mac[1], 16) & 0b10)


def vendor(mac: str | None) -> str:
    if not mac:
        return "Unknown"
    if is_randomized(mac):
        return PRIVATE
    return _registry().get(mac.replace("-", "").upper()[:6], "Unknown vendor")
```

3. Show it as a **Vendor** column in Devices, in the device panel (`DeviceDetail.vendor`), and in the HTML report.
4. In `advisor.py`, the New-device detail says "This device uses a randomized MAC address, so it can appear new on every network." when `is_randomized` is true.

**Tests:** `a4-2b-b0-…` with a one-row fake registry → its name; `da-a1-19-…` → `PRIVATE`; `None` → "Unknown"; a missing file → "Unknown vendor". Point `config.OUI_PATH` at a two-line CSV in `tmp_path`, and call `_registry.cache_clear()` in the fixture.

### Step 6.2: ARP spoofing rules (`core/advisor.py`)

Concept: ARP has no authentication (RFC 826), so any host can claim any IP.

`recommend()` gains two keyword arguments with defaults, so existing calls and tests keep working: `arp: dict[str, str] | None = None` (the live `{ip: mac}` table) and `gateway: str | None = None`.

```python
def _arp_findings(arp, gateway, add):
    """One MAC answering for several IPs. If one of them is the gateway, that is what ARP poisoning looks like."""
    owners = {}
    for ip, mac in arp.items():
        owners.setdefault(mac, []).append(ip)
    for mac, ips in owners.items():
        if len(ips) < 2:
            continue
        ips = sorted(ips, key=ipaddress.ip_address)
        if gateway in ips:
            add("critical", "ARP spoofing", None, f"Possible ARP spoofing: the gateway shares MAC {mac}",
                f"{', '.join(ips)} all answer with the same MAC address. Traffic to the internet may be "
                "passing through another device (a man-in-the-middle).",
                "Disconnect unknown devices, restart the router, and change the Wi-Fi password.")
        else:
            add("warning", "ARP", None, f"{len(ips)} addresses share MAC {mac}",
                f"{', '.join(ips)} answer with one MAC. A Wi-Fi extender or a PC with two addresses does this harmlessly.",
                "Check that you recognise this device.")
```

In services, `dashboard()` and `generate_report()` pass `arp=discovery.read_arp(...)` and `gateway=info.gateway`. Always use the **live** table: stored devices keep old IPs after DHCP reassigns them and would raise false alarms.

**Tests:** a gateway duplicate → one critical; a non-gateway duplicate → one warning; a clean table → nothing new.

**Live test (A-1, own PC only, Administrator PowerShell):** copy the gateway's MAC from `arp -a`, then
`netsh interface ipv4 add neighbors "Wi-Fi" 192.168.1.250 aa-bb-cc-dd-ee-ff` (an unused address and the gateway's MAC). Open Security and confirm the critical finding. Remove it with `netsh interface ipv4 delete neighbors "Wi-Fi" 192.168.1.250`.

### Step 6.3: Port check (bonus: Port Scanner)

This is the code designed in the old Step 5.4. Put `check_ports` in `core/advisor.py` or a new `core/ports.py`:

```python
def check_ports(ip, ports=config.COMMON_PORTS) -> list[dict]:
    """TCP connect scan of a few common ports on one host."""
    ip = pinger.validate_ip(ip)
    def probe(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(config.PORT_TIMEOUT_S)
            return port if s.connect_ex((ip, port)) == 0 else None
    with ThreadPoolExecutor(max_workers=len(ports)) as pool:
        open_ports = [p for p in pool.map(probe, ports) if p]
    return [{"port": p, "service": ports[p], "risk": "high" if p in config.RISKY_PORTS else "normal"}
            for p in open_ports]
```

`connect_ex` returns 0 only when the handshake completes; closed and filtered ports both return non-zero within the 0.5 s timeout.

- `services.check_ports(ip)` calls `require_admin()`, runs the check, and stores the result in `port_checks` (JSON list) for this network.
- `recommend()` gains `ports: dict[str, list] | None = None`. Any risky port → **critical**: "Risky port open on …: Telnet (23)". Port 80 open on the gateway → **info**: "The router's admin page uses unencrypted HTTP."
- Device panel: a **Check ports** button (Admin) and an "Open ports" list. The panel shows the visible line "Only check devices on a network you own or administer." Repeat it in the README.

**Tests:** start a listening socket on `127.0.0.1` on a free port, then pass `ports={that_port: "test"}`; the risky-port rule fires on a stored result.

### Step 6.4: Traceroute (`core/tracer.py`)

Concept: TTL; each router that decrements the TTL to 0 returns ICMP Time Exceeded (type 11), which reveals one hop at a time.

`config.py`: `TRACE_MAX_HOPS = 15`, `TRACE_TIMEOUT_MS = 500`, `TRACE_JUMP_MS = 30`.

`models.py`: `Hop(number: int, times_ms: list[float | None], address: str | None)` with properties `loss_pct` and `avg_ms` (None when all three are lost).

Parser **(checked against real `tracert` output, Nov 20)**:

```python
# "  1    <1 ms     2 ms     1 ms  192.168.1.1"   and   "  2     *        *        *     Request timed out."
_HOP = re.compile(r"^\s*(\d+)\s+(<?\d+ ms|\*)\s+(<?\d+ ms|\*)\s+(<?\d+ ms|\*)\s+(\S+)")

def parse_hop(line: str) -> Hop | None:
    """One line of tracert output as a Hop, or None for headers and blank lines."""
    found = _HOP.match(line)
    if not found:
        return None
    times = [None if t == "*" else 0.5 if t.startswith("<") else float(t.split()[0]) for t in found.group(2, 3, 4)]
    try:
        address = str(ipaddress.IPv4Address(found.group(5)))
    except ValueError:                       # "Request timed out."
        address = None
    return Hop(int(found.group(1)), times, address)
```

Running it: the same pattern as continuous ping (Step 7.2). A `Traceroute` class starts `["tracert", "-d", "-h", str(TRACE_MAX_HOPS), "-w", str(TRACE_TIMEOUT_MS), ip]` with `subprocess.Popen(..., stdout=PIPE, text=True, creationflags=NO_WINDOW)`, reads lines in a thread, calls `on_hop(hop)` for each parsed hop and `on_done(hops)` when tracert exits, and has a `stop()`. `-d` skips reverse DNS, which would make every hop slower. `services.start_traceroute(target, on_hop, on_done)` resolves a name to an IP, starts it, registers the handle so `stop_all()` reaches it, and passes `on_done` the hops and the verdict from `analyse`. Building Step 6.4 before Step 7.2 is fine: create `_running` and fill in `stop_all` here, and Step 7.2 adds continuous ping to them.

Segments and verdict, as pure functions with tests:

```python
CGNAT = ipaddress.ip_network("100.64.0.0/10")      # ISP shared space; is_private is False for it

def segment(hop) -> str:
    if hop.number == 1:
        return "your router"
    if hop.address is None:
        return "unknown"
    address = ipaddress.ip_address(hop.address)
    return "ISP access network" if address.is_private or address in CGNAT else "internet"
```

`analyse(hops, target) -> (status, sentence)`:
- The target was not reached → amber: "The route stops after hop N (segment)."
- Otherwise, find the hop with the largest rise in average latency over the previous answering hop. Count it only if the final hop is still at least that high, since a rise that later disappears is a router answering slowly, not delay on the path. A rise above `TRACE_JUMP_MS` is amber; otherwise green.
- Ignore loss at a middle hop when the final hop has none. Routers rate-limit their replies to traceroute, and this is the most common way people misread a trace.

**Ping view:** a `CTkTabview` with tabs **Ping** (what exists) and **Traceroute**. The Traceroute tab has a target entry (IP or name; resolve a name with `socket.gethostbyname` in the service), Trace/Stop, a hop table (hop, three times, address, segment, loss) filled as hops arrive, a bar chart of average latency per hop, and the verdict line. Add a **Traceroute** button to the device panel.

**Tests:** save `tracert -d 1.1.1.1 > tests\fixtures\tracert_ok.txt` and a run to an unused public address (all timeouts). Parse all hops; segment for 192.168.x, 100.64.x and public addresses; `analyse` for reached / not reached / middle-hop loss ignored / big rise flagged.

### Step 6.5: Network diagnosis and the verdict card (`core/diagnosis.py`)

Concept: troubleshoot one layer at a time; DNS is a UDP request and response.

`config.py`:

```python
# --- Diagnosis ----------------------------------------------------------------
DIAG_PINGS = 10
INTERNET_TARGETS = ("1.1.1.1", "8.8.8.8")
DNS_TEST_NAME = "example.com"
DNS_TIMEOUT_S = 2
GATEWAY_SLOW_MS = 50          # a router this slow to answer means a poor Wi-Fi/LAN link
INTERNET_SLOW_MS = 150
DNS_SLOW_MS = 300
```

DNS query over UDP **(checked against the router and 1.1.1.1, Nov 20)**:

```python
def build_query(name: str, query_id: int) -> bytes:
    """A DNS query for name's A record (RFC 1035): a 12-byte header, then one question."""
    header = struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0)   # flags 0x0100 = recursion desired
    question = b"".join(bytes([len(part)]) + part.encode("ascii") for part in name.split(".")) + b"\0"
    return header + question + struct.pack(">HH", 1, 1)            # type A, class IN


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
    if len(reply) < 12:
        return None
    reply_id, flags, _, answers = struct.unpack(">HHHH", reply[:8])
    # Same ID, rcode 0 (no error) and at least one answer, or it is not our answer.
    return round(elapsed, 1) if reply_id == query_id and flags & 0x000F == 0 and answers > 0 else None
```

The PC's DNS servers, by adapter name (`netinfo.get_adapter(local_ip)`: the same `psutil.net_if_addrs()` loop as `get_netmask`, but it returns the name):

```python
def dns_servers(adapter: str) -> list[str]:
    alias = adapter.replace("'", "''")         # quote safely inside the PowerShell string
    output = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-DnsClientServerAddress -AddressFamily IPv4 -InterfaceAlias '{alias}').ServerAddresses"],
        capture_output=True, text=True, timeout=10, creationflags=pinger.NO_WINDOW).stdout
    return [line.strip() for line in output.splitlines() if line.strip()]
```

`models.py`:

```python
@dataclass
class DiagnosisStep:
    name: str                # "Adapter", "Wi-Fi link", "Router", "Internet", "DNS"
    ok: bool | None          # None = skipped
    detail: str              # "0% loss, 3 ms average"

@dataclass
class Verdict:
    status: str              # "good", "warn", "bad"  (the theme.TAG_COLORS keys)
    where: str               # "This PC", "Wi-Fi / LAN", "Router", "ISP", "DNS", "None"
    headline: str
    evidence: list[str]
    action: str
    layer: str               # "1–2", "3", "7"
    steps: list = field(default_factory=list)
```

`diagnosis.verdict(m)` is a list of rules over a `Measurements` record (local_ip, wifi, gateway PingResult, best internet PingResult, dns_ms for the PC's server, dns_public_ms). The **first match wins**:

| # | Condition | Verdict |
|---|---|---|
| 1 | no local IP | bad · This PC · "Not connected to a network." |
| 2 | local IP starts 169.254. | bad · Router · "Connected, but the router gave no address (DHCP failed)." |
| 3 | gateway 100% loss | bad · Wi-Fi / LAN · "This PC cannot reach the router." (+ weak signal if below 40%) |
| 4 | gateway loss > LOSS_WARN_PCT or avg > GATEWAY_SLOW_MS or jitter > JITTER_WARN_MS | warn · Wi-Fi / LAN · "The link to your router is unstable." |
| 5 | internet 100% loss | bad · ISP · "Your router is fine, but the internet connection is down (ISP or modem)." |
| 6 | internet loss > LOSS_WARN_PCT or avg > INTERNET_SLOW_MS | warn · ISP · "The internet connection is slow beyond your router." |
| 7 | dns_ms is None and dns_public_ms is not None | bad · DNS · "DNS problem: your DNS server did not answer; 1.1.1.1 did. Change DNS to 1.1.1.1." |
| 8 | dns_ms is None and dns_public_ms is None | bad · DNS · "No DNS server answers; websites will not open by name." |
| 9 | dns_ms > DNS_SLOW_MS | warn · DNS · "DNS is slow (… ms); pages will start slowly." |
| 10 | otherwise | good · None · "Your network is healthy." with all the numbers |

Every verdict's `evidence` quotes the measured numbers, so it can be checked.

`services.diagnose(on_step)` runs the steps in order and calls `on_step(DiagnosisStep)` after each, so the card fills in live. It pings the two internet targets in parallel (`pinger.ping_many`) and keeps the better result. It stores the verdict in `_last_verdict` for the report (Step 8.2).

**`gui/widgets/verdict_card.py`:** a wide card at the top of the Dashboard with a coloured left strip, the headline in large type, the five steps with ✓, ✗ or – and their detail, then "Recommended: …". The **Diagnose network** button (both roles) runs `diagnose` through `run_async`, with `post` for each step.

**Tests (`tests/test_diagnosis.py`):** one `Measurements` per rule row, asserting `where` and `status`; `build_query("example.com", 0x1234)` equals the known bytes `12 34 01 00 00 01 00 00 00 00 00 00 07 example 03 com 00 00 01 00 01`; a crafted reply with the wrong ID → None.

**Checkpoint 6 (Nov 24)**
- [ ] Vendor column filled; a phone with a private address shows "Private (randomized MAC)".
- [ ] ARP and port rules pass their tests; A-1 and P-1 work live.
- [ ] A trace to 1.1.1.1 ends in a verdict naming a hop.
- [ ] Diagnose on the home network gives a green verdict with numbers. With the hotspot's mobile data off, it says the router is fine and the internet is down.

---

## Phase 7: Real-time monitoring

### Step 7.1: Events and the alert bar

`models.py`: `Event(id, at, kind, severity, ip, mac, detail, dismissed=False)`.

`store.py`: `add_event(network, event)`, `get_events(network, limit=20, include_dismissed=False)`, `dismiss_event(id)`.

`services.py`: `record_event(kind, severity, ip, mac, detail)` stores the event and returns it; `events(limit)`; `dismiss(id)`.

**`gui/widgets/alert_bar.py`:** a slim coloured frame across the top of the main area, hidden while there is nothing to show. `show(event)` displays the detail, a **View** button (only when the event has an IP; opens the device panel) and **Dismiss**. Newer alerts replace older ones; dismissed ones stay in the list.

The Dashboard gains a "Recent alerts" box with the last five events. Clicking one opens the device panel.

### Step 7.2: Continuous ping with the ECG chart

Concept: ICMP echo over time; jitter; outage length.

`config.py`: `ECG_WINDOW = 60` (replies on screen), `LOG_MAX_LINES = 500`.

**Line parser and child process (checked, Nov 20):** `ping -t` through a pipe gives one line per reply, about one second apart; `terminate()` ends it.

```python
_LOST = ("Request timed out", "Reply from", "General failure", "PING: transmit failed",
         "Destination host unreachable")

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
```

**`PingSession`** (pure, in `pinger.py`): `add(rtt)`, and properties `sent`, `received`, `loss_pct`, `min/avg/max`, `jitter` (same formula as statistics), `current_outage` and `longest_outage` (the longest run of `None`, in replies ≈ seconds, with the time it started), and `spikes` (Step 7.4). `result()` returns a `PingResult` built with the existing `build_result(ip, sent, replies)`, so a stored session looks like any other test. `verdict()` returns the sentence for Stop.

**Services:**

```python
_running = set()                                  # from Step 6.4: every ContinuousPing and Traceroute handle

def start_continuous_ping(ip, on_reply):
    session = pinger.PingSession(ip)
    def reply(rtt, line):                         # reader thread
        session.add(rtt)
        on_reply(session, rtt, line)
    handle = pinger.ContinuousPing(ip, reply)
    handle.session = session
    _running.add(handle)
    return handle

def stop_continuous_ping(handle):
    handle.stop()
    _running.discard(handle)
    if handle.session.sent:
        _record([handle.session.result()])        # stored like any ping; ARP check included
    return handle.session.verdict()

def stop_all():
    """Stop every child process (continuous pings and traceroutes). Called by sign-out and window close."""
    for handle in list(_running):
        handle.stop()
    _running.clear()
```

A continuous ping stopped by `stop_all` (window closed) is not stored. Only the Stop button stores the session.

`on_reply` runs in the reader thread, so the view passes `lambda s, rtt, line: post(self._on_reply, (s, rtt, line))`.

**`gui/widgets/ecg_chart.py`:**

```python
PAPER, GRID_MAJOR, GRID_MINOR, TRACE = "#0f1712", "#1f3b2b", "#16281e", "#3ddc84"

class EcgChart(ctk.CTkFrame):
    """Reply times drawn like a heart monitor: newest on the right, a gap and a red × for each lost reply."""

    def __init__(self, parent, window=config.ECG_WINDOW):
        super().__init__(parent)
        self.points = deque(maxlen=window)        # (reply number, rtt or None)
        self.figure = Figure(figsize=(5, 2.4), dpi=100, facecolor=PAPER)
        self.axes = self.figure.add_subplot(111, facecolor=PAPER)
        self.axes.minorticks_on()
        self.axes.grid(which="major", color=GRID_MAJOR, linewidth=0.8)
        self.axes.grid(which="minor", color=GRID_MINOR, linewidth=0.4)
        self.axes.tick_params(colors=theme.MUTED)
        self.axes.axhline(config.LATENCY_WARN_MS, color=theme.AMBER, linestyle="--", linewidth=1)
        self.trace, = self.axes.plot([], [], color=TRACE, linewidth=1.6)
        self.head, = self.axes.plot([], [], "o", color=TRACE, markersize=5)
        self.lost, = self.axes.plot([], [], "x", color=theme.RED, markersize=8, markeredgewidth=2)
        self.readout = self.axes.text(0.98, 0.95, "", transform=self.axes.transAxes, ha="right", va="top",
                                      color=TRACE, fontsize=20, family="Consolas")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    def add(self, number, rtt):
        self.points.append((number, rtt))
        xs = [n for n, _ in self.points]
        ys = [math.nan if r is None else r for _, r in self.points]   # NaN breaks the line: a visible gap
        top = max(20, max((r for _, r in self.points if r is not None), default=0) * 1.3)
        self.trace.set_data(xs, ys)
        self.head.set_data(xs[-1:], ys[-1:])
        lost = [n for n, r in self.points if r is None]
        self.lost.set_data(lost, [top * 0.9] * len(lost))
        self.axes.set_xlim(number - self.points.maxlen + 1, number + 1)
        self.axes.set_ylim(0, top)
        self.readout.set_text("LOST" if rtt is None else f"{rtt:g} ms")
        self.readout.set_color(theme.RED if rtt is None else TRACE)
        self.canvas.draw_idle()

    def clear(self): ...
```

**Ping view:**
1. A `CTkSwitch` **Continuous (-t)**. When it is on, the count entry is disabled, the bar chart is swapped for the `EcgChart` (`pack_forget` and `pack`), and **Run ping** reads **Start**.
2. While running, the button reads **Stop** (red), the IP entry is disabled, and a live strip shows sent · received · loss · min/avg/max · jitter · longest outage.
3. Each reply appends one log line; keep at most `LOG_MAX_LINES` by deleting from the top.
4. Stop calls `stop_continuous_ping` through `run_async` (`wait` can take a moment) and shows the verdict in the result line, coloured.
5. Leaving the view does not stop the ping. The sidebar button reads "Ping ●" while it runs.
6. Device panel: **Continuous ping** opens `app.show("Ping", ip=ip, continuous=True)`.

**Tests:** `parse_reply` on every line type (reply, `time<1ms`, Request timed out, Destination host unreachable, General failure, the "Pinging …" header, a blank line); `PingSession` totals and longest outage for `[2, 3, None, None, None, 4]`; a `ContinuousPing("127.0.0.1", …)` run for 3 s gives 3–5 replies and `process.poll()` is not None after `stop()` (checked: 4 replies in 3.2 s).

**Check after every run:** `tasklist /FI "IMAGENAME eq PING.EXE"` must report no tasks, including after closing the window mid-run.

### Step 7.3: Bandwidth monitor and limits (Connection view)

Concept: throughput vs bandwidth vs latency; 1 byte = 8 bits.

`config.py`:

```python
# --- Bandwidth --------------------------------------------------------------
BW_SAMPLE_MS = 1000
BW_SUSTAIN_S = 10             # seconds above a limit before it alerts
BW_SAVE_EVERY_S = 10
BW_WINDOW_S = 120             # seconds shown in the chart
BW_DEFAULTS = {"bw_down_mbps": 0, "bw_up_mbps": 0, "bw_daily_gb": 0}   # 0 = no limit
```

`core/bandwidth.py` **(checked)**:

```python
def read_counters(adapter: str) -> tuple[int, int] | None:
    """(bytes received, bytes sent) since the adapter started, or None if it is gone."""
    counters = psutil.net_io_counters(pernic=True).get(adapter)
    return (counters.bytes_recv, counters.bytes_sent) if counters else None


class Meter:
    """Turns the adapter's byte counters into download and upload rates."""
    def __init__(self):
        self._last = None                         # (bytes_recv, bytes_sent, seconds)

    def update(self, recv: int, sent: int, now: float):
        """(down_mbps, up_mbps, new_recv_bytes, new_sent_bytes), or None for the first sample
        and after a counter reset (an adapter restart makes the counters go backwards)."""
        last, self._last = self._last, (recv, sent, now)
        if last is None or recv < last[0] or sent < last[1] or now <= last[2]:
            return None
        seconds = now - last[2]
        down, up = recv - last[0], sent - last[1]
        return down * 8 / seconds / 1e6, up * 8 / seconds / 1e6, down, up


class LimitAlarm:
    """Fires once when a value stays above its limit for `seconds` samples in a row; re-arms after it drops."""
    def __init__(self, seconds=config.BW_SUSTAIN_S):
        self.seconds, self.run, self.fired = seconds, 0, False

    def update(self, value: float, limit: float) -> bool:
        if not limit or value <= limit:           # a limit of 0 means off
            self.run, self.fired = 0, False
            return False
        self.run += 1
        if self.run >= self.seconds and not self.fired:
            self.fired = True
            return True
        return False


def cap_level(used_bytes: int, cap_gb: float) -> int:
    """0, 80 or 100: the highest daily-cap warning reached."""
    if not cap_gb:
        return 0
    share = used_bytes / (cap_gb * 1e9)
    return 100 if share >= 1 else 80 if share >= 0.8 else 0
```

**Services:** `bandwidth_sample()` reads the counters for `netinfo.get_adapter(local_ip)` (cache the name until the local IP changes), updates the meter and the two alarms, and adds to today's byte counts. It returns a `BandwidthSample(down_mbps, up_mbps, today_bytes, alerts)` (a new record in `models.py`), or None for the first sample. A rate alert or a higher cap level calls `record_event("bandwidth", "warning", …)`. `flush_usage()` adds the unsaved bytes to today's `usage` row. `usage_today()` returns the saved total plus the unsaved part.

**App loop** (in `app.py`, started by `start(user)`, cancelled in `sign_out` with `after_cancel`):

```python
def _sample_bandwidth(self):
    self._bw_job = self.after(config.BW_SAMPLE_MS, self._sample_bandwidth)   # reschedule first, like the pump
    sample = services.bandwidth_sample()     # reads one counter: no network traffic, well under 1 ms
    if sample:
        self.views["Connection"].add_sample(sample)
        for event in sample.alerts:
            self.alert_bar.show(event)
    self._bw_ticks += 1
    if self._bw_ticks % config.BW_SAVE_EVERY_S == 0:
        run_async(services.flush_usage)       # the database write happens off the UI thread
```

**`gui/views/connection.py`:** the top half is Wi-Fi (Step 7.5). The bottom half has:
- A line chart of download (blue) and upload (green) over the last `BW_WINDOW_S` seconds, with each limit as a dashed line of the same colour. Use one `Figure` and `set_data`, as the ECG chart does.
- Tiles for download now, upload now, peak, and today's use against the cap (a `CTkProgressBar`).
- The verdict line, e.g. "Within limits: 12.4 Mbps down (limit 20), 1.1 GB of 5 GB today."
- A note: "Measures this PC only, while NetMonitor is running."

**Admin > Settings:** three entries (download Mbps, upload Mbps, daily GB) saved with `services.save_settings` (admin), which validates that each is a number ≥ 0.

**Tests:** `Meter` with crafted counters (10 Mbps, 1 Mbps), the first sample, a counter reset; `LimitAlarm` fires on the 10th second, once, and re-arms after a drop; limit 0 never fires; `cap_level` at 79%, 80%, 100%.

### Step 7.4: Baseline anomaly detection

Concept: judge a value against that host's own history (mean and standard deviation) instead of one fixed threshold.

`config.py`: `BASELINE_MIN_SAMPLES = 30`, `BASELINE_WINDOW = 300` (most recent replies used), `SPIKE_SIGMAS = 3`, `SPIKE_FLOOR_MS = 20`.

`statistics.py`:

```python
def baseline(rtts: list[float]) -> tuple[float, float] | None:
    """(mean, standard deviation) of a host's recent replies, or None until there are enough."""
    recent = rtts[-config.BASELINE_WINDOW:]
    if len(recent) < config.BASELINE_MIN_SAMPLES:
        return None
    return mean(recent), pstdev(recent)


def is_spike(rtt: float, base: tuple[float, float]) -> bool:
    """Above mean + 3σ, and at least 20 ms above the mean: a LAN host with σ = 0.3 ms
    must not call a 3 ms reply a spike."""
    mu, sigma = base
    return rtt > max(mu + config.SPIKE_SIGMAS * sigma, mu + config.SPIKE_FLOOR_MS)
```

Use it in three places:
1. **Continuous ping:** `start_continuous_ping` loads the host's baseline once; `PingSession.add` counts spikes; `EcgChart` draws spikes as amber dots (a fourth `plot` line, set like `lost`). Before there is a baseline, show "Learning baseline (12/30)" under the chart.
2. **Advisor rule** "Slower than usual": if the host's latest test average is a spike against the baseline of all earlier replies → warning "85 ms against a usual 4 ms." `recommend()` gains `baselines: dict[str, tuple] | None = None`.
3. **Watch mode** (Step 7.6): the gateway ping each tick records an event on a spike.

**Tests:** a steady series has no spike; one large value is a spike; a LAN series (mean 2, σ 0.3) with 5 ms is not a spike because of the floor; 29 samples → None.

### Step 7.5: Wi-Fi details and Wi-Fi security (`core/wifi.py`)

Concept: 802.11 bands and channels, co-channel interference, RSSI, WPA2/WPA3.

`config.py`: `WIFI_WEAK_PCT = 40`.

`models.py`: `WifiInfo(ssid, band, channel, radio, auth, cipher, rx_mbps, tx_mbps, signal_pct, rssi_dbm)` with a `quality` property (Excellent ≥ 80, Good ≥ 60, Fair ≥ 40, Weak below).

Parser **(checked against this PC, Nov 20)**. The labels on this PC are `State, SSID, AP BSSID, Band, Channel, Radio type, Authentication, Cipher, Receive rate (Mbps), Transmit rate (Mbps), Signal, Rssi`:

```python
def parse_fields(output: str) -> dict[str, str]:
    """'Label : value' pairs, first occurrence wins. Values may contain ':' (BSSIDs), so split once."""
    fields = {}
    for line in output.splitlines():
        label, sep, value = line.partition(":")
        if sep and label.strip() and label.strip() not in fields:
            fields[label.strip()] = value.strip()
    return fields


def read() -> WifiInfo | None:
    """This PC's Wi-Fi link, or None when wired or not connected.
    Raises WifiUnavailable(message) when Windows withholds the details (Location permission)."""
    result = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True,
                            timeout=10, creationflags=pinger.NO_WINDOW)
    fields = parse_fields(result.stdout)
    if "State" not in fields and "location" in result.stdout.lower():   # no details, and a Location message
        raise WifiUnavailable("Windows needs Location access to show Wi-Fi details: Settings > Privacy & "
                              "security > Location > Let desktop apps access your location.")
    if fields.get("State") != "connected":
        return None
    signal = int(fields["Signal"].rstrip("%"))
    rssi = int(fields["Rssi"]) if fields.get("Rssi", "").lstrip("-").isdigit() else signal // 2 - 100
    ...
```

Nearby networks (cut first if time is short): `netsh wlan show networks mode=bssid` lists blocks with `SSID n`, `Authentication`, `BSSID n`, `Signal`, `Channel`, `Band` and, on this PC, `Channel Utilization` and `Connected Stations`. Count the BSSIDs per channel. On 2.4 GHz, recommend the least crowded of 1, 6 and 11, the three that do not overlap.

**Rules** (`recommend()` gains `wifi: WifiInfo | None = None`):
- Authentication `Open` → critical "Your Wi-Fi has no password"; `WEP` → critical "WEP can be cracked in minutes"; WPA with cipher TKIP → warning.
- Signal below `WIFI_WEAK_PCT` → warning "Weak Wi-Fi signal (35%, −82 dBm)".
- The existing password reminder now quotes the mode: "This network uses WPA2-Personal. Use a passphrase of 12 or more characters; switch to WPA3 if the router supports it."

**Where it shows:** the top half of the Connection view (link details, the verdict "Excellent signal (93%, −41 dBm) on 5 GHz channel 40, WPA2-Personal", and the nearby-channels bar chart); a Wi-Fi card on the Dashboard; diagnosis step 2.

**Tests:** save `netsh wlan show interfaces > tests\fixtures\wlan_interfaces.txt`, then replace the SSID, BSSID and profile name with placeholders before committing. Also test a disconnected fixture, a fixture without an `Rssi` line (formula used), and the location message (raises `WifiUnavailable`).

### Step 7.6: Watch mode and uptime (`core/watch.py`)

Concept: real-time monitoring by polling. The interval sets how quickly a change is noticed and how much traffic the checks add.

`config.py`: `WATCH_DEFAULT_MIN = 5`, `WATCH_MISSES = 2`.

**(checked)**:

```python
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
```

**Services:** `_watch = WatchState()`, reset by `start_watch()` (admin) and `stop_watch()`. `watch_tick()`:
1. `scan()`.
2. Ping the gateway (`DIAG_PINGS`) and check for a spike (Step 7.4).
3. `_watch.update({d.mac: d.ip for d in found if d.mac}, known_macs, gateway_mac)`.
4. Store each event and a `presence` row (up or down) for every known device. Severities: gateway MAC changed → critical; new device → warning; offline → warning; back online → info.
5. Return the events.

**App loop:** an Admin switch **Watch** with the interval from settings, on the Dashboard and the Devices view. `after(minutes × 60000)` runs `run_async(services.watch_tick)`. A `_watch_busy` flag skips a tick while the previous one runs. Each returned event goes to the alert bar. The switch, sign-out and `close()` cancel the job.

**Uptime:** `services.device_detail` fills `presence` (the last 24 hours) and `uptime_pct` (up checks ÷ all checks). The device panel draws a thin strip with `axes.broken_barh`: one green or red segment from each check to the next.

**Tests:** the WatchState sequence in the snippet above (first check silent; offline only after two misses; back online; new device; gateway MAC change); `uptime_pct` from crafted presence rows.

**Checkpoint 7 (Nov 28)**
- [ ] C-1, C-2: continuous ping draws the ECG, marks lost replies, stores the session, and leaves no `ping.exe`.
- [ ] B-1: a download over a 5 Mbps limit alerts after about 10 s, once.
- [ ] The Wi-Fi card and Connection view show real values; the password reminder quotes the real security mode.
- [ ] W-1: with Watch on at 1 minute, a phone joining raises an alert, and View opens its panel.
- [ ] `pytest` green.

---

## Phase 8: Map, polish, freeze

### Step 8.1: Interactive network map

Concept: logical (layer-3) topology. Every device reaches the internet through the gateway. Switches and access points are invisible without SNMP or LLDP; the map's legend says so.

**Layout (checked):**

```python
def ring_layout(n, cx, cy, radius, per_ring=16, gap=90) -> list[tuple[float, float]]:
    """Positions for n devices on rings around (cx, cy), at most per_ring per ring, starting at the top."""
    points = []
    for i in range(n):
        ring, slot = divmod(i, per_ring)
        on_ring = min(per_ring, n - ring * per_ring)
        angle = -math.pi / 2 + 2 * math.pi * slot / on_ring
        r = radius + ring * gap
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points
```

**`gui/widgets/map_canvas.py`:** a `tk.Canvas` (CustomTkinter has no canvas of its own; set `background` to the theme colour and `highlightthickness=0`).

- `draw(data)`: an "Internet" node at the top, the gateway in the centre, devices from `ring_layout`, and This PC with a thicker outline. Each node is an oval and a label tagged `("node", f"ip:{ip}")`. Each edge from the gateway is a line tagged `f"edge:{ip}"` and drawn first, so nodes sit on top.
- Colours: node fill from `theme.STATUS_TAGS`; edge green below 20 ms, amber up to `LATENCY_WARN_MS`, red above, grey dashed with no data. New devices get a red ring. Risky ports or ARP findings get a "!" badge.
- **One set of mouse handlers on the canvas** decides between dragging a node and panning:

```python
def _press(self, event):
    item = self.find_withtag("current")
    tags = self.gettags(item[0]) if item else ()
    self._drag_ip = next((t[3:] for t in tags if t.startswith("ip:")), None)
    self._start = self._last = (event.x, event.y)
    if self._drag_ip is None:
        self.scan_mark(event.x, event.y)                 # pan the whole canvas

def _motion(self, event):
    if self._drag_ip is None:
        return self.scan_dragto(event.x, event.y, gain=1)
    dx, dy = event.x - self._last[0], event.y - self._last[1]
    self.move(f"ip:{self._drag_ip}", dx, dy)
    x1, y1, x2, y2 = self.coords(f"edge:{self._drag_ip}")
    self.coords(f"edge:{self._drag_ip}", x1, y1, x2 + dx, y2 + dy)   # the gateway end stays put
    self._last = (event.x, event.y)

def _release(self, event):
    moved = abs(event.x - self._start[0]) + abs(event.y - self._start[1])
    if self._drag_ip and moved < 4:                       # a click, not a drag
        self.on_open(self._drag_ip)
```

  Dragging the gateway node needs every edge's gateway end moved instead. Either handle that case, or leave the gateway fixed.
- Hover: `tag_bind("node", "<Enter>")` draws a tooltip (a rectangle and text near the cursor) with name, IP, vendor and average latency; `<Leave>` deletes it.
- Zoom: `<MouseWheel>` → `self.scale("all", event.x, event.y, f, f)` with `f = 1.1` or `1/1.1` from `event.delta`. Text stays the same size, which is acceptable.
- Right-click on a node: a `tk.Menu` with Ping, Continuous ping, Traceroute, and Check ports (disabled for Users).

**`gui/views/map.py`:** a toolbar with Refresh, Scan (Admin), a filter `CTkSegmentedButton` (All · Online · New · Issues) and a legend; the canvas; a footer verdict ("9 devices · 1 new · 0 issues"). `services.map_data()` returns devices, statistics, vendors and the hosts with findings in one call. Add "Map" to `VIEWS` after Devices.

**Tests:** `ring_layout(4, 0, 0, 100)` gives top, right, bottom, left (checked); 20 devices use two rings; the filter function keeps the right devices.

### Step 8.2: Report additions

In `report_builder` and `templates/report.html`:
1. A **Diagnosis** section at the top: the last verdict from `services._last_verdict` with its evidence, or "Diagnosis not run in this session."
2. A **Vendor** column in the device table.
3. **Open ports** for devices that were checked.
4. **Recent alerts**: the last 10 events.
5. The **Wi-Fi** line and today's data use.

The CSV gains Vendor and Open ports columns. Update `test_report.py`: the HTML contains the verdict headline, or the "not run" line when no verdict is passed.

### Step 8.3: Polish for the UI points (10)

The old Step 5.5 list still applies, plus:
- [ ] Every view ends in a coloured verdict line (Devices: "9 devices, 1 new"; Statistics: "Worst host: …"; Reports: "Saved report_….html").
- [ ] Admin-only buttons read "(Admin)" and are disabled for Users; no `PermissionError` text ever reaches a User.
- [ ] The sidebar shows "Ping ●" while a continuous ping runs and "Watch ●" while watch mode is on.
- [ ] Charts are dark-themed alike: the ECG chart, the bandwidth chart, the traceroute bars, the history chart.
- [ ] The window opens at a size where the Map and Connection views fit without scrolling (`WINDOW_SIZE` may need to grow).
- [ ] Closing the window during a continuous ping, a trace, or a watch check leaves no process running.

### Step 8.4: Optional — PDF export (bonus: Export to PDF)

Only if Steps 8.1–8.3 are done before the freeze. Use the reportlab code from the previous revision of this file (git history, old Step 5.2), with the same sections as the HTML including the Diagnosis section. Add PDF to the format selector. Test: the file exists and starts with `%PDF`.

**Checkpoint 8 — feature freeze, Nov 29**
- [ ] One uninterrupted session as Admin: sign in, Diagnose, scan, map, device panel (ping, traceroute, ports), continuous ping, Connection, watch alert, statistics, report, security. No errors.
- [ ] The same session as User: no admin-only action is available anywhere.
- [ ] Full `pytest` run is green.
- [ ] No new features after this point; bug fixes only.

---

## Phase 9: Test evidence

Collected once, used in Chapter 4, the slides and the video. Save everything under `Documentation/`.

### Step 9.1: Unit tests

`pytest -v` in a terminal; screenshot the result. Note the number of tests per module in a small table, now including auth, vendor, tracer, diagnosis, bandwidth, wifi and watch.

### Step 9.2: Functional test table

One row per requirement, run by hand in the app. Rows F1-1 to E-2 are as before:

| ID | Requirement | Steps | Expected | Actual | Pass |
|---|---|---|---|---|---|
| F1-1 | Detect local IP | Open Devices | Matches `ipconfig` | | |
| F1-2 | Display network range | Open Devices | CIDR and host range shown | | |
| F1-3 | List active devices | Scan | Gateway, this PC, phone listed | | |
| F2-1 | Ping selected devices | Select two rows, Ping selected | A result per device | | |
| F2-2 | Display response time | Ping gateway | Per-reply times shown | | |
| F2-3 | Packet loss percentage | Ping unused address | 100% | | |
| F3-1 | Statistics columns | Open Statistics | Five required columns | | |
| F4-1 | Report contents | Generate HTML | Date/time, devices, pings, summary, diagnosis | | |
| F5-1 | Weak connectivity alert | Ping a host with poor signal | Warning shown | | |
| F5-2 | Unreachable host | Disconnect a device, refresh | Warning shown | | |
| F5-3 | Firewall recommendation | Open Security | Reminder shown | | |
| F5-4 | Password reminder | Open Security | Reminder quotes the Wi-Fi security mode | | |
| E-1 | Invalid input | Ping `abc` | Message, no crash | | |
| E-2 | No network | Disable Wi-Fi, Scan | Message, no crash | | |
| R-1 | First run | Start with no database | Create-admin form; no default password | | |
| R-2 | User role | Sign in as a User | No Scan, Check ports, Watch or Admin | | |
| R-3 | Lockout | Five wrong passwords | Sign-in disabled for 30 s | | |
| D-1 | Healthy network | Diagnose | Green verdict with numbers | | |
| D-2 | Internet down | Hotspot with mobile data off, Diagnose | "Router fine, internet down" | | |
| D-3 | No network | Wi-Fi off, Diagnose | "Not connected" | | |
| C-1 | Continuous ping | Start, wait 30 s, Stop | ECG trace; verdict; stored; no ping.exe left | | |
| C-2 | Outage | Phone Wi-Fi off for 5 s during C-1 | Red × markers; longest outage ≈ 5 s | | |
| T-1 | Traceroute | Trace 1.1.1.1 | Hop table; verdict names a hop | | |
| B-1 | Bandwidth limit | Limit 5 Mbps, download a large file | Alert after about 10 s | | |
| W-1 | New device | Watch on (1 min), join a phone | Alert banner; View opens the panel | | |
| A-1 | ARP spoofing | Static neighbour with the gateway's MAC (Step 6.2) | Critical finding | | |
| V-1 | Vendor | Scan | Vendor column; phone shows Private (randomized MAC) | | |
| M-1 | Map | Click a node; drag a node | Panel opens; node and edge move | | |
| P-1 | Port check | Listener on port 23, Check ports on own IP | Critical risky-port finding | | |

For F5-1, walk the phone far from the router or use a deliberately slow target; if nothing on your network is slow enough, lower `LATENCY_WARN_MS` for the test and say so.

### Step 9.3: Two-network comparison

Run the same sequence on home Wi-Fi and on a phone hotspot (join a second device to the hotspot): devices found, scan time, network average latency, loss, health score, diagnosis verdict, Wi-Fi signal. One table, two columns of results. The two networks now keep separate device lists (Step 5.1); show both.

### Step 9.4: Wireshark evidence

1. **ICMP accuracy:** capture with display filter `icmp` while the app pings the gateway with count 10. Record each reply's time from Wireshark next to the app's time; give the mean difference. Expect the app to read slightly higher and rounded to whole milliseconds, because `ping` reports integers.
2. **Traceroute:** filter `icmp.type == 11` during a trace: one Time Exceeded per hop, from the routers in the hop table.
3. **DNS:** filter `dns` during a diagnosis. Select the app's query: the transaction ID matches the reply, and the query asks for example.com, type A.
4. **ARP:** `arp` during a scan. **TCP:** `tcp.flags.syn==1` during a port check.
5. **Continuous ping:** `icmp` while a phone drops off: the requests continue and the replies stop, matching the red × markers.

One screenshot each. Together they illustrate layers 2, 3, 4 and 7 for Chapter 3.

### Step 9.5: Fault tests

- **Unreachable host:** turn a scanned phone's Wi-Fi off, clear ARP (`arp -d *` as administrator), Refresh all. Screenshot the offline row and the warning.
- **ICMP blocked:** a Windows PC with the default firewall. Screenshot the "No ICMP reply (host up)" row and the info card.
- **Risky port:** on this PC run a listener on port 23, then Check ports against your own IP:

```powershell
python -c "import socket; s=socket.socket(); s.bind(('0.0.0.0',23)); s.listen(); input('listening on 23, Enter to stop')"
```

  Windows Firewall may ask for permission; allow it on private networks. Screenshot the critical card.
- **Internet down, router fine (D-2):** on the phone hotspot, turn mobile data off and Diagnose.
- **ARP spoofing (A-1):** Step 6.2's static neighbour. Remove it afterwards.
- **Bandwidth (B-1):** set a 5 Mbps download limit and download a large file (for example a Linux ISO) for 15 s.

**Checkpoint 9 (Nov 30)**
- [ ] Every row of the functional table has an actual result and a screenshot.
- [ ] Wireshark comparison table and the four protocol screenshots complete.
- [ ] Any bug found is fixed and the suite re-run.

---

## Phase 10: Packaging

### Step 10.1: Comment pass

- Module docstring on every file: the feature and the protocol or concept it implements.
- Docstring on every public function.
- Comments where a networking or security decision is made: why the OS summary line is ignored, why ARP is read after the sweep, why the live ARP table and not stored devices feeds the spoofing rule, why middle-hop loss in a trace is ignored, why the spike rule has a 20 ms floor, why `compare_digest`.
- Delete dead code and debugging prints.

### Step 10.2: `README.txt` and `README.md` (top level)

Plain text, in this order:

1. Project title, your name, course, date.
2. One-paragraph description, ending with the diagnosis verdict as the main feature.
3. Requirements: Windows 10 or 11, Python 3.11 or newer.
4. Installation: `cd SourceCode`, `python -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements.txt`.
5. Running: `python main.py`, or double-click `run.bat`. **First run:** create the administrator account; add User accounts in Admin > Users.
6. Features: the five core features, then the v3 features, then the permissions table.
7. Wi-Fi details need Windows Location access for desktop apps on some PCs (where to enable it).
8. Running the tests: `pytest -v`.
9. Folder contents, including `netmonitor/resources/oui.csv` (IEEE MA-L registry, downloaded on the date you downloaded it).
10. Known limitations: Windows only and English `netsh` labels; scans at most a /24; hostnames are not always resolvable; the login protects the app, not its database file; bandwidth is measured for this PC only, while the app runs; the map shows logical topology only; port checks and watch mode are for networks you own or administer.

Update `README.md` the same way, and remove "Two networks with the same address range share one device list" from its limitations.

### Step 10.3: Clean-install test

Copy `SourceCode/` to a new folder **without** `.venv` and `data/*.db`, follow the README exactly, create the admin account, and run a scan and a diagnosis. If you have a second Windows PC, do it there. Fix the README wherever you had to think.

### Step 10.4: Build the zip

1. Delete from `SourceCode/`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.pytest_tmp/`, `build/`, `dist/`, `data/*.db`, and old files in `output/` (keep one sample report). Keep `netmonitor/resources/oui.csv`.
2. Put the slides in `Presentation/` and the video in `VideoDemo/`.
3. Move `Documentation/` out of the folder; it goes to Teams separately.
4. Zip the folder as `LASTNAME_FIRSTNAME_FINALPROJECT.zip`.
5. Unzip it somewhere else and confirm it contains `/SourceCode`, `/Presentation`, `/VideoDemo`, and `README.txt`.

### Step 10.5: Optional `.exe`

Only if everything above is done:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name NetMonitor --collect-all customtkinter --add-data "netmonitor/templates;netmonitor/templates" --add-data "netmonitor/resources;netmonitor/resources" main.py
```

Use `--onedir`, not `--onefile`. In a frozen app `Path(__file__)` points inside the bundle, so `DB_PATH` and `OUTPUT_DIR` would need to move to a writable folder (for example under `%LOCALAPPDATA%`); test this before relying on it. Do not add `pyinstaller` to `requirements.txt`.

**Checkpoint 10 (Dec 3)**
- [ ] The unzipped folder runs from a fresh virtual environment by following README.txt.
- [ ] Zip name and contents match the submission requirements.

---

## Demo-day checklist (Dec 8–10)

- [ ] Rehearse on the exact network you will present on. School Wi-Fi often isolates clients, so a scan may find only the gateway; bring a phone hotspot with a second device joined.
- [ ] Delete `data/netmonitor.db` before the demo, then create the Admin account and one User account (this also shows R-1). Run one scan, Refresh all and one 2-minute continuous ping, so the history charts and baselines are not empty.
- [ ] Set the watch interval to 1 minute and a download limit low enough to cross with one download.
- [ ] Keep Wireshark open with the `icmp` filter ready, and a second capture tab with `dns`.
- [ ] Keep one generated report open as a fallback if the live network misbehaves.
- [ ] After closing the app, `tasklist /FI "IMAGENAME eq PING.EXE"` shows nothing.
- [ ] Be ready to explain: how the local IP is found without sending a packet; why ARP finds devices that ping misses; what `time<1ms` means; how loss and jitter are computed; the health score formula; how the diagnosis decides where the problem is; why middle-hop loss in a traceroute is not a problem; what a DNS query looks like on the wire; why a randomized MAC has no vendor; how ARP spoofing is detected; why passwords are salted and hashed slowly; why the bandwidth limit alerts instead of throttling.

---

## Quick reference

**Module to feature**

| Module | Feature | Protocols and concepts |
|---|---|---|
| `core/netinfo.py` | F1 | UDP socket, IPv4, subnet mask, CIDR, default route, adapter |
| `core/discovery.py` | F1 | ICMP sweep, ARP, reverse DNS |
| `core/vendor.py` | F1 (N3) | IEEE OUI, universal/local MAC bit |
| `core/pinger.py` | F2 (N8) | ICMP echo, RTT, loss, continuous ping |
| `core/tracer.py` | F2 (N6) | TTL, ICMP Time Exceeded, routing hops |
| `core/statistics.py` | F3 (N10) | Latency, jitter, loss, baseline, standard deviation |
| `core/bandwidth.py` | F3 (N9) | Throughput, bits vs bytes |
| `core/wifi.py` | F3, F5 (N11) | 802.11 bands, channels, RSSI, WPA2/WPA3 |
| `core/report_builder.py` | F4 | — |
| `core/advisor.py` | F5 (N4, N5) | Firewalls, ports, ARP spoofing, Wi-Fi security |
| `core/diagnosis.py` | F5 (N7) | OSI layers, DNS over UDP |
| `core/watch.py` | F5 (N12) | Polling, events |
| `core/auth.py` | N1 | Salted PBKDF2, authentication vs authorization |

**Commands**

| Task | Command (inside `SourceCode/`, venv active) |
|---|---|
| Run | `python main.py` |
| Test | `pytest -v` |
| One test file | `pytest tests/test_pinger.py -v` |
| Save a fixture | `ping -n 4 192.168.1.1 > tests\fixtures\ping_ok.txt` |
| Traceroute fixture | `tracert -d -h 15 -w 500 1.1.1.1 > tests\fixtures\tracert_ok.txt` |
| Wi-Fi fixture | `netsh wlan show interfaces > tests\fixtures\wlan_interfaces.txt` (then hide the SSID and BSSID) |
| DNS servers | `(Get-DnsClientServerAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi').ServerAddresses` |
| Leftover pings? | `tasklist /FI "IMAGENAME eq PING.EXE"` |
| Clear ARP cache | `arp -d *` (administrator) |
| Fake ARP duplicate (A-1) | `netsh interface ipv4 add neighbors "Wi-Fi" <unused-ip> <gateway-mac>` (administrator); remove with `delete neighbors` |
| Freeze versions | `pip freeze > requirements.txt` |

**If time runs short**, cut in this order: PDF export, nearby-channel analysis, uptime strip, map drag/zoom/right-click (keep click and hover), baseline anomaly detection, watch mode. Never cut a core feature, its tests, a required deliverable, or the items requested on Nov 20: roles, device panel, diagnosis verdict, continuous ping with the ECG chart, bandwidth limits, the clickable map.
