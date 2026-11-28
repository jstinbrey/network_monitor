"""Tests for Step 7.5: the Wi-Fi link and nearby networks (fixtures are this PC's netsh output, names replaced)."""
import pytest
from conftest import FIXTURES

from netmonitor import models, services
from netmonitor.core import advisor, diagnosis, wifi
from netmonitor.models import HostStats, Measurements, WifiInfo

LINK = WifiInfo("HomeWiFi", "5 GHz", 40, "802.11ax", "WPA2-Personal", "CCMP", 2042.0, 2269.0, 92, -43,
                bssid="aa:bb:cc:00:00:02")


def interfaces(name="wlan_interfaces.txt"):
    return (FIXTURES / name).read_text()


def test_a_connected_link_is_parsed():
    link = wifi.parse_interfaces(interfaces())
    assert link == LINK and link.quality == "Excellent"
    assert wifi.describe(link) == "Excellent signal (92%, -43 dBm) on 5 GHz channel 40, WPA2-Personal"


def test_without_an_rssi_line_the_signal_formula_is_used():
    text = "\n".join(line for line in interfaces().splitlines() if not line.strip().startswith("Rssi"))
    assert wifi.parse_interfaces(text).rssi_dbm == 92 // 2 - 100


def test_disconnected_or_wired_is_none_and_the_location_message_raises():
    assert wifi.parse_interfaces(interfaces("wlan_disconnected.txt")) is None
    assert wifi.parse_interfaces("The Wireless AutoConfig Service (wlansvc) is not running.") is None   # wired PC
    with pytest.raises(wifi.WifiUnavailable, match="Location"):
        wifi.parse_interfaces(interfaces("wlan_location.txt"))


@pytest.mark.parametrize("signal, quality", [(80, "Excellent"), (79, "Good"), (60, "Good"), (40, "Fair"), (39, "Weak")])
def test_quality(signal, quality):
    assert WifiInfo("x", "5 GHz", 36, "", "", "", 0, 0, signal, -60).quality == quality


def test_nearby_access_points_and_the_least_crowded_24ghz_channel():
    assert wifi.parse_networks((FIXTURES / "wlan_networks.txt").read_text()) == \
        [("5 GHz", 100), ("5 GHz", 40), ("2.4 GHz", 8), ("5 GHz", 132)]
    assert wifi.best_24ghz_channel([]) == 1
    assert wifi.best_24ghz_channel([("2.4 GHz", 4)]) == 11            # 4 overlaps both 1 and 6
    assert wifi.best_24ghz_channel([("2.4 GHz", 1), ("2.4 GHz", 11), ("5 GHz", 6)]) == 6   # 5 GHz does not count


def recs(link):
    return [(r.severity, r.title) for r in advisor.recommend([], [], wifi=link) if r.category == "Wi-Fi"]


def test_wifi_security_and_signal_rules():
    weak = WifiInfo("Cafe", "2.4 GHz", 6, "802.11n", "Open", "None", 72, 72, 35, -82)
    assert recs(weak) == [("critical", "Your Wi-Fi has no password"), ("warning", "Weak Wi-Fi signal (35%, -82 dBm)")]
    wep = WifiInfo("Old", "2.4 GHz", 6, "802.11g", "Open", "WEP", 54, 54, 70, -60)
    assert recs(wep) == [("critical", "Your Wi-Fi uses WEP, which can be cracked in minutes")]
    tkip = WifiInfo("Old", "5 GHz", 136, "802.11a", "WPA-Personal", "TKIP", 54, 54, 70, -60)
    assert recs(tkip) == [("warning", "Your Wi-Fi uses the old TKIP cipher")]
    assert recs(LINK) == []


def test_the_password_reminder_quotes_the_real_security_mode():
    reminder = next(r for r in advisor.recommend([], [], wifi=LINK) if r.category == "Passwords")
    assert reminder.detail.startswith("This network uses WPA2-Personal.") and "WPA3" in reminder.action
    wpa3 = WifiInfo("New", "6 GHz", 5, "802.11ax", "WPA3-Personal", "GCMP", 2400, 2400, 90, -40)
    assert "WPA3" not in next(r for r in advisor.recommend([], [], wifi=wpa3) if r.category == "Passwords").action


def test_an_unstable_router_link_names_a_weak_signal():
    router = HostStats("192.168.1.1", "Unknown", 10, 3.0, 3.0, 3.0, 1.0, 20.0, models.DEGRADED)
    weak = WifiInfo("x", "2.4 GHz", 6, "", "WPA2-Personal", "CCMP", 72, 72, 30, -85)
    verdict = diagnosis.verdict(Measurements(local_ip="192.168.1.6", gateway=router, wifi=weak))
    assert verdict.headline == "The link to your router is unstable, and the Wi-Fi signal is weak."
    assert "Wi-Fi signal 30% (-85 dBm): weak." in verdict.evidence


def test_wifi_link_turns_the_location_message_into_a_note(monkeypatch):
    def withheld():
        raise wifi.WifiUnavailable("Windows needs Location access")
    monkeypatch.setattr(services.wifi, "read", withheld)
    assert services.wifi_link() == (None, "Windows needs Location access")
    monkeypatch.setattr(services.wifi, "read", lambda: None)
    assert services.wifi_link()[1].startswith("Not on Wi-Fi")
