"""A bar chart of latency values, drawn with matplotlib inside the window."""
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure   # Figure directly, not pyplot: pyplot keeps global state

from netmonitor.gui import theme

BACKGROUND, TEXT = theme.SURFACE, theme.TEXT_2


class LatencyChart(ctk.CTkFrame):
    def __init__(self, parent, width=5, height=2.4):
        super().__init__(parent, fg_color=BACKGROUND)
        self.figure = Figure(figsize=(width, height), dpi=100, facecolor=theme.color(BACKGROUND))
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._bars, self._bar_colors, self._on_pick = [], [], None
        self._baseline = None
        self.canvas.mpl_connect("pick_event", self._picked)   # connected once; plot() only swaps the bars
        theme.appearance_callback(self, self._apply_palette)
        self.plot([], [], "Reply times")

    def plot(self, labels, values, title, on_pick=None, unit="ms", distinct_labels=False, baseline=None):
        """Redraw the chart with one bar per label; values are in `unit` (the y-axis label).

        on_pick: when given, clicking a bar calls on_pick(index of that bar in labels).
        distinct_labels: reserve separate positions even for repeated device names.
        """
        self.axes.clear()
        positions = range(len(labels)) if distinct_labels else labels
        self._bars = list(self.axes.bar(positions, values, width=0.35 if distinct_labels else 0.8,
                                       color=theme.color(theme.INK), picker=on_pick is not None))
        self._bar_colors = [theme.AMBER if baseline is not None and value > baseline else theme.INK for value in values]
        self._baseline = self.axes.axhline(baseline, linestyle="--", linewidth=1) if baseline is not None else None
        if distinct_labels and labels:
            sparse = "" in labels
            rotation = 0 if sparse else 90 if len(labels) > 7 else 30
            self.axes.set_xticks(positions, labels, rotation=rotation, ha="center" if sparse else "right", fontsize=8)
            self.axes.set_axisbelow(True)
            self.axes.grid(axis="y", color=theme.color(theme.BORDER))
        self._on_pick = on_pick
        self.axes.set_title(title)
        self.axes.set_ylabel(unit)
        if not labels:
            self.axes.set_xticks([])
            self.axes.set_yticks([])
        self._apply_palette()
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _apply_palette(self, _mode=None):
        background, text, border = map(theme.color, (BACKGROUND, TEXT, theme.BORDER))
        self.figure.set_facecolor(background)
        self.axes.set_facecolor(background)
        self.axes.title.set_color(text)
        self.axes.yaxis.label.set_color(text)
        self.axes.tick_params(colors=text)
        for line in self.axes.get_ygridlines():
            line.set_color(border)
        for spine in self.axes.spines.values():
            spine.set_color(border)
        for bar, token in zip(self._bars, self._bar_colors):
            bar.set_facecolor(theme.color(token))
        if self._baseline is not None:
            self._baseline.set_color(theme.color(theme.GREEN))
        self.canvas.draw_idle()

    def _picked(self, event):
        if self._on_pick and event.artist in self._bars:
            self._on_pick(self._bars.index(event.artist))
