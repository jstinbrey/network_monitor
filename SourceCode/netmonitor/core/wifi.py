"""Wi-Fi link and nearby networks (Feature 3 and 5), from the Windows `netsh wlan` commands.

802.11 concepts: 2.4 GHz has 13 channels 5 MHz apart, but each transmission is 20 MHz wide, so
only 1, 6 and 11 do not overlap; 5 GHz has many non-overlapping channels. Signal is shown as a
percentage and as RSSI in dBm (about -30 is excellent, below -80 is unusable). WPA2/WPA3 with
CCMP (AES) is secure; TKIP and WEP are old ciphers that can be broken.
"""
import subprocess

from netmonitor.core.pinger import NO_WINDOW
from netmonitor.models import WifiInfo

NON_OVERLAPPING_24 = (1, 6, 11)


class WifiUnavailable(Exception):
    """Windows withholds the Wi-Fi details from desktop apps (Location permission)."""


def parse_fields(output: str) -> dict[str, str]:
    """'Label : value' pairs, first occurrence wins. Values may contain ':' (BSSIDs), so split once."""
    fields = {}
    for line in output.splitlines():
        label, sep, value = line.partition(":")
        if sep and label.strip() and label.strip() not in fields:
            fields[label.strip()] = value.strip()
    return fields


def parse_interfaces(output: str) -> WifiInfo | None:
    """The output of `netsh wlan show interfaces` as a WifiInfo, or None when Wi-Fi is not connected.
    Raises WifiUnavailable when Windows replaced the details with its Location message."""
    fields = parse_fields(output)
    if "State" not in fields and "location" in output.lower():   # no details, and a Location message
        raise WifiUnavailable("Windows needs Location access to show Wi-Fi details: Settings > Privacy & "
                              "security > Location > Let desktop apps access your location.")
    if fields.get("State") != "connected":
        return None
    signal = int(fields["Signal"].rstrip("%"))
    # Older drivers print no Rssi line; Windows' own signal % is roughly linear from -100 dBm (0%) to -50 dBm (100%).
    rssi = int(fields["Rssi"]) if fields.get("Rssi", "").lstrip("-").isdigit() else signal // 2 - 100
    return WifiInfo(ssid=fields.get("SSID", ""), band=fields.get("Band", "?"), channel=int(fields.get("Channel", 0)),
                    radio=fields.get("Radio type", ""), auth=fields.get("Authentication", ""),
                    cipher=fields.get("Cipher", ""), rx_mbps=float(fields.get("Receive rate (Mbps)", 0)),
                    tx_mbps=float(fields.get("Transmit rate (Mbps)", 0)), signal_pct=signal, rssi_dbm=rssi)


def parse_networks(output: str) -> list[tuple[str, int]]:
    """(band, channel) of every access point (BSSID) in `netsh wlan show networks mode=bssid`."""
    found, band = [], None
    for line in output.splitlines():
        label, _, value = line.partition(":")
        label, value = label.strip(), value.strip()
        if label == "Band":
            band = value
        elif label == "Channel" and value.isdigit():      # each BSSID block lists Band, then Channel
            found.append((band, int(value)))
    return found


def best_24ghz_channel(networks: list[tuple[str, int]]) -> int:
    """The least crowded of 1, 6 and 11. Channels less than 5 apart overlap, so a network on 4 crowds 1 and 6."""
    def crowd(channel):
        return sum(band == "2.4 GHz" and abs(c - channel) < 5 for band, c in networks)
    return min(NON_OVERLAPPING_24, key=crowd)


def describe(info: WifiInfo) -> str:
    """"Excellent signal (92%, -43 dBm) on 5 GHz channel 40, WPA2-Personal"."""
    return f"{info.quality} signal ({info.signal_pct}%, {info.rssi_dbm} dBm) on {info.band} channel {info.channel}, {info.auth}"


def _netsh(*args) -> str:
    return subprocess.run(["netsh", "wlan", *args], capture_output=True, text=True, timeout=10,
                          creationflags=NO_WINDOW).stdout


def read() -> WifiInfo | None:
    """This PC's Wi-Fi link, or None when wired or not connected. Raises WifiUnavailable (see parse_interfaces)."""
    return parse_interfaces(_netsh("show", "interfaces"))


def nearby() -> list[tuple[str, int]]:
    """(band, channel) of every access point Windows can see."""
    return parse_networks(_netsh("show", "networks", "mode=bssid"))
