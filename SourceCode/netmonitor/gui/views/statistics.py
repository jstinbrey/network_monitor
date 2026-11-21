"""Statistics view (Feature 3): latency, packet loss and jitter for every known device."""
import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.host_table import HostTable
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import run_async
from netmonitor.models import STATUS_LABELS


def ms(value):
    return "No data" if value is None else f"{value:g} ms"


class StatisticsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="Statistics", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=(0, 12))
        self.refresh_button = ctk.CTkButton(bar, text="Refresh all", command=self.refresh)
        self.refresh_button.pack(side="left")
        self.status = ctk.CTkLabel(bar, text="", text_color=theme.MUTED)
        self.status.pack(side="left", padx=12)

        # The first five columns are the ones the project brief requires, in its order.
        self.table = HostTable(self, [("hostname", "Hostname", 190), ("ip", "IP Address", 130),
                                      ("avg", "Average Latency", 130), ("max", "Maximum Latency", 140),
                                      ("loss", "Packet Loss", 100), ("jitter", "Jitter", 90),
                                      ("samples", "Replies", 70), ("status", "Status", 190)])
        self.table.pack(fill="both", expand=True, padx=theme.PAD)
        self.table.tree.bind("<<TreeviewSelect>>", self._load_history)
        self.table.on_open(app.open_device)

        self.chart = LatencyChart(self)
        self.chart.pack(fill="x", padx=theme.PAD, pady=theme.PAD)
        self.chart.plot([], [], "Select a device to see its history")

    def on_show(self):
        """Reload from stored history each time the view is opened."""
        run_async(services.stats, on_done=self._show_stats, on_error=self._show_error)

    def refresh(self):
        """Ping every known device again, then reload."""
        self.refresh_button.configure(state="disabled")
        self.status.configure(text="Pinging every device...", text_color=theme.MUTED)
        run_async(services.refresh_all, on_done=self._refreshed, on_error=self._refresh_failed)

    def _refreshed(self, stats):
        self._show_stats(stats)
        self.refresh_button.configure(state="normal")

    def _refresh_failed(self, error):
        self._show_error(error)
        self.refresh_button.configure(state="normal")

    def _show_stats(self, stats):
        self.table.set_rows([{
            "hostname": s.hostname, "ip": s.ip, "avg": ms(s.avg_ms), "max": ms(s.max_ms),
            "loss": "No data" if s.loss_pct is None else f"{s.loss_pct:g}%",
            "jitter": ms(s.jitter_ms), "samples": s.samples,
            "status": STATUS_LABELS[s.status], "tag": theme.STATUS_TAGS.get(s.status, ""),
        } for s in stats])
        worst = max((s for s in stats if s.avg_ms is not None), key=lambda s: s.avg_ms, default=None)
        if worst:
            self.status.configure(text=f"Worst host: {worst.hostname} ({worst.ip}), {worst.avg_ms:g} ms average, "
                                       f"{worst.loss_pct:g}% loss.  Click a row for its history.",
                                  text_color=theme.TAG_COLORS.get(theme.STATUS_TAGS.get(worst.status), theme.MUTED))
        else:
            self.status.configure(text="No ping results yet: click Refresh all." if stats
                                  else "No devices yet. Run a scan in the Devices view.", text_color=theme.MUTED)

    def _load_history(self, event):
        if self.table.selected():
            run_async(services.history, self.table.selected()[0], on_done=self._show_history, on_error=self._show_error)

    def _show_history(self, results):
        if results:
            self.chart.plot([r.timestamp[11:] for r in results], [r.avg_ms or 0 for r in results],
                            f"Average latency per test: {results[0].ip}")
        else:
            self.chart.plot([], [], "No ping tests stored for this device yet")

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)