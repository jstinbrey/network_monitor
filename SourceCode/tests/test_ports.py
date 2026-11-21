"""Tests for Step 6.3: the port check, its storage, and the advice it leads to."""
import socket

import pytest

from netmonitor import config, models, services, store
from netmonitor.core import advisor, ports
from netmonitor.gui.widgets.device_panel import ports_line
from netmonitor.models import Device

NETWORK = "192.168.1.0/24 via aa"
GATEWAY = Device(ip="192.168.1.1", hostname="router", is_gateway=True)
PC = Device(ip="192.168.1.20", hostname="pc")
TELNET = {"port": 23, "service": "Telnet", "risk": "high"}
HTTP = {"port": 80, "service": "HTTP", "risk": "normal"}


def test_a_listening_port_is_open_and_a_closed_one_is_not():
    with socket.socket() as spare:                 # a port nothing listens on
        spare.bind(("127.0.0.1", 0))
        closed = spare.getsockname()[1]
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
        found = ports.check_ports("127.0.0.1", {port: "test", closed: "closed"})
    assert found == [{"port": port, "service": "test", "risk": "normal"}]


def test_bad_input_never_reaches_connect():
    with pytest.raises(ValueError):
        ports.check_ports("192.168.1.1; del *")


def test_a_stored_risky_port_is_critical(tmp_path):
    store.save_port_check(PC.ip, [HTTP, TELNET], NETWORK, tmp_path / "t.db")
    store.save_port_check(PC.ip, [TELNET], NETWORK, tmp_path / "t.db")          # a newer check replaces the old one
    checks = store.get_port_checks(NETWORK, tmp_path / "t.db")
    assert checks == {PC.ip: [TELNET]}
    rec = advisor.recommend([PC], [], ports=checks)[0]
    assert (rec.severity, rec.title) == ("critical", "Risky port open on pc (192.168.1.20): Telnet (23)")


def test_http_on_the_gateway_is_info_and_on_a_pc_is_nothing():
    titles = [r.title for r in advisor.recommend([GATEWAY, PC], [], ports={GATEWAY.ip: [HTTP], PC.ip: [HTTP]})]
    assert titles == ["The router's admin page uses unencrypted HTTP",
                      "Keep the firewall turned on", "Use strong router and Wi-Fi passwords"]


def test_a_user_cannot_check_ports(monkeypatch):
    monkeypatch.setattr(services, "_user", models.User("bob", models.USER))
    with pytest.raises(PermissionError):
        services.check_ports(PC.ip)


@pytest.mark.parametrize("open_ports, expected", [
    (None, "Open ports: not checked yet"),
    ([], f"Open ports: none of the {len(config.COMMON_PORTS)} common ports"),
    ([HTTP, TELNET], "Open ports: HTTP (80), Telnet (23)"),
])
def test_ports_line(open_ports, expected):
    assert ports_line(open_ports)[0] == expected
