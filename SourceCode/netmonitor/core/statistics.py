"""Feature 3 (Network Statistics): per-host latency, jitter and packet loss, and a network summary.

These are pure calculations over stored ping results; nothing here touches
the network or the database, which keeps every formula easy to test.
"""
from statistics import mean, pstdev

from netmonitor import config, models
from netmonitor.models import Device, HostStats, NetworkSummary, PingResult


def host_stats(device: Device, results: list[PingResult]) -> HostStats:
    """Combine every ping result for one host (oldest first) into one row of statistics."""
    name = device.alias or device.hostname           # a name the admin gave wins
    if not results:
        return HostStats(device.ip, name, 0, None, None, None, None, None, models.NO_DATA)
    rtts = [rtt for result in results for rtt in result.rtts_ms]
    sent = sum(result.sent for result in results)
    # Jitter: how much the delay changes from one reply to the next, on average.
    changes = [abs(later - earlier) for earlier, later in zip(rtts, rtts[1:])]
    return HostStats(
        ip=device.ip, hostname=name, samples=len(rtts),
        avg_ms=round(mean(rtts), 1) if rtts else None,
        max_ms=max(rtts, default=None),
        min_ms=min(rtts, default=None),
        jitter_ms=round(mean(changes), 1) if changes else None,
        loss_pct=round((sent - len(rtts)) / sent * 100, 1),   # lost / sent over all runs
        status=results[-1].status,                             # the most recent test decides
    )


def baseline(rtts: list[float]) -> tuple[float, float] | None:
    """(mean, standard deviation) of a host's recent replies, or None until there are enough."""
    recent = rtts[-config.BASELINE_WINDOW:]
    if len(recent) < config.BASELINE_MIN_SAMPLES:
        return None
    return mean(recent), pstdev(recent)


def is_spike(rtt: float, base: tuple[float, float]) -> bool:
    """Above mean + 3σ, and at least 20 ms above the mean: a LAN host with σ = 0.3 ms
    must not call a 3 ms reply a spike."""
    mu, sigma = base
    return rtt > max(mu + config.SPIKE_SIGMAS * sigma, mu + config.SPIKE_FLOOR_MS)


def summary(stats: list[HostStats]) -> NetworkSummary:
    """Network-wide totals and a 0 to 100 health score.

    Health score: start at 100; subtract 50 x the share of unreachable
    devices; subtract the average packet loss % of hosts that replied (at
    most 30); subtract (average latency - 50) / 5 when it is above 50 ms
    (at most 20).
    """
    replied = [s for s in stats if s.avg_ms is not None]
    unreachable = sum(s.status == models.OFFLINE for s in stats)
    network_avg = round(mean(s.avg_ms for s in replied), 1) if replied else None
    score = 0
    if stats:
        score = 100 - 50 * unreachable / len(stats)
    if replied:
        score -= min(30, mean(s.loss_pct for s in replied))
        score -= min(20, max(0, network_avg - 50) / 5)
    return NetworkSummary(
        devices=len(stats), reachable=len(stats) - unreachable, unreachable=unreachable,
        network_avg_ms=network_avg,
        best_host=min(replied, key=lambda s: s.avg_ms).ip if replied else None,
        worst_host=max(replied, key=lambda s: s.avg_ms).ip if replied else None,
        health_score=max(0, round(score)),
    )