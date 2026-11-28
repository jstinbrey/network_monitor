"""Statistics view (Feature 3): latency, packet loss and jitter for every known device."""
from statistics import fmean

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
        actions, _ = theme.page_heading(self, "Statistics", "Latency, loss, and jitter from every stored test")
        self.refresh_button = theme.ActionButton(actions, text="Re-test devices", width=150, height=40,
                                                 corner_radius=20, image=theme.icon("refresh", size=16),
                                                 command=self.refresh)
        self.refresh_button.pack()
        summary = ctk.CTkFrame(self, fg_color=theme.SURFACE)
        summary.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        values = ctk.CTkFrame(summary, fg_color="transparent")
        values.pack(side="right", padx=(8, 16), pady=12)
        self.rollup = {}
        for name in ("Network average", "Avg. packet loss", "Avg. jitter"):
            metric = ctk.CTkFrame(values, fg_color="transparent")
            metric.pack(side="left", padx=(8, 0))
            ctk.CTkLabel(metric, text=name, text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(anchor="w")
            self.rollup[name] = ctk.CTkLabel(metric, text="—", font=theme.MONO_FONT)
            self.rollup[name].pack(anchor="w")
        theme.icon_badge(summary, "alert", 36, theme.AMBER_SOFT, theme.AMBER, 17).pack(
            side="left", padx=(16, 10), pady=12)
        body = ctk.CTkFrame(summary, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True, pady=10, padx=(0, 8))
        self.headline = theme.WrappedLabel(body, text="Stored tests", font=theme.CARD_FONT)
        self.headline.pack(fill="x")
        self.status = theme.WrappedLabel(body, text="Loading tests…", text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.status.pack(fill="x")

        # The first five columns are the ones the project brief requires, in its order.
        self.table = HostTable(self, [("hostname", "Hostname", 134), ("ip", "IP Address", 102),
                                      ("avg", "Average", 75), ("max", "Maximum", 75),
                                      ("loss", "Packet loss", 78), ("jitter", "Jitter", 50),
                                      ("samples", "Replies", 57), ("status", "Status", 125)])
        self.table.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, 12))
        self.table.tree.bind("<<TreeviewSelect>>", self._load_history)
        self.table.on_open(app.open_device)

        self.chart = LatencyChart(self, height=1.55)
        self.caption = theme.WrappedLabel(self, text="Select a device to see its history. Jitter is the average change "
                                                     "between replies.", text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.caption.pack(side="bottom", fill="x", padx=theme.PAD, pady=(0, 10))

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
        for label, attribute, unit in zip(self.rollup.values(), ("avg_ms", "loss_pct", "jitter_ms"),
                                          (" ms", "%", " ms")):
            measured = [getattr(row, attribute) for row in stats if getattr(row, attribute) is not None]
            label.configure(text=f"{fmean(measured):.1f}{unit}" if measured else "—")
        if worst:
            self.headline.configure(text=f"{worst.hostname or worst.ip} is the slowest device")
            self.status.configure(text=f"{worst.avg_ms:g} ms average · {worst.loss_pct:g}% loss · "
                                       f"{worst.samples} replies", text_color=theme.MUTED)
        else:
            self.headline.configure(text="No stored replies yet")
            self.status.configure(text="Re-test devices to collect measurements." if stats
                                  else "No devices yet. Run a scan in the Devices view.", text_color=theme.MUTED)

    def _load_history(self, event):
        selected = self.table.selected()
        if not selected:
            self.chart.pack_forget()
            return
        ip = selected[0]
        run_async(services.history, ip, on_done=lambda results: self._show_history(results)
                  if self.table.selected()[:1] == [ip] else None, on_error=self._show_error)

    def _show_history(self, results):
        self.chart.pack(side="bottom", fill="x", padx=theme.PAD, pady=(0, 8))
        if results:
            self.chart.plot([r.timestamp[11:] for r in results], [r.avg_ms or 0 for r in results],
                            f"Average latency per test: {results[0].ip}")
        else:
            self.chart.plot([], [], "No ping tests stored for this device yet")

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
