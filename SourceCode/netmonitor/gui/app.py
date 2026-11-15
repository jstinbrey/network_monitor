"""Main application window: a sidebar on the left and one view at a time on the right."""
import customtkinter as ctk

from netmonitor import config
from netmonitor.gui import theme, worker
from netmonitor.gui.views.devices import DevicesView
from netmonitor.gui.views.ping import PingView
from netmonitor.gui.views.reports import ReportsView
from netmonitor.gui.views.statistics import StatisticsView

VIEWS = [("Devices", DevicesView), ("Ping", PingView), ("Statistics", StatisticsView), ("Reports", ReportsView)]   # sidebar order; later views are added here

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        theme.style_tables()
        worker.start_pump(self)

        self.title(config.APP_TITLE)
        self.geometry(config.WINDOW_SIZE)
        self.minsize(*config.MIN_WINDOW_SIZE)
        self.grid_columnconfigure(1, weight=1)   # the view stretches, the sidebar does not
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=190, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text=config.APP_TITLE, font=theme.TITLE_FONT).pack(padx=theme.PAD, pady=(theme.PAD, 24))

        self.views, self.buttons = {}, {}
        for name, view_class in VIEWS:
            self.views[name] = view_class(self, self)
            self.views[name].grid(row=0, column=1, sticky="nsew")
            self.buttons[name] = ctk.CTkButton(sidebar, text=name, anchor="w", height=36,
                                               command=lambda n=name: self.show(n))
            self.buttons[name].pack(fill="x", padx=10, pady=3)
        self.show(VIEWS[0][0])

    def show(self, name, **kwargs):
        """Bring a view to the front, highlight its sidebar button, and let it refresh."""
        for key, button in self.buttons.items():
            button.configure(fg_color=theme.BLUE if key == name else "transparent")
        self.views[name].tkraise()
        self.views[name].on_show(**kwargs)