"""A bar chart of latency values, drawn with matplotlib inside the window."""
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure   # Figure directly, not pyplot: pyplot keeps global state

from netmonitor.gui import theme

BACKGROUND, TEXT = theme.SURFACE, theme.TEXT_2


class LatencyChart(ctk.CTkFrame):
    def __init__(self, parent, width=5, height=2.4):
        super().__init__(parent, fg_color=BACKGROUND)
        self.figure = Figure(figsize=(width, height), dpi=100, facecolor=BACKGROUND)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._bars, self._on_pick = [], None
        self.canvas.mpl_connect("pick_event", self._picked)   # connected once; plot() only swaps the bars
        self.plot([], [], "Reply times")

    def plot(self, labels, values, title, on_pick=None, unit="ms", distinct_labels=False):
        """Redraw the chart with one bar per label; values are in `unit` (the y-axis label).

        on_pick: when given, clicking a bar calls on_pick(index of that bar in labels).
        distinct_labels: reserve separate positions even for repeated device names.
        """
        self.axes.clear()
        positions = range(len(labels)) if distinct_labels else labels
        self._bars = list(self.axes.bar(positions, values, width=0.35 if distinct_labels else 0.8,
                                       color=theme.INK, picker=on_pick is not None))
        if distinct_labels and labels:
            self.axes.set_xticks(positions, labels, rotation=90 if len(labels) > 7 else 30, ha="right", fontsize=8)
            self.axes.set_axisbelow(True)
            self.axes.grid(axis="y", color=theme.BORDER)
        self._on_pick = on_pick
        self.axes.set_title(title, color=TEXT)
        self.axes.set_ylabel(unit, color=TEXT)
        self.axes.set_facecolor(BACKGROUND)
        self.axes.tick_params(colors=TEXT)
        if not labels:
            self.axes.set_xticks([])
            self.axes.set_yticks([])
        for spine in self.axes.spines.values():
            spine.set_color(theme.BORDER)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _picked(self, event):
        if self._on_pick and event.artist in self._bars:
            self._on_pick(self._bars.index(event.artist))
