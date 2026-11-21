"""Dashboard view: the state of the whole network at a glance."""
import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.widgets.recommendation_card import RecommendationCard
from netmonitor.gui.widgets.verdict_card import VerdictCard
from netmonitor.gui.worker import post, run_async

CARDS = ["Devices", "Reachable", "Average latency", "Health score"]
MAX_BARS = 15              # more bars than this cannot be read
TOP_RECOMMENDATIONS = 3


class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(self, text="Dashboard", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=(0, 12))
        # A User may not scan, so their button only pings the devices already known.
        self.scan_button = ctk.CTkButton(bar, text="Scan and refresh" if app.is_admin else "Refresh",
                                         command=self.scan_and_refresh)
        self.scan_button.pack(side="left")
        self.diagnose_button = ctk.CTkButton(bar, text="Diagnose network", command=self.diagnose)
        self.diagnose_button.pack(side="left", padx=(8, 0))
        self.status = ctk.CTkLabel(bar, text="", text_color=theme.MUTED)
        self.status.pack(side="left", padx=12)

        self.verdict = VerdictCard(self)
        self.verdict.pack(fill="x", padx=theme.PAD, pady=(0, 12))

        # Four stat cards: a small muted title above a large value.
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD)
        self.values = {}
        for title in CARDS:
            card = ctk.CTkFrame(row)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(card, text=title, text_color=theme.MUTED).pack(anchor="w", padx=12, pady=(8, 0))
            self.values[title] = ctk.CTkLabel(card, text="-", font=theme.TITLE_FONT)
            self.values[title].pack(anchor="w", padx=12, pady=(0, 8))

        self.chart = LatencyChart(self)
        self.chart.pack(fill="x", padx=theme.PAD, pady=12)

        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x", padx=theme.PAD)
        ctk.CTkLabel(heading, text="Top recommendations", font=("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkButton(heading, text="View all", width=90, command=lambda: app.show("Security")).pack(side="right")
        self.recommendations = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.recommendations.pack(fill="both", expand=True, padx=theme.PAD, pady=(4, theme.PAD))

    def on_show(self):
        """Reload from stored results each time the view is opened."""
        run_async(services.dashboard, on_done=self._show, on_error=self._show_error)

    def scan_and_refresh(self):
        """Find the devices (Feature 1), ping each one (Feature 2), then show the new totals."""
        self.scan_button.configure(state="disabled")
        if not self.app.is_admin:
            self.status.configure(text="Pinging every device...", text_color=theme.MUTED)
            run_async(services.refresh_dashboard, on_done=self._show, on_error=self._show_error)
            return
        self.status.configure(text="Scanning...", text_color=theme.MUTED)
        # Progress comes from the scan's own thread, so post() carries it to the UI thread.
        run_async(services.scan_and_refresh, lambda done, total: post(self._show_progress, (done, total)),
                  on_done=self._show, on_error=self._show_error)

    def diagnose(self):
        """Test this PC, the router, the internet and DNS in turn, and show where a problem is."""
        self.diagnose_button.configure(state="disabled")
        self.verdict.start()
        # Each layer is reported from the worker thread, so post() carries it to the UI thread.
        run_async(services.diagnose, lambda step: post(self.verdict.add_step, step),
                  on_done=self._show_verdict, on_error=self._diagnose_failed)

    def _show_verdict(self, verdict):
        self.verdict.show(verdict)
        self.diagnose_button.configure(state="normal")

    def _diagnose_failed(self, error):
        self.verdict.show_error(error)
        self.diagnose_button.configure(state="normal")

    def _show_progress(self, progress):
        done, total = progress
        self.status.configure(text=f"Scanning {done} / {total}" if done < total else "Pinging every device...")

    def _show(self, data):
        summary, stats, recommendations = data
        self.scan_button.configure(state="normal")
        self.status.configure(text="" if summary.devices else "Run a scan to begin.", text_color=theme.MUTED)

        score = summary.health_score
        score_color = theme.GREEN if score >= 80 else theme.AMBER if score >= 50 else theme.RED
        latency = summary.network_avg_ms
        shown = {"Devices": (summary.devices, None),
                 "Reachable": (f"{summary.reachable} / {summary.devices}", None),
                 "Average latency": ("No data" if latency is None else f"{latency:g} ms", None),
                 "Health score": (f"{score} / 100", score_color)}
        for title, (text, color) in shown.items():
            if not summary.devices:
                text, color = "-", None            # no scan yet: do not show a red 0 / 100
            self.values[title].configure(text=text, text_color=color or ("gray10", "gray90"))

        replied = [s for s in stats if s.avg_ms is not None][:MAX_BARS]
        self.chart.plot(["." + s.ip.rsplit(".", 1)[1] for s in replied], [s.avg_ms for s in replied],
                        "Average latency per host (click a bar for details)" if replied
                        else "No ping results yet", on_pick=lambda i: self.app.open_device(replied[i].ip))

        for card in self.recommendations.winfo_children():
            card.destroy()
        for rec in recommendations[:TOP_RECOMMENDATIONS]:
            RecommendationCard(self.recommendations, rec, on_open=self.app.open_device).pack(fill="x", pady=4)

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
        self.scan_button.configure(state="normal")