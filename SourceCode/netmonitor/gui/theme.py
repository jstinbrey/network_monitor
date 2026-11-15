"""Colors, fonts and table styling shared by every view."""
from tkinter import ttk

GREEN, AMBER, RED, BLUE, MUTED = "#2fa572", "#e0a030", "#d9534f", "#1f6aa5", "#9aa0a6"
TAG_COLORS = {"good": GREEN, "warn": AMBER, "bad": RED}   # row colours in tables
PAD = 16
TITLE_FONT = ("Segoe UI", 22, "bold")


def style_tables():
    """ttk.Treeview is not a CustomTkinter widget, so it is styled here to match dark mode."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b",
                    foreground="#e6e6e6", rowheight=30, borderwidth=0, font=("Segoe UI", 11),
                    bordercolor="#2b2b2b", lightcolor="#2b2b2b", darkcolor="#2b2b2b")
    style.configure("Treeview.Heading", background="#1f538d", foreground="white",
                    relief="flat", font=("Segoe UI", 11, "bold"))
    style.map("Treeview", background=[("selected", "#1f538d")])
    style.map("Treeview.Heading", background=[("active", "#26609e")])