"""The diagnosis card at the top of the Dashboard: where a problem is, the evidence, and what to do.

It is a live instrument, so it sits on dark chart paper (DESIGN.md: The Live-on-Paper Rule).
"""
import customtkinter as ctk

from netmonitor.gui import theme

STEPS = ["Adapter", "Wi-Fi", "Router", "Internet", "DNS"]      # the order services.diagnose tests them in
MARKS = {True: ("✓", theme.LIME), False: ("✗", theme.PAPER_BAD), None: ("–", theme.PAPER_MUTED)}
HEADLINE_COLORS = {"good": theme.PAPER_TEXT, "warn": theme.PAPER_WARN, "bad": theme.PAPER_BAD}   # readable on paper


class VerdictCard(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.PAPER, border_width=1, border_color=theme.BORDER_STRONG)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=20, pady=16)
        self.headline = ctk.CTkLabel(body, text="Press Diagnose network to find where a problem is.",
                                     font=theme.TITLE_FONT, anchor="w", text_color=theme.PAPER_TEXT)
        self.headline.pack(fill="x")
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=6)
        self.steps = {}
        for name in STEPS:
            self.steps[name] = ctk.CTkLabel(row, text=f"–  {name}", text_color=theme.PAPER_MUTED, font=theme.BODY_FONT)
            self.steps[name].pack(side="left", padx=(0, 20))
        self.details = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=780, text_color=theme.PAPER_MUTED)
        self.details.pack(fill="x")

    def start(self):
        self.headline.configure(text="Diagnosing... (10 to 20 seconds)", text_color=theme.PAPER_MUTED)
        for name, label in self.steps.items():
            label.configure(text=f"…  {name}", text_color=theme.PAPER_MUTED)
        self.details.configure(text="")

    def add_step(self, step):
        """One layer tested: ✓ it answered, ✗ it did not."""
        mark, color = MARKS[step.ok]
        self.steps[step.name].configure(text=f"{mark}  {step.name}: {step.detail}", text_color=color)

    def show(self, verdict):
        self.headline.configure(text=verdict.headline, text_color=HEADLINE_COLORS[verdict.status])
        for name, label in self.steps.items():
            if label.cget("text").startswith("…"):  # a layer below failed, so this one was not tested
                label.configure(text=f"–  {name}: not tested")
        self.details.configure(text="  ·  ".join(verdict.evidence) +
                                    f"\nRecommended: {verdict.action}   (OSI layer {verdict.layer})")

    def show_error(self, error):
        self.headline.configure(text=str(error), text_color=theme.PAPER_BAD)
