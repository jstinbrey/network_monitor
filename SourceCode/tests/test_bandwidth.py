"""Tests for Step 7.3: bandwidth rates, limit alarms, the daily cap and the limit settings."""
from datetime import date
from types import SimpleNamespace

import pytest

from netmonitor import config, models, services, store
from netmonitor.core import bandwidth

LIMITS = {"bw_down_mbps": 20, "bw_up_mbps": 0, "bw_daily_gb": 5}


def test_meter_rates_first_sample_and_counter_reset():
    meter = bandwidth.Meter()
    assert meter.update(1_000_000, 500_000, 10.0) is None                    # nothing to compare with yet
    assert meter.update(2_250_000, 625_000, 11.0) == (10.0, 1.0, 1_250_000, 125_000)   # 10 Mbps down, 1 up
    assert meter.update(100, 100, 12.0) is None                              # the adapter restarted


def test_alarm_fires_on_the_10th_second_once_and_rearms_after_a_drop():
    alarm = bandwidth.LimitAlarm()
    assert [alarm.update(25, 20) for _ in range(12)] == [False] * 9 + [True, False, False]
    alarm.update(5, 20)                                                       # below the limit: re-armed
    assert [alarm.update(25, 20) for _ in range(10)][-1] is True
    assert not any(alarm.update(999, 0) for _ in range(20))                   # a limit of 0 is off


@pytest.mark.parametrize("used, level", [(3.95e9, 0), (4e9, 80), (5e9, 100), (9e9, 100)])
def test_cap_level(used, level):
    assert bandwidth.cap_level(used, 5) == level
    assert bandwidth.cap_level(used, 0) == 0


def test_describe():
    assert bandwidth.describe(12.4, 0.35, 1.1e9, LIMITS) == \
        ("good", "Within limits: 12.4 Mbps down (limit 20 Mbps), 350 kbps up, 1.10 GB of 5 GB today.")
    assert bandwidth.describe(25.3, 1.1, 1.1e9, LIMITS) == \
        ("warn", "Above the limit: download 25.3 Mbps (limit 20 Mbps).")
    assert bandwidth.describe(1, 1, 4.2e9, LIMITS)[0] == "warn"                # past 80% of the cap
    assert bandwidth.describe(1, 1, 0, config.SETTING_DEFAULTS)[1].startswith("No limits set")


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    """An empty database, the bandwidth monitor's state reset, a fake clock and a fake adapter."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(services, "_limits", {})
    monkeypatch.setattr(services, "_adapter", {"ip": None, "name": None, "meter": None})
    monkeypatch.setattr(services, "_alarms", {"bw_down_mbps": bandwidth.LimitAlarm(), "bw_up_mbps": bandwidth.LimitAlarm()})
    monkeypatch.setattr(services, "_today", {"day": None, "bytes": 0, "cap_level": 0})
    monkeypatch.setattr(services, "_unsaved", [0, 0])
    monkeypatch.setattr(services.netinfo, "get_local_ip", lambda: "192.168.1.20")
    monkeypatch.setattr(services.netinfo, "get_adapter", lambda ip: "Wi-Fi")
    fake = SimpleNamespace(clock=0, recv=0)
    monkeypatch.setattr(services, "time", SimpleNamespace(monotonic=lambda: fake.clock))
    monkeypatch.setattr(services.bandwidth, "read_counters", lambda adapter: (fake.recv, 0))
    return fake


def run(fake, seconds, bytes_per_second):
    samples = []
    for second in range(seconds):
        fake.clock, fake.recv = second, second * bytes_per_second
        samples.append(services.bandwidth_sample())
    return samples


def test_a_sustained_download_alerts_once_and_the_bytes_are_saved(fresh):
    store.save_settings({"bw_down_mbps": 5})
    samples = run(fresh, 15, 1_250_000)                                       # 10 Mbps for 14 s
    assert samples[0] is None and samples[1].down_mbps == 10
    alerts = [sample.alerts for sample in samples[1:]]
    assert alerts[9] == ["Download above the 5 Mbps limit for 10 s: 10.0 Mbps."] and sum(map(len, alerts)) == 1
    services.flush_usage()
    services.flush_usage()                                                    # nothing new: nothing added
    assert store.get_usage(date.today().isoformat()) == 14 * 1_250_000 == samples[-1].today_bytes


def test_the_daily_cap_warns_at_80_and_at_100_percent_once_each(fresh):
    store.save_settings({"bw_daily_gb": 0.001})                               # 1 MB
    alerts = [a for sample in run(fresh, 6, 400_000)[1:] for a in sample.alerts]
    assert alerts == ["80% of today's 0.001 GB cap used: 0.00 GB.", "100% of today's 0.001 GB cap used: 0.00 GB."]


def test_limits_are_admin_only_and_must_be_numbers_of_0_or_more(fresh, monkeypatch):
    monkeypatch.setattr(services, "_user", models.User("bob", models.USER))
    with pytest.raises(PermissionError):
        services.save_settings({"bw_down_mbps": "5"})
    monkeypatch.setattr(services, "_user", models.User("admin", models.ADMIN))
    for bad in ({"bw_down_mbps": "-1"}, {"bw_down_mbps": "abc"}, {"bw_down_mbps": ""}, {"bw_down_mbps": "nan"},
                {"watch": "5"}, {"watch_min": "0.5"}, {}):                 # watch: at least 1 minute
        with pytest.raises(ValueError):
            services.save_settings(bad)
    assert services.save_settings({"bw_down_mbps": " 20 ", "bw_daily_gb": "5"}) == LIMITS | {"watch_min": 5}
    assert services._limits == LIMITS | {"watch_min": 5}                                   # the monitor uses them at once
