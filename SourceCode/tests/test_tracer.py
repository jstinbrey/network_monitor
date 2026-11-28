"""Tests for core/tracer.py (Step 6.4: traceroute). Fixtures are real tracert output from this PC."""
import threading

import pytest
from conftest import FIXTURES

from netmonitor import services
from netmonitor.core import tracer
from netmonitor.models import Hop


def hops(name):
    return [hop for line in (FIXTURES / name).read_text().splitlines() if (hop := tracer.parse_hop(line))]


def test_a_complete_trace_parses_every_hop():
    trace = hops("tracert_ok.txt")                  # header, blank lines and "Trace complete." are skipped
    assert [h.number for h in trace] == list(range(1, 10))
    assert trace[0] == Hop(1, [1.0, 1.0, 2.0], "192.168.1.1")
    assert trace[4] == Hop(5, [None, 37.0, 36.0], "210.213.134.106")
    assert trace[-1].address == "1.1.1.1"


def test_less_than_one_ms_and_timeouts():
    assert tracer.parse_hop("  1    <1 ms    <1 ms    <1 ms  127.0.0.1").times_ms == [0.5, 0.5, 0.5]
    lost = hops("tracert_unreachable.txt")[-1]
    assert (lost.number, lost.address, lost.loss_pct, lost.avg_ms) == (15, None, 100.0, None)


def test_ipv6_hop_reaches_a_link_local_target_with_an_interface_index():
    hop = tracer.parse_hop("  1    <1 ms    <1 ms    <1 ms  fe80::1")
    assert hop.address == "fe80::1"
    assert tracer.analyse([hop], "fe80::1%15")[0] == "good"


def test_loss_and_average_of_one_hop():
    hop = Hop(5, [None, 37.0, 36.0], "210.213.134.106")
    assert (hop.loss_pct, hop.avg_ms) == (33.3, 36.5)


@pytest.mark.parametrize("hop, expected", [
    (Hop(1, [1.0, 1.0, 1.0], "192.168.1.1"), "your router"),
    (Hop(2, [5.0, 5.0, 5.0], "192.168.0.1"), "ISP access network"),
    (Hop(2, [5.0, 5.0, 5.0], "100.64.3.1"), "ISP access network"),       # CGNAT: not "private" to Python
    (Hop(3, [9.0, 9.0, 9.0], "49.145.48.1"), "internet"),
    (Hop(4, [None, None, None], None), "unknown"),
])
def test_segment(hop, expected):
    assert tracer.segment(hop) == expected


def test_reached_with_middle_hop_loss_is_good():
    status, sentence = tracer.analyse(hops("tracert_ok.txt"), "1.1.1.1")
    assert status == "good" and sentence.startswith("1.1.1.1 reached in 9 hops")
    assert "routers limiting traceroute answers" in sentence


def test_not_reached_names_the_last_hop_that_answered():
    assert tracer.analyse(hops("tracert_unreachable.txt"), "192.0.2.1") == \
        ("warn", "The route stops after hop 2 (internet); 192.0.2.1 was not reached.")


def test_a_lasting_rise_is_flagged_and_a_slow_router_is_not():
    lasting = [Hop(1, [1.0] * 3, "192.168.1.1"), Hop(2, [5.0] * 3, "10.0.0.1"),
               Hop(3, [80.0] * 3, "8.8.4.4"), Hop(4, [85.0] * 3, "8.8.8.8")]
    assert tracer.analyse(lasting, "8.8.8.8") == \
        ("warn", "Latency rises by 75 ms at hop 3 (internet) and stays high up to 8.8.8.8.")
    slow_router = [Hop(1, [1.0] * 3, "192.168.1.1"), Hop(2, [90.0] * 3, "10.0.0.1"), Hop(3, [10.0] * 3, "8.8.8.8")]
    assert tracer.analyse(slow_router, "8.8.8.8")[0] == "good"


def test_a_real_trace_to_this_pc_and_stop_ends_tracert():
    done, found = threading.Event(), []
    tracer.Traceroute("127.0.0.1", found.append, lambda hops: done.set()).start()
    assert done.wait(15) and [h.address for h in found] == ["127.0.0.1"]

    stopped = threading.Event()
    trace = tracer.Traceroute("192.0.2.1", lambda hop: None, lambda hops: stopped.set())   # would take ~20 s
    trace.start()
    trace.stop()
    assert stopped.wait(5) and trace._process.poll() is not None    # no tracert.exe is left running


def test_a_real_ipv6_trace_to_windows_loopback():
    done, found = threading.Event(), []
    tracer.Traceroute("::1", found.append, lambda _: done.set()).start()
    assert done.wait(15) and [hop.address for hop in found] == ["::1"]


def test_an_unknown_target_is_refused():
    with pytest.raises(ValueError):
        services.start_traceroute("   ", None, None)
