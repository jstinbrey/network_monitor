"""Feature 4 (Network Report Generator): writes a dated summary report as HTML or CSV."""
import csv
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from netmonitor import config
from netmonitor.models import STATUS_LABELS

CSV_HEADER = ["Hostname", "IP Address", "Average Latency (ms)", "Maximum Latency (ms)", "Packet Loss (%)", "Status"]


def build(data: dict, fmt: str, folder: Path = None) -> Path:
    """Write one report file and return its path.

    data holds: info (NetworkInfo), devices, pings (latest PingResult per
    device), stats (HostStats per device), summary (NetworkSummary), and
    optionally recommendations (Feature 5).
    """
    now = datetime.now()
    data = data | {"generated_at": now.strftime("%Y-%m-%d %H:%M:%S"), "labels": STATUS_LABELS}
    folder = folder or config.OUTPUT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"report_{now:%Y%m%d_%H%M%S}.{fmt}"

    if fmt == "html":
        # autoescape: a hostname containing HTML is shown as text, never run as markup
        env = Environment(loader=FileSystemLoader(config.TEMPLATE_DIR), autoescape=select_autoescape())
        path.write_text(env.get_template("report.html").render(data), encoding="utf-8")
    elif fmt == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as file:   # utf-8-sig: Excel reads it correctly
            writer = csv.writer(file)
            writer.writerows([["Generated", data["generated_at"]], ["Network", data["info"].cidr], [], CSV_HEADER])
            writer.writerows([s.hostname, s.ip, s.avg_ms, s.max_ms, s.loss_pct, STATUS_LABELS[s.status]]
                             for s in data["stats"])
    else:
        raise ValueError(f"Unknown report format: {fmt}")
    return path