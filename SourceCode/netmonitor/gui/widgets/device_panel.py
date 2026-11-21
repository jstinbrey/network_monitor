"""Device panel: everything about one device in a window of its own, opened from any list of devices."""
import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.views.statistics import ms
from netmonitor.gui.widgets.latency_chart import LatencyChart
from netmonitor.gui.worker import run_async
from netmonitor.models import STATUS_LABELS

TILES = ["Average", "Maximum", "Packet loss", "Jitter"]


def tags(device):
    """The labels shown next to a device, e.g. "Gateway, New"."""
    return ", ".join(tag for tag, on in (("This PC", device.is_self), ("Gateway", device.is_gateway),
                                         ("New", not device.known)) if on)


def ports_line(open_ports):
    """(text, colour) for the latest port check: red when a risky service is open."""
    if open_ports is None:
        return "Open ports: not checked yet", theme.MUTED
    if not open_ports:
        return f"Open ports: none of the {len(config.COMMON_PORTS)} common ports", theme.GREEN
    text = "Open ports: " + ", ".join(f"{p['service']} ({p['port']})" for p in open_ports)
    return text, theme.RED if any(p["risk"] == "high" for p in open_ports) else theme.MUTED


def verdict(stats):
    """One line that sums the device up, e.g. "Online  ·  normal latency"."""
    parts = [STATUS_LABELS[stats.status]]
    if stats.avg_ms is not None:
        parts.append("high latency" if stats.avg_ms > config.LATENCY_WARN_MS else "normal latency")
    if stats.loss_pct:
        parts.append(f"{stats.loss_pct:g}% packet loss")
    return "  ·  ".join(parts)


class DevicePanel(ctk.CTkToplevel):
    def __init__(self, parent, app):
        """parent: the frame that holds the views, so signing out destroys the panel along with them."""
        super().__init__(parent)
        self.app, self.ip = app, None
        self.title("Device")
        self.geometry("760x680")                             # wide enough for an admin's six buttons in one row
        self.transient(app)                                  # stays above the main window
        self.protocol("WM_DELETE_WINDOW", self.withdraw)     # closing only hides it; the next open reuses it

        self.name = ctk.CTkLabel(self, text="", font=theme.TITLE_FONT, anchor="w")
        self.name.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 0))
        self.address = ctk.CTkLabel(self, text="", text_color=theme.MUTED, anchor="w")
        self.address.pack(fill="x", padx=theme.PAD)
        self.verdict = ctk.CTkLabel(self, text="", font=("Segoe UI", 14, "bold"), anchor="w")
        self.verdict.pack(fill="x", padx=theme.PAD, pady=(4, 12))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD)
        self.tiles = {}
        for title in TILES:
            tile = ctk.CTkFrame(row)
            tile.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(tile, text=title, text_color=theme.MUTED).pack(anchor="w", padx=12, pady=(8, 0))
            self.tiles[title] = ctk.CTkLabel(tile, text="-", font=("Segoe UI", 18, "bold"))
            self.tiles[title].pack(anchor="w", padx=12, pady=(0, 8))
        self.seen = ctk.CTkLabel(self, text="", text_color=theme.MUTED, anchor="w")
        self.seen.pack(fill="x", padx=theme.PAD, pady=(8, 0))
        self.ports = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=640)
        self.ports.pack(fill="x", padx=theme.PAD)
        self.chart = LatencyChart(self)
        self.chart.pack(fill="both", expand=True, padx=theme.PAD, pady=8)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=theme.PAD)
        self.ping_button = ctk.CTkButton(actions, text="Ping", width=100, command=self.ping)
        self.ping_button.pack(side="left")
        ctk.CTkButton(actions, text="Traceroute", width=100, command=self.traceroute).pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="Continuous ping", width=130,
                      command=self.continuous_ping).pack(side="left", padx=(8, 0))
        self.known_button = None
        if app.is_admin:   # a User never gets these buttons, and services refuse the calls anyway
            self.known_button = ctk.CTkButton(actions, text="Mark as known", width=130, command=self.mark_known)
            self.known_button.pack(side="left", padx=8)
            ctk.CTkButton(actions, text="Rename", width=100, command=self.rename).pack(side="left")
            ctk.CTkButton(actions, text="Check ports", width=110, command=self.check_ports).pack(side="left", padx=8)
            ctk.CTkLabel(self, text="Only check devices on a network you own or administer.",
                         text_color=theme.MUTED, anchor="w").pack(fill="x", padx=theme.PAD, pady=(4, 0))
        self.status = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=640)
        self.status.pack(fill="x", padx=theme.PAD, pady=(8, theme.PAD))

    def show(self, ip):
        """Bring the panel to the front with one device in it."""
        self.ip = ip
        self.title(f"Device {ip}")
        self.status.configure(text="")
        self.deiconify()
        self.lift()
        self.focus()
        self._load()

    def _load(self):
        run_async(services.device_detail, self.ip, on_done=self._show, on_error=self._show_error)

    def _show(self, detail):
        if detail.device.ip != self.ip:     # another device was opened while this one loaded
            return
        device, s = detail.device, detail.stats
        self.name.configure(text=device.alias or device.hostname)
        self.address.configure(text="  ·  ".join(filter(None, [device.ip, device.mac or "MAC unknown", device.vendor, tags(device)])))
        self.verdict.configure(text=verdict(s),
                               text_color=theme.TAG_COLORS.get(theme.STATUS_TAGS.get(s.status), theme.MUTED))
        loss = "No data" if s.loss_pct is None else f"{s.loss_pct:g}%"
        for title, text in zip(TILES, [ms(s.avg_ms), ms(s.max_ms), loss, ms(s.jitter_ms)]):
            self.tiles[title].configure(text=text)
        self.seen.configure(text=f"First seen {device.first_seen.replace('T', ' ') or '-'}        "
                                 f"Last seen {device.last_seen.replace('T', ' ') or '-'}")
        text, color = ports_line(detail.open_ports)
        self.ports.configure(text=text, text_color=color)
        history = detail.history
        self.chart.plot([r.timestamp[11:] for r in history], [r.avg_ms or 0 for r in history],
                        "Average latency of the last 10 tests" if history else "No ping tests stored yet")
        if self.known_button:
            self.known_button.configure(state="disabled" if device.known else "normal")

    def ping(self):
        self.ping_button.configure(state="disabled")
        self.status.configure(text=f"Pinging {self.ip}...", text_color=theme.MUTED)
        run_async(services.run_ping, self.ip, on_done=self._pinged, on_error=self._show_error)

    def _pinged(self, result):
        self.ping_button.configure(state="normal")
        times = f", average {result.avg_ms:g} ms" if result.rtts_ms else ""
        self.status.configure(text=f"Ping {result.ip}: {STATUS_LABELS[result.status]}, "
                                   f"{result.received} of {result.sent} replies{times}.",
                              text_color=theme.TAG_COLORS.get(theme.STATUS_TAGS.get(result.status), theme.MUTED))
        self._load()        # the new test changes the tiles and the history

    def traceroute(self):
        self.withdraw()                     # the trace shows in the main window, which the panel would cover
        self.app.show("Traceroute", ip=self.ip)

    def continuous_ping(self):
        self.withdraw()                     # the chart shows in the main window
        self.app.show("Ping", ip=self.ip, continuous=True)

    def mark_known(self):
        run_async(services.mark_known, self.ip, on_done=lambda recs: self._load(), on_error=self._show_error)

    def check_ports(self):
        self.status.configure(text=f"Checking {len(config.COMMON_PORTS)} common ports on {self.ip}...",
                              text_color=theme.MUTED)
        run_async(services.check_ports, self.ip, on_done=self._ports_checked, on_error=self._show_error)

    def _ports_checked(self, detail):
        self.status.configure(text="")
        self._show(detail)

    def rename(self):
        dialog = ctk.CTkInputDialog(title="Rename device", text=f"Name for {self.ip}\n(leave empty to use its hostname):")
        name = dialog.get_input()           # None when the dialog was cancelled
        if name is not None:
            run_async(services.set_alias, self.ip, name, on_done=self._show, on_error=self._show_error)

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
        self.ping_button.configure(state="normal")