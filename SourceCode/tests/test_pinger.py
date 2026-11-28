""" Test for core/pinger.py (Feature 2: connectivity testing)."""
import threading
import time

import pytest

from netmonitor import models, services
from netmonitor.core import pinger

OUTPUT = """
Pinging 192.168.1.1 with 32 bytes of data:
Reply from 192.168.1.1: bytes=32 time=3ms TTL=64
Reply from 192.168.1.1: bytes=32 time<1ms TTL=64
Request timed out.
Reply from 192.168.1.37: Destination host unreachable.

Ping statistics for192.168.1.1:
    Packets: Sent = 4, Received = 3, Lost = 1 (25% loss),
"""

def test_only_lines_with_a_time_count():
    assert pinger.parse_rtts(OUTPUT) == [3.0, 0.5]

def test_loss_and_status():
    result = pinger.build_result("192.168.1.1", 4, [3.0, 5.0, 4.0])
    assert (result.loss_pct, result.avg_ms, result.max_ms) == (25.0, 4.0, 5.0)
    assert result.status == models.DEGRADED
    assert pinger.build_result("192.168.1.1", 4, [1.0, 2.0, 3.0, 2.0]).status == models.ONLINE


def test_no_replies_is_offline():
    result = pinger.build_result("192.168.1.9", 4, [])
    assert (result.loss_pct, result.avg_ms, result.status) == (100.0, None, models.OFFLINE)


@pytest.mark.parametrize("bad", ["1.1.1.1; dir", "abc", "999.1.1.1", ""])
def test_bad_input_is_rejected(bad):
    with pytest.raises(ValueError):
        pinger.ping(bad)


def test_link_local_ipv6_requires_a_numeric_scope():
    assert pinger.validate_ip("FE80::A%015", 6) == "fe80::a%15"
    with pytest.raises(ValueError, match="interface index"):
        pinger.validate_ip("fe80::a", 6)
    with pytest.raises(ValueError, match="interface index"):
        pinger.validate_ip("fe80::a%Wi-Fi", 6)
    with pytest.raises(ValueError, match="switch the address family"):
        pinger.validate_ip("::1", 4)


def test_a_real_ipv6_ping_to_windows_loopback():
    result = pinger.ping("::1", 1)
    assert result.ip == "::1" and result.received == 1


# --- Step 7.2: continuous ping ------------------------------------------------
@pytest.mark.parametrize("line, expected", [
    ("Reply from 1.1.1.1: bytes=32 time=12ms TTL=57", (True, 12.0)),
    ("Reply from 127.0.0.1: bytes=32 time<1ms TTL=128", (True, 0.5)),
    ("Request timed out.", (True, None)),
    ("Reply from 192.168.1.37: Destination host unreachable.", (True, None)),   # a reply line with no time: lost
    ("General failure.", (True, None)),
    ("PING: transmit failed. General failure.", (True, None)),
    ("Pinging 1.1.1.1 with 32 bytes of data:", (False, None)),
    ("", (False, None)),
])
def test_parse_reply(line, expected):
    assert pinger.parse_reply(line) == expected


def test_session_totals_and_longest_outage():
    session = pinger.PingSession("192.168.1.1")
    for rtt in [2, 3, None, None, None, 4]:
        session.add(rtt)
    r = session.result()
    assert (r.sent, r.received, r.loss_pct, r.min_ms, r.avg_ms, r.max_ms) == (6, 3, 50.0, 2, 3.0, 4)
    assert (session.longest_outage, session.current_outage, session.jitter_ms) == (3, 0, 1.0)
    status, sentence = session.verdict()
    assert status == "warn" and "3 lost in a row" in sentence


def test_a_real_continuous_ping_and_stop_ends_it():
    replies = []
    handle = pinger.ContinuousPing("127.0.0.1", lambda rtt, line: replies.append(rtt))
    time.sleep(3)
    handle.stop()
    handle.stop()                                   # safe twice
    assert 3 <= len(replies) <= 5 and None not in replies
    assert handle.process.poll() is not None        # no ping.exe is left running


def test_stop_stores_the_session_and_stop_all_does_not(monkeypatch):
    recorded = []
    monkeypatch.setattr(services, "_record", lambda results, started: recorded.extend(results))
    monkeypatch.setattr(services.netinfo, "get_local_ip", lambda: "127.0.0.1")
    info = models.NetworkInfo("pc", "127.0.0.1", "255.255.255.0", "127.0.0.0/24",
                              "127.0.0.1", "127.0.0.254", None, 254)
    started = services._Network(info, "loopback", {})
    for stop in (services.stop_continuous_ping, lambda handle: services.stop_all()):
        got = threading.Event()
        prepared = started, pinger.PingSession("127.0.0.1")
        handle = services.start_continuous_ping(prepared, lambda session, rtt, line: got.set())
        assert got.wait(5)
        stop(handle)
        assert handle.process.poll() is not None and handle not in services._running
    assert len(recorded) == 1 and recorded[0].received >= 1


def test_stop_children_ends_a_running_ping_and_its_caller_raises():
    errors = []

    def long_ping():
        try:
            pinger.ping("192.0.2.1", 10)        # a documentation address: about 10 s of timeouts
        except RuntimeError as error:
            errors.append(error)
    thread = threading.Thread(target=long_ping)
    thread.start()
    time.sleep(0.5)
    started = time.time()
    pinger.stop_children()                  # what closing the window does
    thread.join(5)
    assert errors and time.time() - started < 2 and not pinger._children
