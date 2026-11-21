"""Connection view: this PC's download and upload rates against the limits an administrator set.

The window samples the adapter once a second whichever view is showing (App._sample_bandwidth), so
the chart already holds the last two minutes when this view is opened. Wi-Fi details come in Step 7.5.
"""
import time
from collections import deque

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.widgets.latency_chart import BACKGROUND, TEXT
from netmonitor.gui.worker import run_async

DOWN_COLOR, UP_COLOR = "#4da3ff", theme.GREEN     # a lighter blue than theme.BLUE, readable on the dark chart
TILES = ["Download now", "Upload now", "Peak download (2 min)", "Used today"]


class ConnectionView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.limits = dict(config.BW_DEFAULTS)
        self.samples = deque(maxlen=config.BW_WINDOW_S)        # (time.monotonic(), down_mbps, up_mbps)
        self.last = None                                       # the latest BandwidthSample
        ctk.CTkLabel(self, text="Connection", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))
        ctk.CTkLabel(self, text="Bandwidth", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=theme.PAD)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=(4, 0))
        self.tiles = {}
        for title in TILES:
            tile = ctk.CTkFrame(row)
            tile.pack(side="left", fill="both", expand=True, padx=(0, 8))
            ctk.CTkLabel(tile, text=title, text_color=theme.MUTED).pack(anchor="w", padx=12, pady=(8, 0))
            self.tiles[title] = ctk.CTkLabel(tile, text="-", font=("Segoe UI", 18, "bold"))
            self.tiles[title].pack(anchor="w", padx=12, pady=(0, 8))
        self.cap_bar = ctk.CTkProgressBar(tile)                # inside the last tile: today's use against the cap
        self.cap_bar.set(0)
        self.cap_bar.pack(fill="x", padx=12, pady=(0, 10))

        self.verdict = ctk.CTkLabel(self, text="Measuring...", anchor="w", font=("Segoe UI", 14, "bold"),
                                    text_color=theme.MUTED)
        self.verdict.pack(fill="x", padx=theme.PAD, pady=(10, 0))
        ctk.CTkLabel(self, text="Measures this PC only, while NetMonitor is running.", text_color=theme.MUTED,
                     anchor="w").pack(side="bottom", fill="x", padx=theme.PAD, pady=(0, theme.PAD))

        # One Figure, updated with set_data each second, as the continuous ping chart does.
        self.figure = Figure(figsize=(5, 2.6), dpi=100, facecolor=BACKGROUND)
        self.axes = self.figure.add_subplot(111, facecolor=BACKGROUND)
        self.axes.tick_params(colors=TEXT)
        for spine in self.axes.spines.values():
            spine.set_color(theme.MUTED)
        self.axes.set_xlim(-config.BW_WINDOW_S, 0)
        self.axes.set_ylim(0, 1)
        self.axes.set_xlabel("seconds ago", color=TEXT)
        self.axes.set_ylabel("Mbps", color=TEXT)
        self.down_line, = self.axes.plot([], [], color=DOWN_COLOR, linewidth=1.6, label="Download")
        self.up_line, = self.axes.plot([], [], color=UP_COLOR, linewidth=1.6, label="Upload")
        self.down_limit = self.axes.axhline(0, color=DOWN_COLOR, linestyle="--", linewidth=1, visible=False)
        self.up_limit = self.axes.axhline(0, color=UP_COLOR, linestyle="--", linewidth=1, visible=False)
        self.axes.legend(loc="upper left", facecolor=BACKGROUND, edgecolor=theme.MUTED, labelcolor=TEXT)
        self.figure.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=theme.PAD, pady=8)

    def on_show(self):
        """The limits may have changed in Admin > Settings, so they are read again each time."""
        run_async(services.settings, on_done=self._set_limits)
        self._redraw()

    def _set_limits(self, limits):
        if not self.winfo_exists():
            return
        self.limits = limits
        for line, key in ((self.down_limit, "bw_down_mbps"), (self.up_limit, "bw_up_mbps")):
            line.set_ydata([limits[key]] * 2)
            line.set_visible(bool(limits[key]))
        self._redraw()

    def add_sample(self, sample):
        """Called by the window once a second, whichever view is showing."""
        self.samples.append((time.monotonic(), sample.down_mbps, sample.up_mbps))
        self.last = sample
        if self.app.current == "Connection":   # redrawing a hidden chart every second would waste time
            self._redraw()

    def _redraw(self):
        if not self.last:
            return
        s, now, cap = self.last, self.samples[-1][0], self.limits["bw_daily_gb"]
        xs = [t - now for t, _, _ in self.samples]
        self.down_line.set_data(xs, [down for _, down, _ in self.samples])
        self.up_line.set_data(xs, [up for _, _, up in self.samples])
        top = max(1, self.limits["bw_down_mbps"], self.limits["bw_up_mbps"], *(max(d, u) for _, d, u in self.samples))
        self.axes.set_ylim(0, top * 1.2)
        self.canvas.draw_idle()

        peak = max(down for _, down, _ in self.samples)
        used = f"{s.today_bytes / 1e9:.2f} GB" + (f" of {cap:g}" if cap else "")
        for title, text in zip(TILES, [*map(services.rate_text, (s.down_mbps, s.up_mbps, peak)), used]):
            self.tiles[title].configure(text=text)
        self.cap_bar.set(min(1, s.today_bytes / (cap * 1e9)) if cap else 0)
        status, sentence = services.describe_bandwidth(s.down_mbps, s.up_mbps, s.today_bytes, self.limits)
        self.verdict.configure(text=sentence, text_color=theme.TAG_COLORS[status])
