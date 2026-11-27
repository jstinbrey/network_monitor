"""Ping view (Feature 2): connectivity test of one device, of several selected devices, or continuously (ping -t)."""
from datetime import datetime

import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.widgets.ecg_chart import EcgChart
from netmonitor.gui.widgets.host_table import HostTable
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import post, run_async
from netmonitor.models import STATUS_LABELS


class PingView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.handle, self.replies = None, 0        # the running continuous ping, for Stop; its replies drawn so far
        ctk.CTkLabel(self, text="Ping", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD)
        # Type an IP, or pick a scanned device: the list shows "ip  name", picking one keeps only the ip.
        self.ip_entry = ctk.CTkComboBox(bar, width=260, values=[], command=lambda v: self.ip_entry.set(v.split()[0]))
        self.ip_entry.set("")                       # an empty CTkComboBox otherwise shows the text "CTkComboBox"
        self.ip_entry.pack(side="left")
        self.ip_entry.bind("<Return>", lambda event: self.run())
        ctk.CTkLabel(bar, text="Packets:").pack(side="left", padx=(12, 6))
        self.count_entry = ctk.CTkEntry(bar, width=50)
        self.count_entry.insert(0, "4")
        self.count_entry.pack(side="left")
        self.run_button = ctk.CTkButton(bar, text="Run ping", command=self.run)
        self.run_button.pack(side="left", padx=12)
        self.colors = self.run_button.cget("fg_color"), self.run_button.cget("hover_color")   # restored after Stop
        self.continuous = ctk.CTkSwitch(bar, text="Continuous (-t)", command=self._mode_changed)
        self.continuous.pack(side="left")

        self.result = ctk.CTkLabel(self, text="Pick a scanned device from the list, or type an IP address.",
                                   text_color=theme.MUTED, anchor="w")
        self.result.pack(fill="x", padx=theme.PAD, pady=10)

        middle = ctk.CTkFrame(self, fg_color="transparent")
        middle.pack(fill="both", expand=True, padx=theme.PAD)
        self.log = ctk.CTkTextbox(middle, width=430, font=("Consolas", 13), state="disabled")
        self.log.pack(side="left", fill="y")
        self.chart = LatencyChart(middle)
        self.chart.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.ecg = EcgChart(middle)                 # takes the bar chart's place in continuous mode

        self.table = HostTable(self, [("ip", "IP Address", 150), ("sent", "Sent", 70), ("received", "Received", 90),
                                      ("loss", "Packet Loss", 110), ("avg", "Average", 100), ("max", "Maximum", 100),
                                      ("status", "Status", 220)])
        self.table.tree.configure(height=7)
        self.table.on_open(app.open_device)
        self.table.pack(fill="x", padx=theme.PAD, pady=theme.PAD)

    def on_show(self, ip=None, ips=None, continuous=False):
        """ip: ping this one device now, continuously if continuous=True. ips: ping all of these and list the results.
        Leaving the view does not stop a continuous ping."""
        run_async(services.devices, on_done=self._fill_devices)   # the list follows the latest scan
        if (ip or ips) and self.handle:
            return self._show_error("Stop the continuous ping first.")
        if ip or ips:
            self.continuous.select() if continuous else self.continuous.deselect()
            self._mode_changed()
        if ip:
            self.ip_entry.set(ip)
            self.run()
        if ips:
            self._busy(f"Pinging {len(ips)} devices...")
            run_async(services.run_ping_many, ips, on_done=self._show_batch, on_error=self._show_error)

    def _fill_devices(self, devices):
        if self.winfo_exists():                     # the user may have signed in or out while it loaded
            self.ip_entry.configure(values=[f"{d.ip}  {d.alias or d.hostname}" for d in devices])

    def _mode_changed(self):
        """Continuous mode: no packet count, Start instead of Run ping, and the heart-monitor chart."""
        on = bool(self.continuous.get())
        self.count_entry.configure(state="disabled" if on else "normal")
        self.run_button.configure(text="Start" if on else "Run ping")
        (self.chart if on else self.ecg).pack_forget()
        (self.ecg if on else self.chart).pack(side="left", fill="both", expand=True, padx=(12, 0))

    def run(self):
        if self.handle:                             # the button reads Stop while a continuous ping runs
            return self.stop()
        try:   # validate before starting a thread, so bad input never reaches the ping command
            ip = services.validate_ip(self.ip_entry.get())
            count = max(1, min(20, int(self.count_entry.get())))
        except ValueError:
            return self._show_error("Enter a valid IPv4 address (for example 192.168.1.1) and a packet count.")
        if self.continuous.get():
            return self._start(ip)
        self._busy(f"Pinging {ip} with {count} packets...")
        run_async(services.run_ping, ip, count, on_done=self._show_result, on_error=self._show_error)

    def _start(self, ip):
        self.ecg.clear()
        self.replies = 0
        # Replies arrive on ping's reading thread, so post() carries each one to the UI thread.
        self.handle = services.start_continuous_ping(ip, lambda session, rtt, line: post(self._on_reply, (session, rtt, line)))
        self.run_button.configure(text="Stop", fg_color=theme.RED, hover_color="#b52b27")
        self.ip_entry.configure(state="disabled")
        self.continuous.configure(state="disabled")
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
        times = f"min {r.min_ms:g} / avg {r.avg_ms:g} / max {r.max_ms:g} ms" if r.received else "no replies yet"
        self.result.configure(text_color=theme.MUTED, text=(
            f"Sent {r.sent}  ·  received {r.received}  ·  lost {r.loss_pct:g}%  ·  {times}  ·  "
            f"jitter {'-' if jitter is None else f'{jitter:g} ms'}  ·  longest outage {session.longest_outage} s"))

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
        self.run_button.configure(state="normal", text="Start" if self.continuous.get() else "Run ping",
                                  fg_color=self.colors[0], hover_color=self.colors[1])
        self.ip_entry.configure(state="normal")
        self.continuous.configure(state="normal")
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
        self._ready()

    def _show_batch(self, results):
        self.table.set_rows([{
            "ip": r.ip, "sent": r.sent, "received": r.received, "loss": f"{r.loss_pct:g}%",
            "avg": f"{r.avg_ms:g} ms" if r.rtts_ms else "-", "max": f"{r.max_ms:g} ms" if r.rtts_ms else "-",
            "status": STATUS_LABELS[r.status], "tag": theme.STATUS_TAGS[r.status],
        } for r in results])
        self.chart.plot([r.ip.rsplit(".", 1)[1] for r in results if r.rtts_ms],
                        [r.avg_ms for r in results if r.rtts_ms], "Average latency per device (last octet)")
        self.result.configure(text=f"{len(results)} devices pinged.", text_color=theme.MUTED)
        self._ready()

    def _show_error(self, error):
        if not self.winfo_exists():
            return
        self.result.configure(text=str(error), text_color=theme.RED)
        if not self.handle:                         # nothing running any more: the button may start a test
            self._ready()
