"""Feature 1 extension: who made a device, from the first three bytes of its MAC address.

The first three bytes (the OUI) are assigned to manufacturers by the IEEE.
The registry is resources/oui.csv, downloaded from standards-oui.ieee.org.
"""
import csv
from functools import cache

from netmonitor import config

PRIVATE = "Private (randomized MAC)"


@cache                                      # read the 40,000-row file once, on first use
def _registry() -> dict[str, str]:
    try:
        with open(config.OUI_PATH, newline="", encoding="utf-8", errors="replace") as file:
            return {row["Assignment"].upper(): row["Organization Name"] for row in csv.DictReader(file)}
    except FileNotFoundError:
        return {}


def is_randomized(mac: str) -> bool:
    """True when the locally administered bit (0x02) of the first byte is set.

    Phones and laptops set it when they make up a random MAC for privacy,
    so such an address belongs to no manufacturer.
    """
    return bool(int(mac[1], 16) & 0b10)


def vendor(mac: str | None) -> str:
    """The manufacturer's name, PRIVATE for a randomized MAC, or "Unknown vendor" when not registered."""
    if not mac:
        return "Unknown"
    if is_randomized(mac):
        return PRIVATE
    return _registry().get(mac.replace("-", "").upper()[:6], "Unknown vendor")