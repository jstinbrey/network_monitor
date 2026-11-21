"""Bandwidth monitor: this PC's download and upload rates, and alerts when they pass a limit.

Windows counts every byte each adapter receives and sends. Reading the two
counters once a second and dividing the change by the time between the
readings gives the throughput; times 8, because 1 byte = 8 bits and line
speeds are quoted in bits per second (Mbps).
"""
import psutil

from netmonitor import config


def read_counters(adapter: str) -> tuple[int, int] | None:
    """(bytes received, bytes sent) since the adapter started, or None if it is gone."""
    counters = psutil.net_io_counters(pernic=True).get(adapter)
    return (counters.bytes_recv, counters.bytes_sent) if counters else None


class Meter:
    """Turns the adapter's byte counters into download and upload rates."""

    def __init__(self):
        self._last = None                         # (bytes_recv, bytes_sent, seconds)

    def update(self, recv: int, sent: int, now: float):
        """(down_mbps, up_mbps, new_recv_bytes, new_sent_bytes), or None for the first sample
        and after a counter reset (an adapter restart makes the counters go backwards)."""
        last, self._last = self._last, (recv, sent, now)
        if last is None or recv < last[0] or sent < last[1] or now <= last[2]:
            return None
        seconds = now - last[2]
        down, up = recv - last[0], sent - last[1]
        return down * 8 / seconds / 1e6, up * 8 / seconds / 1e6, down, up


class LimitAlarm:
    """Fires once when a value stays above its limit for `seconds` samples in a row; re-arms after it drops."""

    def __init__(self, seconds=config.BW_SUSTAIN_S):
        self.seconds, self.run, self.fired = seconds, 0, False

    def update(self, value: float, limit: float) -> bool:
        if not limit or value <= limit:           # a limit of 0 means off
            self.run, self.fired = 0, False
            return False
        self.run += 1
        if self.run >= self.seconds and not self.fired:
            self.fired = True
            return True
        return False


def cap_level(used_bytes: int, cap_gb: float) -> int:
    """0, 80 or 100: the highest daily-cap warning reached."""
    if not cap_gb:
        return 0
    share = used_bytes / (cap_gb * 1e9)
    return 100 if share >= 1 else 80 if share >= 0.8 else 0


def rate_text(mbps: float) -> str:
    """A rate as people read it: "12.4 Mbps", or "350 kbps" below 1 Mbps."""
    return f"{mbps:.1f} Mbps" if mbps >= 1 else f"{mbps * 1000:.0f} kbps"


def describe(down: float, up: float, today_bytes: int, limits: dict) -> tuple[str, str]:
    """("good" or "warn", the Connection view's verdict line) for the latest rates and today's use."""
    down_limit, up_limit, cap = limits["bw_down_mbps"], limits["bw_up_mbps"], limits["bw_daily_gb"]
    gb = today_bytes / 1e9
    over = [text for text, passed in [
        (f"download {rate_text(down)} (limit {down_limit:g} Mbps)", down_limit and down > down_limit),
        (f"upload {rate_text(up)} (limit {up_limit:g} Mbps)", up_limit and up > up_limit),
        (f"{gb:.2f} GB used today (cap {cap:g} GB)", cap_level(today_bytes, cap) == 100)] if passed]
    if over:
        return "warn", "Above the limit: " + ", ".join(over) + "."
    parts = [f"{rate_text(down)} down" + (f" (limit {down_limit:g} Mbps)" if down_limit else ""),
             f"{rate_text(up)} up" + (f" (limit {up_limit:g} Mbps)" if up_limit else ""),
             f"{gb:.2f} GB" + (f" of {cap:g} GB" if cap else "") + " today"]
    head = "Within limits" if down_limit or up_limit or cap else "No limits set"
    return "warn" if cap_level(today_bytes, cap) else "good", f"{head}: {', '.join(parts)}."
