"""Security findings, severity filters, and device confirmation with Undo."""
import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.recommendation_card import RecommendationCard
from netmonitor.gui.worker import run_async

FILTERS = {"all": "All", "critical": "Critical", "warning": "Warnings", "info": "Info"}


class SecurityView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.recs = []
        self.severity = "all"
        self.busy = False
        self.change = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 12))
        self.refresh = theme.ActionButton(header, text="Re-test devices", width=158, height=40, corner_radius=20,
                                     image=theme.icon("refresh"), command=self._retest)
        self.refresh.pack(side="right", anchor="n", padx=(12, 0))
        ctk.CTkLabel(header, text="Security", font=theme.TITLE_FONT, anchor="w").pack(fill="x")
        self.status = ctk.CTkLabel(header, text="Checking for findings…", anchor="w", justify="left",
                                    wraplength=520, text_color=theme.MUTED)
        self.status.pack(fill="x")

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(fill="x", padx=theme.PAD, pady=(0, 12))
        self.filters = {}
        for severity, label in FILTERS.items():
            button = theme.ActionButton(filters, text=label, width=74, height=36, corner_radius=18,
                                   command=lambda key=severity: self._filter(key), font=theme.BODY_FONT)
            button.pack(side="left", padx=(0, 8))
            self.filters[severity] = button

        self.toast = ctk.CTkFrame(self, fg_color=theme.INK)
        self.toast_text = ctk.CTkLabel(self.toast, text="Device marked as known", text_color=theme.SURFACE)
        self.toast_text.pack(side="left", padx=16, pady=8)
        self.undo = theme.ActionButton(self.toast, text="Undo", width=72, height=32, command=self._undo)
        self.undo.pack(side="right", padx=8, pady=8)
        theme.ActionButton(self.toast, text="Dismiss", width=80, height=32,
                      command=self._hide_toast).pack(side="right")

        self.cards = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.cards.pack(fill="both", expand=True, padx=(theme.PAD, 4), pady=(0, theme.PAD))
        self._filter("all", render=False)

    def on_show(self, mark_ip=None):
        """Refresh findings from the stored scan and ping results."""
        if mark_ip:
            self._mark_known(mark_ip)
        else:
            self._load(services.recommendations, self._show)

    def _retest(self):
        self.status.configure(text="Re-testing devices…", text_color=theme.MUTED)
        self._load(services.refresh_dashboard, lambda data: self._show(data[2]))

    def _load(self, service, callback, *args):
        if self.busy:
            return
        self.busy = True
        self.refresh.configure(state="disabled")
        self.undo.configure(state="disabled")
        run_async(service, *args, on_done=callback, on_error=self._show_error)

    def _ready(self):
        self.busy = False
        self.refresh.configure(state="normal")
        self.undo.configure(state="normal")

    def _mark_known(self, ip):
        if self.app.is_admin:
            self._load(services.mark_known_change, self._marked, ip)
        elif self.app.user is None:
            self.app.ask_login("Sign in to mark this device as known", "Only an administrator can confirm new devices.",
                               "Sign in and mark", mark_ip=ip)

    def _marked(self, change):
        self._ready()
        if change:
            self.change = change
            self.toast.pack(side="bottom", fill="x", padx=theme.PAD, pady=(0, theme.PAD))
        self.on_show()

    def _undo(self):
        self._load(services.undo_mark_known, self._undone, self.change)

    def _hide_toast(self):
        self.change = None
        self.toast.pack_forget()

    def _undone(self, _):
        self._hide_toast()
        self._ready()
        self.on_show()

    def _show(self, recs):
        self._ready()
        self.recs = recs
        critical = sum(r.severity == "critical" for r in recs)
        warnings = sum(r.severity == "warning" for r in recs)
        if critical:
            text, color = ("1 critical finding needs attention." if critical == 1 else
                           f"{critical} critical findings need attention."), theme.RED
        elif warnings:
            text, color = f"{warnings} warning{'s' if warnings != 1 else ''} to review.", theme.AMBER
        else:
            text, color = "No critical findings or warnings in the latest results.", theme.TEXT_2
        self.status.configure(text=text, text_color=color)
        self._filter(self.severity)

    def _filter(self, severity, render=True):
        self.severity = severity
        for key, button in self.filters.items():
            selected = key == severity
            count = len(self.recs) if key == "all" else sum(rec.severity == key for rec in self.recs)
            button.configure(text=f"{FILTERS[key]}  {count}", fg_color=theme.INK if selected else theme.SURFACE,
                             text_color=theme.SURFACE if selected else theme.TEXT, border_color=theme.BORDER,
                             hover_color=theme.INK_HOVER if selected else theme.SUBTLE)
        if not render:
            return
        for card in self.cards.winfo_children():
            card.destroy()
        recs = [rec for rec in self.recs if severity == "all" or rec.severity == severity]
        if not recs:
            ctk.CTkLabel(self.cards, text="No findings in this view.", text_color=theme.MUTED).pack(anchor="w")
        for rec in recs:
            can_mark = rec.category == "Access control" and (self.app.is_admin or self.app.user is None)
            RecommendationCard(self.cards, rec, on_mark_known=self._mark_known if can_mark else None,
                               on_open=self.app.open_device, locked=self.app.user is None).pack(fill="x", pady=(0, 12))

    def _show_error(self, error):
        self._ready()
        self.status.configure(text=str(error), text_color=theme.RED)
