"""Map view: every device around the gateway, coloured by status, each link coloured by latency."""
import customtkinter as ctk

from netmonitor import models, services
from netmonitor.gui import theme
from netmonitor.gui.widgets.map_canvas import MapCanvas
from netmonitor.gui.worker import run_async

FILTERS = ["All", "Online", "New", "Issues"]
UP = {models.ONLINE, models.DEGRADED, models.NO_ICMP}      # the latest ping test found the host up
LEGEND = [("●", theme.GREEN, "Online"), ("●", theme.AMBER, "Degraded or no ICMP"), ("●", theme.RED, "Offline"),
          ("●", theme.MUTED, "Not pinged"), ("◯", theme.RED, "New device"), ("!", theme.RED, "Finding")]


def keep(devices, stats, issues, mode):
    """The devices a filter shows. The gateway always stays: it is the centre of the map."""
    def wanted(device):
        status = stats[device.ip].status if device.ip in stats else models.NO_DATA
        return {"All": True, "Online": status in UP, "New": not device.known, "Issues": device.ip in issues}[mode]
    return [d for d in devices if d.is_gateway or wanted(d)]


class MapView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app, self.data = app, ([], {}, set())       # the latest map_data(), redrawn when the filter changes
        ctk.CTkLabel(self, text="Map", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD)
        self.refresh_button = ctk.CTkButton(bar, text="Re-test devices", width=126, command=self.refresh)
        self.refresh_button.pack(side="left")
        self.scan_state = "normal" if app.is_admin or not app.user else "disabled"
        self.scan_button = (ctk.CTkButton(bar, text="Scan network", width=146, height=40, corner_radius=20,
                                          state=self.scan_state, **theme.PRIMARY, command=self.scan) if app.user else
                            theme.locked_button(bar, "Scan network", app.ask_scan, width=146))
        self.scan_button.pack(side="left", padx=8)
        self.filter = ctk.CTkSegmentedButton(bar, values=FILTERS, command=lambda mode: self._redraw())
        self.filter.set("All")
        self.filter.pack(side="left", padx=8)
        self.status = ctk.CTkLabel(bar, text="", text_color=theme.MUTED)
        self.status.pack(side="left", padx=8)

        footer = ctk.CTkFrame(self, fg_color="transparent")     # packed before the canvas, so it keeps its room
        footer.pack(side="bottom", fill="x", padx=theme.PAD, pady=(6, theme.PAD))
        self.verdict = ctk.CTkLabel(footer, text="", font=theme.CARD_FONT, anchor="w")
        self.verdict.pack(side="left")
        for mark, color, label in reversed(LEGEND):
            ctk.CTkLabel(footer, text=label, text_color=theme.MUTED).pack(side="right", padx=(2, 10))
            ctk.CTkLabel(footer, text=mark, text_color=color, font=theme.CARD_FONT).pack(side="right")
        ctk.CTkLabel(self, text="Logical map: every device reaches the internet through the gateway. Switches and "
                                "access points are not shown. Drag a device, drag the background to pan, scroll to "
                                "zoom, click for details, right-click for actions.",
                     text_color=theme.MUTED, anchor="w", justify="left", wraplength=900
                     ).pack(side="bottom", fill="x", padx=theme.PAD)

        self.canvas = MapCanvas(self, on_open=app.open_device, menu_items=[
            ("Ping", lambda ip: app.show("Ping", ip=ip)),
            ("Continuous ping", lambda ip: app.show("Ping", ip=ip, continuous=True)),
            ("Traceroute", lambda ip: app.show("Traceroute", ip=ip)),
            ("Check ports" if app.is_admin else "Check ports (Admin)",
             self._check_ports if app.is_admin or not app.user else None),
        ])
        self.canvas.pack(fill="both", expand=True, padx=theme.PAD, pady=8)

    def _check_ports(self, ip):
        """The device panel runs the check and shows the open ports."""
        self.app.open_device(ip)
        self.app.panel.check_ports()

    def on_show(self, scan=False):
        if scan:
            self.scan()
        elif self.refresh_button.cget("state") == "normal":   # its result will redraw
            self._load(None, "")

    def scan(self):
        self.refresh(scan=True)

    def refresh(self, scan=False):
        """Ping every known device (Refresh), or scan for devices first (Scan, Admin), then redraw."""
        self._load("scan" if scan else "ping", "Scanning..." if scan else "Pinging every device...")

    def _load(self, update, message):
        for button in (self.refresh_button, self.scan_button):
            button.configure(state="disabled")
        self.status.configure(text=message, text_color=theme.MUTED)
        run_async(services.map_data, update, on_done=self._show, on_error=self._show_error)

    def _show(self, data):
        if not self.winfo_exists():
            return
        self.data = data
        self._ready()
        self.status.configure(text="")
        self._redraw()

    def _redraw(self):
        devices, stats, issues = self.data
        self.canvas.draw(keep(devices, stats, issues, self.filter.get()), stats, issues)
        new = sum(not d.known for d in devices)
        found = len(issues & {d.ip for d in devices})
        self.verdict.configure(
            text=f"{len(devices)} devices  ·  {new} new  ·  {found} with findings" if devices else "",
            text_color=theme.RED if found else theme.AMBER if new else theme.GREEN)

    def _ready(self):
        self.refresh_button.configure(state="normal")
        self.scan_button.configure(state=self.scan_state)

    def _show_error(self, error):
        if self.winfo_exists():
            self._ready()
            self.status.configure(text=str(error), text_color=theme.RED)
