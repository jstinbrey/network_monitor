"""Tests for core/statistics.py (Feature 3). Expected values are worked out by hand."""
from netmonitor import models
from netmonitor.core import pinger, statistics
from netmonitor.models import Device

PHONE = Device(ip="192.168.1.5", hostname="phone")


def runs(*reply_times):
    """One 4-packet ping result per list of reply times."""
    return [pinger.build_result(PHONE.ip, 4, rtts) for rtts in reply_times]


def host(ip, avg, loss=0.0, status=models.ONLINE):
    return models.HostStats(ip, "pc", 4, avg, avg, avg, 0.0, loss, status)


def test_average_max_min_and_jitter():
    s = statistics.host_stats(PHONE, runs([10.0, 14.0, 12.0, 12.0]))
    # jitter: |14-10| + |12-14| + |12-12| = 6, over 3 gaps = 2.0
    assert (s.avg_ms, s.max_ms, s.min_ms, s.jitter_ms, s.loss_pct, s.samples) == (12.0, 14.0, 10.0, 2.0, 0.0, 4)
    assert s.hostname == "phone"


def test_loss_is_counted_across_runs():
    s = statistics.host_stats(PHONE, runs([1.0, 2.0, 3.0, 4.0], [1.0, 2.0]))   # 6 of 8 received
    assert s.loss_pct == 25.0
    assert s.status == models.DEGRADED          # the latest run lost packets


def test_never_pinged_host_has_no_data():
    s = statistics.host_stats(PHONE, [])
    assert (s.status, s.avg_ms, s.loss_pct, s.jitter_ms) == (models.NO_DATA, None, None, None)


def test_host_that_never_replied():
    s = statistics.host_stats(PHONE, runs([]))
    assert (s.avg_ms, s.max_ms, s.jitter_ms, s.loss_pct, s.status) == (None, None, None, 100.0, models.OFFLINE)


def test_summary_with_one_unreachable_host():
    s = statistics.summary([host("192.168.1.1", 10.0), host("192.168.1.2", 20.0),
                            host("192.168.1.3", None, 100.0, models.OFFLINE)])
    assert (s.devices, s.reachable, s.unreachable, s.network_avg_ms) == (3, 2, 1, 15.0)
    assert (s.best_host, s.worst_host) == ("192.168.1.1", "192.168.1.2")
    assert s.health_score == 83                 # 100 - 50 * 1/3


def test_health_score_penalties():
    assert statistics.summary([host("192.168.1.1", 10.0)]).health_score == 100
    assert statistics.summary([host("192.168.1.1", 150.0)]).health_score == 80            # latency: (150-50)/5 = 20
    assert statistics.summary([host("192.168.1.1", 10.0, loss=25.0)]).health_score == 75  # loss: 25


def test_summary_of_nothing():
    s = statistics.summary([])
    assert (s.devices, s.network_avg_ms, s.best_host, s.health_score) == (0, None, None, 0)