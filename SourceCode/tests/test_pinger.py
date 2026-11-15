""" Test for core/pinger.py (Feature 2: connectivity testing)."""
import pytest

from netmonitor import models
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