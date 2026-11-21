"""Main application window: the sign-in screen, then a sidebar on the left and one view at a time on the right."""
import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme, worker
from netmonitor.gui.views.admin import AdminView
from netmonitor.gui.views.connection import ConnectionView
from netmonitor.gui.views.dashboard import DashboardView
from netmonitor.gui.views.devices import DevicesView
from netmonitor.gui.views.login import LoginView
from netmonitor.gui.views.ping import PingView
from netmonitor.gui.views.reports import ReportsView
from netmonitor.gui.views.security import SecurityView
from netmonitor.gui.views.statistics import StatisticsView
from netmonitor.gui.views.traceroute import TracerouteView
from netmonitor.gui.widgets.alert_bar import AlertBar
from netmonitor.gui.widgets.device_panel import DevicePanel
from netmonitor.gui.worker import run_async

VIEWS = [("Dashboard", DashboardView), ("Devices", DevicesView), ("Ping", PingView), ("Traceroute", TracerouteView),
         ("Connection", ConnectionView), ("Statistics", StatisticsView), ("Reports", ReportsView),
         ("Security", SecurityView)]   # sidebar order; the first one opens after sign-in
ADMIN_VIEWS = [("Admin", AdminView)]   # built only for administrators, so a User's window never contains them


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        theme.style_tables()
        worker.start_pump(self)

        self.title(f"{config.APP_TITLE} {config.VERSION}")
        self.geometry(config.WINDOW_SIZE)
        self.minsize(*config.MIN_WINDOW_SIZE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.user = self.main = self.panel = self.current = None
        self.login = LoginView(self, on_success=self.start)
        self.login.grid(row=0, column=0, sticky="nsew")

    @property
    def is_admin(self):
        return self.user.is_admin

    def start(self, user):
        """After sign-in: build the sidebar and only the views this user may open."""
        self.user = user
        self.login.grid_remove()
        self.main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main.grid(row=0, column=0, sticky="nsew")
        self.main.grid_columnconfigure(1, weight=1)   # the view stretches, the sidebar does not
        self.main.grid_rowconfigure(1, weight=1)      # row 0: the alert bar, when there is one; row 1: the view

        sidebar = ctk.CTkFrame(self.main, width=190, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text=config.APP_TITLE, font=theme.TITLE_FONT).pack(padx=theme.PAD, pady=(theme.PAD, 24))
        # The bottom of the sidebar, packed bottom-up: Sign out, and above it who is signed in.
        ctk.CTkButton(sidebar, text="Sign out", height=32, fg_color="transparent", border_width=1,
                      command=self.sign_out).pack(side="bottom", fill="x", padx=10, pady=(4, theme.PAD))
        ctk.CTkLabel(sidebar, text=f"{user.username}\n{'Administrator' if user.is_admin else 'User'}",
                     text_color=theme.MUTED).pack(side="bottom")

        self.views, self.buttons = {}, {}
        for name, view_class in VIEWS + (ADMIN_VIEWS if user.is_admin else []):
            self.views[name] = view_class(self.main, self)
            self.views[name].grid(row=1, column=1, sticky="nsew")
            self.buttons[name] = ctk.CTkButton(sidebar, text=name, anchor="w", height=36,
                                               command=lambda n=name: self.show(n))
            self.buttons[name].pack(fill="x", padx=10, pady=3)
        self.alert_bar = AlertBar(self.main, on_view=self.open_device, on_dismiss=self._dismiss)
        self.alert_bar.grid(row=0, column=1, sticky="ew")
        self.alert_bar.grid_remove()                  # hidden until the first alert
        self.show(VIEWS[0][0])
        self._bw_ticks = 0
        self._sample_bandwidth()

    def show(self, name, **kwargs):
        """Bring a view to the front, highlight its sidebar button, and let it refresh."""
        self.current = name
        for key, button in self.buttons.items():
            button.configure(fg_color=theme.BLUE if key == name else "transparent")
        self.views[name].tkraise()
        self.views[name].on_show(**kwargs)

    def _sample_bandwidth(self):
        """Once a second while signed in: this PC's download and upload rates, and any limit just passed."""
        self._bw_job = self.after(config.BW_SAMPLE_MS, self._sample_bandwidth)   # reschedule first, like the pump
        sample = services.bandwidth_sample()     # reads two counters: no network traffic, about 5 ms
        if sample:
            self.views["Connection"].add_sample(sample)
            for detail in sample.alerts:         # storing one works out the network id (about 0.2 s): a worker does it
                run_async(services.record_event, "bandwidth", "warning", None, None, detail, on_done=self.alert)
        self._bw_ticks += 1
        if self._bw_ticks % config.BW_SAVE_EVERY_S == 0:
            run_async(services.flush_usage)       # the database write happens off the UI thread

    def alert(self, event):
        """A new event: show it in the alert bar and in the Dashboard's list."""
        if self.main:                             # not signed out while it was being stored
            self.alert_bar.show(event)
            self.views["Dashboard"].load_alerts()

    def _dismiss(self, event_id):
        run_async(services.dismiss, event_id, on_done=lambda _: self.views["Dashboard"].load_alerts())

    def open_device(self, ip):
        """One device panel for the whole app: made on first use, then reused."""
        if self.panel is None:
            self.panel = DevicePanel(self.main, self)
        self.panel.show(ip)

    def sign_out(self):
        """Stop anything still running, throw the views away, and go back to the sign-in screen."""
        self.after_cancel(self._bw_job)
        services.flush_usage()
        services.logout()
        self.main.destroy()                           # the device panel is inside it, so it goes too
        self.user = self.main = self.panel = self.current = None
        self.login.reset()
        self.login.grid()

    def close(self):
        services.stop_all()      # no ping.exe or tracert.exe may outlive the window
        services.flush_usage()   # the last seconds of today's use
        self.destroy()