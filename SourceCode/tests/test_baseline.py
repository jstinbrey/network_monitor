"""Tests for Step 7.4: a host judged against its own history (mean and standard deviation)."""
from netmonitor import config, services, store
from netmonitor.core import advisor, pinger, statistics
from netmonitor.models import Device


def test_no_baseline_until_30_replies():
    assert statistics.baseline([5.0] * 29) is None
    assert statistics.baseline([5.0] * 30) == (5.0, 0.0)


def test_spikes_and_the_20_ms_floor():
    steady = [40.0, 42.0, 38.0, 41.0, 39.0] * 6
    base = statistics.baseline(steady)
    assert not any(statistics.is_spike(rtt, base) for rtt in steady)
    assert statistics.is_spike(120.0, base)
    lan = (2.0, 0.3)                              # a LAN host: 3σ alone would call 5 ms a spike
    assert not statistics.is_spike(5.0, lan) and statistics.is_spike(25.0, lan)


def test_a_continuous_ping_learns_its_baseline_then_counts_spikes():
    session = pinger.PingSession("192.168.1.1")
    session.history = [4.0] * 25                 # stored replies, loaded when the session starts
    for _ in range(4):
        session.add(4.0)
    assert session.baseline() is None and session.learned() == 29
    session.add(80.0)                             # still learning: not a spike, but it now counts
    assert not session.last_spike
    session.add(90.0)
    assert session.last_spike and session.spikes == 1
    assert "1 slower than usual" in session.verdict()[1]


def test_slower_than_usual_is_a_warning():
    pc = Device(ip="192.168.1.20", hostname="pc")

    def performance(baselines):
        return [(r.severity, r.title, r.detail) for r in advisor.recommend([pc], [], baselines=baselines)
                if r.category == "Performance"]
    assert performance({pc.ip: (85.0, (4.0, 1.0))}) == \
        [("warning", "pc (192.168.1.20) is slower than usual", "Its latest test averaged 85 ms against a usual 4.0 ms.")]
    assert performance({pc.ip: (6.0, (4.0, 1.0))}) == []          # within the floor
    assert performance({pc.ip: (85.0, None)}) == []               # no baseline yet


def test_baselines_judge_the_latest_test_against_every_earlier_reply(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    network, pc = "192.168.1.0/24 via aa", Device(ip="192.168.1.20")
    for rtts in ([4.0] * 10, [4.0] * 10, [4.0] * 10, [85.0] * 4):
        store.save_ping(pinger.build_result(pc.ip, len(rtts), rtts), network)
    assert services._baselines([pc], network) == {pc.ip: (85.0, (4.0, 0.0))}
