"""Ping view (Feature 2): connectivity test of one device, of several selected devices, or continuously (ping -t)."""
from datetime import datetime
from time import monotonic

import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.widgets.ecg_chart import EcgChart
from netmonitor.gui.widgets.host_table import HostTable
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import post, run_async
from netmonitor.models import STATUS_LABELS


SESSION_FIELDS = ("Sent", "Received", "Lost", "Jitter", "Min / avg / max", "Longest outage")


class PingView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.handle, self.replies = None, 0        # the running continuous ping, for Stop; its replies drawn so far
        self.choices = {}
        self.devices_request = 0
        self.batch_visible = False
        self.live_started = None
        actions, self.result = theme.page_heading(self, "Ping", "Choose a device or enter an IP address.")
        self.family = theme.SegmentedButton(actions, values=["IPv4", "IPv6"], height=38,
                                            command=lambda _: self._family_changed())
        self.family.set("IPv4")
        self.family.pack()

        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=20)
        bar.pack(fill="x", padx=theme.PAD, pady=(0, 16))
        picker = ctk.CTkFrame(bar, fg_color=theme.SUBTLE, corner_radius=22, border_width=1,
                              border_color=theme.BORDER_CONTROL)
        picker.pack(side="left", fill="x", expand=True, padx=(12, 10), pady=12)
        self.device_icon = ctk.CTkLabel(picker, text="", image=theme.icon("devices", size=16),
                                        width=30, height=30, corner_radius=15, fg_color=theme.SURFACE)
        self.device_icon.pack(side="left", padx=(6, 3))
        self.ip_entry = theme.ComboBox(picker, width=190, height=36, values=[], command=self._choose_device,
                                        fg_color=theme.SUBTLE, button_color=theme.SUBTLE, button_hover_color=theme.BORDER,
                                        border_width=0, font=theme.BODY_FONT)
        self.ip_entry.set("")
        self.ip_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=4)
        self.ip_entry.bind("<Return>", lambda _: self.run())
        self.ip_entry.bind("<KeyRelease>", lambda _: self._choose_device(self.ip_entry.get()))
        self.ip_entry.bind("<FocusIn>", lambda _: picker.configure(border_color=theme.INK, border_width=2))
        self.ip_entry.bind("<FocusOut>", lambda _: picker.configure(border_color=theme.BORDER_CONTROL, border_width=1))
        self.mode = theme.SegmentedButton(bar, values=["Packets", "Continuous"], height=40, corner_radius=20,
                                          command=lambda _: self._mode_changed())
        self.mode.set("Packets")
        self.mode.pack(side="left", padx=(0, 8))
        self.count_entry = ctk.CTkEntry(bar, width=48, height=36, justify="center")
        self.count_entry.insert(0, "4")
        self.count_entry.bind("<Return>", lambda _: self.run())
        self.count_entry.pack(side="left", padx=(0, 8))
        self.live = ctk.CTkLabel(bar, text="", fg_color=theme.LIME_SOFT, text_color=theme.TEXT,
                                 corner_radius=15, height=30, padx=8, font=theme.MONO_FONT)
        self.run_button = theme.ActionButton(bar, text="Run ping", width=110, height=40, corner_radius=20,
                                             image=theme.icon("play", theme.ON_INK, 16),
                                             command=self.run, **theme.PRIMARY)
        self.run_button.pack(side="left", padx=(0, 12))

        self.result_area = middle = ctk.CTkFrame(self, fg_color="transparent")
        middle.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, 12))
        middle.grid_columnconfigure(0, weight=2, uniform="ping")
        middle.grid_columnconfigure(1, weight=1, uniform="ping")
        middle.grid_rowconfigure(0, weight=1)
        self.chart = LatencyChart(middle, width=3.8, height=2.2)
        self.chart.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.ecg = EcgChart(middle)
        side = ctk.CTkFrame(middle, fg_color="transparent")
        side.grid(row=0, column=1, sticky="nsew")
        session = ctk.CTkFrame(side, fg_color=theme.SURFACE)
        session.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(session, text="This session", font=theme.CARD_FONT, anchor="w").pack(
            fill="x", padx=16, pady=(12, 4))
        metrics = ctk.CTkFrame(session, fg_color="transparent")
        metrics.pack(fill="x", padx=16, pady=(0, 12))
        metrics.grid_columnconfigure((0, 1), weight=1, uniform="metric")
        self.measurements = {}
        for index, label in enumerate(SESSION_FIELDS):
            row, column = divmod(index, 2)
            ctk.CTkLabel(metrics, text=label, font=theme.CAPTION_FONT, text_color=theme.MUTED, anchor="w").grid(
                row=row * 2, column=column, sticky="w", pady=(4, 0))
            self.measurements[label] = ctk.CTkLabel(metrics, text="—", font=theme.MONO_FONT, anchor="w")
            self.measurements[label].grid(row=row * 2 + 1, column=column, sticky="w")
        output = ctk.CTkFrame(side, fg_color=theme.SURFACE)
        output.pack(fill="both", expand=True)
        ctk.CTkLabel(output, text="Ping output", font=theme.CARD_FONT, anchor="w").pack(
            fill="x", padx=16, pady=(12, 4))
        self.log = ctk.CTkTextbox(output, width=160, height=80, font=theme.MONO_FONT, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.table = HostTable(self, [("ip", "IP Address", 135), ("sent", "Sent", 64), ("received", "Received", 75),
                                      ("loss", "Packet loss", 85), ("avg", "Average", 75), ("max", "Maximum", 75),
                                      ("status", "Status", 145)])
        self.table.tree.configure(height=4)
        self.table.on_open(app.open_device)

    def on_show(self, ip=None, ips=None, continuous=False):
        """ip: ping this one device now, continuously if continuous=True. ips: ping all of these and list the results.
        Leaving the view does not stop a continuous ping."""
        if (ip or ips) and (self.handle or self.run_button.cget("state") == "disabled"):
            self.result.configure(text="Stop the continuous ping first." if self.handle else
                                  "A ping test is already running.", text_color=theme.AMBER)
            return
        if ip or ips:
            target = ip or ips[0]
            self.family.set("IPv6" if ":" in target else "IPv4")
            self._family_changed()
            self.mode.set("Continuous" if continuous else "Packets")
            self._mode_changed()
        else:
            self._load_devices()
        if ip:
            self.ip_entry.set(ip)
            self._choose_device(ip)
            self.run()
        if ips:
            self._busy(f"Pinging {len(ips)} devices...")
            run_async(services.run_ping_many, ips, on_done=self._show_batch, on_error=self._show_error)

    def _family_changed(self):
        self.ip_entry.set("")
        self._choose_device("")
        self.choices.clear()
        self.ip_entry.configure(values=[])
        self.result.configure(text=f"Choose a device or enter an {self.family.get()} address.", text_color=theme.MUTED)
        self._load_devices()

    def _load_devices(self):
        self.devices_request += 1
        request = self.devices_request
        run_async(services.devices, int(self.family.get()[-1]), on_done=lambda devices: self._fill_devices(request, devices),
                  on_error=lambda _: self._fill_devices(request, ()))

    def _fill_devices(self, request, devices):
        if self.winfo_exists() and self.devices_request == request:
            display = self.ip_entry.get()
            selected = self.choices[display].ip if display in self.choices else display
            self.choices = {f"{d.alias or d.hostname} · {d.ip}": d for d in devices}
            self.ip_entry.configure(values=list(self.choices))
            label = next((name for name, device in self.choices.items() if device.ip == selected), selected)
            state = self.ip_entry.cget("state")
            if state == "disabled":
                self.ip_entry.configure(state="normal")
            self.ip_entry.set(label)
            if state == "disabled":
                self.ip_entry.configure(state="disabled")
            self._choose_device(label)

    def _choose_device(self, value):
        device = self.choices.get(value)
        self.device_icon.configure(image=theme.icon(theme.device_icon(device) if device else "devices", size=16))

    def _mode_changed(self):
        """Continuous mode: no packet count, Start instead of Run ping, and the heart-monitor chart."""
        on = self.mode.get() == "Continuous"
        if on:
            self.count_entry.pack_forget()
        else:
            self.count_entry.pack(side="left", before=self.run_button, padx=(0, 8))
        self.run_button.configure(text="Start" if on else "Run ping")
        (self.chart if on else self.ecg).grid_remove()
        (self.ecg if on else self.chart).grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        if on or not self.batch_visible:
            self.table.pack_forget()
        else:
            self.table.pack(side="bottom", before=self.result_area, fill="x", padx=theme.PAD, pady=(0, 12))

    def run(self):
        if self.run_button.cget("state") == "disabled":
            return
        if self.handle:                             # the button reads Stop while a continuous ping runs
            return self.stop()
        try:   # validate before starting a thread, so bad input never reaches the ping command
            target = self.ip_entry.get()
            ip = services.validate_ip(self.choices[target].ip if target in self.choices else target,
                                      int(self.family.get()[-1]))
        except ValueError as error:
            return self._show_error(error)
        if self.mode.get() == "Continuous":
            return self._start(ip)
        try:
            count = max(1, min(20, int(self.count_entry.get())))
        except ValueError:
            return self._show_error("Enter a packet count between 1 and 20.")
        self.batch_visible = False
        self.table.pack_forget()
        self._busy(f"Pinging {ip} with {count} packets...")
        run_async(services.run_ping, ip, count, on_done=self._show_result, on_error=self._show_error)

    def _start(self, ip):
        self._busy(f"Preparing continuous ping to {ip}…")
        self.ip_entry.configure(state="disabled")
        self.mode.configure(state="disabled")
        run_async(services.prepare_continuous_ping, ip, on_done=lambda prepared: self._start_prepared(ip, prepared),
                  on_error=self._show_error)

    def _start_prepared(self, ip, prepared):
        if not self.winfo_exists():
            return
        try:
            # Replies arrive on ping's reader thread. Deliver them on the Tk thread.
            self.handle = services.start_continuous_ping(
                prepared, lambda session, rtt, line: post(self._on_reply, (session, rtt, line)))
        except OSError as error:
            self._show_error(error)
            return
        self.ecg.clear()
        self.replies = 0
        self.live_started = monotonic()
        self.live.configure(text="Live 00:00")
        self.live.pack(side="left", before=self.run_button, padx=(0, 8))
        for label in self.measurements.values():
            label.configure(text="—", text_color=theme.TEXT)
        self.run_button.configure(text="Stop", image=theme.icon("stop", theme.ON_INK, 16), state="normal")
        self.app.buttons["Ping"].configure(text="Ping ●")
        self.result.configure(text=f"Pinging {ip} until Stop...", text_color=theme.MUTED)
        self._log(f"--- {ip}, continuous, from {datetime.now():%H:%M:%S} ---")

    def _on_reply(self, reply):
        session, rtt, line = reply
        if not self.winfo_exists() or not self.handle or session is not self.handle.session:
            return                                  # signed out, or a last line that came after Stop
        self.replies += 1
        self.ecg.add(self.replies, rtt, session.last_spike)
        base = session.baseline()
        self.ecg.note.configure(text=f"Usual for this host: {base[0]:.1f} ms ± {base[1]:.1f} ms  ·  "
                                     f"{session.spikes} slower than usual (amber)" if base else
                                f"Learning baseline ({session.learned()}/{config.BASELINE_MIN_SAMPLES})")
        self._log(line)
        r, jitter = session.result(), session.jitter_ms
        self._measure(r, jitter, session.longest_outage)
        minutes, seconds = divmod(int(monotonic() - self.live_started), 60)
        self.live.configure(text=f"Live {minutes:02}:{seconds:02}")
        target = self.ip_entry.get()
        name = (self.choices[target].alias or self.choices[target].hostname) if target in self.choices else target
        self.result.configure(text_color=theme.MUTED, text=f"{name} · {r.received} of {r.sent} replies")

    def stop(self):
        """Stop and store the session. stop_continuous_ping waits for ping to end, so it runs in a worker."""
        handle, self.handle = self.handle, None
        self.run_button.configure(text="Stopping...", state="disabled")
        run_async(services.stop_continuous_ping, handle, on_done=self._stopped, on_error=self._show_error)

    def _stopped(self, verdict):
        if self.winfo_exists():
            status, sentence = verdict
            self.result.configure(text=sentence, text_color=theme.TAG_COLORS[status])
            self._ready()

    def _ready(self):
        """No test running: the button starts a new one."""
        self.run_button.configure(state="normal", text="Start" if self.mode.get() == "Continuous" else "Run ping",
                                  image=theme.icon("play", theme.ON_INK, 16))
        self.ip_entry.configure(state="normal")
        self.mode.configure(state="normal")
        self.family.configure(state="normal")
        self.live.pack_forget()
        self.app.buttons["Ping"].configure(text="Ping")

    def _log(self, text):
        """Append to the log, keeping at most LOG_MAX_LINES lines."""
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        extra = int(self.log.index("end-1c").split(".")[0]) - 1 - config.LOG_MAX_LINES
        if extra > 0:
            self.log.delete("1.0", f"{extra + 1}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _busy(self, message):
        self.run_button.configure(state="disabled")
        self.family.configure(state="disabled")
        self.result.configure(text=message, text_color=theme.MUTED)

    def _show_result(self, result):
        self._log(f"--- {result.ip} at {result.timestamp[11:]} ---\n" + "\n".join(result.raw_lines) + "\n")
        times = (f"min {result.min_ms:g} ms, avg {result.avg_ms:g} ms, max {result.max_ms:g} ms"
                 if result.rtts_ms else "no replies")
        self.result.configure(
            text=f"{STATUS_LABELS[result.status]}:  sent {result.sent}, received {result.received}, "
                 f"lost {result.loss_pct:g}%   |   {times}",
            text_color=theme.TAG_COLORS[theme.STATUS_TAGS[result.status]])
        self.chart.plot([str(n) for n in range(1, len(result.rtts_ms) + 1)], result.rtts_ms,
                        f"Reply times from {result.ip}")
        self._measure(result)
        self._ready()

    def _measure(self, result, jitter=None, outage=None):
        times = f"{result.min_ms:g}/{result.avg_ms:g}/{result.max_ms:g} ms" if result.received else "—"
        for key, text in zip(SESSION_FIELDS, (result.sent, result.received, f"{result.loss_pct:g}%",
                                               f"{jitter:g} ms" if jitter is not None else "—", times,
                                               f"{outage} s" if outage is not None else "—")):
            self.measurements[key].configure(text=str(text),
                                             text_color=theme.AMBER if key == "Lost" and result.loss_pct else theme.TEXT)

    def _show_batch(self, results):
        self.batch_visible = True
        self.table.pack(side="bottom", before=self.result_area, fill="x", padx=theme.PAD, pady=(0, 12))
        self.table.set_rows([{
            "ip": r.ip, "sent": r.sent, "received": r.received, "loss": f"{r.loss_pct:g}%",
            "avg": f"{r.avg_ms:g} ms" if r.rtts_ms else "-", "max": f"{r.max_ms:g} ms" if r.rtts_ms else "-",
            "status": STATUS_LABELS[r.status], "tag": theme.STATUS_TAGS[r.status],
        } for r in results])
        self.chart.plot([r.ip for r in results if r.rtts_ms],
                        [r.avg_ms for r in results if r.rtts_ms], "Average latency per device", distinct_labels=True)
        self.result.configure(text=f"{len(results)} devices pinged.", text_color=theme.MUTED)
        self._ready()

    def _show_error(self, error):
        if not self.winfo_exists():
            return
        self.result.configure(text=str(error), text_color=theme.RED)
        if not self.handle:                         # nothing running any more: the button may start a test
            self._ready()
