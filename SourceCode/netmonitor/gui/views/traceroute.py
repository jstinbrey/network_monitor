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
        self.targets = {}
        self.target_request = 0
        actions, _ = theme.page_heading(self, "Traceroute", "Every router between this PC and a target, and where delay starts")
        self.family = theme.SegmentedButton(actions, values=["IPv4", "IPv6"], height=38,
                                            command=lambda _: self._family_changed())
        self.family.set("IPv4")
        self.family.pack()

        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE)
        bar.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        self.button = theme.ActionButton(bar, text="Trace", width=100, height=40, corner_radius=20,
                                          image=theme.icon("traceroute", theme.ON_INK, 16),
                                          command=self.trace, **theme.PRIMARY)
        self.button.pack(side="right", padx=12, pady=12)
        picker = ctk.CTkFrame(bar, fg_color=theme.SUBTLE, corner_radius=20, border_width=1,
                              border_color=theme.BORDER_CONTROL)
        picker.pack(side="left", fill="x", expand=True, padx=(12, 10))
        self.target = theme.ComboBox(picker, width=208, height=32, corner_radius=16, values=[], fg_color=theme.SUBTLE,
                                     button_color=theme.SUBTLE, button_hover_color=theme.BORDER, border_width=0,
                                     font=theme.BODY_FONT)
        self.target.set("")
        self.target.pack(fill="x", expand=True, padx=12, pady=4)
        self.target.bind("<Return>", lambda event: self.trace())
        self.target.bind("<FocusIn>", lambda _: picker.configure(border_color=theme.INK, border_width=2))
        self.target.bind("<FocusOut>", lambda _: picker.configure(border_color=theme.BORDER_CONTROL, border_width=1))
        for label in ("Router", "1.1.1.1", "google.com"):
            shortcut = theme.ActionButton(bar, text=label, width=72, height=28, corner_radius=14,
                                          fg_color=theme.SUBTLE, border_width=0,
                                          command=lambda value=label: self._choose_target(value))
            shortcut.pack(side="left", padx=(0, 4))
            if label == "1.1.1.1":
                self.cloudflare = shortcut

        result = ctk.CTkFrame(self, fg_color=theme.SURFACE)
        result.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        theme.icon_badge(result, "traceroute", 36, theme.SUBTLE, theme.TEXT, 18).pack(side="left", padx=16, pady=12)
        self.status = theme.WrappedLabel(result, text="", text_color=theme.MUTED, width=86, font=theme.CAPTION_FONT)
        self.status.pack(side="right", padx=12)
        self.verdict = theme.WrappedLabel(result, text="Choose a device or enter an IP address or hostname.",
                                          text_color=theme.TEXT, font=theme.CARD_FONT)
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
        selected = self._target_address()
        family = self.family.get()

        def use_router(gateway):
            if self.winfo_exists() and self.family.get() == family and self._target_address() == selected:
                if gateway:
                    self._set_target(gateway)
                    self.target.focus_set()
                else:
                    self._show_error(f"A default {family} gateway could not be found.")

        if value == "Router":
            if family == "IPv6":
                run_async(services.ipv6_gateway, on_done=use_router, on_error=self._show_error)
            else:
                run_async(services.network_info, on_done=lambda info: use_router(info.gateway), on_error=self._show_error)
        else:
            if value == "1.1.1.1" and family == "IPv6":
                value = "2606:4700:4700::1111"
            self._set_target(value)
            self.target.focus_set()

    def _target_address(self):
        value = self.target.get().strip()
        return self.targets.get(value, value)

    def _set_target(self, address):
        self.target.set(next((label for label, ip in self.targets.items() if ip == address), address))

    def _fill_targets(self, request, devices):
        if self.winfo_exists() and request == self.target_request:
            address = self._target_address()
            self.targets = {f"{d.alias or d.hostname} · {d.ip}": d.ip for d in devices}
            self.target.configure(values=list(self.targets))
            self._set_target(address)

    def _family_changed(self):
        self.targets.clear()
        self.target.set("")
        self.target.configure(values=[])
        self.cloudflare.configure(text="Cloudflare" if self.family.get() == "IPv6" else "1.1.1.1")
        self.verdict.configure(text=f"Choose a device or enter an {self.family.get()} address or hostname.",
                               text_color=theme.TEXT)
        self._load_targets()

    def _load_targets(self):
        self.target_request += 1
        request = self.target_request
        run_async(services.devices, int(self.family.get()[-1]), on_done=lambda devices: self._fill_targets(request, devices),
                  on_error=lambda _: self._fill_targets(request, ()))

    def _toggle_chart(self):
        if self.chart.winfo_manager():
            self.chart.pack_forget()
        else:
            self.chart.pack(side="bottom", before=self.chart_anchor, fill="x", padx=8, pady=(0, 8))
            self._draw_chart()

    def on_show(self, ip=None):
        """ip: trace this device now (the device panel's Traceroute button)."""
        if ip and self.button.cget("text") == "Trace" and self.button.cget("state") == "normal":
            self.family.set("IPv6" if ":" in ip else "IPv4")
            self._family_changed()
            self._set_target(ip)
            self.trace()
        else:
            self._load_targets()

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
        self.family.configure(state="disabled")
        self.status.configure(text="Starting...", text_color=theme.MUTED)
        # Hops arrive on tracert's own reading thread, so post() carries each one to the UI thread.
        run_async(services.start_traceroute, self._target_address(),
                  lambda hop: post(self._add_hop, hop), lambda result: post(self._done, result), int(self.family.get()[-1]),
                  on_done=self._started, on_error=self._show_error)

    def _started(self, handle):
        if self.winfo_exists() and self.button.cget("state") == "disabled":
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
        self.family.configure(state="normal")

    def _show_error(self, error):
        if not self.winfo_exists():
            return
        self.verdict.configure(text=str(error), text_color=theme.RED)
        self.status.configure(text="")
        self.button.configure(state="normal")
        if not self.handle:
            self.family.configure(state="normal")

    def _style_rows(self, _mode=None):
        for tag, token in theme.TAG_COLORS.items():
            self.table.tag_configure(tag, foreground=theme.color(token))
