"""Security view (Feature 5): connectivity alerts, new-device warnings, and firewall and password reminders."""
import customtkinter as ctk

from netmonitor import services
from netmonitor.gui import theme
from netmonitor.gui.widgets.recommendation_card import RecommendationCard
from netmonitor.gui.worker import run_async


class SecurityView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(self, text="Security", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))
        self.status = ctk.CTkLabel(self, text="Checking...", anchor="w", text_color=theme.MUTED)
        self.status.pack(fill="x", padx=theme.PAD, pady=(0, 12))
        self.cards = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.cards.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, theme.PAD))

    def on_show(self):
        """Work the recommendations out again from the stored scan and ping results."""
        run_async(services.recommendations, on_done=self._show, on_error=self._show_error)

    def _mark_known(self, ip):
        run_async(services.mark_known, ip, on_done=self._show, on_error=self._show_error)

    def _show(self, recs):
        for card in self.cards.winfo_children():
            card.destroy()
        for rec in recs:
            is_new_device = rec.category == "Access control" and self.app.is_admin   # only an Admin may mark it known
            RecommendationCard(self.cards, rec, self._mark_known if is_new_device else None).pack(fill="x", pady=4)
        counts = [sum(r.severity == severity for r in recs) for severity in ("critical", "warning", "info")]
        self.status.configure(text="{} critical  ·  {} warnings  ·  {} info.  "
                                   "Run Refresh all in Statistics for up-to-date results.".format(*counts),
                              text_color=theme.RED if counts[0] else theme.AMBER if counts[1] else theme.MUTED)

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
