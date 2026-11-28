"""Keyboard- and pointer-operable canvas for hosts around the network gateway."""
import math
import tkinter as tk

import customtkinter as ctk

from netmonitor import config, models
from netmonitor.gui import theme

PER_RING, RING_GAP = 16, 90
FAST_MS = 20


def ring_layout(n, cx, cy, radius, per_ring=PER_RING, gap=RING_GAP) -> list[tuple[float, float]]:
    """Positions on rings, starting at the top and moving clockwise."""
    points = []
    for i in range(n):
        ring, slot = divmod(i, per_ring)
        on_ring = min(per_ring, n - ring * per_ring)
        angle = -math.pi / 2 + 2 * math.pi * slot / on_ring
        r = radius + ring * gap
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def map_positions(n, width, height):
    """Use the viewport's width and reserve room between compact nodes on a full ring."""
    radius_y = max(116, height / 2 - 48)
    radius_x = max(175, width / 2 - 96)
    points = ring_layout(n, 0, 0, radius_y, per_ring=18, gap=72)
    return [(width / 2 + x * radius_x / radius_y, height / 2 + y) for x, y in points]


def edge_style(stats):
    """Use link latency for color and a dashed line when there is no data."""
    if stats is None or stats.avg_ms is None:
        return theme.MUTED, (4, 4)
    color = theme.GREEN if stats.avg_ms < FAST_MS else theme.AMBER if stats.avg_ms <= config.LATENCY_WARN_MS else theme.RED
    return color, ""


class MapCanvas(tk.Canvas):
    def __init__(self, parent, on_open, on_select, menu_items):
        super().__init__(parent, background=theme.color(theme.SURFACE), highlightthickness=2,
                         highlightcolor=theme.color(theme.INK), highlightbackground=theme.color(theme.SURFACE),
                         takefocus=1)
        self.on_open, self.on_select, self.menu_items = on_open, on_select, menu_items
        self.data = ([], {}, set())
        self.nodes, self.tips = {}, {}
        self.selected = self.gateway = self._drag_ip = self._draw_job = None
        self._start = self._last = (0, 0)
        self.bind("<Configure>", self._schedule_layout)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._zoom)
        self.bind("<Button-3>", self._right_click)
        self.bind("<FocusIn>", self._focus_node)
        self.bind("<Left>", lambda _: self._move_selection(-1))
        self.bind("<Up>", lambda _: self._move_selection(-1))
        self.bind("<Right>", lambda _: self._move_selection(1))
        self.bind("<Down>", lambda _: self._move_selection(1))
        self.bind("<Return>", self._open_selection)
        self.bind("<Shift-F10>", self._keyboard_menu)
        self.bind("<Menu>", self._keyboard_menu)
        self.tag_bind("node", "<Enter>", self._hover)
        self.tag_bind("node", "<Leave>", lambda _: self.delete("tooltip"))
        theme.appearance_callback(self, self._apply_palette)

    def _schedule_layout(self, _event):
        if self._draw_job is None:
            self._draw_job = self.after_idle(self._layout)

    def draw(self, devices, stats, issues):
        """Replace the visible topology and preserve the selection if it still exists."""
        self.data = devices, stats, issues
        if self._draw_job is None:
            self._layout()

    def _layout(self):
        self._draw_job = None
        self.delete("all")
        self.nodes.clear()
        self.tips.clear()
        devices, stats, issues = self.data
        scale = ctk.ScalingTracker.get_widget_scaling(self.master)
        width, height = self.winfo_width() / scale, self.winfo_height() / scale
        cx, cy = self.winfo_width() / 2, self.winfo_height() / 2
        gateway = next((device for device in devices if device.is_gateway), None)
        self.gateway = gateway.ip if gateway else None
        if not devices:
            self.create_text(cx, cy, text="No devices yet. Select Scan network.", fill=theme.color(theme.TEXT_2))
        else:
            self._draw_devices(devices, stats, issues, gateway, width, height, scale)
        self._update_scrollregion()
        self._move_view(0, 0)
        selected = self.selected if self.selected in self.nodes else None
        self._select(selected)
        if selected is None and self.focus_get() is self:
            self._focus_node(None)

    def _draw_devices(self, devices, stats, issues, gateway, width, height, scale):
        others = [device for device in devices if device is not gateway]
        cx, cy = width * scale / 2, height * scale / 2
        points = [(x * scale, y * scale) for x, y in map_positions(len(others), width, height)]
        if gateway:
            for device, (x, y) in zip(others, points):
                color, dash = edge_style(stats.get(device.ip))
                self.create_line(cx, cy, x, y, fill=theme.color(color), dash=dash, width=2,
                                 tags=(f"edge:{device.ip}",))
            angle = -math.pi / 2 + math.pi / max(2, min(len(others), 18))
            ix, iy = cx + 152 * scale * math.cos(angle), cy + 74 * scale * math.sin(angle)
            self.create_line(cx, cy, ix, iy, fill=theme.color(theme.BORDER_CONTROL), width=2)
            label = self.create_text(ix, iy, text="Internet", fill=theme.color(theme.TEXT),
                                     font=(theme.SANS_SEMIBOLD, 10))
            x0, y0, x1, y1 = self.bbox(label)
            badge = self.create_rectangle(x0 - 6, y0 - 4, x1 + 6, y1 + 4, fill=theme.color(theme.SUBTLE),
                                          outline=theme.color(theme.BORDER))
            self.tag_lower(badge, label)
            self._node(gateway, cx, cy, 20 * scale, stats.get(gateway.ip), gateway.ip in issues, False)
        compact = len(others) > 8
        for device, (x, y) in zip(others, points):
            self._node(device, x, y, (13 if compact else 16) * scale, stats.get(device.ip),
                       device.ip in issues, compact)

    def _node(self, device, x, y, radius, stats, issue, compact):
        status = stats.status if stats else models.NO_DATA
        token = theme.TAG_COLORS.get(theme.STATUS_TAGS.get(status), theme.MUTED)
        surface, text = theme.color(theme.SURFACE), theme.color(theme.TEXT)
        ip = device.ip
        tags = ("node", f"ip:{ip}")
        self.nodes[ip] = self.create_oval(x - radius, y - radius, x + radius, y + radius,
                                         fill=theme.color(theme.INK) if device.is_gateway else surface,
                                         outline=theme.color(token), width=2, tags=tags)
        if not device.known:
            r = radius + 4
            self.create_oval(x - r, y - r, x + r, y + r, outline=theme.color(theme.BLUE), width=2, tags=tags)
        name = device.alias or ("Gateway" if device.is_gateway else device.hostname)
        label = name if len(name) <= 22 else name[:15] + "…" + name[-6:]
        status_text = models.STATUS_LABELS[status]
        scale = ctk.ScalingTracker.get_widget_scaling(self.master)
        glyph = theme.icon(theme.device_icon(device), theme.LIME_ON_INK if device.is_gateway else theme.TEXT,
                           14 if compact else 18)
        image = glyph.create_scaled_photo_image(scale, ctk.get_appearance_mode().lower())
        self.create_image(x, y, image=image, tags=tags)
        if compact:
            self.create_text(x, y + radius + 7, text=f".{ip.rsplit('.', 1)[-1]}", fill=theme.color(theme.TEXT_2),
                             font=(theme.MONO, 8), tags=tags)
        else:
            line = f"{label}\n{ip}" if status == models.ONLINE else f"{label}\n{ip} · {status_text}"
            item = self.create_text(x, y + radius + 6, text=line, fill=text, font=(theme.SANS, 9),
                                    justify="center", anchor="n", tags=tags)
            self.tag_lower(self.create_rectangle(self.bbox(item), fill=surface, outline="", tags=tags), item)
        if issue:
            bx, by = x + radius * 0.75, y - radius * 0.75
            self.create_oval(bx - 7, by - 7, bx + 7, by + 7, fill=theme.color(theme.RED), outline=surface, tags=tags)
            self.create_text(bx, by, text="!", fill=theme.color(theme.ON_INK), font=(theme.SANS_SEMIBOLD, 9), tags=tags)
        latency = f"{stats.avg_ms:g} ms average" if stats and stats.avg_ms is not None else None
        self.tips[ip] = tuple(filter(None, (device.alias or device.hostname, ip, status_text, latency,
                                            "New device" if not device.known else None, "Finding" if issue else None,
                                            device.mac, device.vendor)))

    def _apply_palette(self, _mode):
        self.configure(background=theme.color(theme.SURFACE), highlightbackground=theme.color(theme.SURFACE),
                       highlightcolor=theme.color(theme.INK))
        self._schedule_layout(None)

    def _update_scrollregion(self):
        x0, y0, x1, y1 = self.bbox("all") or (0, 0, 0, 0)
        self.configure(scrollregion=(min(x0 - 24, 0), min(y0 - 24, 0),
                                     max(x1 + 24, self.winfo_width()), max(y1 + 24, self.winfo_height())))

    def _move_view(self, x, y):
        x0, y0, x1, y1 = self.tk.splitlist(self.cget("scrollregion"))
        left, top, right, bottom = map(float, (x0, y0, x1, y1))
        self.xview_moveto((x - left) / (right - left))
        self.yview_moveto((y - top) / (bottom - top))

    def _select(self, ip, reveal=False):
        self.selected = ip
        self.delete("selection")
        self.on_select(self.tips[ip] if ip else ())
        if ip is None:
            return
        x0, y0, x1, y1 = self.coords(self.nodes[ip])
        self.create_oval(x0 - 7, y0 - 7, x1 + 7, y1 + 7, outline=theme.color(theme.INK), width=2,
                         tags=("selection", f"ip:{ip}"))
        if reveal:
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            left, top = self.canvasx(0), self.canvasy(0)
            width, height = self.winfo_width(), self.winfo_height()
            if not (left + 24 < x < left + width - 24 and top + 24 < y < top + height - 24):
                self._move_view(x - width / 2, y - height / 2)

    def _focus_node(self, _event):
        if self.selected is None and self.nodes:
            self._select(next(iter(self.nodes)), reveal=True)

    def _move_selection(self, step):
        if self.nodes:
            order = list(self.nodes)
            i = order.index(self.selected) if self.selected in self.nodes else (-1 if step > 0 else 0)
            self._select(order[(i + step) % len(order)], reveal=True)
        return "break"

    def _open_selection(self, _event):
        if self.selected:
            self.on_open(self.selected)
        return "break"

    def _ip_at(self):
        item = self.find_withtag("current")
        tags = self.gettags(item[0]) if item else ()
        return next((tag[3:] for tag in tags if tag.startswith("ip:")), None)

    def _press(self, event):
        self._drag_ip = self._ip_at()
        self._start = self._last = (event.x, event.y)
        if self._drag_ip is None:
            self.scan_mark(event.x, event.y)

    def _motion(self, event):
        if self._drag_ip is None:
            self.scan_dragto(event.x, event.y, gain=1)
            return
        if self._drag_ip == self.gateway:
            return
        dx, dy = event.x - self._last[0], event.y - self._last[1]
        self.delete("tooltip")
        self.move(f"ip:{self._drag_ip}", dx, dy)
        edge = self.coords(f"edge:{self._drag_ip}")
        if edge:
            self.coords(f"edge:{self._drag_ip}", *edge[:2], edge[2] + dx, edge[3] + dy)
        self._last = (event.x, event.y)

    def _release(self, event):
        moved = abs(event.x - self._start[0]) + abs(event.y - self._start[1])
        if self._drag_ip:
            self._select(self._drag_ip)
            self.focus_set()
            if moved < 4:
                self.on_open(self._drag_ip)
            self._update_scrollregion()
        self._drag_ip = None

    def _hover(self, event):
        ip = self._ip_at()
        if not ip or self._drag_ip:
            return
        self.delete("tooltip")
        x, y = self.canvasx(event.x) + 16, self.canvasy(event.y) + 16
        item = self.create_text(x, y, text="\n".join(self.tips[ip]), anchor="nw", fill=theme.color(theme.TEXT),
                                font=(theme.SANS, 9), tags="tooltip")
        x0, y0, x1, y1 = self.bbox(item)
        right, bottom = self.canvasx(self.winfo_width()), self.canvasy(self.winfo_height())
        self.move(item, min(0, right - x1 - 10), min(0, bottom - y1 - 10))
        x0, y0, x1, y1 = self.bbox(item)
        box = self.create_rectangle(x0 - 6, y0 - 4, x1 + 6, y1 + 4, fill=theme.color(theme.SURFACE),
                                    outline=theme.color(theme.BORDER_STRONG), tags="tooltip")
        self.tag_lower(box, item)

    def _zoom(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self.zoom(factor, event.x, event.y)

    def zoom(self, factor, x=None, y=None):
        """Zoom around the pointer or the center when using the toolbar."""
        x = self.winfo_width() / 2 if x is None else x
        y = self.winfo_height() / 2 if y is None else y
        self.delete("tooltip")
        self.scale("all", self.canvasx(x), self.canvasy(y), factor, factor)
        self._update_scrollregion()

    def fit(self):
        """Restore the layout to the available canvas."""
        self._layout()

    def menu(self, ip):
        """Create the context menu for one device."""
        menu = tk.Menu(self, tearoff=False, background=theme.color(theme.SURFACE),
                       foreground=theme.color(theme.TEXT), activebackground=theme.color(theme.INK),
                       activeforeground=theme.color(theme.ON_INK))
        for label, command in self.menu_items:
            menu.add_command(label=label, state="normal" if command else "disabled",
                             command=lambda command=command: command(ip))
        return menu

    def _popup(self, ip, x, y):
        menu = self.menu(ip)
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _right_click(self, event):
        if ip := self._ip_at():
            self._select(ip)
            self._popup(ip, event.x_root, event.y_root)

    def _keyboard_menu(self, _event):
        if self.selected:
            _, _, x, y = self.coords(self.nodes[self.selected])
            self._popup(self.selected, int(self.winfo_rootx() + x - self.canvasx(0)),
                        int(self.winfo_rooty() + y - self.canvasy(0)))
        return "break"
