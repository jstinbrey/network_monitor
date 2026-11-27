"""Network map: the logical (layer-3) topology on a canvas.

Every device reaches the internet through the gateway, so each one is linked to it. Switches and
Wi-Fi access points do not answer as hosts in a ping sweep or ARP table (finding them needs SNMP or
LLDP), so they are not drawn. CustomTkinter has no canvas of its own, so this is a tk.Canvas.
"""
import math
import tkinter as tk

from netmonitor import config
from netmonitor.gui import theme
from netmonitor.gui.widgets.latency_chart import BACKGROUND, TEXT

NODE_R, GATEWAY_R = 16, 24
PER_RING, RING_GAP = 16, 90                    # devices per ring; distance between rings
INTERNET_GAP = 70                              # the Internet node sits this far outside the first ring
FAST_MS = 20                                   # a link this fast is green


def ring_layout(n, cx, cy, radius, per_ring=PER_RING, gap=RING_GAP) -> list[tuple[float, float]]:
    """Positions for n devices on rings around (cx, cy), at most per_ring per ring, starting at the top."""
    points = []
    for i in range(n):
        ring, slot = divmod(i, per_ring)
        on_ring = min(per_ring, n - ring * per_ring)
        angle = -math.pi / 2 + 2 * math.pi * slot / on_ring
        r = radius + ring * gap
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def edge_style(stats):
    """(colour, dash) of a device's link to the gateway, from its average latency; grey dashes without data."""
    if stats is None or stats.avg_ms is None:
        return theme.MUTED, (4, 4)
    color = theme.GREEN if stats.avg_ms < FAST_MS else theme.AMBER if stats.avg_ms <= config.LATENCY_WARN_MS else theme.RED
    return color, ""


class MapCanvas(tk.Canvas):
    def __init__(self, parent, on_open, menu_items):
        """on_open(ip) opens a device panel. menu_items: [(label, command(ip) or None)] for the right-click
        menu; None greys the item out (an admin-only action shown to a User)."""
        super().__init__(parent, background=BACKGROUND, highlightthickness=0)
        self.on_open, self.menu_items = on_open, menu_items
        self.tips, self.gateway = {}, None             # ip -> tooltip text; the gateway's IP
        self._drag_ip, self._start, self._last = None, (0, 0), (0, 0)
        self.bind("<ButtonPress-1>", self._press)      # one set of handlers decides: drag a node, or pan
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._zoom)
        self.bind("<Button-3>", self._right_click)
        self.tag_bind("node", "<Enter>", self._hover)
        self.tag_bind("node", "<Leave>", lambda event: self.delete("tooltip"))

    def draw(self, devices, stats, issues):
        """devices: the ones to show; stats: {ip: HostStats}; issues: IPs with a security or connectivity finding."""
        self.delete("all")
        self.xview_moveto(0)                           # undo any panning
        self.yview_moveto(0)
        width, height = max(self.winfo_width(), 600), max(self.winfo_height(), 400)
        if not devices:
            self.create_text(width / 2, height / 2, text="No devices yet: scan the network (Admin).", fill=TEXT)
            return
        gateway = next((d for d in devices if d.is_gateway), None)
        others = [d for d in devices if d is not gateway]
        cx, cy = width / 2, height / 2
        # The outer rings, or the Internet node, must still fit (50 px is left for the outermost labels).
        rings = max(1, math.ceil(len(others) / PER_RING))
        radius = max(min(width, height) / 2 - 50 - max(INTERNET_GAP, (rings - 1) * RING_GAP), 60)
        points = ring_layout(len(others), cx, cy, radius)
        self.gateway = gateway and gateway.ip
        self.tips = {d.ip: self._tip(d, stats.get(d.ip)) for d in devices}

        # Edges first, so the nodes are drawn on top of them.
        if gateway:
            # The internet sits half a slot after the top device, so its link passes between two devices.
            angle = -math.pi / 2 + math.pi / max(1, min(PER_RING, len(others)))
            ix, iy = cx + (radius + INTERNET_GAP) * math.cos(angle), cy + (radius + INTERNET_GAP) * math.sin(angle)
            self.create_line(cx, cy, ix, iy, fill=theme.BORDER_CONTROL, width=2, tags=("edge:internet",))
            for d, (x, y) in zip(others, points):
                color, dash = edge_style(stats.get(d.ip))
                self.create_line(cx, cy, x, y, fill=color, dash=dash, width=2, tags=(f"edge:{d.ip}",))
            self.create_oval(ix - 20, iy - 14, ix + 20, iy + 14, fill=theme.INK, outline="", tags=("internet",))
            self.create_text(ix, iy + 26, text="Internet", fill=TEXT, font=(theme.SANS_SEMIBOLD, 9), tags=("internet",))
            self._node(gateway, cx, cy, GATEWAY_R, stats.get(gateway.ip), gateway.ip in issues)
        for d, (x, y) in zip(others, points):
            self._node(d, x, y, NODE_R, stats.get(d.ip), d.ip in issues)

    def _node(self, device, x, y, r, stats, issue):
        tags = ("node", f"ip:{device.ip}")
        fill = theme.TAG_COLORS.get(theme.STATUS_TAGS.get(stats.status if stats else ""), theme.MUTED)
        # This PC has a thick white outline.
        outline, width = (theme.INK, 3) if device.is_self else (BACKGROUND, 1)
        self.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline, width=width, tags=tags)
        if not device.known:                            # new on the network: a red ring, visible on any fill
            self.create_oval(x - r - 6, y - r - 6, x + r + 6, y + r + 6, outline=theme.RED, width=2, tags=tags)
        name = device.alias or ("Gateway" if device.is_gateway else device.hostname)
        label = self.create_text(x, y + r + 8, text=f"{name[:18]}\n{device.ip}", fill=TEXT, font=(theme.SANS, 9),
                                 justify="center", anchor="n", tags=tags)   # hangs below the node, whatever the font height
        x1, y1, x2, y2 = self.bbox(label)              # a white backing, so links pass behind the label
        self.tag_lower(self.create_rectangle(x1 - 3, y1 - 1, x2 + 3, y2 + 1, fill=BACKGROUND, outline="", tags=tags), label)
        if issue:                                       # a "!" badge: risky port, ARP or connectivity finding
            bx, by = x + r * 0.75, y - r * 0.75
            self.create_oval(bx - 7, by - 7, bx + 7, by + 7, fill=theme.RED, outline=BACKGROUND, tags=tags)
            self.create_text(bx, by, text="!", fill=theme.SURFACE, font=(theme.SANS_SEMIBOLD, 9), tags=tags)

    @staticmethod
    def _tip(device, stats):
        latency = "no ping results" if stats is None or stats.avg_ms is None else f"{stats.avg_ms:g} ms average"
        return "\n".join(filter(None, [device.alias or device.hostname, device.ip, device.mac, device.vendor, latency]))

    def _ip_at(self):
        """The IP of the node under the mouse, or None."""
        item = self.find_withtag("current")
        tags = self.gettags(item[0]) if item else ()
        return next((t[3:] for t in tags if t.startswith("ip:")), None)

    def _press(self, event):
        self._drag_ip = self._ip_at()
        self._start = self._last = (event.x, event.y)
        if self._drag_ip is None:
            self.scan_mark(event.x, event.y)                 # pan the whole canvas

    def _motion(self, event):
        if self._drag_ip is None:
            return self.scan_dragto(event.x, event.y, gain=1)
        if self._drag_ip == self.gateway:                    # the gateway stays fixed: every edge starts there
            return
        dx, dy = event.x - self._last[0], event.y - self._last[1]
        self.delete("tooltip")
        self.move(f"ip:{self._drag_ip}", dx, dy)
        if self.find_withtag(f"edge:{self._drag_ip}"):
            x1, y1, x2, y2 = self.coords(f"edge:{self._drag_ip}")
            self.coords(f"edge:{self._drag_ip}", x1, y1, x2 + dx, y2 + dy)   # the gateway end stays put
        self._last = (event.x, event.y)

    def _release(self, event):
        moved = abs(event.x - self._start[0]) + abs(event.y - self._start[1])
        if self._drag_ip and moved < 4:                      # a click, not a drag
            self.on_open(self._drag_ip)
        self._drag_ip = None

    def _hover(self, event):
        ip = self._ip_at()
        if ip is None or self._drag_ip:
            return
        self.delete("tooltip")
        x, y = self.canvasx(event.x) + 16, self.canvasy(event.y) + 16   # canvas coordinates: the map may be panned
        text = self.create_text(x, y, text=self.tips[ip], anchor="nw", fill=TEXT, font=(theme.SANS, 9), tags="tooltip")
        x1, y1, x2, y2 = self.bbox(text)
        box = self.create_rectangle(x1 - 6, y1 - 4, x2 + 6, y2 + 4, fill=theme.SURFACE, outline=theme.BORDER_STRONG, tags="tooltip")
        self.tag_lower(box, text)

    def _zoom(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self.delete("tooltip")
        self.scale("all", self.canvasx(event.x), self.canvasy(event.y), factor, factor)   # text keeps its size

    def menu(self, ip):
        """The right-click menu for one device."""
        menu = tk.Menu(self, tearoff=False)
        for label, command in self.menu_items:
            menu.add_command(label=label, state="normal" if command else "disabled",
                             command=lambda command=command: command(ip))
        return menu

    def _right_click(self, event):
        ip = self._ip_at()
        if ip:
            self.menu(ip).tk_popup(event.x_root, event.y_root)
