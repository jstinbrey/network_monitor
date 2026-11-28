"""A sortable, multi-select table of hosts, reused by several views."""
import ipaddress
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from netmonitor.gui import theme


def sort_key(value: str):
    """Order for one cell: IP addresses and numbers by value, then text; "No data" goes last."""
    try:
        return (0, int(ipaddress.ip_address(value)))        # 192.168.1.9 before 192.168.1.10
    except ValueError:
        pass
    try:
        return (0, float(value.split()[0].rstrip("%")))     # "12.4 ms" and "25%" sort as numbers
    except (ValueError, IndexError):
        return (1, value.lower())


class HostTable(ctk.CTkFrame):
    def __init__(self, parent, columns, device_column=False):
        """columns: list of (key, title, width). One column must have the key "ip"."""
        super().__init__(parent)
        self.tree = ttk.Treeview(self, columns=[key for key, _, _ in columns], selectmode="extended",
                                 show="tree headings" if device_column else "headings",
                                 style="Devices.Treeview" if device_column else "Treeview")
        for key, title, width in columns:
            self.tree.heading(key, text=title, anchor="w", command=lambda k=key: self._sort(k))
            self.tree.column(key, width=width, anchor="w")
        self._style_rows()
        theme.appearance_callback(self, self._style_rows)
        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=8)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        self._sorted_by = None
        self._reverse = False

    def set_rows(self, rows):
        """rows: list of dicts with a value per column key, plus an optional "tag"."""
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", "end", iid=row["ip"], tags=(row.get("tag", ""),),
                             values=[row[key] for key in self.tree["columns"]])
        self._sort_rows()

    def on_open(self, callback):
        """Open a focused device by keyboard or double-click."""
        def opened(event):
            row = self.tree.identify_row(event.y)   # empty when the heading was double-clicked
            if row:
                callback(row)
        def open_focused(event):
            row = self.tree.focus()
            if row:
                callback(row)
            return "break"
        def show_menu(event):
            row = self.tree.focus()
            if row:
                self.tree.see(row)
                x, y, _, height = self.tree.bbox(row)
                menu = tk.Menu(self.tree, tearoff=False, background=theme.color(theme.SURFACE),
                               foreground=theme.color(theme.TEXT), activebackground=theme.color(theme.INK),
                               activeforeground=theme.color(theme.ON_INK))
                menu.add_command(label="Open device", command=lambda: callback(row))
                try:
                    menu.tk_popup(self.tree.winfo_rootx() + x, self.tree.winfo_rooty() + y + height)
                finally:
                    menu.grab_release()
            return "break"
        self.tree.bind("<Double-1>", opened)
        self.tree.bind("<Return>", open_focused)
        self.tree.bind("<Shift-F10>", show_menu)
        self.tree.bind("<Menu>", show_menu)

    def _style_rows(self, _mode=None):
        for tag, token in theme.TAG_COLORS.items():
            self.tree.tag_configure(tag, foreground=theme.color(theme.TEXT if tag == "good" else token))

    def selected(self) -> list[str]:
        """The IP addresses of the selected rows."""
        return list(self.tree.selection())

    def _sort(self, key):
        """Sort by a column; clicking the same heading again reverses the order."""
        self._reverse = self._sorted_by == key and not self._reverse
        self._sorted_by = key
        self._sort_rows()

    def _sort_rows(self):
        key = self._sorted_by
        if key is None:
            return
        def value(row):
            return self.tree.item(row, "text").split("\n", 1)[0] if key == "#0" else self.tree.set(row, key)
        rows = sorted(self.tree.get_children(), key=lambda row: sort_key(value(row)), reverse=self._reverse)
        for index, row in enumerate(rows):
            self.tree.move(row, "", index)


class DeviceTable(HostTable):
    """Dense ttk rows with a separate bulk selection and drawer highlight."""

    def __init__(self, parent, on_open, on_selection, on_menu):
        super().__init__(parent, [("ip", "IP address", 125), ("mac", "MAC address", 145),
                                  ("latency", "Latency", 75), ("status", "Status", 130),
                                  ("options", "", 36)], device_column=True)
        self.on_open_device, self.on_selection, self.on_menu = on_open, on_selection, on_menu
        self.devices, self.images = {}, {}
        self.active_ip = None
        self.tree.heading("#0", text="Device", anchor="w", command=lambda: self._sort("#0"))
        self.tree.column("#0", width=265, anchor="w")
        self.tree.column("options", stretch=False)
        self.on_open(on_open)
        self.tree.bind("<Button-1>", self._click, add="+")
        self.tree.bind("<Button-3>", self._menu_event)
        self.tree.bind("<Shift-F10>", self._menu_event)
        self.tree.bind("<Menu>", self._menu_event)
        self.tree.bind("<space>", self._toggle_focused)
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.bind("<Configure>", self._fit_columns, add="+")
        self._style_device_rows()
        theme.appearance_callback(self, self._style_device_rows)

    def set_rows(self, rows):
        """Replace visible rows while keeping the selected devices, focus, and scroll offset."""
        selected, focused, y = set(self.selected()), self.tree.focus(), self.tree.yview()[0]
        self.tree.delete(*self.tree.get_children())
        self.devices = {row["ip"]: row for row in rows}
        for ip, row in self.devices.items():
            self.tree.insert("", "end", iid=ip, text=row["name"],
                             values=[row[key] for key in self.tree["columns"]])
        self._sort_rows()
        self.tree.selection_set([ip for ip in self.devices if ip in selected])
        if focused in self.devices:
            self.tree.focus(focused)
        self.tree.yview_moveto(y)
        self._selection_changed()

    def show_open(self, ip=None):
        """Highlight the row associated with the drawer."""
        self.active_ip = ip
        self._paint_rows()

    def _style_device_rows(self, _mode=None):
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        style = ttk.Style(self)
        style.configure("Devices.Treeview", rowheight=round(scale * 54), font=theme.CAPTION_FONT)
        style.layout("Devices.Treeview.Item", [
            ("Treeitem.padding", {"sticky": "nsew", "children": [
                ("Treeitem.image", {"side": "left"}), ("Treeitem.text", {"side": "left", "sticky": "w"}),
            ]}),
        ])
        self.tree.tag_configure("open", background=theme.color(theme.SUBTLE))
        self.images.clear()
        self._paint_rows()

    def _fit_columns(self, event):
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        fixed = {"ip": 117, "mac": 138, "latency": 73, "status": 135, "options": 30}
        for key, width in fixed.items():
            self.tree.column(key, width=round(width * scale), stretch=False)
        self.tree.column("#0", width=max(round(150 * scale), event.width - round(sum(fixed.values()) * scale) - 2),
                         stretch=False)

    def _image(self, icon, checked, opened):
        state = (icon, checked, opened)
        if state not in self.images:
            scale = ctk.ScalingTracker.get_widget_scaling(self)
            def px(x):
                return round(x * scale)
            def box(*coordinates):
                return tuple(map(px, coordinates))
            image = Image.new("RGBA", box(73, 54))
            paint = ImageDraw.Draw(image)
            paint.rounded_rectangle(box(12, 19, 29, 36), px(4),
                                    fill=theme.color(theme.INK if checked else theme.SURFACE),
                                    outline=theme.color(theme.INK if checked else theme.BORDER_CONTROL),
                                    width=max(1, px(1)))
            paint.ellipse(box(39, 11, 70, 42), fill=theme.color(theme.INK if opened else theme.SUBTLE))
            def paste(name, token, size, x, y):
                shape = Image.open(theme.RESOURCES / "icons" / f"{name}.png").getchannel("A")
                mark = Image.new("RGBA", box(size, size), theme.color(token))
                mark.putalpha(shape.resize(mark.size, Image.Resampling.LANCZOS))
                image.alpha_composite(mark, box(x, y))
            if checked:
                paste("check", theme.ON_INK, 12, 15, 22)
            paste(icon, theme.ON_INK if opened else theme.TEXT, 16, 47, 19)
            self.images[state] = ImageTk.PhotoImage(image, master=self.tree)
        return self.images[state]

    def _paint_rows(self):
        selected = set(self.selected())
        for ip, row in self.devices.items():
            opened = ip == self.active_ip
            self.tree.item(ip, tags=(row["tag"], "open") if opened else (row["tag"],),
                           image=self._image(row["icon"], ip in selected, opened))

    def _selection_changed(self, event=None):
        self._paint_rows()
        self.on_selection(self.selected())

    def _click(self, event):
        if self.tree.identify_region(event.x, event.y) != "tree" and self.tree.identify_region(event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        column = self.tree.identify_column(event.x)
        if column == "#5":
            return self._menu_event(event)
        if column == "#0" and not event.state & 5:
            self.tree.focus_set()
            self.tree.focus(row)
            if event.x <= 34 * ctk.ScalingTracker.get_widget_scaling(self):
                self.tree.selection_toggle(row)
            else:
                self.on_open_device(row)
            return "break"

    def _toggle_focused(self, event):
        if row := self.tree.focus():
            self.tree.selection_toggle(row)
        return "break"

    def _select_all(self, event):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _menu_event(self, event):
        row = self.tree.identify_row(event.y) if event.num in (1, 3) else self.tree.focus()
        if row:
            self.tree.see(row)
            x, y, _, height = self.tree.bbox(row)
            self.on_menu(row, self.tree.winfo_rootx() + x + min(self.tree.winfo_width() - 20, event.x or 20),
                         self.tree.winfo_rooty() + y + height)
        return "break"
