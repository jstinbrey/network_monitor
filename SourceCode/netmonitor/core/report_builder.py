"""Feature 4 (Network Report Generator): writes a dated summary report as HTML or CSV."""
import csv
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from netmonitor import config
from netmonitor.models import STATUS_LABELS

CSV_HEADER = ["Hostname", "IP Address", "Vendor", "Average Latency (ms)", "Maximum Latency (ms)", "Packet Loss (%)",
              "Status", "Open Ports"]
# Parts a report may leave out; a missing one shows as "not run", "not checked" or "none".
OPTIONAL = {"recommendations": [], "verdict": None, "diagnosed_at": "", "ports": {}, "events": [], "wifi": "",
            "usage_bytes": None}


def ports_text(open_ports: list[dict] | None) -> str:
    """"Telnet (23), HTTP (80)" for a port check, "None open", or "Not checked"."""
    if open_ports is None:
        return "Not checked"
    return ", ".join(f"{p['service']} ({p['port']})" for p in open_ports) or "None open"


def build(data: dict, fmt: str, folder: Path = None) -> Path:
    """Write one report file and return its path.

    data holds: info (NetworkInfo), devices, pings (latest PingResult per
    device), stats (HostStats per device), summary (NetworkSummary), and
    optionally: recommendations (Feature 5), verdict and diagnosed_at (the
    last diagnosis), ports ({ip: open ports}), events (recent alerts),
    wifi (one line) and usage_bytes (this PC's data use today).
    """
    now = datetime.now()
    data = OPTIONAL | data | {"generated_at": now.strftime("%Y-%m-%d %H:%M:%S"), "labels": STATUS_LABELS}
    folder = folder or config.OUTPUT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"report_{now:%Y%m%d_%H%M%S}.{fmt}"

    if fmt == "html":
        # autoescape: a hostname containing HTML is shown as text, never run as markup
        env = Environment(loader=FileSystemLoader(config.TEMPLATE_DIR), autoescape=select_autoescape())
        env.filters["ports"] = ports_text
        path.write_text(env.get_template("report.html").render(data), encoding="utf-8")
    elif fmt == "csv":
        vendors = {d.ip: d.vendor for d in data["devices"]}
        with open(path, "w", newline="", encoding="utf-8-sig") as file:   # utf-8-sig: Excel reads it correctly
            writer = csv.writer(file)
            writer.writerows([["Generated", data["generated_at"]], ["Network", data["info"].cidr], [], CSV_HEADER])
            writer.writerows([s.hostname, s.ip, vendors.get(s.ip, ""), s.avg_ms, s.max_ms, s.loss_pct,
                              STATUS_LABELS[s.status], ports_text(data["ports"].get(s.ip))] for s in data["stats"])
    else:
        raise ValueError(f"Unknown report format: {fmt}")
    return path