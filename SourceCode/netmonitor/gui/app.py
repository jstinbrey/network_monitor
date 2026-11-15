"""Main application window.

Phase 0: an empty window that proves the environment works. The sidebar and
the feature views are added in Phase 1.
"""
import customtkinter as ctk

from netmonitor import config


class App(ctk.CTk):
    """The NetMonitor main window."""

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(config.APP_TITLE)
        self.geometry(config.WINDOW_SIZE)
        self.minsize(*config.MIN_WINDOW_SIZE)
