"""Tests for core/diagnosis.py (Step 6.5): one Measurements per verdict rule, and the DNS packet."""
import struct

import pytest

from netmonitor import models
from netmonitor.core import diagnosis
from netmonitor.models import HostStats, Measurements


def pinged(ip, avg=5.0, loss=0.0, jitter=1.0):
    """A host's statistics after the diagnosis pings; avg None means no replies at all."""
    return HostStats(ip, "Unknown", 10, avg, avg, avg, jitter, loss, models.ONLINE)


ROUTER, NET = pinged("192.168.1.1", 3.0), pinged("1.1.1.1", 40.0)
HEALTHY = dict(local_ip="192.168.1.6", gateway=ROUTER, internet=NET, dns_server="192.168.1.1",
               dns_ms=12.0, dns_public_ms=30.0)


@pytest.mark.parametrize("changes, status, where", [
    (dict(local_ip=None), "bad", "This PC"),                                              # 1
    (dict(local_ip="169.254.10.20"), "bad", "Router"),                                    # 2 DHCP failed
    (dict(gateway=pinged("192.168.1.1", None, 100.0, None)), "bad", "Wi-Fi / LAN"),       # 3
    (dict(gateway=None), "bad", "Wi-Fi / LAN"),                                           # 3 no gateway at all
    (dict(gateway=pinged("192.168.1.1", 3.0, 20.0)), "warn", "Wi-Fi / LAN"),              # 4 loss
    (dict(gateway=pinged("192.168.1.1", 80.0)), "warn", "Wi-Fi / LAN"),                   # 4 slow
    (dict(gateway=pinged("192.168.1.1", 9.0, 0.0, 45.0)), "warn", "Wi-Fi / LAN"),         # 4 jitter
    (dict(internet=pinged("1.1.1.1", None, 100.0, None)), "bad", "ISP"),                  # 5
    (dict(internet=pinged("1.1.1.1", 220.0)), "warn", "ISP"),                             # 6
    (dict(dns_ms=None), "bad", "DNS"),                                                    # 7 only 1.1.1.1 answers
    (dict(dns_ms=None, dns_public_ms=None), "bad", "DNS"),                                # 8
    (dict(dns_ms=450.0), "warn", "DNS"),                                                  # 9
    (dict(), "good", "None"),                                                             # 10
])
def test_each_rule(changes, status, where):
    result = diagnosis.verdict(Measurements(**HEALTHY | changes))
    assert (result.status, result.where) == (status, where)


def test_the_first_matching_rule_wins_and_quotes_its_numbers():
    both_bad = diagnosis.verdict(Measurements(**HEALTHY | dict(gateway=pinged("192.168.1.1", 80.0), dns_ms=None)))
    assert both_bad.where == "Wi-Fi / LAN"                     # the router rule comes before the DNS rules
    healthy = diagnosis.verdict(Measurements(**HEALTHY))
    assert healthy.evidence == ["Router 192.168.1.1: 0% loss, 3 ms average, 1 ms jitter.",
                                "Internet 1.1.1.1: 0% loss, 40 ms average, 1 ms jitter.",
                                "DNS server 192.168.1.1: answered in 12 ms.", "1.1.1.1: answered in 30 ms."]


def test_build_query_is_the_rfc_1035_packet():
    assert diagnosis.build_query("example.com", 0x1234) == bytes.fromhex("1234 0100 0001 0000 0000 0000") + \
        b"\x07example\x03com\x00" + bytes.fromhex("0001 0001")


@pytest.mark.parametrize("reply, expected", [
    (struct.pack(">HHHHHH", 0x1234, 0x8180, 1, 1, 0, 0), True),     # our ID, no error, one answer
    (struct.pack(">HHHHHH", 0x9999, 0x8180, 1, 1, 0, 0), False),    # someone else's ID
    (struct.pack(">HHHHHH", 0x1234, 0x8183, 1, 0, 0, 0), False),    # rcode 3: the name does not exist
    (b"\x12\x34", False),                                            # too short to be DNS
])
def test_only_the_answer_to_our_query_counts(reply, expected):
    assert diagnosis.is_answer(reply, 0x1234) == expected
