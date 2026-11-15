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
        self.plot([], [], "Reply times")

    def plot(self, labels, values, title):
        """Redraw the chart with one bar per label; values are in milliseconds."""
        self.axes.clear()
        self.axes.bar(labels, values, color=theme.BLUE)
        self.axes.set_title(title, color=TEXT)
        self.axes.set_ylabel("ms", color=TEXT)
        self.axes.set_facecolor(BACKGROUND)
        self.axes.tick_params(colors=TEXT)
        for spine in self.axes.spines.values():
            spine.set_color(theme.MUTED)
        self.figure.tight_layout()
        self.canvas.draw_idle()