"""Feature 4 (Network Report Generator): writes a dated summary report as HTML, CSV or PDF."""
import csv
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from netmonitor import config
from netmonitor.models import NO_DATA, STATUS_LABELS

HEADER_BLUE = colors.HexColor("#1f538d")
VERDICT_COLORS = {"good": "#2f8a5f", "warn": "#b7791f", "bad": "#c0392b"}   # as in the HTML report
MARGIN = 40                                                                  # points (1/72 inch)

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
    data["device_statuses"] = {s.ip: STATUS_LABELS[s.status] for s in data["stats"]}
    score = data["summary"].health_score
    data["health_text"] = f"{score} / 100" if score is not None else STATUS_LABELS[NO_DATA]
    folder = folder or config.OUTPUT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"report_{now:%Y%m%d_%H%M%S_%f}.{fmt}"   # microseconds: two reports never share a name

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
    elif fmt == "pdf":
        _pdf(data, path)
    else:
        raise ValueError(f"Unknown report format: {fmt}")
    return path


def _ms(value):
    return "No data" if value is None else f"{value} ms"


def _pdf(data: dict, path: Path):
    """The HTML report's sections, laid out on A4 pages with reportlab."""
    styles = getSampleStyleSheet()
    body, heading = styles["Normal"], styles["Heading2"]
    cell = ParagraphStyle("cell", parent=body, fontSize=7.5, leading=9)
    head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    width = A4[0] - 2 * MARGIN

    def text(value, style=body):
        return Paragraph(escape(str(value)), style)   # escaped: reportlab reads <b> and & in a Paragraph as markup

    def table(header, rows, shares):
        """A table whose cells wrap; shares: each column's part of the page width."""
        grid = Table([[text(h, head) for h in header]] + [[text(v, cell) for v in row] for row in rows],
                     colWidths=[width * share for share in shares], repeatRows=1)
        grid.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                  ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        return grid

    info, verdict, devices, pings, stats, summary = (data[key] for key in
                                                     ("info", "verdict", "devices", "pings", "stats", "summary"))
    story = [Paragraph("Network Monitoring Report", styles["Title"]),
             text(f"Generated: {data['generated_at']}"),
             text(f"Host: {info.hostname} ({info.local_ip})  |  Network: {info.cidr} ({info.first_host} to "
                  f"{info.last_host})  |  Gateway: {info.gateway or 'none'}")]
    if data["wifi"]:
        story.append(text(f"Wi-Fi: {data['wifi']}"))
    if data["usage_bytes"] is not None:
        story.append(text(f"Data used today by this PC: {data['usage_bytes'] / 1e9:.2f} GB"))

    story.append(Paragraph("Diagnosis", heading))
    if verdict:
        story.append(Paragraph(f'<font color="{VERDICT_COLORS[verdict.status]}"><b>{escape(verdict.headline)}</b>'
                               f'</font> (run at {escape(data["diagnosed_at"])})', body))
        story += [text(f"•  {line}") for line in verdict.evidence]
        story.append(text(f"Recommended: {verdict.action}  (OSI layer {verdict.layer})"))
    else:
        story.append(text("Diagnosis not run in this session."))

    story.append(Paragraph(f"Devices Detected ({len(devices)})", heading))
    story.append(table(["IP Address", "Hostname", "MAC Address", "Vendor", "Status", "Open Ports", "Last Seen"],
                       [[d.ip, d.hostname, d.mac or "-", d.vendor,
                         data["device_statuses"].get(d.ip, STATUS_LABELS[NO_DATA]),
                         ports_text(data["ports"].get(d.ip)), d.last_seen.replace("T", " ")] for d in devices],
                       [0.11, 0.18, 0.17, 0.15, 0.12, 0.14, 0.13])
                 if devices else text("No devices found. Run a scan first."))

    story.append(Paragraph("Ping Results", heading))
    story.append(table(["IP Address", "Sent", "Received", "Packet Loss", "Minimum", "Average", "Maximum", "Status",
                        "Tested At"],
                       [[p.ip, p.sent, p.received, f"{p.loss_pct}%", _ms(p.min_ms), _ms(p.avg_ms), _ms(p.max_ms),
                         data["labels"][p.status], p.timestamp.replace("T", " ")] for p in pings],
                       [0.13, 0.06, 0.08, 0.09, 0.1, 0.1, 0.1, 0.18, 0.16])
                 if pings else text("No ping tests have been run yet."))

    story.append(Paragraph("Network Performance Summary", heading))
    story.append(table(["Devices", "Reachable", "Unreachable", "Average latency", "Health score"],
                       [[summary.devices, summary.reachable, summary.unreachable, _ms(summary.network_avg_ms),
                         data["health_text"]]], [0.2] * 5))
    story += [Spacer(1, 4), text(f"Fastest host: {summary.best_host or 'No data'}  |  "
                                 f"Slowest host: {summary.worst_host or 'No data'}")]
    if stats:
        story += [Spacer(1, 6), table(
            ["Hostname", "IP Address", "Average Latency", "Maximum Latency", "Packet Loss", "Jitter", "Status"],
            [[s.hostname, s.ip, _ms(s.avg_ms), _ms(s.max_ms), "No data" if s.loss_pct is None else f"{s.loss_pct}%",
              _ms(s.jitter_ms), data["labels"][s.status]] for s in stats], [0.2, 0.14, 0.13, 0.13, 0.11, 0.11, 0.18])]

    if data["recommendations"]:
        story.append(Paragraph("Security Recommendations", heading))
        story.append(table(["Severity", "Finding", "Details", "Recommended Action"],
                           [[r.severity.capitalize(), r.title, r.detail, r.action] for r in data["recommendations"]],
                           [0.1, 0.26, 0.34, 0.3]))

    story.append(Paragraph("Recent Alerts", heading))
    story.append(table(["Time", "Severity", "Alert", "Device", "Status"],
                       [[e.at.replace("T", " "), e.severity.capitalize(), e.detail, e.ip or "-",
                         "Dismissed" if e.dismissed else "New"] for e in data["events"]], [0.18, 0.1, 0.48, 0.13, 0.11])
                 if data["events"] else text("No alerts recorded on this network."))
    SimpleDocTemplate(str(path), pagesize=A4, title="Network Monitoring Report", leftMargin=MARGIN,
                      rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN).build(story)
