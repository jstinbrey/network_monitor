"""An in-window device drawer with stored history and actions."""
from math import ceil
import tkinter as tk

import customtkinter as ctk

from netmonitor import config, models, services
from netmonitor.gui import theme
from netmonitor.gui.views.statistics import ms
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import run_async

TILES = ("Average", "Maximum", "Packet loss", "Jitter")
STATUS_TONES = {
    models.ONLINE: (theme.GREEN_SOFT, theme.GREEN),
    models.DEGRADED: (theme.AMBER_SOFT, theme.AMBER),
    models.NO_ICMP: (theme.AMBER_SOFT, theme.AMBER),
    models.OFFLINE: (theme.RED_SOFT, theme.RED),
    models.NO_DATA: (theme.SUBTLE, theme.MUTED),
}


def ports_line(open_ports):
    """Summarize the open ports and return the status color."""
    if open_ports is None:
        return "Open ports: not checked yet", theme.MUTED
    if not open_ports:
        return f"Open ports: none of the {len(config.COMMON_PORTS)} common ports", theme.GREEN
    text = "Open ports: " + ", ".join(f"{p['service']} ({p['port']})" for p in open_ports)
    return text, theme.RED if any(p["risk"] == "high" for p in open_ports) else theme.MUTED


def verdict(stats):
    """Summarize reachability, latency, and loss for this device."""
    parts = [models.STATUS_LABELS[stats.status]]
    if stats.avg_ms is not None:
        parts.append("high latency" if stats.avg_ms > config.LATENCY_WARN_MS else "normal latency")
    if stats.loss_pct:
        parts.append(f"{stats.loss_pct:g}% packet loss")
    return "  ·  ".join(parts)


class DevicePanel(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, width=440, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER)
        self.pack_propagate(False)
        self.app, self.ip = app, None
        self.request = 0
        self.busy = False
        self.presence = []
        self.known = True

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 12))
        line = ctk.CTkFrame(header, fg_color="transparent")
        line.pack(fill="x")
        self.close_button = theme.ActionButton(line, text="", image=theme.icon("x", size=14),
                                                width=32, height=32, corner_radius=16,
                                                command=app.close_device, **theme.GHOST)
        self.close_button.pack(side="right", anchor="n", padx=(4, 0))
        theme.tooltip(self.close_button, "Close device details")
        badge = ctk.CTkFrame(line, width=44, height=44, corner_radius=22, fg_color=theme.SUBTLE)
        badge.pack(side="left", anchor="n", padx=(0, 12))
        self.icon = ctk.CTkLabel(badge, text="", image=theme.icon("devices"))
        self.icon.place(relx=0.5, rely=0.5, anchor="center")
        description = ctk.CTkFrame(line, fg_color="transparent")
        description.pack(fill="x", expand=True)
        title = ctk.CTkFrame(description, fg_color="transparent")
        title.pack(fill="x")
        self.rename_button = None
        if app.is_admin or app.user is None:
            icon = "pencil" if app.is_admin else "lock"
            self.rename_button = theme.ActionButton(title, text="", image=theme.icon(icon, size=14),
                                                     width=30, height=30, corner_radius=15,
                                                     command=self.rename, **theme.GHOST)
            self.rename_button.pack(side="right", padx=(4, 0))
            theme.tooltip(self.rename_button, "Rename device")
        self.name = theme.WrappedLabel(title, text="", height=30, font=theme.TITLE_FONT)
        self.name.pack(side="left", fill="x", expand=True)
        self.address = theme.WrappedLabel(description, text="", height=18, font=theme.MONO_FONT, text_color=theme.MUTED)
        self.address.pack(fill="x")
        self.seen = theme.WrappedLabel(description, text="", height=18, font=theme.CAPTION_FONT, text_color=theme.MUTED)
        self.seen.pack(fill="x")
        summary = ctk.CTkFrame(header, fg_color="transparent")
        summary.pack(fill="x", pady=(8, 0))
        self.status_chip = ctk.CTkLabel(summary, text="No data", height=24, corner_radius=12, padx=8,
                                        fg_color=theme.SUBTLE, text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.status_chip.pack(side="left")
        self.verdict = theme.WrappedLabel(summary, text="", font=theme.CAPTION_FONT, text_color=theme.TEXT_2)
        self.verdict.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.content = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=theme.SURFACE)
        self.content.pack(fill="both", expand=True, padx=(20, 8))
        tiles = ctk.CTkFrame(self.content, fg_color="transparent")
        tiles.pack(fill="x")
        self.tiles = {}
        for index, title in enumerate(TILES):
            tiles.grid_columnconfigure(index, weight=1, uniform="measurement")
            tile = ctk.CTkFrame(tiles, fg_color=theme.SUBTLE, corner_radius=12)
            tile.grid(row=0, column=index, sticky="nsew", padx=(0, 6 if index < 3 else 0))
            ctk.CTkLabel(tile, text=title, font=theme.CAPTION_FONT, text_color=theme.MUTED).pack(
                anchor="w", padx=8, pady=(5, 0))
            self.tiles[title] = ctk.CTkLabel(tile, text="—", font=theme.BODY_FONT, anchor="w")
            self.tiles[title].pack(fill="x", padx=8, pady=(0, 5))

        history = ctk.CTkFrame(self.content, fg_color="transparent")
        history.pack(fill="x", pady=(16, 0))
        ctk.CTkLabel(history, text="Last 10 tests", font=theme.CARD_FONT).pack(side="left")
        self.baseline = ctk.CTkLabel(history, text="", text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.baseline.pack(side="right")
        self.chart = LatencyChart(self.content, width=3.5, height=1.3)
        self.chart.pack(fill="x")

        uptime = ctk.CTkFrame(self.content, fg_color="transparent")
        uptime.pack(fill="x", pady=(12, 2))
        ctk.CTkLabel(uptime, text="Uptime, last 24 hours", font=theme.CARD_FONT).pack(side="left")
        self.uptime = ctk.CTkLabel(uptime, text="—", font=theme.MONO_FONT)
        self.uptime.pack(side="right")
        self.strip = tk.Canvas(self.content, width=1, height=14, bg=theme.color(theme.SURFACE), highlightthickness=0)
        self.strip.pack(fill="x")
        self.strip.bind("<Configure>", self._draw_uptime)
        theme.appearance_callback(self.strip, self._draw_uptime)
        self.uptime_note = theme.WrappedLabel(self.content, text="", font=theme.CAPTION_FONT, text_color=theme.MUTED)
        self.uptime_note.pack(fill="x", pady=(4, 0))

        ports = ctk.CTkFrame(self.content, fg_color="transparent")
        ports.pack(fill="x", pady=(14, 4))
        ctk.CTkLabel(ports, text="Open ports", font=theme.CARD_FONT).pack(side="left")
        self.port_button = self.known_button = None
        if app.is_admin or app.user is None:
            if app.is_admin:
                self.port_button = theme.ActionButton(ports, text="Check ports", width=128, height=32,
                                                       corner_radius=16, image=theme.icon("refresh", size=14),
                                                       command=self.check_ports)
            else:
                self.port_button = theme.locked_button(ports, "Check ports", self.check_ports, width=128)
            self.port_button.pack(side="right")
        self.port_rows = ctk.CTkFrame(self.content, fg_color="transparent")
        self.port_rows.pack(fill="x")
        if app.is_admin or app.user is None:
            actions = ctk.CTkFrame(self.content, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 6))
            if app.is_admin:
                self.known_button = theme.ActionButton(actions, text="Mark as known", width=140, height=34,
                                                       command=self.mark_known)
            else:
                self.known_button = theme.locked_button(actions, "Mark as known", self.mark_known, width=140)
            self.known_button.pack(side="left")
            theme.WrappedLabel(self.content, text="Only check devices on a network you own or administer.",
                               text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(fill="x", pady=(0, 6))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", before=self.content._parent_frame, fill="x", padx=20, pady=(0, 16))
        self.status = theme.WrappedLabel(footer, text="", font=theme.CAPTION_FONT, text_color=theme.MUTED)
        controls = ctk.CTkFrame(footer, fg_color="transparent")
        controls.pack(fill="x")
        self.ping_button = theme.ActionButton(controls, text="Ping", width=80, height=40, corner_radius=20,
                                               image=theme.icon("ping", theme.ON_INK, 16),
                                               command=self.ping, **theme.PRIMARY)
        self.ping_button.pack(side="left")
        theme.ActionButton(controls, text="Continuous ping", width=146, height=40, corner_radius=20,
                           image=theme.icon("play", size=16), command=self.continuous_ping).pack(side="left", padx=8)
        self.trace_button = theme.ActionButton(controls, text="Traceroute", width=118, height=40, corner_radius=20,
                                               image=theme.icon("traceroute", size=16), command=self.traceroute)
        self.trace_button.pack(side="left")

    def show(self, ip):
        """Reveal the drawer, discarding the previous host's content while the next loads."""
        if self.ip == ip:
            self.focus_first()
            return
        self.ip = ip
        self._set_busy(False)
        self.known = True
        self.name.configure(text=ip)
        self.icon.configure(image=theme.icon("devices"))
        for label in (self.address, self.seen, self.verdict, self.baseline, self.uptime_note):
            label.configure(text="")
        self.status_chip.configure(text="Loading", fg_color=theme.SUBTLE, text_color=theme.MUTED)
        self.uptime.configure(text="—")
        self.presence = []
        self._draw_uptime()
        for label in self.tiles.values():
            label.configure(text="—")
        self.chart.plot([], [], "")
        self._show_ports(None)
        self._notice("Loading device details…")
        self.content._parent_canvas.yview_moveto(0)
        self._position()
        self.lift()
        self.focus_first()
        self._load(clear_status=True)

    def _position(self):
        margin = round(self._apply_widget_scaling(12))
        tk.Place.place_configure(self, relx=1, x=-margin, y=margin, relheight=1, height=-2 * margin, anchor="ne")

    def _set_scaling(self, *args):
        super()._set_scaling(*args)
        if self.winfo_manager() == "place":
            self._position()

    def hide(self):
        """Dismiss the drawer and ignore worker results from the previous opening."""
        self.ip = None
        self.request += 1
        self.place_forget()

    def focus_first(self):
        tk.Misc.focus_set(self.close_button)

    def focus_last(self):
        tk.Misc.focus_set(self.trace_button)

    def _run(self, service, *args, done):
        self.request += 1
        request = self.request
        def complete(result):
            if request == self.request and self.winfo_exists():
                self._set_busy(False)
                done(result)
        def failed(error):
            if request == self.request and self.winfo_exists():
                self._set_busy(False)
                self._notice(str(error), theme.RED)
        run_async(service, *args, on_done=complete, on_error=failed)

    def _set_busy(self, busy):
        self.busy = busy
        for button in (self.ping_button, self.port_button, self.rename_button, self.known_button):
            if button:
                button.configure(state="disabled" if busy or button is self.known_button and self.known else "normal")

    def _load(self, clear_status=False):
        def loaded(detail):
            if clear_status:
                self._notice()
            self._show(detail)
        self._run(services.device_detail, self.ip, done=loaded)

    def _notice(self, message="", color=theme.MUTED):
        self.status.configure(text=message, text_color=color)
        if message:
            self.status.pack(before=self.ping_button.master, fill="x", pady=(0, 4))
        else:
            self.status.pack_forget()

    def _show(self, detail):
        device, stats = detail.device, detail.stats
        self.known = device.known
        self._set_busy(False)
        self.name.configure(text=device.alias or device.hostname)
        self.icon.configure(image=theme.icon(theme.device_icon(device), size=20))
        self.address.configure(text=f"{device.ip} · {device.mac or 'MAC unknown'}")
        first_seen = device.first_seen[:10]
        self.seen.configure(text=" · ".join(filter(None, (device.vendor, f"first seen {first_seen}" if first_seen else ""))))
        background, foreground = STATUS_TONES[stats.status]
        status = "Up, no ping reply" if stats.status == models.NO_ICMP else models.STATUS_LABELS[stats.status]
        self.status_chip.configure(text=status, fg_color=background, text_color=foreground)
        self.verdict.configure(text=verdict(stats).partition("  ·  ")[2] or "No latency measurements yet")
        loss = "No data" if stats.loss_pct is None else f"{stats.loss_pct:g}%"
        for title, text in zip(TILES, (ms(stats.avg_ms), ms(stats.max_ms), loss, ms(stats.jitter_ms))):
            self.tiles[title].configure(text=text)
        self.baseline.configure(text=f"Usual {detail.baseline_ms:g} ms" if detail.baseline_ms is not None else "")
        self.chart.plot([result.timestamp[11:16] if i in (0, 4, len(detail.history) - 1) else ""
                         for i, result in enumerate(detail.history)],
                        [result.avg_ms or 0 for result in detail.history],
                        "" if detail.history else "No ping tests stored yet", distinct_labels=True,
                        baseline=detail.baseline_ms)
        self.presence = [up for _, up in detail.presence]
        self.uptime.configure(text=f"{detail.uptime_pct:g}%" if detail.uptime_pct is not None else "—")
        self.uptime_note.configure(text=f"{len(self.presence)} watch checks · hollow marks show no reply"
                                   if self.presence else "No Watch checks in the last 24 hours.")
        self._draw_uptime()
        self._show_ports(detail.open_ports)
        if self.port_button and self.app.is_admin:
            self.port_button.configure(text="Check again" if detail.open_ports is not None else "Check ports")
        if devices := self.app.views.get("Devices"):
            devices.update_device(detail)

    def _draw_uptime(self, event=None):
        self.strip.configure(bg=theme.color(theme.SURFACE))
        self.strip.delete("all")
        if self.presence:
            width = self.strip.winfo_width()
            group = max(1, ceil(len(self.presence) / 52))
            checks = [all(self.presence[i:i + group]) for i in range(0, len(self.presence), group)]
            step = width / len(checks)
            for index, up in enumerate(checks):
                self.strip.create_rectangle(index * step + 1, 2, (index + 1) * step - 2, 11,
                                            fill=theme.color(theme.GREEN) if up else "",
                                            outline=theme.color(theme.GREEN if up else theme.RED))

    def _show_ports(self, ports):
        for row in self.port_rows.winfo_children():
            row.destroy()
        if not ports:
            summary, color = ports_line(ports)
            caption = summary.partition(": ")[2].capitalize()
            theme.WrappedLabel(self.port_rows, text=caption, text_color=color).pack(fill="x")
        for port in ports or ():
            row = ctk.CTkFrame(self.port_rows, fg_color=theme.SUBTLE, corner_radius=12)
            row.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(row, text=str(port["port"]), width=48, font=theme.MONO_FONT).pack(side="left", padx=8, pady=5)
            risk = port["risk"] == "high"
            ctk.CTkLabel(row, text="Review" if risk else "Info", height=22, corner_radius=11, padx=8,
                         text_color=theme.RED if risk else theme.BLUE,
                         fg_color=theme.RED_SOFT if risk else theme.BLUE_SOFT).pack(side="right", padx=8)
            theme.WrappedLabel(row, text=port["service"]).pack(side="left", fill="x", expand=True)

    def ping(self):
        if self.busy:
            return
        self._notice(f"Pinging {self.ip}…")
        self._set_busy(True)
        self._run(services.run_ping, self.ip, done=self._pinged)

    def _pinged(self, result):
        times = f" · {result.avg_ms:g} ms average" if result.rtts_ms else ""
        self._notice(f"{result.received} of {result.sent} replies{times}.",
                     theme.TAG_COLORS.get(theme.STATUS_TAGS.get(result.status), theme.MUTED))
        self._load()

    def traceroute(self):
        self.app.show("Traceroute", ip=self.ip)

    def continuous_ping(self):
        self.app.show("Ping", ip=self.ip, continuous=True)

    def mark_known(self):
        if not self.app.user:
            self._ask_admin("mark this device as known", "Sign in and mark", DevicePanel.mark_known)
        elif not self.busy:
            self._notice("Marking device as known…")
            self._set_busy(True)
            self._run(services.mark_known, self.ip, done=lambda _: self._load(clear_status=True))

    def check_ports(self):
        if not self.app.user:
            self._ask_admin("check ports", "Sign in and check", DevicePanel.check_ports)
        elif not self.busy:
            self._notice(f"Checking {len(config.COMMON_PORTS)} common ports…")
            self._set_busy(True)
            self._run(services.check_ports, self.ip, done=self._saved)

    def rename(self):
        if not self.app.user:
            self._ask_admin("rename this device", "Sign in and rename", DevicePanel.rename)
        elif not self.busy:
            dialog = ctk.CTkInputDialog(title="Rename device", text=f"Name for {self.ip}\nLeave empty to use its hostname.")
            if (name := dialog.get_input()) is not None:
                self._set_busy(True)
                self._run(services.set_alias, self.ip, name, done=self._saved)

    def _saved(self, detail):
        self._notice()
        self._show(detail)

    def _ask_admin(self, action, submit, callback):
        ip, app = self.ip, self.app
        app.ask_login(f"Sign in to {action}", f"An administrator account is required for this action on {ip}.",
                      submit, lambda: callback(app.open_device(ip)))
