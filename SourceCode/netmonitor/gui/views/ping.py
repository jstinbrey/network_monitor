"""Ping view (Feature 2): connectivity test of one device, or of several selected devices."""
import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.host_table import HostTable
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import run_async
from netmonitor.models import STATUS_LABELS


class PingView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="Ping", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD)
        self.ip_entry = ctk.CTkEntry(bar, width=180, placeholder_text="IP address")
        self.ip_entry.pack(side="left")
        self.ip_entry.bind("<Return>", lambda event: self.run())
        ctk.CTkLabel(bar, text="Packets:").pack(side="left", padx=(12, 6))
        self.count_entry = ctk.CTkEntry(bar, width=50)
        self.count_entry.insert(0, "4")
        self.count_entry.pack(side="left")
        self.run_button = ctk.CTkButton(bar, text="Run ping", command=self.run)
        self.run_button.pack(side="left", padx=12)

        self.result = ctk.CTkLabel(self, text="Enter an IP address, or pick devices in the Devices view.",
                                   text_color=theme.MUTED, anchor="w")
        self.result.pack(fill="x", padx=theme.PAD, pady=10)

        middle = ctk.CTkFrame(self, fg_color="transparent")
        middle.pack(fill="both", expand=True, padx=theme.PAD)
        self.log = ctk.CTkTextbox(middle, width=430, font=("Consolas", 13), state="disabled")
        self.log.pack(side="left", fill="y")
        self.chart = LatencyChart(middle)
        self.chart.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.table = HostTable(self, [("ip", "IP Address", 150), ("sent", "Sent", 70), ("received", "Received", 90),
                                      ("loss", "Packet Loss", 110), ("avg", "Average", 100), ("max", "Maximum", 100),
                                      ("status", "Status", 220)])
        self.table.tree.configure(height=7)
        self.table.on_open(app.open_device)
        self.table.pack(fill="x", padx=theme.PAD, pady=theme.PAD)

    def on_show(self, ip=None, ips=None):
        """ip: ping this one device now. ips: ping all of these and list the results."""
        if ip:
            self.ip_entry.delete(0, "end")
            self.ip_entry.insert(0, ip)
            self.run()
        if ips:
            self._busy(f"Pinging {len(ips)} devices...")
            run_async(services.run_ping_many, ips, on_done=self._show_batch, on_error=self._show_error)

    def run(self):
        try:   # validate before starting a thread, so bad input never reaches the ping command
            ip = services.validate_ip(self.ip_entry.get())
            count = max(1, min(20, int(self.count_entry.get())))
        except ValueError:
            return self._show_error("Enter a valid IPv4 address (for example 192.168.1.1) and a packet count.")
        self._busy(f"Pinging {ip} with {count} packets...")
        run_async(services.run_ping, ip, count, on_done=self._show_result, on_error=self._show_error)

    def _busy(self, message):
        self.run_button.configure(state="disabled")
        self.result.configure(text=message, text_color=theme.MUTED)

    def _show_result(self, result):
        self.log.configure(state="normal")
        self.log.insert("end", f"--- {result.ip} at {result.timestamp[11:]} ---\n" + "\n".join(result.raw_lines) + "\n\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        times = (f"min {result.min_ms:g} ms, avg {result.avg_ms:g} ms, max {result.max_ms:g} ms"
                 if result.rtts_ms else "no replies")
        self.result.configure(
            text=f"{STATUS_LABELS[result.status]}:  sent {result.sent}, received {result.received}, "
                 f"lost {result.loss_pct:g}%   |   {times}",
            text_color=theme.TAG_COLORS[theme.STATUS_TAGS[result.status]])
        self.chart.plot([str(n) for n in range(1, len(result.rtts_ms) + 1)], result.rtts_ms,
                        f"Reply times from {result.ip}")
        self.run_button.configure(state="normal")

    def _show_batch(self, results):
        self.table.set_rows([{
            "ip": r.ip, "sent": r.sent, "received": r.received, "loss": f"{r.loss_pct:g}%",
            "avg": f"{r.avg_ms:g} ms" if r.rtts_ms else "-", "max": f"{r.max_ms:g} ms" if r.rtts_ms else "-",
            "status": STATUS_LABELS[r.status], "tag": theme.STATUS_TAGS[r.status],
        } for r in results])
        self.chart.plot([r.ip.rsplit(".", 1)[1] for r in results if r.rtts_ms],
                        [r.avg_ms for r in results if r.rtts_ms], "Average latency per device (last octet)")
        self.result.configure(text=f"{len(results)} devices pinged.", text_color=theme.MUTED)
        self.run_button.configure(state="normal")

    def _show_error(self, error):
        self.result.configure(text=str(error), text_color=theme.RED)
        self.run_button.configure(state="normal")