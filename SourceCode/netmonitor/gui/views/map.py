"""Map view: every device around the gateway, coloured by status, each link coloured by latency."""
import customtkinter as ctk

from netmonitor import models, services
from netmonitor.gui import theme
from netmonitor.gui.widgets.map_canvas import MapCanvas
from netmonitor.gui.worker import run_async

FILTERS = ["All", "Online", "New", "Issues"]
LEGEND = [("●", theme.GREEN, "Online"), ("●", theme.AMBER, "Slow or no ping reply"), ("●", theme.RED, "Offline"),
          ("●", theme.MUTED, "No data"), ("◯", theme.BLUE, "New device"), ("!", theme.RED, "Finding")]


def keep(devices, stats, issues, mode):
    """The devices a filter shows. The gateway always stays: it is the centre of the map."""
    def wanted(device):
        status = stats[device.ip].status if device.ip in stats else models.NO_DATA
        return {"All": True, "Online": status in models.REACHABLE_STATUSES, "New": not device.known,
                "Issues": device.ip in issues}[mode]
    return [d for d in devices if d.is_gateway or wanted(d)]


class MapView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app, self.data = app, ([], {}, set())       # the latest map_data(), redrawn when the filter changes
        actions, self.verdict = theme.page_heading(self, "Map", "Devices discovered by this PC")
        self.filter_name = "All"
        self._reload_pending = False
        self.router_snapshot = None
        self.scan_state = "normal" if app.is_admin or not app.user else "disabled"
        self.scan_button = (theme.ActionButton(actions, text="Scan network", width=146, height=40, corner_radius=20,
                                               image=theme.icon("radar", theme.ON_INK), state=self.scan_state,
                                               **theme.PRIMARY, command=self.scan) if app.user else
                            theme.locked_button(actions, "Scan network", app.ask_scan, width=146))
        self.scan_button.pack(side="right")
        self.refresh_button = theme.ActionButton(actions, text="Re-test devices", width=150, height=40, corner_radius=20,
                                                 image=theme.icon("refresh", size=16), command=self.refresh)
        self.refresh_button.pack(side="right", padx=(0, 8))
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(fill="x", padx=theme.PAD, pady=(0, 12))
        self.filters = {}
        for name in FILTERS:
            self.filters[name] = theme.ActionButton(filters, text=name, width=78, height=36, corner_radius=18,
                                                     command=lambda value=name: self._filter(value))
            self.filters[name].pack(side="left", padx=(0, 8))
        if app.is_admin:
            theme.ActionButton(filters, text="Router clients", width=118, height=36, corner_radius=18,
                               command=self._router_clients).pack(side="right")
        card = ctk.CTkFrame(self, fg_color=theme.SURFACE)
        card.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, 12))
        self.legend = ctk.CTkFrame(card, fg_color="transparent")
        self.legend.pack(side="bottom", fill="x", padx=16, pady=(4, 10))
        for i, (mark, color, label) in enumerate(LEGEND):
            row, column = divmod(i, 3)
            self.legend.grid_columnconfigure(column, weight=1)
            chip = ctk.CTkFrame(self.legend, fg_color="transparent")
            chip.grid(row=row, column=column, sticky="ew")
            ctk.CTkLabel(chip, text=mark, text_color=color, font=theme.CARD_FONT).pack(side="left")
            ctk.CTkLabel(chip, text=label, text_color=theme.MUTED).pack(side="left", padx=(4, 8))
        self.selection = theme.WrappedLabel(card, text="", text_color=theme.TEXT_2, font=theme.CAPTION_FONT)
        self.selection.pack(side="bottom", fill="x", padx=16)
        self._describe_selection(())

        graph = ctk.CTkFrame(card, fg_color=theme.SURFACE)
        graph.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas = MapCanvas(graph, on_open=app.open_device, on_select=self._describe_selection, menu_items=[
            ("Ping", lambda ip: app.show("Ping", ip=ip)),
            ("Continuous ping", lambda ip: app.show("Ping", ip=ip, continuous=True)),
            ("Traceroute", lambda ip: app.show("Traceroute", ip=ip)),
            ("Check ports" if app.is_admin else "Check ports (Admin)",
             self._check_ports if app.is_admin or not app.user else None),
        ])
        self.canvas.pack(fill="both", expand=True)
        zoom = ctk.CTkFrame(graph, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=18)
        zoom.place(relx=1, rely=1, x=-12, y=-12, anchor="se")
        for icon, label, action in (("plus", "Zoom in", lambda: self.canvas.zoom(1.15)),
                                     ("minus", "Zoom out", lambda: self.canvas.zoom(1 / 1.15)),
                                     ("fit", "Fit devices", self.canvas.fit)):
            button = theme.ActionButton(zoom, text="", image=theme.icon(icon, size=16), width=30, height=30,
                                        corner_radius=15, command=action, **theme.GHOST)
            button.pack(padx=4, pady=2)
            theme.tooltip(button, label)
        self._redraw()

    def _filter(self, value):
        self.filter_name = value
        self._redraw()

    def _describe_selection(self, details):
        self.selection.configure(text=" · ".join(details) if details else
                                 "Use arrow keys to select a device, Enter for details, or Shift+F10 for actions. "
                                 "Scroll to zoom or drag to pan.")

    def _check_ports(self, ip):
        """The device panel runs the check and shows the open ports."""
        self.app.open_device(ip)
        self.app.panel.check_ports()

    def _router_clients(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Router Wi-Fi clients")
        dialog.geometry("550x350")
        dialog.transient(self.winfo_toplevel())
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        theme.WrappedLabel(dialog, text="On the HG6245D, open Status → Wireless Status → WIFI Clients List. "
                           "Copy the table and paste it here.").pack(fill="x", padx=16, pady=(16, 8))
        rows = ctk.CTkTextbox(dialog, height=120, font=theme.MONO_FONT, wrap="word")
        rows.pack(fill="both", expand=True, padx=16)
        notice = theme.WrappedLabel(dialog, text="", text_color=theme.MUTED)
        notice.pack(fill="x", padx=16, pady=(6, 0))
        if snapshot := self.router_snapshot:
            rows.insert("1.0", "\n".join(f"{i}\t{c.ssid}\t{c.mac}\t{c.ip or '—'}"
                                          for i, c in enumerate(snapshot.clients, 1)))
            notice.configure(text=f"Snapshot imported {snapshot.captured_at.replace('T', ' ')}.")

        def loaded(snapshot):
            if dialog.winfo_exists():
                self.router_snapshot = snapshot
                self.filter_name = "All"
                mapped = sum(c.ip is not None for c in snapshot.clients)
                notice.configure(text=f"Loaded {len(snapshot.clients)} clients · {mapped} with IPv4 addresses. "
                                      "Clients without IPv4 stay listed here.", text_color=theme.MUTED)
                button.configure(state="normal")
                clear.configure(state="normal")
                self.refresh_after_watch()

        def failed(error):
            if dialog.winfo_exists():
                notice.configure(text=str(error), text_color=theme.RED)
                button.configure(state="normal")
                clear.configure(state="normal" if self.router_snapshot else "disabled")

        def load():
            button.configure(state="disabled")
            clear.configure(state="disabled")
            run_async(services.read_router_clients, rows.get("1.0", "end-1c"), on_done=loaded, on_error=failed)

        def clear_snapshot():
            self.router_snapshot = None
            rows.delete("1.0", "end")
            notice.configure(text="")
            clear.configure(state="disabled")
            self.refresh_after_watch()

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(8, 16))
        clear = theme.ActionButton(actions, text="Clear snapshot", height=38, corner_radius=19, command=clear_snapshot,
                                   state="normal" if self.router_snapshot else "disabled")
        clear.pack(side="left")
        button = theme.ActionButton(actions, text="Show on map", height=38, corner_radius=19, command=load, **theme.PRIMARY)
        button.pack(side="right")
        dialog.grab_set()
        rows.focus_set()

    def on_show(self, scan=False):
        if scan:
            self.scan()
        elif self.refresh_button.cget("state") == "normal":   # its result will redraw
            self._load(None, "")

    def refresh_after_watch(self):
        """Reload the saved results once any manual work in the Map finishes."""
        if self.refresh_button.cget("state") == "disabled":
            self._reload_pending = True
        else:
            self._load(None, "")

    def scan(self):
        self.refresh(scan=True)

    def refresh(self, scan=False):
        """Ping every known device (Refresh), or scan for devices first (Scan, Admin), then redraw."""
        self._load("scan" if scan else "ping", "Scanning..." if scan else "Pinging every device...")

    def _load(self, update, message):
        for button in (self.refresh_button, self.scan_button):
            button.configure(state="disabled")
        self.verdict.configure(text=message, text_color=theme.MUTED)
        args = (update, self.router_snapshot) if self.router_snapshot else (update,)
        run_async(services.map_data, *args, on_done=self._show, on_error=self._show_error)

    def _show(self, data):
        if not self.winfo_exists():
            return
        self.data = data
        self._ready()
        self._redraw()
        self._finish_watch_reload()

    def _redraw(self):
        devices, stats, issues = self.data
        self.canvas.draw(keep(devices, stats, issues, self.filter_name), stats, issues)
        new = sum(not d.known for d in devices)
        found = len(issues & {d.ip for d in devices})
        counts = {"All": len(devices), "Online": sum(s.status in models.REACHABLE_STATUSES for s in stats.values()),
                  "New": new, "Issues": found}
        for name, button in self.filters.items():
            style = theme.PRIMARY if name == self.filter_name else dict(
                fg_color=theme.SURFACE, hover_color=theme.SUBTLE, text_color=theme.TEXT, border_width=1)
            button.configure(text=f"{name}  {counts[name]}", **style)
        local = sum(not d.router_only for d in devices)
        summary = f"{local} devices discovered by this PC" if local else "Devices discovered by this PC"
        if last_scan := max((d.last_seen for d in devices), default=""):
            summary += f" · Last scan {last_scan[:16].replace('T', ' ')}"
        if ipv6 := sum(bool(d.ipv6_addresses) for d in devices):
            summary += f" · {ipv6} with IPv6 addresses"
        if self.router_snapshot and (from_router := sum(d.router_ssid is not None for d in devices)):
            summary += f" · {from_router} in router snapshot from {self.router_snapshot.captured_at.replace('T', ' ')}"
        self.verdict.configure(text=summary, text_color=theme.MUTED)

    def _ready(self):
        self.refresh_button.configure(state="normal")
        self.scan_button.configure(state=self.scan_state)

    def _show_error(self, error):
        if self.winfo_exists():
            self._ready()
            self.verdict.configure(text=str(error), text_color=theme.RED)
            self._finish_watch_reload()

    def _finish_watch_reload(self):
        if self._reload_pending:
            self._reload_pending = False
            if self.winfo_ismapped():
                self._load(None, "")
