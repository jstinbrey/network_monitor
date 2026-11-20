"""A sortable, multi-select table of hosts, reused by several views."""
import ipaddress
from tkinter import ttk

import customtkinter as ctk

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
    def __init__(self, parent, columns):
        """columns: list of (key, title, width). One column must have the key "ip"."""
        super().__init__(parent)
        self.tree = ttk.Treeview(self, columns=[key for key, _, _ in columns],
                                 show="headings", selectmode="extended")
        for key, title, width in columns:
            self.tree.heading(key, text=title, anchor="w", command=lambda k=key: self._sort(k))
            self.tree.column(key, width=width, anchor="w")
        for tag, color in theme.TAG_COLORS.items():
            self.tree.tag_configure(tag, foreground=color)
        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        scrollbar.pack(side="right", fill="y")
        self._sorted_by = None

    def set_rows(self, rows):
        """rows: list of dicts with a value per column key, plus an optional "tag"."""
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", "end", iid=row["ip"], tags=(row.get("tag", ""),),
                             values=[row[key] for key in self.tree["columns"]])

    def on_open(self, callback):
        """Double-clicking a row calls callback(ip). Double-clicking a heading does nothing."""
        def opened(event):
            row = self.tree.identify_row(event.y)   # empty when the heading was double-clicked
            if row:
                callback(row)
        self.tree.bind("<Double-1>", opened)

    def selected(self) -> list[str]:
        """The IP addresses of the selected rows."""
        return list(self.tree.selection())

    def _sort(self, key):
        """Sort by a column; clicking the same heading again reverses the order."""
        reverse = self._sorted_by == key
        self._sorted_by = None if reverse else key
        rows = sorted(self.tree.get_children(), key=lambda row: sort_key(self.tree.set(row, key)), reverse=reverse)
        for index, row in enumerate(rows):
            self.tree.move(row, "", index)
