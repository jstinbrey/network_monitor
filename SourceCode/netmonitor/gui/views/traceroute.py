"""Traceroute view (Feature 2 extension): every router between this PC and a target, and where delay starts."""
from tkinter import ttk

import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import post, run_async

COLUMNS = [("hop", "Hop", 42), ("address", "Router", 195), ("segment", "Segment", 126),
           ("t1", "Probe 1", 69), ("t2", "Probe 2", 69), ("t3", "Probe 3", 69),
           ("average", "Average", 85), ("loss", "Loss", 54)]
VERDICT_COLORS = {"good": theme.GREEN, "warn": theme.AMBER, "info": theme.MUTED}
CHART_TITLE = "Average latency per hop"


class TracerouteView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.handle, self.hops = None, []          # the running trace, for Stop; the hops so far
        theme.page_heading(self, "Traceroute", "Every router between this PC and a target, and where delay starts")

        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE)
        bar.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        self.button = theme.ActionButton(bar, text="Trace", width=100, height=40, corner_radius=20,
                                          image=theme.icon("traceroute", theme.ON_INK, 16),
                                          command=self.trace, **theme.PRIMARY)
        self.button.pack(side="right", padx=12, pady=12)
        self.target = ctk.CTkEntry(bar, width=214, height=40, corner_radius=20, fg_color=theme.SUBTLE,
                                   placeholder_text="IP address or hostname")
        self.target.pack(side="left", padx=(12, 10))
        self.target.bind("<Return>", lambda event: self.trace())
        for label in ("Router", "1.1.1.1", "google.com"):
            theme.ActionButton(bar, text=label, width=72, height=28, corner_radius=14,
                               fg_color=theme.SUBTLE, border_width=0,
                               command=lambda value=label: self._choose_target(value)).pack(side="left", padx=(0, 4))

        result = ctk.CTkFrame(self, fg_color=theme.SURFACE)
        result.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        theme.icon_badge(result, "traceroute", 36, theme.SUBTLE, theme.TEXT, 18).pack(side="left", padx=16, pady=12)
        self.status = theme.WrappedLabel(result, text="", text_color=theme.MUTED, width=86, font=theme.CAPTION_FONT)
        self.status.pack(side="right", padx=12)
        self.verdict = theme.WrappedLabel(result, text="Enter an address or choose a target.", text_color=theme.TEXT,
                                          font=theme.CARD_FONT)
        self.verdict.pack(side="left", fill="x", expand=True, pady=12)

        card = ctk.CTkFrame(self)
        card.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, 12))
        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        theme.ActionButton(bottom, text="Hop chart", width=88, height=32, command=self._toggle_chart,
                           image=theme.icon("statistics", size=14), **theme.GHOST).pack(side="right")
        theme.WrappedLabel(bottom, text="Three probes per hop. Some routers skip replies and still forward traffic.",
                           font=theme.CAPTION_FONT, text_color=theme.MUTED).pack(side="left", fill="x", expand=True)
        rows = ctk.CTkFrame(card, fg_color="transparent")
        rows.pack(fill="both", expand=True, padx=8, pady=8)
        self.table = ttk.Treeview(rows, columns=[key for key, _, _ in COLUMNS], show="headings", height=10)
        for key, title, width in COLUMNS:
            self.table.heading(key, text=title, anchor="w")
            self.table.column(key, width=width, anchor="w")
        self._style_rows()
        theme.appearance_callback(self.table, self._style_rows)
        scrollbar = ctk.CTkScrollbar(rows, command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)

        self.chart = LatencyChart(card, height=1.6)
        self.chart_anchor = rows

    def _choose_target(self, value):
        def use_target(target):
            self.target.delete(0, "end")
            self.target.insert(0, target)
            self.target.focus_set()

        if value == "Router":
            run_async(services.network_info, on_done=lambda info: use_target(info.gateway)
                      if info.gateway else self._show_error("A default gateway could not be found."),
                      on_error=self._show_error)
        else:
            use_target(value)

    def _toggle_chart(self):
        if self.chart.winfo_manager():
            self.chart.pack_forget()
        else:
            self.chart.pack(side="bottom", before=self.chart_anchor, fill="x", padx=8, pady=(0, 8))
            self._draw_chart()

    def on_show(self, ip=None):
        """ip: trace this device now (the device panel's Traceroute button)."""
        if ip and self.button.cget("text") == "Trace" and self.button.cget("state") == "normal":
            if self.target.get():
                self.target.delete(0, "end")
            self.target.insert(0, ip)
            self.trace()

    def trace(self):
        if self.button.cget("state") == "disabled":
            return
        if self.handle:                              # the button reads Stop while a trace runs
            self.button.configure(text="Stopping…", state="disabled")
            self.handle.stop()
            return
        self.table.delete(*self.table.get_children())
        self.hops = []
        self._draw_chart()
        self.verdict.configure(text="Tracing the route…", text_color=theme.MUTED)
        self.button.configure(state="disabled")
        self.status.configure(text="Starting...", text_color=theme.MUTED)
        # Hops arrive on tracert's own reading thread, so post() carries each one to the UI thread.
        run_async(services.start_traceroute, self.target.get(),
                  lambda hop: post(self._add_hop, hop), lambda result: post(self._done, result),
                  on_done=self._started, on_error=self._show_error)

    def _started(self, handle):
        if self.button.cget("state") == "disabled":  # still running: _done has not re-enabled the button yet
            self.handle = handle
            self.button.configure(text="Stop", state="normal", image=theme.icon("stop", theme.ON_INK, 16))

    def _add_hop(self, hop):
        if not self.winfo_exists():                  # signed out while the trace ran
            return
        self.hops.append(hop)
        times = ["*" if t is None else f"{t:g} ms" for t in hop.times_ms]
        tag = "warn" if hop.address and hop.loss_pct else "good"
        average = f"{hop.avg_ms:g} ms" if hop.avg_ms is not None else "—"
        self.table.insert("", "end", tags=(tag,), values=[
            hop.number, hop.address or "No reply", services.hop_segment(hop), *times, average, f"{hop.loss_pct:g}%"])
        self._draw_chart()
        self.status.configure(text=f"Hop {hop.number}...")

    def _draw_chart(self):
        if self.chart.winfo_manager():
            answered = [hop for hop in self.hops if hop.avg_ms is not None]
            self.chart.plot([str(hop.number) for hop in answered], [hop.avg_ms for hop in answered], CHART_TITLE)

    def _done(self, result):
        if not self.winfo_exists():
            return
        hops, status, sentence = result
        self.handle = None
        self.verdict.configure(text=sentence, text_color=VERDICT_COLORS[status])
        self.status.configure(text="1 hop" if len(hops) == 1 else f"{len(hops)} hops")
        self.button.configure(text="Trace", state="normal", image=theme.icon("traceroute", theme.ON_INK, 16))

    def _show_error(self, error):
        self.verdict.configure(text=str(error), text_color=theme.RED)
        self.status.configure(text="")
        self.button.configure(state="normal")

    def _style_rows(self, _mode=None):
        for tag, token in theme.TAG_COLORS.items():
            self.table.tag_configure(tag, foreground=theme.color(token))
