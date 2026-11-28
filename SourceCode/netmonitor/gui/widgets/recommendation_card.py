"""Recommendation cards with severity, evidence and the action the user can take."""
import customtkinter as ctk

from netmonitor.gui import theme

SEVERITY_COLORS = {"critical": theme.RED, "warning": theme.AMBER, "info": theme.BLUE}
SEVERITY_SOFT = {"critical": theme.RED_SOFT, "warning": theme.AMBER_SOFT, "info": theme.BLUE_SOFT}
SEVERITY_ICONS = {"critical": "shield-alert", "warning": "alert", "info": "info"}
CATEGORY_ICONS = {"Access control": "user", "Open ports": "alert"}


def chip(parent, text, severity):
    """A severity pill with its label and matching tint."""
    return ctk.CTkLabel(parent, text=text, padx=8, fg_color=SEVERITY_SOFT[severity],
                        text_color=SEVERITY_COLORS[severity], corner_radius=12,
                        height=22, font=theme.CAPTION_FONT)


def badge(parent, rec, size=40):
    """Use the finding's severity and category to pick its icon badge."""
    icon = CATEGORY_ICONS.get(rec.category, SEVERITY_ICONS[rec.severity])
    return theme.icon_badge(parent, icon, size, SEVERITY_SOFT[rec.severity],
                            SEVERITY_COLORS[rec.severity], 18 if size == 40 else 14)


class RecommendationCard(ctk.CTkFrame):
    def __init__(self, parent, rec, on_mark_known=None, on_open=None, locked=False):
        super().__init__(parent)
        badge(self, rec).pack(side="left", anchor="n", padx=(20, 16), pady=16)
        if rec.host and (on_mark_known or on_open):
            actions = ctk.CTkFrame(self, fg_color="transparent")
            actions.pack(side="right", anchor="n", padx=(12, 20), pady=16)
            if on_mark_known:
                command = lambda: on_mark_known(rec.host)
                button = (theme.locked_button(actions, "Mark as known", command, width=150) if locked else
                          theme.ActionButton(actions, text="Mark as known", command=command, width=150, height=40,
                                        corner_radius=20, image=theme.icon("check", theme.SURFACE), **theme.PRIMARY))
                button.pack(fill="x", pady=(0, 8))
            if on_open:
                theme.ActionButton(actions, text="Open device", width=140, height=40, corner_radius=20,
                              image=theme.icon("arrow-up-right", size=16),
                              command=lambda: on_open(rec.host)).pack(fill="x")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, pady=16, padx=(0, 12))
        title = ctk.CTkLabel(body, text=rec.title, anchor="w", justify="left", font=theme.CARD_FONT)
        title.pack(fill="x")
        meta = ctk.CTkFrame(body, fg_color="transparent")
        meta.pack(fill="x", pady=(3, 4))
        chip(meta, rec.severity.capitalize(), rec.severity).pack(side="left")
        context = f"{rec.category} · {rec.host}" if rec.host else rec.category
        ctk.CTkLabel(meta, text=context, text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(side="left", padx=8)
        detail = ctk.CTkLabel(body, text=rec.detail, anchor="w", justify="left", text_color=theme.TEXT_2)
        detail.pack(fill="x")
        labels = [title, detail]
        if rec.action:
            action = ctk.CTkLabel(body, text=rec.action, anchor="w", justify="left", image=theme.icon("arrow-right", size=14),
                                  compound="left")
            action.pack(fill="x", pady=(4, 0))
            labels.append(action)

        def wrap(event):
            width = event.width / ctk.ScalingTracker.get_widget_scaling(body)
            for label in labels:
                label.configure(wraplength=max(120, int(width - 24)))

        for label in labels:
            label.configure(wraplength=330)
        body.bind("<Configure>", wrap)
