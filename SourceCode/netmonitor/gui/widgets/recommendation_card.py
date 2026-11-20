"""One recommendation shown as a card with a coloured severity strip on its left edge."""
import customtkinter as ctk

from netmonitor.gui import theme

SEVERITY_COLORS = {"critical": theme.RED, "warning": theme.AMBER, "info": theme.BLUE}
WRAP = 780   # pixels; the window's minimum width leaves this much room for text


class RecommendationCard(ctk.CTkFrame):
    def __init__(self, parent, rec, on_mark_known=None, on_open=None):
        """on_mark_known, on_open: when given and the card is about a device, it gets a button for each,
        which calls the function with the device's IP."""
        super().__init__(parent)
        ctk.CTkFrame(self, width=4, corner_radius=0, fg_color=SEVERITY_COLORS[rec.severity]).pack(side="left", fill="y")
        if on_open and rec.host:
            ctk.CTkButton(self, text="Open device", width=110,
                          command=lambda: on_open(rec.host)).pack(side="right", padx=(0, 12))
        if on_mark_known:
            ctk.CTkButton(self, text="Mark as known", width=120,
                          command=lambda: on_mark_known(rec.host)).pack(side="right", padx=12)
        for text, style in [(rec.title, {"font": ("Segoe UI", 14, "bold")}),
                            (f"{rec.severity.capitalize()}  ·  {rec.category}", {"text_color": theme.MUTED}),
                            (rec.detail, {}),
                            (f"Recommended: {rec.action}", {})]:
            if text:
                ctk.CTkLabel(self, text=text, anchor="w", justify="left", wraplength=WRAP, **style).pack(
                    fill="x", padx=12, pady=(6 if text is rec.title else 0, 0))
        ctk.CTkFrame(self, height=8, fg_color="transparent").pack()   # bottom padding
