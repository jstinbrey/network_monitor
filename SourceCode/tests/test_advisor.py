"""Tests for core/advisor.py (Feature 5: security recommendations)."""
from netmonitor import models
from netmonitor.core import advisor
from netmonitor.models import Device, HostStats

GATEWAY = Device(ip="192.168.1.1", hostname="Gateway", is_gateway=True)
PC = Device(ip="192.168.1.20", hostname="pc")


def stats(device, avg=10.0, loss=0.0, jitter=1.0, status=models.ONLINE):
    return HostStats(device.ip, device.hostname, 4, avg, avg, avg, jitter, loss, status)


def titles(devices, host_stats, severity=None):
    return [r.title for r in advisor.recommend(devices, host_stats) if severity in (None, r.severity)]


def test_healthy_network_gets_only_the_two_reminders():
    recs = advisor.recommend([GATEWAY, PC], [stats(GATEWAY), stats(PC)])
    assert [(r.severity, r.category, r.host) for r in recs] == [("info", "Firewall", None), ("info", "Passwords", None)]
    assert len(advisor.recommend([], [])) == 2           # also before the first scan


def test_gateway_down_is_one_critical_finding_listed_first():
    offline = stats(GATEWAY, None, 100.0, None, models.OFFLINE)
    recs = advisor.recommend([PC, GATEWAY], [stats(PC, loss=50.0), offline])
    assert [r.severity for r in recs] == ["critical", "warning", "info", "info"]
    assert recs[0].title == "The gateway 192.168.1.1 is unreachable"
    assert sum(r.host == GATEWAY.ip for r in recs) == 1  # not repeated as "unstable" or "weak"


def test_unreachable_host():
    assert titles([PC], [stats(PC, None, 100.0, None, models.OFFLINE)], "warning") == ["pc (192.168.1.20) is unreachable"]


def test_weak_connectivity_thresholds():
    assert titles([PC], [stats(PC, loss=5.0)], "warning") == []                    # exactly at the limit is fine
    assert titles([PC], [stats(PC, loss=12.5)], "warning") == ["Weak connectivity to pc (192.168.1.20)"]
    assert titles([PC], [stats(PC, avg=150.0)], "warning") == ["Weak connectivity to pc (192.168.1.20)"]


def test_gateway_unstable_thresholds():
    assert titles([GATEWAY], [stats(GATEWAY, loss=12.5)], "warning") == []         # below the gateway limit of 25%
    assert titles([GATEWAY], [stats(GATEWAY, loss=25.0)], "warning") == ["The gateway 192.168.1.1 is unstable"]
    assert titles([GATEWAY], [stats(GATEWAY, avg=150.0)], "warning") == ["The gateway 192.168.1.1 is unstable"]


def test_new_device_is_flagged():
    new = Device(ip="192.168.1.50", hostname="phone", mac="aa-bb", known=False)
    assert titles([new], [], "warning") == ["New device on the network: phone (192.168.1.50)"]


def test_high_jitter_and_blocked_icmp_are_info():
    assert "High jitter on pc (192.168.1.20)" in titles([PC], [stats(PC, jitter=45.0)], "info")
    blocked = stats(PC, None, 100.0, None, models.NO_ICMP)
    assert titles([PC], [blocked]) == ["pc (192.168.1.20) does not answer ping",
                                       "Keep the firewall turned on", "Use strong router and Wi-Fi passwords"]


ARP = {"192.168.1.1": "aa-aa-aa-aa-aa-aa", "192.168.1.20": "bb-bb-bb-bb-bb-bb"}   # the gateway and the PC


def arp_findings(arp):
    return [(r.severity, r.title) for r in advisor.recommend([], [], arp, "192.168.1.1") if r.category.startswith("ARP")]


def test_another_address_with_the_gateway_mac_is_critical():
    spoofed = ARP | {"192.168.1.250": "aa-aa-aa-aa-aa-aa"}
    assert arp_findings(spoofed) == [("critical", "Possible ARP spoofing: the gateway shares MAC aa-aa-aa-aa-aa-aa")]


def test_two_addresses_sharing_another_mac_is_a_warning():
    extender = ARP | {"192.168.1.30": "bb-bb-bb-bb-bb-bb"}
    assert arp_findings(extender) == [("warning", "2 addresses share MAC bb-bb-bb-bb-bb-bb")]


def test_a_clean_arp_table_adds_nothing():
    assert arp_findings(ARP) == [] and len(advisor.recommend([], [], ARP, "192.168.1.1")) == 2


def test_device_that_was_never_pinged_raises_nothing():
    assert len(advisor.recommend([PC], [stats(PC, None, None, None, models.NO_DATA)])) == 2
