"""Tests for core/report_builder.py (Feature 4: the report generator)."""
import csv

import pytest

from netmonitor.core import advisor, pinger, report_builder, statistics
from netmonitor.models import Device, Event, NetworkInfo, Verdict

INFO = NetworkInfo("my-pc", "192.168.1.37", "255.255.255.0", "192.168.1.0/24",
                   "192.168.1.1", "192.168.1.254", "192.168.1.1", 254)


def report_data(devices):
    pings = [pinger.build_result(d.ip, 4, [3.0, 5.0, 4.0]) for d in devices]
    stats = [statistics.host_stats(d, [p]) for d, p in zip(devices, pings)]
    return {"info": INFO, "devices": devices, "pings": pings, "stats": stats,
            "summary": statistics.summary(stats), "recommendations": advisor.recommend(devices, stats)}


DEVICES = [Device(ip="192.168.1.1", hostname="Gateway", mac="aa-bb", replied_icmp=True, vendor="Huawei"),
           Device(ip="192.168.1.20", hostname="<script>alert(1)</script>")]
TELNET = {"port": 23, "service": "Telnet", "risk": "high"}


def test_html_has_the_four_required_parts(tmp_path):
    path = report_builder.build(report_data(DEVICES), "html", tmp_path)
    html = path.read_text(encoding="utf-8")
    assert path.name.startswith("report_20") and path.suffix == ".html"
    assert "Generated: 20" in html                                         # date and time
    assert "Devices Detected (2)" in html and "192.168.1.20" in html       # devices detected
    assert "Ping Results" in html and "25.0%" in html                      # ping results
    assert "Network Performance Summary" in html and "/ 100" in html       # performance summary
    assert "Security Recommendations" in html and "Weak connectivity to" in html   # Feature 5 advice


def test_html_escapes_hostnames(tmp_path):
    html = report_builder.build(report_data(DEVICES), "html", tmp_path).read_text(encoding="utf-8")
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_report_with_no_devices_still_renders(tmp_path):
    html = report_builder.build(report_data([]), "html", tmp_path).read_text(encoding="utf-8")
    assert "No devices found" in html and "No ping tests" in html


def test_csv_has_a_header_and_one_row_per_device(tmp_path):
    path = report_builder.build(report_data(DEVICES), "csv", tmp_path)
    rows = list(csv.reader(open(path, encoding="utf-8-sig", newline="")))
    assert rows[0][0] == "Generated" and rows[1] == ["Network", "192.168.1.0/24"]
    assert rows[3] == report_builder.CSV_HEADER
    assert rows[4] == ["Gateway", "192.168.1.1", "Huawei", "4.0", "5.0", "25.0", "Degraded", "Not checked"]
    assert len(rows) == 6


def test_csv_lists_open_ports(tmp_path):
    path = report_builder.build(report_data(DEVICES) | {"ports": {"192.168.1.1": [TELNET], "192.168.1.20": []}},
                                "csv", tmp_path)
    rows = list(csv.reader(open(path, encoding="utf-8-sig", newline="")))
    assert [row[-1] for row in rows[4:]] == ["Telnet (23)", "None open"]


def test_the_diagnosis_section_shows_the_last_verdict_or_says_it_was_not_run(tmp_path):
    verdict = Verdict("bad", "ISP", "Your router is fine, but the internet connection is down (ISP or modem).",
                      ["Router 192.168.1.1: 0% loss, 3 ms average."], "Restart the modem and router.", "3")
    html = report_builder.build(report_data(DEVICES) | {"verdict": verdict, "diagnosed_at": "2026-11-22 10:00:00"},
                                "html", tmp_path).read_text(encoding="utf-8")
    assert '<p class="bad"><b>Your router is fine, but the internet connection is down (ISP or modem).</b>' in html
    assert "<li>Router 192.168.1.1: 0% loss, 3 ms average.</li>" in html and "(OSI layer 3)" in html
    assert "run at 2026-11-22 10:00:00" in html
    not_run = report_builder.build(report_data(DEVICES), "html", tmp_path).read_text(encoding="utf-8")
    assert "Diagnosis not run in this session." in not_run


def test_open_ports_alerts_wifi_and_data_use(tmp_path):
    alert = Event(1, "2026-11-22T09:30:00", "bandwidth", "warning", None, None,
                  "Download above the 5 Mbps limit for 10 s: 9.1 Mbps.", dismissed=True)
    html = report_builder.build(report_data(DEVICES) | {
        "ports": {"192.168.1.1": [TELNET]}, "events": [alert], "usage_bytes": 1.234e9,
        "wifi": "Excellent signal (92%, -43 dBm) on 5 GHz channel 40, WPA2-Personal"}, "html", tmp_path
    ).read_text(encoding="utf-8")
    assert "<td>Telnet (23)</td>" in html and "<td>Not checked</td>" in html     # checked, and never checked
    assert "Recent Alerts" in html and "2026-11-22 09:30:00" in html and "Dismissed" in html
    assert "Wi-Fi: Excellent signal (92%" in html and "Data used today by this PC: 1.23 GB" in html
    assert "No alerts recorded" in report_builder.build(report_data(DEVICES), "html", tmp_path).read_text(
        encoding="utf-8")


def test_unknown_format_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        report_builder.build(report_data(DEVICES), "docx", tmp_path)