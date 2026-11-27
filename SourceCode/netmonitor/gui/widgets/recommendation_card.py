"""One recommendation shown as a card: title, a severity chip with its word, the detail, and the fix."""
import customtkinter as ctk

from netmonitor.gui import theme

SEVERITY_COLORS = {"critical": theme.RED, "warning": theme.AMBER, "info": theme.BLUE}
SEVERITY_SOFT = {"critical": theme.RED_SOFT, "warning": theme.AMBER_SOFT, "info": theme.BLUE_SOFT}
WRAP = 780   # pixels; the window's minimum width leaves this much room for text


def chip(parent, text, severity):
    """A small pill: the severity's colour on its pale wash, always with a word (never colour alone)."""
    return ctk.CTkLabel(parent, text=f" {text} ", fg_color=SEVERITY_SOFT[severity], text_color=SEVERITY_COLORS[severity],
                        corner_radius=10, height=22, font=theme.CAPTION_FONT)


class RecommendationCard(ctk.CTkFrame):
    def __init__(self, parent, rec, on_mark_known=None, on_open=None):
        """on_mark_known, on_open: when given and the card is about a device, it gets a button for each,
        which calls the function with the device's IP."""
        super().__init__(parent)
        if on_open and rec.host:
            ctk.CTkButton(self, text="Open device", width=110,
                          command=lambda: on_open(rec.host)).pack(side="right", padx=(0, 12))
        if on_mark_known:
            ctk.CTkButton(self, text="Mark as known", width=120, **theme.PRIMARY,
                          command=lambda: on_mark_known(rec.host)).pack(side="right", padx=12)
        ctk.CTkLabel(self, text=rec.title, anchor="w", justify="left", wraplength=WRAP, font=theme.CARD_FONT).pack(
            fill="x", padx=20, pady=(14, 4))
        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.pack(fill="x", padx=20)
        chip(meta, rec.severity.capitalize(), rec.severity).pack(side="left")
        ctk.CTkLabel(meta, text=rec.category, text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(side="left", padx=8)
        for text, color in [(rec.detail, theme.TEXT_2), (f"→  {rec.action}" if rec.action else "", theme.TEXT)]:
            if text:
                ctk.CTkLabel(self, text=text, anchor="w", justify="left", wraplength=WRAP, text_color=color).pack(
                    fill="x", padx=20, pady=(4, 0))
        ctk.CTkFrame(self, height=14, fg_color="transparent").pack()   # bottom padding
