"""Main application window: a sidebar on the left and one view at a time on the right. Signing in is optional."""
from collections import deque
from datetime import datetime
from time import monotonic
import tkinter as tk

import customtkinter as ctk

from netmonitor import config, models, services
from netmonitor.gui import theme, worker
from netmonitor.gui.views.admin import AdminView
from netmonitor.gui.views.connection import ConnectionView
from netmonitor.gui.views.dashboard import DashboardView
from netmonitor.gui.views.devices import DevicesView
from netmonitor.gui.views.login import LoginView
from netmonitor.gui.views.map import MapView
from netmonitor.gui.views.ping import PingView
from netmonitor.gui.views.reports import ReportsView
from netmonitor.gui.views.security import SecurityView
from netmonitor.gui.views.statistics import StatisticsView
from netmonitor.gui.views.traceroute import TracerouteView
from netmonitor.gui.widgets.alert_bar import AlertBar
from netmonitor.gui.widgets.device_panel import DevicePanel
from netmonitor.gui.worker import run_async

VIEWS = [("Dashboard", DashboardView), ("Devices", DevicesView), ("Map", MapView), ("Ping", PingView),
         ("Traceroute", TracerouteView), ("Connection", ConnectionView), ("Statistics", StatisticsView),
         ("Reports", ReportsView), ("Security", SecurityView)]   # sidebar order
ADMIN_VIEWS = [("Admin", AdminView)]   # built only for administrators, so a User's window never contains them
# Sidebar groups: (label, [(view, icon)]). "Manage" is shown only to administrators.
NAV_GROUPS = [("Monitor", [("Dashboard", "dashboard"), ("Devices", "devices"), ("Map", "map")]),
              ("Test", [("Ping", "ping"), ("Traceroute", "traceroute"), ("Connection", "connection")]),
              ("Analyze", [("Statistics", "statistics"), ("Reports", "reports"), ("Security", "security")]),
              ("Manage", [("Admin", "users")])]
ICONS = {name: icon for _, items in NAV_GROUPS for name, icon in items}


class App(ctk.CTk):
    def __init__(self):
        theme.load()             # fonts and theme.json must be in place before the first widget exists
        super().__init__()
        theme.setup(self)
        worker.start_pump(self)

        self.title(f"{config.APP_TITLE} {config.VERSION}")
        self.geometry(config.WINDOW_SIZE)
        self.minsize(*config.MIN_WINDOW_SIZE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", self._escape_drawer, add="+")
        self.bind("<Tab>", self._drawer_tab, add="+")
        self.bind("<Shift-Tab>", self._drawer_tab, add="+")

        self.user = self.main = self.panel = self.current = self.login = None
        self.start(None)                              # signing in is optional: everyone starts as a guest

    @property
    def is_admin(self):
        return bool(self.user and self.user.is_admin)

    def start(self, user, view="Dashboard", **view_options):
        """Build the sidebar and only the views this user may open. user is None for a guest."""
        if self.main is not None:                     # replacing the guest window after a sign-in
            self._close_main()
        self.user, self.panel = user, None
        self.bandwidth_samples = deque(maxlen=config.BW_WINDOW_S)
        self.main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main.grid(row=0, column=0, sticky="nsew")
        self.main.grid_columnconfigure(1, weight=1)   # the view stretches, the sidebar does not
        self.main.grid_rowconfigure(1, weight=1)      # row 0: the alert bar, when there is one; row 1: the view

        sidebar = self._sidebar(user)
        self.watch_switches, self._watch_job, self._watch_busy = [], None, False   # views add their switches
        self.views = {}
        self.view_types = dict(VIEWS + (ADMIN_VIEWS if self.is_admin else []))
        self.buttons = self._nav(sidebar)
        self.alert_bar = AlertBar(self.main, on_view=self.open_device, on_dismiss=self._dismiss)
        self.alert_bar.grid(row=0, column=1, sticky="ew", padx=theme.PAD, pady=(12, 0))
        self.alert_bar.grid_remove()                  # hidden until the first alert
        self.show(view, **view_options)
        self._bw_ticks = 0
        self._sample_bandwidth()
        run_async(services.wifi_link, on_done=self._show_network)   # netsh takes ~0.3 s: off the UI thread

    def _sidebar(self, user):
        """The sidebar card: logo, the optional admin sign-in (upper left), and the Wi-Fi card at the bottom."""
        sidebar = ctk.CTkFrame(self.main, width=212)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(12, 0), pady=12)
        sidebar.pack_propagate(False)
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(16, 12))
        ctk.CTkLabel(brand, text="", image=theme.icon("ping", theme.ON_LIME, 18), fg_color=theme.LIME, corner_radius=10,
                     width=32, height=32).pack(side="left")
        ctk.CTkLabel(brand, text=config.APP_TITLE, font=theme.CARD_FONT).pack(side="left", padx=10)
        if user:   # who is signed in, with Sign out beside it
            account = ctk.CTkFrame(sidebar, fg_color=theme.SUBTLE, corner_radius=12)
            account.pack(fill="x", padx=8)
            ctk.CTkLabel(account, text=user.username[:1].upper(), text_color=theme.LIME_ON_INK, fg_color=theme.INK,
                         corner_radius=14, width=28, height=28, font=theme.CAPTION_FONT).pack(side="left", padx=6, pady=6)
            theme.ActionButton(account, text="", image=theme.icon("log-out", theme.TEXT_2, 16), width=28, height=28,
                          command=self.sign_out, **theme.GHOST).pack(side="right", padx=6)
            ctk.CTkLabel(account, text=f"{user.username}\n{'Administrator' if user.is_admin else 'User'}",
                         justify="left", anchor="w", font=theme.CAPTION_FONT).pack(side="left", fill="x", expand=True)
        else:      # signing in is optional: a guest sees this button at the upper left
            theme.ActionButton(sidebar, text="Admin sign in", image=theme.icon("lock", theme.TEXT, 16), compound="left",
                               height=36, command=self.ask_login).pack(fill="x", padx=8)
        # The bottom, packed bottom-up: the Wi-Fi card, and above it the watch state.
        network = ctk.CTkFrame(sidebar, fg_color=theme.SUBTLE, corner_radius=12)
        network.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
        self.ssid = ctk.CTkLabel(network, text=" Reading Wi-Fi...", image=theme.icon("wifi", theme.GREEN, 16),
                                 compound="left", anchor="w", font=theme.BODY_FONT)
        self.ssid.pack(fill="x", padx=12, pady=(8, 0))
        self.rates = ctk.CTkLabel(network, text="↓ –   ↑ –", anchor="w", font=theme.MONO_FONT)
        self.rates.pack(fill="x", padx=12, pady=(0, 8))
        self.watch_label = ctk.CTkLabel(sidebar, text="", text_color=theme.GREEN, font=theme.CAPTION_FONT, height=16)
        return sidebar

    def _nav(self, sidebar):
        """One button per view, grouped; only the groups this user may open."""
        buttons = {}
        for group, items in NAV_GROUPS:
            items = [(name, icon) for name, icon in items if name in self.view_types]
            if not items:
                continue
            ctk.CTkLabel(sidebar, text=group, text_color=theme.MUTED, font=theme.CAPTION_FONT, anchor="w",
                         height=18).pack(fill="x", padx=20, pady=(4, 1))
            for name, icon in items:
                buttons[name] = theme.ActionButton(sidebar, text=name, image=theme.icon(icon, theme.TEXT_2), compound="left",
                                              anchor="w", height=34, corner_radius=12, font=theme.BODY_FONT,
                                              command=lambda n=name: self.show(n), **theme.GHOST)
                buttons[name].pack(fill="x", padx=8)
        return buttons

    def show(self, name, **kwargs):
        """Mount only the active view while retaining the state of views already visited."""
        if name not in self.views:
            self.views[name] = self.view_types[name](self.main, self)
        if self.current and self.current != name:
            self.close_device(restore_focus=False)
            self.views[self.current].grid_remove()
        self.current = name
        for key, button in self.buttons.items():
            on = key == name
            button.configure(fg_color=theme.INK if on else "transparent", hover_color=theme.INK if on else theme.SUBTLE,
                             text_color=theme.ON_INK if on else theme.TEXT_2,
                             image=theme.icon(ICONS[key], theme.LIME_ON_INK if on else theme.TEXT_2))
        view = self.views[name]
        view.grid(row=1, column=1, sticky="nsew")
        view.focus_set()
        view.on_show(**kwargs)

    def _show_network(self, result):
        link, note = result
        if self.main:   # not signed in or out while netsh ran
            self.ssid.configure(text=f" {link.ssid}" if link else f" {'Wired or offline' if note else 'No network'}",
                                image=theme.icon("wifi", theme.GREEN if link else theme.MUTED, 16))

    def _sample_bandwidth(self):
        """Once a second while the window is open: this PC's download and upload rates, and any limit just passed."""
        self._bw_job = self.after(config.BW_SAMPLE_MS, self._sample_bandwidth)   # reschedule first, like the pump
        sample = services.bandwidth_sample()     # reads two counters: no network traffic, about 5 ms
        if sample:
            self.rates.configure(text=f"↓ {sample.down_mbps:.1f}   ↑ {sample.up_mbps:.1f} Mbps")
            self.bandwidth_samples.append((monotonic(), sample))
            if self.current == "Connection":
                self.views["Connection"].redraw_bandwidth()
            for detail in sample.alerts:         # storing one works out the network id (about 0.2 s): a worker does it
                run_async(services.record_event, "bandwidth", "warning", None, None, detail, on_done=self.alert)
        self._bw_ticks += 1
        if self._bw_ticks % config.BW_SAVE_EVERY_S == 0:
            run_async(services.flush_usage)       # the database write happens off the UI thread

    def add_watch_switch(self, parent):
        """A Watch switch in a view's toolbar, packed on the right. All of them show the same state."""
        if not self.user:
            button = theme.locked_button(parent, "Watch", lambda: self.ask_login(
                "Sign in to start watch mode", "Watch checks the local network for changes.",
                "Sign in and start", lambda: self.set_watch(True)), width=100)
            button.pack(side="right")
            return button
        if not self.is_admin:
            return None
        switch = theme.Switch(parent, text="Watch", command=lambda: self.set_watch(bool(switch.get())))
        if self._watch_job:
            switch.select()
        switch.pack(side="right")
        self.watch_switches.append(switch)
        return switch

    def set_watch(self, on):
        """Watch mode (Admin): scan every few minutes, and raise an alert for each change."""
        for switch in self.watch_switches:
            switch.select() if on else switch.deselect()
        if self._watch_job:
            self.after_cancel(self._watch_job)
            self._watch_job = None
        self.watch_label.pack_forget()
        if on:
            services.start_watch()
            self._watch_minutes = services.settings()["watch_min"]   # one small database read
            self.watch_label.configure(text=f"Watch ●  every {self._watch_minutes:g} min")
            self.watch_label.pack(side="bottom", before=self.buttons["Dashboard"])
            self._watch_tick()                                       # the first check runs now

    def _watch_tick(self):
        self._watch_job = self.after(round(self._watch_minutes * 60_000), self._watch_tick)   # reschedule first
        if not self._watch_busy:                  # a check still running (a slow scan) is not started twice
            self._watch_busy = True
            run_async(services.watch_tick, on_done=self._watched, on_error=self._watch_failed)

    def _watched(self, events):
        self._watch_busy = False
        for event in events:
            self.alert(event)
        if self._watch_job and self.current == "Map":
            self.views["Map"].refresh_after_watch()

    def _watch_failed(self, error):
        self._watch_busy = False
        self.alert(models.Event(None, datetime.now().isoformat(timespec="seconds"), "watch", "warning", None, None,
                                f"A watch check failed: {error}"))   # not stored: id None, so Dismiss only hides it

    def alert(self, event):
        """A new event: show it in the alert bar and in the Dashboard's list."""
        if self.main:                             # not signed out while it was being stored
            self.alert_bar.show(event)
            self._refresh_dashboard_alerts()

    def _dismiss(self, event_id):
        run_async(services.dismiss, event_id, on_done=self._refresh_dashboard_alerts)

    def _refresh_dashboard_alerts(self, _result=None):
        if self.main and (dashboard := self.views.get("Dashboard")):
            dashboard.load_alerts()

    def open_device(self, ip):
        """Open the selected host in the drawer over the current view."""
        if self.panel is None:
            self.panel = DevicePanel(self.main, self)
        if not self.panel.ip:
            self._device_focus = self.focus_get()
        self.panel.show(ip)
        if self.current == "Devices":
            self.views["Devices"].table.show_open(ip)
        return self.panel

    def close_device(self, restore_focus=True):
        """Dismiss the drawer and return keyboard focus to the caller."""
        if not self.panel or not self.panel.ip:
            return
        self.panel.hide()
        if self.current == "Devices":
            self.views["Devices"].table.show_open()
        if restore_focus:
            target = self._device_focus
            if not (target and target.winfo_exists() and target.winfo_viewable()):
                target = self.views[self.current]
            tk.Misc.focus_set(target)
        self._device_focus = None

    def _escape_drawer(self, event):
        if self.panel and self.panel.ip:
            self.close_device()
            return "break"

    def _drawer_tab(self, event):
        if self.panel and self.panel.ip and str(event.widget).startswith(f"{self.panel}."):
            previous = bool(event.state & 1)
            target = event.widget.tk_focusPrev() if previous else event.widget.tk_focusNext()
            if target and not str(target).startswith(f"{self.panel}."):
                self.panel.focus_last() if previous else self.panel.focus_first()
                return "break"

    def ask_login(self, title="Sign in as administrator", description=None, submit="Sign in", action=None, **view_options):
        """Keep the current view visible and run a pending action only after administrator sign-in."""
        if self.login:
            self.login.lift()
            return
        view = self.current
        self._login_focus = self.focus_get()

        def signed_in(user):
            self.cancel_login()
            self.start(user, view, **view_options)
            if action:
                action()

        self.login = LoginView(self, title, description, submit, signed_in, self.cancel_login,
                               admin_only=bool(action or view_options))

    def ask_scan(self):
        """Sign in and scan from the view where the guest pressed Scan network."""
        self.ask_login("Sign in to scan the network",
                       "Scanning needs an administrator. The scan starts as soon as you sign in.",
                       "Sign in and scan", scan=True)

    def cancel_login(self):
        if self.login:
            self.login.destroy()
            self.login = None
            target, self._login_focus = self._login_focus, None
            if not (target and target.winfo_exists() and target.winfo_viewable()):
                target = self.views.get(self.current)
            if target:
                tk.Misc.focus_set(target)

    def _close_main(self):
        """Stop the timers and anything still running, then throw the views away."""
        self.after_cancel(self._bw_job)
        if self._watch_job:
            self.after_cancel(self._watch_job)
        services.flush_usage()
        services.stop_all()
        self.main.destroy()                           # the device panel is inside it, so it goes too
        self.main = self.current = None

    def sign_out(self):
        """Stop anything still running, throw the views away, and go back to the guest window."""
        self._close_main()
        services.logout()
        self.start(None)

    def close(self):
        services.stop_all()      # no ping.exe or tracert.exe may outlive the window
        services.flush_usage()   # the last seconds of today's use
        self.destroy()
