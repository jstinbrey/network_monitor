"""Connection view: this PC's Wi-Fi link, and its download and upload rates against the limits an administrator set.

The window samples the adapter once a second whichever view is showing (App._sample_bandwidth), so
the chart already holds the last two minutes when this view is opened. The Wi-Fi details are read on opening.
"""
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import run_async

DOWN_COLOR, UP_COLOR = theme.LIME, theme.PAPER_SERIES_2   # live chart: lime and light blue on dark chart paper
BACKGROUND, TEXT = theme.PAPER, theme.PAPER_MUTED
TILES = ("Download now", "Upload now", "Peak download", "Used today")
ICONS = ("arrow-down", "arrow-up", "gauge", "database")
QUALITY_COLORS = {"Excellent": theme.GREEN, "Good": theme.GREEN, "Fair": theme.AMBER, "Weak": theme.RED}


class ConnectionView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.limits = dict(config.SETTING_DEFAULTS)
        actions, _ = theme.page_heading(self, "Connection", "This PC’s Wi-Fi link and the data it moves")
        self.live = ctk.CTkLabel(actions, text="Live · every second", fg_color=theme.LIME_SOFT, font=theme.CAPTION_FONT,
                                 corner_radius=16, height=32, padx=10)
        wifi_row = ctk.CTkFrame(self, fg_color="transparent")
        wifi_row.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        wifi_row.grid_columnconfigure(0, weight=2, uniform="wifi")
        wifi_row.grid_columnconfigure(1, weight=1, uniform="wifi")
        link = ctk.CTkFrame(wifi_row, fg_color=theme.SURFACE)
        link.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        link_header = ctk.CTkFrame(link, fg_color="transparent")
        link_header.pack(fill="x", padx=16, pady=(12, 4))
        theme.icon_badge(link_header, "wifi", 36, theme.GREEN_SOFT, theme.GREEN, 18).pack(side="left", padx=(0, 10))
        self.signal = ctk.CTkLabel(link_header, text="", font=(theme.SANS_SEMIBOLD, 28))
        self.signal.pack(side="right")
        self.wifi_verdict = theme.WrappedLabel(link_header, text="Reading Wi-Fi…", font=theme.CARD_FONT,
                                               text_color=theme.MUTED)
        self.wifi_verdict.pack(fill="x")
        self.wifi_details = theme.WrappedLabel(link, text="", text_color=theme.TEXT_2)
        self.wifi_details.pack(fill="x", padx=16, pady=(4, 12))
        nearby = ctk.CTkFrame(wifi_row, fg_color=theme.SURFACE)
        nearby.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(nearby, text="Nearby networks", font=theme.CARD_FONT).pack(anchor="w", padx=16, pady=(12, 0))
        self.nearby_note = theme.WrappedLabel(nearby, text="", text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.nearby_note.pack(fill="x", padx=16)
        self.nearby = LatencyChart(nearby, width=2.5, height=1.25)
        self.nearby.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        self.tiles, self.notes = {}, {}
        for i, (title, icon) in enumerate(zip(TILES, ICONS)):
            row.grid_columnconfigure(i, weight=1, uniform="bandwidth")
            tile = ctk.CTkFrame(row)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0, 12 if i < 3 else 0))
            head = ctk.CTkFrame(tile, fg_color="transparent")
            head.pack(fill="x", padx=12, pady=(10, 0))
            theme.icon_badge(head, icon, 24, theme.SUBTLE, theme.TEXT, 14).pack(side="right")
            ctk.CTkLabel(head, text=title, text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(side="left")
            self.tiles[title] = ctk.CTkLabel(tile, text="-", font=theme.STAT_FONT)
            self.tiles[title].pack(anchor="w", padx=12)
            self.notes[title] = theme.WrappedLabel(tile, text="", text_color=theme.MUTED, font=theme.CAPTION_FONT)
            self.notes[title].pack(fill="x", padx=12, pady=(0, 8))
        self.cap_bar = ctk.CTkProgressBar(tile, height=5)
        self.cap_bar.set(0)
        plot = ctk.CTkFrame(self, fg_color=BACKGROUND)
        plot.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, 12))
        ctk.CTkLabel(plot, text="Last 2 minutes", text_color=theme.PAPER_TEXT, font=theme.CARD_FONT).pack(
            anchor="w", padx=16, pady=(10, 0))
        self.verdict = theme.WrappedLabel(plot, text="Measuring this PC while NetMonitor is running…",
                                          font=theme.CAPTION_FONT, text_color=theme.PAPER_MUTED)
        self.verdict.pack(fill="x", padx=16)

        # One Figure, updated with set_data each second, as the continuous ping chart does.
        self.figure = Figure(figsize=(5, 2.6), dpi=100, facecolor=BACKGROUND, layout="constrained")
        self.axes = self.figure.add_subplot(111, facecolor=BACKGROUND)
        self.axes.tick_params(colors=TEXT)
        for spine in self.axes.spines.values():
            spine.set_color(theme.PAPER_GRID)
        self.axes.set_xlim(-config.BW_WINDOW_S, 0)
        self.axes.set_ylim(0, 1)
        self.axes.set_xlabel("seconds ago", color=TEXT)
        self.axes.set_ylabel("Mbps", color=TEXT)
        self.down_line, = self.axes.plot([], [], color=DOWN_COLOR, linewidth=1.6, label="Download")
        self.up_line, = self.axes.plot([], [], color=UP_COLOR, linewidth=1.6, label="Upload")
        self.down_limit = self.axes.axhline(0, color=TEXT, linestyle="--", linewidth=1, visible=False)
        self.up_limit = self.axes.axhline(0, color=TEXT, linestyle=":", linewidth=1, visible=False)
        self.axes.legend(loc="upper left", facecolor=BACKGROUND, edgecolor=theme.PAPER_GRID, labelcolor=TEXT)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot)
        self.canvas.get_tk_widget().configure(height=130)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def on_show(self):
        """The limits may have changed in Admin > Settings, and the Wi-Fi signal moves, so both are read each time."""
        run_async(services.settings, on_done=self._set_limits)
        run_async(services.wifi_details, on_done=self._show_wifi,
                  on_error=lambda error: self.wifi_verdict.configure(text=str(error), text_color=theme.RED))
        self.redraw_bandwidth()

    def _show_wifi(self, details):
        if not self.winfo_exists():
            return
        link, note, nearby, advice = details
        if not link:
            self.wifi_verdict.configure(text=note, text_color=theme.MUTED)
            self.wifi_details.configure(text="")
            self.signal.configure(text="")
            self.nearby_note.configure(text="")
            self.nearby.plot([], [], "No Wi-Fi link", unit="access points")
            return
        self.wifi_verdict.configure(text=f"{link.quality} Wi-Fi signal", text_color=QUALITY_COLORS[link.quality])
        self.signal.configure(text=f"{link.signal_pct}%")
        self.nearby_note.configure(text=f"Access points by channel · yours is {link.channel}")
        self.wifi_details.configure(text="\n".join(filter(None, [
            f"{link.ssid} · {link.band} · channel {link.channel} · {link.rssi_dbm:g} dBm",
            f"{link.radio} · {link.auth} · {link.cipher} encryption",
            f"Link rate {link.rx_mbps:g} Mbps receive, {link.tx_mbps:g} Mbps send (agreed with the router, "
            "not measured speed)",
            f"{len(nearby)} access point{'' if len(nearby) == 1 else 's'} in range.", advice])))
        channels = sorted({channel for _, channel in nearby} | {link.channel})
        self.nearby.plot([str(c) for c in channels], [sum(c == n for _, n in nearby) for c in channels],
                         "", unit="")

    def _set_limits(self, limits):
        if not self.winfo_exists():
            return
        self.limits = limits
        for line, key in ((self.down_limit, "bw_down_mbps"), (self.up_limit, "bw_up_mbps")):
            line.set_ydata([limits[key]] * 2)
            line.set_visible(bool(limits[key]))
        self.redraw_bandwidth()

    def redraw_bandwidth(self):
        """Draw the recent samples kept by the window, including those from before this view opened."""
        samples = self.app.bandwidth_samples
        if not samples:
            return
        now, s = samples[-1]
        self.live.pack()
        cap = self.limits["bw_daily_gb"]
        xs = [t - now for t, _ in samples]
        down = [sample.down_mbps for _, sample in samples]
        up = [sample.up_mbps for _, sample in samples]
        self.down_line.set_data(xs, down)
        self.up_line.set_data(xs, up)
        peak = max(down)
        top = max(1, self.limits["bw_down_mbps"], self.limits["bw_up_mbps"], peak, max(up))
        self.axes.set_ylim(0, top * 1.2)
        self.canvas.draw_idle()

        used = f"{s.today_bytes / 1e9:.2f} GB"
        for title, text in zip(TILES, [*map(services.rate_text, (s.down_mbps, s.up_mbps, peak)), used]):
            self.tiles[title].configure(text=text)
        for title, limit in zip(TILES, (self.limits["bw_down_mbps"], self.limits["bw_up_mbps"])):
            self.notes[title].configure(text=f"Limit {limit:g} Mbps" if limit else "No limit set")
        self.notes[TILES[2]].configure(text="In the last 2 minutes")
        if cap:
            self.cap_bar.set(min(1, s.today_bytes / (cap * 1e9)))
            self.cap_bar.pack(fill="x", padx=12, pady=(0, 8))
        else:
            self.cap_bar.pack_forget()
        self.notes[TILES[3]].configure(text=f"Of the {cap:g} GB daily cap" if cap else "No daily cap set")
        status, sentence = services.describe_bandwidth(s.down_mbps, s.up_mbps, s.today_bytes, self.limits)
        self.verdict.configure(text=sentence, text_color={"good": theme.PAPER_MUTED, "warn": theme.PAPER_WARN,
                                                          "bad": theme.PAPER_BAD}[status])
