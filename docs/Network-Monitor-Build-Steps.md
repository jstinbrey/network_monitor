# Network Monitor: Step-by-Step Build Plan

Companion to `Network-Monitor-Implementation-Plan-v2.docx`. That document says **what** is built and why; this one says **how**, in the order to do it. Requirements, dates and point values come from the two course documents in this folder.

- **Target:** Windows 10/11, Python 3.11+ (3.13 is installed on this PC).
- **Submission:** Dec 4. **Progress report:** Nov 17. **Defense:** Dec 8–10.
- **Rule for every step:** do not start the next step until the current step's **Checkpoint** passes.

Code blocks marked **(checked)** were run against this PC's real `ping`, `route print` and `arp -a` output on Nov 15. Everything else is a design to implement and test, not finished code.

---

## Contents

| Phase | Dates | Result |
|---|---|---|
| [0. Setup](#phase-0-setup) | Nov 15 | Folder, virtual environment, empty package that runs |
| [1. Scan and ping](#phase-1-scan-and-ping-f1-f2) | Nov 15–16 | F1 and F2 working in the window |
| [2. Storage and statistics](#phase-2-storage-and-statistics-f3) | Nov 18–20 | F3 working from stored data |
| [3. Reports](#phase-3-reports-f4) | Nov 21–22 | F4: HTML and CSV reports |
| [4. Security](#phase-4-security-recommendations-f5) | Nov 23–24 | F5: rule engine and Security view |
| [5. Dashboard, bonuses, polish](#phase-5-dashboard-bonuses-polish) | Nov 25–26 | Feature freeze |
| [6. Test evidence](#phase-6-test-evidence) | Nov 27–28 | Everything Chapter 4 needs |
| [7. Packaging](#phase-7-packaging) | Dec 3 | The zip |

Nov 17 is the progress report; Nov 29–Dec 2 is the final report, slides and video (see the v2 plan, sections 11–12).

---

## Ground rules

1. **Three layers, one direction.** `gui/` calls `services.py`; `services.py` calls `core/` and `store.py`. `core/` never imports Tkinter. `gui/` never runs `subprocess` or opens a socket.
2. **Nothing slow on the main thread.** Every service call from a view goes through `run_async`. Test by dragging the window while a scan runs; it must keep moving.
3. **Tkinter is touched only from the main thread.** Worker threads put results on a queue; the main thread reads the queue.
4. **Test `core/` before wiring it to a view.** Each core step below has a pytest file. A parser that passes its fixtures will not surprise you in the demo.
5. **Save real command output as fixtures.** When `ping` or `arp -a` prints something new (a timeout, an unreachable reply), save it under `tests/fixtures/` and add a test.
6. **Comment as you write.** The brief requires commented code. Each module gets a docstring naming its feature and protocol; each public function gets a docstring.
7. **Commit after every checkpoint** (`git init` inside `SourceCode/`). A working state you can return to is worth more than any feature.

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

## Phase 5: Dashboard, bonuses, polish

Do these in order and stop at the Nov 26 freeze wherever you are.

### Step 5.1: Dashboard

`gui/widgets/stat_card.py`: a `CTkFrame` with a small muted title and a large value label; `set(value, colour=None)`.

`gui/views/dashboard.py`:

1. Four cards: Devices, Reachable, Average latency, Health score (green ≥ 80, amber ≥ 50, red below).
2. `LatencyChart.plot_bars` of average latency per host (label with the last octet or hostname; cap at 15 bars).
3. The top three recommendations as cards, with a "View all" button to the Security view.
4. A **Scan and refresh** button that runs scan then refresh-all.
5. Make it the first view shown. With no data, show "Run a scan to begin" rather than empty cards.

### Step 5.2: PDF export (bonus: Export to PDF)

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def build_pdf(data, path):
    styles = getSampleStyleSheet()
    story = [Paragraph("Network Monitoring Report", styles["Title"]),
             Paragraph(f"Generated: {data.generated_at}", styles["Normal"]), Spacer(1, 12)]
    rows = [["IP", "Hostname", "MAC", "Status"]] + [[d.ip, d.hostname, d.mac or "-", ...] for d in data.devices]
    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f538d")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    story += [Paragraph("Devices detected", styles["Heading2"]), t]
    ...
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
```

Same five sections as the HTML. Wrap long recommendation text in `Paragraph` objects inside table cells so it wraps. Add PDF to the format selector. Test: the file exists and starts with `%PDF`.

### Step 5.3: TCP latency test (bonus: socket programming in F2)

Concept: TCP three-way handshake (SYN, SYN-ACK, ACK).

```python
def tcp_ping(ip, port=80, count=4, timeout_s=config.TCP_TIMEOUT_S) -> PingResult:
    ip = validate_ip(ip)
    rtts, lines, answered = [], [], 0
    for i in range(count):
        start = time.perf_counter()
        try:
            socket.create_connection((ip, port), timeout=timeout_s).close()
            ms = round((time.perf_counter() - start) * 1000, 1)
            rtts.append(ms); answered += 1
            lines.append(f"Connected to {ip}:{port} time={ms} ms")
        except ConnectionRefusedError:
            answered += 1
            lines.append(f"{ip}:{port} refused the connection (host is up, port closed)")
        except OSError:
            lines.append(f"{ip}:{port} timed out")
        time.sleep(0.2)
    ...
```

**Important, measured on this PC:** when a port is closed, Windows retries the SYN before reporting "refused", so the call returns after about **2 seconds** regardless of real latency. Therefore:

- `TCP_TIMEOUT_S` must be above 2 s (3 s is set), or every refusal looks like a timeout.
- A refusal proves the host is up but its time is **not** a latency. Count it as answered; do not add it to `rtts`.
- Only successful connections give a "TCP latency". Good targets: the router on port 80, or 8.8.8.8 on port 53.

This means the result needs `received = answered` for loss, with statistics from `rtts` only, so build the `PingResult` by hand here instead of with `build_result`. Set `method="tcp"`; statistics ignore TCP results. In the Ping view add a `CTkSegmentedButton` (ICMP / TCP) and a port entry shown only in TCP mode. Label results "TCP latency".

This is a good defense point: explain why ICMP and TCP times differ and why a refused port still proves reachability.

### Step 5.4: Port check (bonus: Port Scanner)

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

`connect_ex` returns 0 only when the handshake completes; closed and filtered ports both return non-zero within the 0.5 s timeout, which is all this check needs.

Security view: a device `CTkOptionMenu`, a **Check ports** button, and a results list. Store results in services so `rule_risky_ports` fires on the next reload. Add a visible line: "Only check devices on a network you own or administer", and repeat it in the README.

Test with a fake: start a listening socket on `127.0.0.1` in the test on a free port and pass `ports={that_port: "test"}`.

### Step 5.5: Polish for the UI points (10)

- [ ] Consistent padding (one constant in `theme.py`) and consistent heading font on every view.
- [ ] Every button that starts work is disabled while it runs and re-enabled on success **and** on error.
- [ ] Empty states on every view ("No devices yet. Run a scan.").
- [ ] Errors appear in the view, in plain words; no tracebacks reach the user. Disconnect Wi-Fi and click Scan to check.
- [ ] `self.minsize(1000, 640)`; tables and charts stretch when the window is resized.
- [ ] Sidebar highlights the current view.
- [ ] Status colours are the same everywhere: green online, amber degraded or no ICMP, red offline, blue info.
- [ ] Window icon (`iconbitmap`) if you have an `.ico`; skip otherwise.

### Step 5.6: Stretch — live refresh

Statistics view: a `CTkSwitch` "Live". On: `self._job = self.after(config.LIVE_REFRESH_S * 1000, self._tick)`, where `_tick` runs refresh-all and reschedules itself in `on_done`. Off, or leaving the view: `self.after_cancel(self._job)`. Never start a refresh while one is running.

**Checkpoint 5 — feature freeze, Nov 26**
- [ ] One uninterrupted session: start, scan, ping, statistics, report, security, with no errors.
- [ ] Full `pytest` run is green.
- [ ] No new features after this point; bug fixes only.

---

## Phase 6: Test evidence

Collected once, used in Chapter 4, the slides, and the video. Save everything under `Documentation/`.

### Step 6.1: Unit tests

`pytest -v` in a terminal; screenshot the result. Note the number of tests per module in a small table.

### Step 6.2: Functional test table

One row per requirement, run by hand in the app:

| ID | Requirement | Steps | Expected | Actual | Pass |
|---|---|---|---|---|---|
| F1-1 | Detect local IP | Open Devices | Matches `ipconfig` | | |
| F1-2 | Display network range | Open Devices | CIDR and host range shown | | |
| F1-3 | List active devices | Scan | Gateway, this PC, phone listed | | |
| F2-1 | Ping selected devices | Select two rows, Ping selected | A result per device | | |
| F2-2 | Display response time | Ping gateway | Per-reply times shown | | |
| F2-3 | Packet loss percentage | Ping unused address | 100% | | |
| F3-1 | Statistics columns | Open Statistics | Five required columns | | |
| F4-1 | Report contents | Generate HTML | Date/time, devices, pings, summary | | |
| F5-1 | Weak connectivity alert | Ping a host with poor signal | Warning shown | | |
| F5-2 | Unreachable host | Disconnect a device, refresh | Warning shown | | |
| F5-3 | Firewall recommendation | Open Security | Reminder shown | | |
| F5-4 | Password reminder | Open Security | Reminder shown | | |
| E-1 | Invalid input | Ping `abc` | Message, no crash | | |
| E-2 | No network | Disable Wi-Fi, Scan | Message, no crash | | |

For F5-1, walk the phone far from the router or use a deliberately slow target; if nothing on your network is slow enough, lower `LATENCY_WARN_MS` for the test and say so.

### Step 6.3: Two-network comparison

Run the same sequence on home Wi-Fi and on a phone hotspot (join a second device to the hotspot): devices found, scan time, network average latency, loss, health score. One table, two columns of results.

### Step 6.4: Wireshark accuracy check

1. Start a capture on the Wi-Fi adapter with display filter `icmp`.
2. In the app, ping the gateway with count 10.
3. In Wireshark, each echo reply shows its response time in the ICMP details. Record all ten.
4. Table: reply number, app time, Wireshark time, difference; then the mean difference. Expect the app to read slightly higher and rounded to whole milliseconds, because `ping` reports integers.
5. Screenshot the capture with a request/reply pair selected.

Also capture `arp` during a scan and `tcp.flags.syn==1` during a port check; one screenshot each. These illustrate layers 2, 3 and 4 for Chapter 3.

### Step 6.5: Fault tests

- **Unreachable host:** turn a scanned phone's Wi-Fi off, clear ARP (`arp -d *` as administrator), Refresh all. Screenshot the offline row and the warning.
- **ICMP blocked:** a Windows PC with the default firewall. Screenshot the "No ICMP reply (host up)" row and the info card.
- **Risky port:** on this PC run a listener on port 23, then Check ports against your own IP:

```powershell
python -c "import socket; s=socket.socket(); s.bind(('0.0.0.0',23)); s.listen(); input('listening on 23, Enter to stop')"
```

  Windows Firewall may ask for permission; allow it on private networks. Screenshot the critical card.

**Checkpoint 6 (Nov 28)**
- [ ] Every row of the functional table has an actual result and a screenshot.
- [ ] Wireshark comparison table complete.
- [ ] Any bug found is fixed and the suite re-run.

---

## Phase 7: Packaging

### Step 7.1: Comment pass

- Module docstring on every file: the feature and the protocol or concept it implements.
- Docstring on every public function.
- Comments where a networking decision is made (why the OS summary line is ignored, why ARP is read after the sweep, why refused TCP connections are not latency).
- Delete dead code and debugging prints.

### Step 7.2: `README.txt` (top level)

Plain text, in this order:

1. Project title, your name, course, date.
2. One-paragraph description.
3. Requirements: Windows 10 or 11, Python 3.11 or newer.
4. Installation: `cd SourceCode`, `python -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements.txt`.
5. Running: `python main.py`, or double-click `run.bat`.
6. Features: the five core features, then the bonus features.
7. Running the tests: `pytest -v`.
8. Folder contents.
9. Known limitations: Windows only; scans at most a /24; hostnames are not always resolvable; port check is for networks you own or administer.

### Step 7.3: Clean-install test

Copy `SourceCode/` to a new folder **without** `.venv`, follow the README exactly, and run a scan. If you have a second Windows PC, do it there. Fix the README wherever you had to think.

### Step 7.4: Build the zip

1. Delete from `SourceCode/`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `build/`, `dist/`, `.git/`, `data/*.db`, and old files in `output/` (keep one sample report).
2. Put the slides in `Presentation/` and the video in `VideoDemo/`.
3. Move `Documentation/` out of the folder; it goes to Teams separately.
4. Zip the folder as `LASTNAME_FIRSTNAME_FINALPROJECT.zip`.
5. Unzip it somewhere else and confirm it contains `/SourceCode`, `/Presentation`, `/VideoDemo`, and `README.txt`.

### Step 7.5: Optional `.exe`

Only if everything above is done:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name NetMonitor --collect-all customtkinter --add-data "netmonitor/templates;netmonitor/templates" main.py
```

Use `--onedir`, not `--onefile`. In a frozen app `Path(__file__)` points inside the bundle, so `DB_PATH` and `OUTPUT_DIR` would need to move to a writable folder (for example under `%LOCALAPPDATA%`); test this before relying on it. Do not add `pyinstaller` to `requirements.txt`.

**Checkpoint 7 (Dec 3)**
- [ ] The unzipped folder runs from a fresh virtual environment by following README.txt.
- [ ] Zip name and contents match the submission requirements.

---

## Demo-day checklist (Dec 8–10)

- [ ] Rehearse on the exact network you will present on. School Wi-Fi often isolates clients, so a scan may find only the gateway; bring a phone hotspot with a second device joined.
- [ ] Delete `data/netmonitor.db` before the demo for a clean first scan, then run one scan and Refresh all so history charts are not empty.
- [ ] Keep Wireshark open with the `icmp` filter ready.
- [ ] Keep one generated PDF report open as a fallback if the live network misbehaves.
- [ ] Be ready to explain: how the local IP is found without sending a packet; why ARP finds devices that ping misses; what `time<1ms` means; how loss and jitter are computed; why a refused TCP connection still proves a host is up; the health score formula.

---

## Quick reference

**Module to feature**

| Module | Feature | Protocols and concepts |
|---|---|---|
| `core/netinfo.py` | F1 | UDP socket, IPv4, subnet mask, CIDR, default route |
| `core/discovery.py` | F1 | ICMP sweep, ARP, reverse DNS |
| `core/pinger.py` | F2 | ICMP echo, RTT, loss, TCP handshake |
| `core/statistics.py` | F3 | Latency, jitter, loss, baseline |
| `core/report_builder.py` | F4 | — |
| `core/advisor.py` | F5 | Firewalls, ports, WPA2/WPA3 |

**Commands**

| Task | Command (inside `SourceCode/`, venv active) |
|---|---|
| Run | `python main.py` |
| Test | `pytest -v` |
| One test file | `pytest tests/test_pinger.py -v` |
| Save a fixture | `ping -n 4 192.168.1.1 > tests\fixtures\ping_ok.txt` |
| Clear ARP cache | `arp -d *` (administrator) |
| Freeze versions | `pip freeze > requirements.txt` |

**If time runs short**, cut in this order: `.exe`, live refresh, TCP latency test, port check, PDF export, Dashboard chart. Never cut a core feature, its tests, or a required deliverable.
