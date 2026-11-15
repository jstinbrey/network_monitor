"""Devices view (Feature 1): shows the local network details and scans for active devices."""
import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.host_table import HostTable
from netmonitor.gui.worker import post, run_async


class DevicesView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(self, text="Devices", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))

        self.info = ctk.CTkLabel(self, text="Detecting network...", justify="left", anchor="w")
        self.info.pack(fill="x", padx=theme.PAD)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=12)
        self.scan_button = ctk.CTkButton(bar, text="Scan network", command=self.scan)
        self.scan_button.pack(side="left")
        self.progress = ctk.CTkProgressBar(bar, width=260)
        self.progress.set(0)
        self.progress.pack(side="left", padx=12)
        self.status = ctk.CTkLabel(bar, text="No devices yet. Run a scan.", text_color=theme.MUTED)
        self.status.pack(side="left")
        ctk.CTkButton(bar, text="Ping selected", command=self.ping_selected).pack(side="right")

        self.table = HostTable(self, [("ip", "IP Address", 140), ("hostname", "Hostname", 260),
                                      ("mac", "MAC Address", 170), ("status", "Status", 210),
                                      ("tags", "Tags", 120)])
        self.table.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, theme.PAD))
        self.table.tree.bind("<Double-1>", self._ping_row)

    def ping_selected(self):
        """Feature 2: ping every selected device and show the results in the Ping view."""
        if self.table.selected():
            self.app.show("Ping", ips=self.table.selected())
        else:
            self.status.configure(text="Select one or more devices first (Ctrl+click for several).")

    def _ping_row(self, event):
        row = self.table.tree.identify_row(event.y)   # empty when the heading was double-clicked
        if row:
            self.app.show("Ping", ip=row)

    def on_show(self):
        """Called each time this view is opened: refresh the network details."""
        run_async(services.network_info, on_done=self._show_info, on_error=self._show_error)

    def scan(self):
        self.scan_button.configure(state="disabled")
        self.progress.set(0)
        self.status.configure(text="Scanning...", text_color=theme.MUTED)
        # The scan reports progress from its own thread, so post() carries it to the UI thread.
        run_async(services.scan, lambda done, total: post(self._show_progress, (done, total)),
                  on_done=self._show_devices, on_error=self._show_error)

    def _show_info(self, info):
        notes = ""
        if info.mask_assumed:
            notes += "\nSubnet mask could not be read; 255.255.255.0 is assumed."
        if info.truncated:
            notes += "\nThe network is larger than a /24; only this /24 is scanned."
        self.info.configure(text=(
            f"Hostname: {info.hostname}        Local IP: {info.local_ip}        Subnet mask: {info.netmask}\n"
            f"Network range: {info.cidr}  ({info.first_host} to {info.last_host})        "
            f"Gateway: {info.gateway or 'none'}        Usable hosts: {info.host_count}{notes}"))

    def _show_progress(self, progress):
        done, total = progress
        self.progress.set(done / total)
        self.status.configure(text=f"{done} / {total}")

    def _show_devices(self, devices):
        self.table.set_rows([{
            "ip": d.ip, "hostname": d.hostname, "mac": d.mac or "-",
            "status": "Online" if d.replied_icmp else "No ICMP reply (host up)",
            "tags": ", ".join(tag for tag, on in (("This PC", d.is_self), ("Gateway", d.is_gateway)) if on),
            "tag": "good" if d.replied_icmp else "warn",
        } for d in devices])
        self.status.configure(text=f"{len(devices)} devices found", text_color=theme.MUTED)
        self.scan_button.configure(state="normal")

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
        self.scan_button.configure(state="normal")