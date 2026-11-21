"""A bar chart of latency values, drawn with matplotlib inside the window."""
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure   # Figure directly, not pyplot: pyplot keeps global state

from netmonitor.gui import theme

BACKGROUND, TEXT = "#2b2b2b", "#e6e6e6"


class LatencyChart(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.figure = Figure(figsize=(5, 2.4), dpi=100, facecolor=BACKGROUND)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._bars, self._on_pick = [], None
        self.canvas.mpl_connect("pick_event", self._picked)   # connected once; plot() only swaps the bars
        self.plot([], [], "Reply times")

    def plot(self, labels, values, title, on_pick=None, unit="ms"):
        """Redraw the chart with one bar per label; values are in `unit` (the y-axis label).

        on_pick: when given, clicking a bar calls on_pick(index of that bar in labels).
        """
        self.axes.clear()
        self._bars = list(self.axes.bar(labels, values, color=theme.BLUE, picker=on_pick is not None))
        self._on_pick = on_pick
        self.axes.set_title(title, color=TEXT)
        self.axes.set_ylabel(unit, color=TEXT)
        self.axes.set_facecolor(BACKGROUND)
        self.axes.tick_params(colors=TEXT)
        for spine in self.axes.spines.values():
            spine.set_color(theme.MUTED)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _picked(self, event):
        if self._on_pick and event.artist in self._bars:
            self._on_pick(self._bars.index(event.artist))