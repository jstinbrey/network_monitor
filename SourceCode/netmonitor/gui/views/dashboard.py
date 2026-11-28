"""Dashboard view with the network verdict, measurements, and findings."""
from collections import Counter

import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.widgets.recommendation_card import SEVERITY_COLORS, SEVERITY_SOFT, badge
from netmonitor.gui.widgets.verdict_card import VerdictCard
from netmonitor.gui.worker import post, run_async

CARDS = {"Devices": "devices", "Reachable": "check", "Average latency": "ping", "Wi-Fi signal": "wifi"}
MAX_BARS = 15
TOP_RECOMMENDATIONS = 3
RECENT_ALERTS = 5


def chart_device_labels(stats):
    """Keep the distinguishing end of long names and fall back to IPs for duplicate labels."""
    names = [s.hostname or s.ip for s in stats]
    labels = [name if len(name) <= 15 else f"{name[:9]}…{name[-5:]}" for name in names]
    counts = Counter(labels)
    labels = [label if counts[label] == 1 else host.ip for host, label in zip(stats, labels)]
    return labels if len(set(labels)) == len(labels) else [host.ip for host in stats]


class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.busy = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD, pady=(12, 8))
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right", anchor="n", padx=(8, 0))
        self.diagnose_button = theme.ActionButton(controls, text="Diagnose network", width=170, height=40,
                                             corner_radius=20, image=theme.icon("diagnose", theme.SURFACE),
                                             command=self.diagnose, **theme.PRIMARY)
        self.diagnose_button.pack(side="right")
        self.retest_button = theme.ActionButton(controls, text="Re-test devices", width=158, height=40,
                                           corner_radius=20, image=theme.icon("refresh"), command=self.retest)
        self.retest_button.pack(side="right", padx=(0, 8))
        theme.ActionButton(controls, text="Alerts", width=84, height=40, corner_radius=20,
                      image=theme.icon("bell", size=16), command=self._toggle_alerts).pack(side="right", padx=(0, 8))
        ctk.CTkLabel(header, text="Dashboard", font=theme.TITLE_FONT, anchor="w").pack(fill="x")
        self.network = ctk.CTkLabel(header, text="Reading network…", text_color=theme.MUTED, anchor="w")
        self.network.pack(fill="x")

        content = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        content.pack(fill="both", expand=True, padx=(theme.PAD, 4), pady=(0, 8))
        self.alerts = ctk.CTkFrame(content)
        ctk.CTkLabel(self.alerts, text="Recent alerts", font=theme.CARD_FONT, anchor="w").pack(
            fill="x", padx=16, pady=(10, 4))
        self.alert_rows = ctk.CTkFrame(self.alerts, fg_color="transparent")
        self.alert_rows.pack(fill="x", padx=16, pady=(0, 12))

        self.verdict = VerdictCard(content, self._open_security)
        self.verdict.pack(fill="x", pady=(0, 12))

        tiles = ctk.CTkFrame(content, fg_color="transparent")
        tiles.pack(fill="x", pady=(0, 12))
        self.values, self.captions = {}, {}
        for i, (title, icon) in enumerate(CARDS.items()):
            tiles.grid_columnconfigure(i, weight=1, uniform="stat")
            card = ctk.CTkFrame(tiles)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 12 if i < len(CARDS) - 1 else 0))
            label = ctk.CTkFrame(card, fg_color="transparent")
            label.pack(fill="x", padx=12, pady=(12, 0))
            theme.icon_badge(label, icon, 26, theme.SUBTLE, theme.TEXT, 15).pack(side="right")
            ctk.CTkLabel(label, text=title, font=theme.CAPTION_FONT, anchor="w",
                         text_color=theme.MUTED).pack(side="left", fill="x", expand=True)
            self.values[title] = ctk.CTkLabel(card, text="—", font=(theme.SANS_SEMIBOLD, 32), anchor="w")
            self.values[title].pack(fill="x", padx=12)
            self.captions[title] = ctk.CTkLabel(card, text="", font=theme.CAPTION_FONT,
                                              text_color=theme.MUTED, anchor="w")
            self.captions[title].pack(fill="x", padx=12, pady=(0, 8))

        middle = ctk.CTkFrame(content, fg_color="transparent")
        middle.pack(fill="x", pady=(0, 12))
        middle.grid_columnconfigure(0, weight=3)
        middle.grid_columnconfigure(1, weight=2, minsize=240)
        chart_panel = ctk.CTkFrame(middle)
        chart_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(chart_panel, text="Latency per device", font=theme.CARD_FONT, anchor="w").pack(
            fill="x", padx=16, pady=(12, 0))
        self.chart_caption = theme.WrappedLabel(chart_panel, text="", text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.chart_caption.pack(fill="x", padx=16)
        self.chart = LatencyChart(chart_panel, width=3.5, height=2)
        self.chart.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        attention = ctk.CTkFrame(middle)
        attention.grid(row=0, column=1, sticky="nsew")
        title = ctk.CTkFrame(attention, fg_color="transparent")
        title.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(title, text="Needs attention", font=theme.CARD_FONT).pack(side="left")
        self.count = ctk.CTkLabel(title, text="0", padx=8, height=22, corner_radius=11,
                                  fg_color=theme.RED_SOFT, text_color=theme.RED, font=theme.CAPTION_FONT)
        self.count.pack(side="right")
        theme.ActionButton(attention, text="See all in Security", height=32, corner_radius=16,
                      image=theme.icon("arrow-up-right", size=14), compound="right",
                      command=self._open_security, **theme.GHOST).pack(side="bottom", anchor="w", padx=12, pady=8)
        self.findings = ctk.CTkFrame(attention, fg_color="transparent")
        self.findings.pack(fill="both", expand=True, padx=16)

        bar = ctk.CTkFrame(content, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 4))
        self.status = ctk.CTkLabel(bar, text="", text_color=theme.MUTED, anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        app.add_watch_switch(bar)
        if app.is_admin:
            self.scan_button = theme.ActionButton(bar, text="Scan network", width=146, height=40, corner_radius=20,
                                             image=theme.icon("radar"), command=self.scan_and_refresh)
            self.scan_button.pack(side="right", padx=(0, 12))

    def _open_security(self):
        self.app.show("Security")

    def on_show(self):
        """Load the latest network summary and alerts when Dashboard opens."""
        if not self.busy:
            run_async(services.dashboard, on_done=self._show, on_error=self._show_error)
        self.load_alerts()

    def _toggle_alerts(self):
        if self.alerts.winfo_manager():
            self.alerts.pack_forget()
        else:
            self.alerts.pack(before=self.verdict, fill="x", pady=(0, 12))
            self.load_alerts()

    def load_alerts(self):
        """Refresh the list when an alert arrives or is dismissed."""
        if self.alerts.winfo_manager():
            run_async(services.events, RECENT_ALERTS, on_done=self._show_alerts)

    def _show_alerts(self, events):
        for row in self.alert_rows.winfo_children():
            row.destroy()
        if not events:
            ctk.CTkLabel(self.alert_rows, text="No alerts yet.", text_color=theme.MUTED).pack(anchor="w")
        for event in events:
            text = f"{event.at[5:16].replace('T', ' ')}   {event.detail}"
            color = theme.MUTED if event.dismissed else SEVERITY_COLORS[event.severity]
            if event.ip:
                theme.ActionButton(self.alert_rows, text=text, anchor="w", fg_color=theme.SURFACE,
                              hover_color=theme.SUBTLE, text_color=color,
                              command=lambda ip=event.ip: self.app.open_device(ip)).pack(fill="x", pady=2)
            else:
                ctk.CTkLabel(self.alert_rows, text=text, text_color=color, anchor="w",
                             wraplength=640, justify="left").pack(fill="x", pady=2)

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.retest_button.configure(state=state)
        if self.app.is_admin:
            self.scan_button.configure(state=state)

    def retest(self):
        """Ping the known devices and update the Dashboard."""
        self._set_busy(True)
        self.status.configure(text="Re-testing devices…", text_color=theme.MUTED)
        run_async(services.refresh_dashboard, on_done=self._refreshed, on_error=self._refresh_failed)

    def scan_and_refresh(self):
        """Scan and ping before loading the new totals."""
        self._set_busy(True)
        self.status.configure(text="Scanning…", text_color=theme.MUTED)
        run_async(services.scan_and_refresh, lambda done, total: post(self._show_progress, (done, total)),
                  on_done=self._refreshed, on_error=self._refresh_failed)

    def _refreshed(self, data):
        self._set_busy(False)
        self._show(data)

    def _refresh_failed(self, error):
        self._set_busy(False)
        self._show_error(error)

    def diagnose(self):
        """Show the connection steps while diagnosis runs on a worker."""
        self.diagnose_button.configure(state="disabled")
        self.verdict.start()
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
        self.status.configure(text=f"Scanning {done} / {total}" if done < total else "Re-testing devices…")

    def _show(self, data):
        summary, stats, recommendations, (link, note) = data
        self.network.configure(text=link.ssid if link else "Wired connection" if note.startswith("Not on Wi-Fi")
                               else "Wi-Fi details unavailable")
        self.status.configure(text="" if summary.devices else "Open Devices to scan your network.", text_color=theme.MUTED)

        latency = summary.network_avg_ms
        self.values["Devices"].configure(text=str(summary.devices) if summary.devices else "—")
        self.values["Reachable"].configure(text=f"{summary.reachable} / {summary.devices}" if summary.devices else "—")
        self.values["Average latency"].configure(text=f"{latency:g} ms" if latency is not None else "—")
        self.values["Wi-Fi signal"].configure(text=f"{link.signal_pct}%" if link else "—")
        self.captions["Devices"].configure(text="On this network" if summary.devices else "Run a scan to begin")
        unknown = summary.devices - summary.reachable - summary.unreachable
        reachability = [f"{count} {label}" for count, label in ((summary.unreachable, "unreachable"),
                                                               (unknown, "unknown")) if count]
        self.captions["Reachable"].configure(text=" · ".join(reachability) or
                                             ("From scans and tests" if summary.devices else "No devices yet"))
        self.captions["Average latency"].configure(text="Across stored tests" if latency is not None else "No replies yet")
        self.captions["Wi-Fi signal"].configure(text=f"{link.quality} · {link.band}" if link else
                                               "Wired or offline" if note.startswith("Not on Wi-Fi") else "Unavailable")

        replies = [s for s in stats if s.avg_ms is not None]
        replied = replies[:MAX_BARS]
        caption = f"Showing {len(replied)} of {len(replies)} devices with replies · " if len(replies) > MAX_BARS else ""
        self.chart_caption.configure(text=caption + "Average of stored replies · select a bar for details")
        self.chart.plot(chart_device_labels(replied),
                        [s.avg_ms for s in replied], "" if replied else "No ping results yet",
                        on_pick=lambda i: self.app.open_device(replied[i].ip), distinct_labels=True)
        critical = [rec for rec in recommendations if rec.severity == "critical"]
        warnings = [rec for rec in recommendations if rec.severity == "warning"]
        self.verdict.set_summary(summary.health_score, len(critical), len(warnings))
        self._show_findings(critical + warnings)

    def _show_findings(self, recs):
        self.count.configure(text=str(len(recs)), fg_color=SEVERITY_SOFT[recs[0].severity] if recs else theme.SUBTLE,
                             text_color=SEVERITY_COLORS[recs[0].severity] if recs else theme.MUTED)
        for row in self.findings.winfo_children():
            row.destroy()
        if not recs:
            ctk.CTkLabel(self.findings, text="No findings need attention.", text_color=theme.MUTED).pack(anchor="w")
        for rec in recs[:TOP_RECOMMENDATIONS]:
            row = ctk.CTkFrame(self.findings, fg_color="transparent")
            row.pack(fill="x", pady=4)
            badge(row, rec, size=32).pack(side="left", anchor="n", padx=(0, 8))
            ctk.CTkLabel(row, text=rec.title, anchor="w", justify="left", wraplength=174,
                         font=theme.BODY_FONT).pack(fill="x")
            ctk.CTkLabel(row, text=rec.host or rec.category, anchor="w", font=theme.CAPTION_FONT,
                         text_color=theme.MUTED).pack(fill="x")

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
