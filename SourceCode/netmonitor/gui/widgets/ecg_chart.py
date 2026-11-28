"""Live latency trace on a Tk canvas, with separate loss and spike markers."""
from collections import deque
from math import ceil
import tkinter as tk

import customtkinter as ctk

from netmonitor import config
from netmonitor.gui import theme


class EcgChart(ctk.CTkFrame):
    def __init__(self, parent, window=config.ECG_WINDOW):
        super().__init__(parent, fg_color=theme.PAPER)
        self.points = deque(maxlen=window)
        self.grid_size = None
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(14, 4))
        reading = ctk.CTkFrame(header, fg_color="transparent")
        reading.pack(side="right", anchor="n", padx=(8, 0))
        self.readout = ctk.CTkLabel(reading, text="—", text_color=theme.LIME, font=(theme.MONO, 26, "bold"), anchor="e")
        self.readout.pack(fill="x")
        ctk.CTkLabel(reading, text="Latest reply", text_color=theme.PAPER_MUTED,
                     font=theme.CAPTION_FONT, anchor="e").pack(fill="x")
        ctk.CTkLabel(header, text="Reply time", text_color=theme.PAPER_TEXT, font=theme.CARD_FONT,
                     anchor="w").pack(fill="x")
        legend = ctk.CTkFrame(header, fg_color="transparent")
        legend.pack(anchor="w")
        for icon, text, color in (("minus", "Reply", theme.LIME), ("clock", "Slower than usual", theme.PAPER_WARN),
                                  ("x", "Lost", theme.PAPER_BAD)):
            ctk.CTkLabel(legend, text=text, image=theme.icon(icon, color, 12), compound="left",
                         text_color=theme.PAPER_MUTED, font=theme.CAPTION_FONT).pack(side="left", padx=(0, 8))
        self.note = theme.WrappedLabel(self, text="", text_color=theme.PAPER_MUTED, font=theme.CAPTION_FONT)
        self.note.pack(side="bottom", fill="x", padx=20, pady=(0, 12))
        self.canvas = tk.Canvas(self, background=theme.PAPER, highlightthickness=0, width=1, height=1)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        self.canvas.bind("<Configure>", self._redraw_trace)

    def add(self, number, rtt, spike=False):
        """Append one observation and update the live graph."""
        self.points.append((number, rtt, spike))
        self.readout.configure(text="No reply" if rtt is None else f"{rtt:g} ms",
                               text_color=theme.PAPER_BAD if rtt is None else theme.LIME)
        self._redraw_trace()

    def clear(self):
        """Reset the readout and trace for a new session."""
        self.points.clear()
        self.readout.configure(text="—", text_color=theme.PAPER_MUTED)
        self.note.configure(text="")
        self._redraw_trace()

    def _redraw_trace(self, event=None):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        left, right, upper, lower = round(42 * scale), width - round(8 * scale), round(10 * scale), height - round(10 * scale)
        if right <= left or lower <= upper:
            return
        peak = max((rtt for _, rtt, _ in self.points if rtt is not None), default=0)
        top = max(config.ECG_MIN_TOP_MS, ceil(peak * 1.25))
        size = (width, height, scale, top)
        if size != self.grid_size:
            self.canvas.delete("grid")
            for index in range(6):
                y = lower - (lower - upper) * index / 5
                value = top * index / 5
                self.canvas.create_line(left, y, right, y, fill=theme.PAPER_GRID, tags="grid")
                self.canvas.create_text(left - round(8 * scale), y, text=f"{value:g}" + (" ms" if index == 5 else ""),
                                        font=theme.MONO_FONT, fill=theme.PAPER_MUTED, anchor="e", tags="grid")
            self.grid_size = size
        self.canvas.delete("trace")
        if not self.points:
            return
        last = self.points[-1][0]
        stride = (right - left) / max(1, self.points.maxlen - 1)
        previous = None
        for number, rtt, spike in self.points:
            x = right - (last - number) * stride
            if rtt is None:
                y, size = upper + (lower - upper) * 0.06, 3 * scale
                self.canvas.create_line(x - size, y - size, x + size, y + size, fill=theme.PAPER_BAD, tags="trace")
                self.canvas.create_line(x - size, y + size, x + size, y - size, fill=theme.PAPER_BAD, tags="trace")
                previous = None
                continue
            y = lower - (lower - upper) * rtt / top
            if previous:
                self.canvas.create_line(*previous, x, y, fill=theme.LIME, width=max(1, round(1.5 * scale)), tags="trace")
            if spike or number == last:
                radius = (3 if spike else 4) * scale
                self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                        fill=theme.PAPER_WARN if spike else theme.LIME, outline="", tags="trace")
            previous = x, y
        self.canvas.tag_lower("grid")
