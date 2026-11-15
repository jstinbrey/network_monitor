"""A sortable, multi-select table of hosts, reused by several views."""
import ipaddress
from tkinter import ttk

import customtkinter as ctk

from netmonitor.gui import theme


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

    def selected(self) -> list[str]:
        """The IP addresses of the selected rows."""
        return list(self.tree.selection())

    def _sort(self, key):
        """Sort by a column; clicking the same heading again reverses the order."""
        def order(row_id):
            value = self.tree.set(row_id, key)
            try:
                return (0, int(ipaddress.ip_address(value)))   # 192.168.1.9 before 192.168.1.10
            except ValueError:
                return (1, value.lower())
        reverse = self._sorted_by == key
        self._sorted_by = None if reverse else key
        for index, row_id in enumerate(sorted(self.tree.get_children(), key=order, reverse=reverse)):
            self.tree.move(row_id, "", index)