"""Traceroute view (Feature 2 extension): every router between this PC and a target, and where delay starts."""
from tkinter import ttk

import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import post, run_async

COLUMNS = [("hop", "Hop", 50), ("t1", "Probe 1", 80), ("t2", "Probe 2", 80), ("t3", "Probe 3", 80),
           ("address", "Address", 170), ("segment", "Segment", 170), ("loss", "Loss", 70)]
VERDICT_COLORS = {"good": theme.GREEN, "warn": theme.AMBER, "info": theme.MUTED}
CHART_TITLE = "Average latency per hop"


class TracerouteView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.handle, self.hops = None, []          # the running trace, for Stop; the hops so far
        ctk.CTkLabel(self, text="Traceroute", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD)
        self.target = ctk.CTkEntry(bar, width=240, placeholder_text="IP address or name, e.g. 1.1.1.1")
        self.target.pack(side="left")
        self.target.bind("<Return>", lambda event: self.trace())
        self.button = ctk.CTkButton(bar, text="Trace", command=self.trace, **theme.PRIMARY)
        self.button.pack(side="left", padx=12)
        self.status = ctk.CTkLabel(bar, text="", text_color=theme.MUTED)
        self.status.pack(side="left")

        self.verdict = ctk.CTkLabel(self, text="Each hop is one router; each probe is one reply time.", anchor="w",
                                    justify="left", wraplength=780, text_color=theme.MUTED, font=theme.CARD_FONT)
        self.verdict.pack(fill="x", padx=theme.PAD, pady=10)

        self.table = ttk.Treeview(self, columns=[key for key, _, _ in COLUMNS], show="headings", height=10)
        for key, title, width in COLUMNS:
            self.table.heading(key, text=title, anchor="w")
            self.table.column(key, width=width, anchor="w")
        for tag, color in theme.TAG_COLORS.items():
            self.table.tag_configure(tag, foreground=color)
        self.table.pack(fill="x", padx=theme.PAD)

        self.chart = LatencyChart(self)
        self.chart.pack(fill="both", expand=True, padx=theme.PAD, pady=theme.PAD)
        self.chart.plot([], [], CHART_TITLE)

    def on_show(self, ip=None):
        """ip: trace this device now (the device panel's Traceroute button)."""
        if ip and self.button.cget("text") == "Trace" and self.button.cget("state") == "normal":
            if self.target.get():
                self.target.delete(0, "end")
            self.target.insert(0, ip)
            self.trace()

    def trace(self):
        if self.handle:                              # the button reads Stop while a trace runs
            self.handle.stop()
            return
        self.table.delete(*self.table.get_children())
        self.hops = []
        self.chart.plot([], [], CHART_TITLE)
        self.verdict.configure(text="")
        self.button.configure(state="disabled")
        self.status.configure(text="Starting...", text_color=theme.MUTED)
        # Hops arrive on tracert's own reading thread, so post() carries each one to the UI thread.
        run_async(services.start_traceroute, self.target.get(),
                  lambda hop: post(self._add_hop, hop), lambda result: post(self._done, result),
                  on_done=self._started, on_error=self._show_error)

    def _started(self, handle):
        if self.button.cget("state") == "disabled":  # still running: _done has not re-enabled the button yet
            self.handle = handle
            self.button.configure(text="Stop", state="normal")

    def _add_hop(self, hop):
        if not self.winfo_exists():                  # signed out while the trace ran
            return
        self.hops.append(hop)
        times = ["*" if t is None else f"{t:g} ms" for t in hop.times_ms]
        tag = "bad" if hop.address is None else "warn" if hop.loss_pct else "good"
        self.table.insert("", "end", tags=(tag,), values=[hop.number, *times, hop.address or "Request timed out",
                                                          services.hop_segment(hop), f"{hop.loss_pct:g}%"])
        answered = [h for h in self.hops if h.avg_ms is not None]
        self.chart.plot([str(h.number) for h in answered], [h.avg_ms for h in answered], CHART_TITLE)
        self.status.configure(text=f"Hop {hop.number}...")

    def _done(self, result):
        if not self.winfo_exists():
            return
        hops, status, sentence = result
        self.handle = None
        self.verdict.configure(text=sentence, text_color=VERDICT_COLORS[status])
        self.status.configure(text="1 hop" if len(hops) == 1 else f"{len(hops)} hops")
        self.button.configure(text="Trace", state="normal")

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
        self.button.configure(state="normal")
