"""Devices table with search, status filters, and actions for selected hosts."""
from datetime import datetime
from time import monotonic
import tkinter as tk

import customtkinter as ctk

from netmonitor import models, services
from netmonitor.gui import theme
from netmonitor.gui.widgets.host_table import DeviceTable
from netmonitor.gui.worker import post, run_async

FILTERS = ("All", "Online", "Issues", "New")
ISSUES = {models.DEGRADED, models.NO_ICMP, models.OFFLINE}


def matches(device, status, filter_name, query):
    """Match the selected filter and each entered search term."""
    group = (filter_name == "All" or
             filter_name == "Online" and status in models.REACHABLE_STATUSES or
             filter_name == "Issues" and status in ISSUES or
             filter_name == "New" and not device.known)
    text = " ".join(filter(None, (device.alias, device.hostname, device.ip, device.mac, device.vendor))).casefold()
    return group and all(term in text for term in query.casefold().split())


class DevicesView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.devices, self.stats = {}, {}
        self.filter_name = "All"
        self.scan_started = self.last_scan = None
        self.details_open = False
        self.request = 0
        self.menu = tk.Menu(self, tearoff=False)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD, pady=(12, 12))
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right", anchor="n", padx=(8, 0))
        self.scan_state = "normal" if app.is_admin or not app.user else "disabled"
        self.scan_button = (theme.ActionButton(controls, text="Scan network", command=self.scan, width=144, height=40,
                                               image=theme.icon("radar", theme.ON_INK), corner_radius=20,
                                               state=self.scan_state, **theme.PRIMARY) if app.user else
                            theme.locked_button(controls, "Scan network", app.ask_scan, width=144))
        self.scan_button.pack(side="right")
        if watch := app.add_watch_switch(controls):
            watch.pack_configure(padx=(0, 8))
        ctk.CTkLabel(header, text="Devices", font=theme.TITLE_FONT, anchor="w").pack(fill="x")
        self.status = theme.WrappedLabel(header, text="Loading devices…", text_color=theme.MUTED)
        self.status.pack(fill="x")
        self.progress = ctk.CTkProgressBar(header, width=210)

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=theme.PAD, pady=(0, 12))
        search = ctk.CTkFrame(toolbar, fg_color=theme.SURFACE, corner_radius=20, border_width=1,
                              border_color=theme.BORDER_CONTROL, height=40)
        search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(search, text="", image=theme.icon("search", theme.MUTED, 16), width=20).pack(
            side="left", padx=(12, 4))
        self.search = ctk.CTkEntry(search, width=180, height=34, border_width=0, fg_color=theme.SURFACE,
                                   placeholder_text="Search by name, IP, or maker")
        self.search.pack(side="left", fill="x", expand=True, pady=3, padx=(0, 12))
        self.search.bind("<Escape>", self._clear_search)
        self.search.bind("<FocusIn>", lambda _: search.configure(border_color=theme.INK, border_width=2))
        self.search.bind("<FocusOut>", lambda _: search.configure(border_color=theme.BORDER_CONTROL, border_width=1))
        self.filters = {}
        for name in FILTERS:
            button = theme.ActionButton(toolbar, text=name, width=72, height=36, corner_radius=18,
                                        command=lambda value=name: self._select_filter(value))
            button.pack(side="left", padx=(0, 8))
            self.filters[name] = button
        theme.ActionButton(toolbar, text="Network details", width=110, height=34, command=self._toggle_details,
                           **theme.GHOST).pack(side="right")
        self.info = theme.WrappedLabel(self, text="Reading network details…", text_color=theme.MUTED)

        self.card = ctk.CTkFrame(self, fg_color=theme.SURFACE)
        self.card.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, 12))
        self.bulk = ctk.CTkFrame(self.card, fg_color=theme.INK, corner_radius=22)
        self.selected_count = ctk.CTkLabel(self.bulk, text="", text_color=theme.ON_INK)
        self.selected_count.pack(side="left", padx=(14, 10))
        theme.ActionButton(self.bulk, text="Ping", image=theme.icon("ping", theme.ON_LIME, 16),
                           width=76, height=32, corner_radius=16, fg_color=theme.LIME,
                           hover_color="#B8E24A", text_color=theme.ON_LIME, border_width=0,
                           command=self.ping_selected).pack(side="left", pady=6, padx=4)
        self.trace_button = theme.ActionButton(self.bulk, text="Traceroute", image=theme.icon("traceroute", size=16),
                                               width=116, height=32, corner_radius=16, command=self._trace_selected)
        self.trace_button.pack(side="left", padx=4)
        theme.ActionButton(self.bulk, text="Clear", width=58, height=32, corner_radius=16,
                           command=self._clear_selection).pack(side="left", padx=(4, 6))
        self.table = DeviceTable(self.card, app.open_device, self._selection_changed, self._row_menu)
        self.table.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.search.configure(validate="key", validatecommand=(self.register(self._queue_search), "%P"))
        self._render()

    def on_show(self, scan=False):
        """Refresh the network context and rows on entry, or resume an authorized scan."""
        run_async(services.network_info, on_done=self._show_info, on_error=lambda error:
                  self.info.configure(text=str(error), text_color=theme.RED))
        if scan:
            self.scan()
        elif self.scan_started is None:
            self._load()

    def _load(self):
        self.request += 1
        request = self.request
        run_async(services.device_overview,
                  on_done=lambda data: self._show_devices(*data) if request == self.request else None,
                  on_error=lambda error: self._show_error(error) if request == self.request else None)

    def scan(self):
        """Scan from this view and keep the stored tests available in the result table."""
        if self.scan_started is not None:
            return
        self.request += 1
        self.scan_started = monotonic()
        self.scan_button.configure(state="disabled")
        self.status.configure(text="Scanning network…", text_color=theme.MUTED)
        self.progress.set(0)
        self.progress.pack(anchor="w", pady=(4, 0))
        run_async(services.scan, lambda done, total: post(self._show_progress, (done, total)),
                  on_done=self._scanned, on_error=self._show_error)

    def _scanned(self, _devices):
        self.last_scan = (datetime.now().strftime("%H:%M"), round(monotonic() - self.scan_started))
        self._scan_ready()
        self._load()

    def _scan_ready(self):
        self.scan_started = None
        self.progress.pack_forget()
        self.scan_button.configure(state=self.scan_state)

    def _show_progress(self, progress):
        if self.scan_started is not None:
            done, total = progress
            self.progress.set(done / total)
            self.status.configure(text=f"Scanning network · {done} of {total} addresses")

    def _show_info(self, info):
        notes = []
        if info.mask_assumed:
            notes.append("Subnet mask could not be read. Using 255.255.255.0.")
        if info.truncated:
            notes.append("Scanning the local /24 of this larger network.")
        self.info.configure(text=(f"{info.hostname} · {info.local_ip} · subnet mask {info.netmask}\n"
                                  f"{info.cidr} · {info.first_host} to {info.last_host} · "
                                  f"gateway {info.gateway or 'none'} · {info.host_count} usable addresses"
                                  + ("\n" + " ".join(notes) if notes else "")), text_color=theme.MUTED)

    def _toggle_details(self):
        self.details_open = not self.details_open
        if self.details_open:
            self.info.pack(before=self.card, fill="x", padx=theme.PAD, pady=(0, 12))
        else:
            self.info.pack_forget()

    def _show_devices(self, devices, stats):
        self.devices = {device.ip: device for device in devices}
        self.stats = dict(stats)
        self._render()

    def update_device(self, detail):
        """Reflect a rename, confirmation, or test made in the open drawer."""
        if detail.device.ip in self.devices:
            self.devices[detail.device.ip] = detail.device
            self.stats[detail.device.ip] = detail.stats
            self._render()

    def _select_filter(self, filter_name):
        self.filter_name = filter_name
        self._render()

    def _queue_search(self, value):
        self.after_idle(self._render)
        return True

    def _clear_search(self, event):
        if self.search.get():
            self.search.delete(0, "end")
            return "break"

    def _render(self):
        query = self.search.get()
        entries = [(device, self.stats.get(device.ip)) for device in self.devices.values()]
        rows = [(device, stats, stats.status if stats else models.NO_DATA) for device, stats in entries]
        counts = {name: sum(matches(device, status, name, "") for device, _, status in rows) for name in FILTERS}
        for name, button in self.filters.items():
            active = self.filter_name == name
            style = theme.PRIMARY if active else dict(fg_color=theme.SURFACE, hover_color=theme.SUBTLE,
                                                     text_color=theme.TEXT, border_width=1)
            button.configure(text=f"{name}  {counts[name]}", **style)
        visible = []
        for device, stats, status in rows:
            if not matches(device, status, self.filter_name, query):
                continue
            name = device.alias or device.hostname
            role = "Gateway" if device.is_gateway else "This PC" if device.is_self else "New" if not device.known else ""
            if name.casefold() == role.casefold():
                role = ""
            label = "  ·  ".join(filter(None, (name, role)))
            if device.vendor:
                label += "\n" + device.vendor
            latency = f"{stats.avg_ms:g} ms" if stats and stats.avg_ms is not None else "—"
            visible.append({"ip": device.ip, "name": label, "mac": device.mac or "—", "latency": latency,
                            "status": models.STATUS_LABELS[status], "icon": theme.device_icon(device), "options": "…",
                            "tag": theme.STATUS_TAGS[status]})
        self.table.set_rows(visible)
        if self.scan_started is not None:
            return
        if not rows:
            summary = "No devices yet. Run a network scan to get started."
        elif not visible:
            summary = "No devices match this search and filter."
        else:
            summary = f"{len(visible)} of {len(rows)} devices" if len(visible) != len(rows) else f"{len(rows)} devices"
            summary += f" · {counts['Issues']} with issues · {counts['New']} new"
            if self.last_scan:
                time, elapsed = self.last_scan
                summary += f" · last scan {time}, {elapsed} s"
        self.status.configure(text=summary, text_color=theme.MUTED)

    def _selection_changed(self, ips):
        if ips:
            self.selected_count.configure(text=f"{len(ips)} selected")
            self.bulk.pack(side="bottom", before=self.table, pady=(0, 12))
        else:
            self.bulk.pack_forget()

    def _clear_selection(self):
        self.table.tree.selection_remove(*self.table.selected())
        self.table.tree.focus_set()

    def ping_selected(self):
        if ips := self.table.selected():
            self.app.show("Ping", ips=ips)

    def _trace_selected(self):
        ips = self.table.selected()
        if len(ips) == 1:
            self.app.show("Traceroute", ip=ips[0])
        elif ips:
            self._menu([(f"Trace {self.devices[ip].alias or self.devices[ip].hostname} · {ip}",
                         lambda target=ip: self.app.show("Traceroute", ip=target)) for ip in ips],
                       self.trace_button.winfo_rootx(), self.trace_button.winfo_rooty() + self.trace_button.winfo_height())

    def _row_menu(self, ip, x, y):
        self._menu([("Open device details", lambda: self.app.open_device(ip)),
                    ("Ping", lambda: self.app.show("Ping", ip=ip)),
                    ("Continuous ping", lambda: self.app.show("Ping", ip=ip, continuous=True)),
                    ("Traceroute", lambda: self.app.show("Traceroute", ip=ip))], x, y)

    def _menu(self, actions, x, y):
        self.menu.configure(background=theme.color(theme.SURFACE), foreground=theme.color(theme.TEXT))
        self.menu.delete(0, "end")
        for label, action in actions:
            self.menu.add_command(label=label, command=action)
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _show_error(self, error):
        self._scan_ready()
        self.status.configure(text=str(error), text_color=theme.RED)
