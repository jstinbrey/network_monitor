"""Tests for core/report_builder.py (Feature 4: the report generator)."""
import csv

import pytest

from netmonitor.core import advisor, pinger, report_builder, statistics
from netmonitor.models import Device, NetworkInfo

INFO = NetworkInfo("my-pc", "192.168.1.37", "255.255.255.0", "192.168.1.0/24",
                   "192.168.1.1", "192.168.1.254", "192.168.1.1", 254)


def report_data(devices):
    pings = [pinger.build_result(d.ip, 4, [3.0, 5.0, 4.0]) for d in devices]
    stats = [statistics.host_stats(d, [p]) for d, p in zip(devices, pings)]
    return {"info": INFO, "devices": devices, "pings": pings, "stats": stats,
            "summary": statistics.summary(stats), "recommendations": advisor.recommend(devices, stats)}


DEVICES = [Device(ip="192.168.1.1", hostname="Gateway", mac="aa-bb", replied_icmp=True),
           Device(ip="192.168.1.20", hostname="<script>alert(1)</script>")]


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
    assert rows[4] == ["Gateway", "192.168.1.1", "4.0", "5.0", "25.0", "Degraded"]
    assert len(rows) == 6


def test_unknown_format_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        report_builder.build(report_data(DEVICES), "docx", tmp_path)