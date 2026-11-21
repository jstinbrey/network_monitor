"""Continuous ping chart: reply times drawn like a heart monitor."""
import math
from collections import deque

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from netmonitor import config
from netmonitor.gui import theme

PAPER, GRID_MAJOR, GRID_MINOR, TRACE = "#0f1712", "#1f3b2b", "#16281e", "#3ddc84"


class EcgChart(ctk.CTkFrame):
    """Reply times drawn like a heart monitor: newest on the right, a gap and a red × for each lost reply."""

    def __init__(self, parent, window=config.ECG_WINDOW):
        super().__init__(parent)
        self.points = deque(maxlen=window)        # (reply number, rtt or None)
        self.figure = Figure(figsize=(5, 2.4), dpi=100, facecolor=PAPER)
        self.axes = self.figure.add_subplot(111, facecolor=PAPER)
        self.axes.minorticks_on()
        self.axes.grid(which="major", color=GRID_MAJOR, linewidth=0.8)
        self.axes.grid(which="minor", color=GRID_MINOR, linewidth=0.4)
        self.axes.tick_params(which="both", colors=theme.MUTED, labelbottom=False)   # reply numbers mean nothing here
        self.axes.set_ylabel("ms", color=theme.MUTED)
        self.axes.axhline(config.LATENCY_WARN_MS, color=theme.AMBER, linestyle="--", linewidth=1)
        self.trace, = self.axes.plot([], [], color=TRACE, linewidth=1.6)
        self.head, = self.axes.plot([], [], "o", color=TRACE, markersize=5)
        self.lost, = self.axes.plot([], [], "x", color=theme.RED, markersize=8, markeredgewidth=2)
        self.readout = self.axes.text(0.98, 0.95, "", transform=self.axes.transAxes, ha="right", va="top",
                                      color=TRACE, fontsize=20, family="Consolas")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self.clear()
        self.figure.tight_layout()

    def add(self, number, rtt):
        self.points.append((number, rtt))
        xs = [n for n, _ in self.points]
        ys = [math.nan if r is None else r for _, r in self.points]   # NaN breaks the line: a visible gap
        top = max(20, max((r for _, r in self.points if r is not None), default=0) * 1.3)
        self.trace.set_data(xs, ys)
        self.head.set_data(xs[-1:], ys[-1:])
        lost = [n for n, r in self.points if r is None]
        self.lost.set_data(lost, [top * 0.9] * len(lost))
        self.axes.set_xlim(number - self.points.maxlen + 1, number + 1)
        self.axes.set_ylim(0, top)
        self.readout.set_text("LOST" if rtt is None else f"{rtt:g} ms")
        self.readout.set_color(theme.RED if rtt is None else TRACE)
        self.canvas.draw_idle()

    def clear(self):
        """An empty screen, ready for a new session."""
        self.points.clear()
        for line in (self.trace, self.head, self.lost):
            line.set_data([], [])
        self.readout.set_text("")
        self.axes.set_xlim(1, self.points.maxlen + 1)
        self.axes.set_ylim(0, 20)
        self.canvas.draw_idle()
