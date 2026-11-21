"""The diagnosis card at the top of the Dashboard: where a problem is, the evidence, and what to do."""
import customtkinter as ctk

from netmonitor.gui import theme

STEPS = ["Adapter", "Router", "Internet", "DNS"]               # the order services.diagnose tests them in
MARKS = {True: ("✓", theme.GREEN), False: ("✗", theme.RED), None: ("–", theme.MUTED)}


class VerdictCard(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.strip = ctk.CTkFrame(self, width=6, height=1, corner_radius=0, fg_color=theme.MUTED)   # fill="y" sets its height
        self.strip.pack(side="left", fill="y")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        self.headline = ctk.CTkLabel(body, text="Press Diagnose network to find where a problem is.",
                                     font=("Segoe UI", 18, "bold"), anchor="w")
        self.headline.pack(fill="x")
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=4)
        self.steps = {}
        for name in STEPS:
            self.steps[name] = ctk.CTkLabel(row, text=f"–  {name}", text_color=theme.MUTED)
            self.steps[name].pack(side="left", padx=(0, 28))
        self.details = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=780, text_color=theme.MUTED)
        self.details.pack(fill="x")

    def start(self):
        self.strip.configure(fg_color=theme.MUTED)
        self.headline.configure(text="Diagnosing... (10 to 20 seconds)", text_color=theme.MUTED)
        for name, label in self.steps.items():
            label.configure(text=f"…  {name}", text_color=theme.MUTED)
        self.details.configure(text="")

    def add_step(self, step):
        """One layer tested: ✓ it answered, ✗ it did not."""
        mark, color = MARKS[step.ok]
        self.steps[step.name].configure(text=f"{mark}  {step.name}: {step.detail}", text_color=color)

    def show(self, verdict):
        color = theme.TAG_COLORS[verdict.status]
        self.strip.configure(fg_color=color)
        self.headline.configure(text=verdict.headline, text_color=color)
        for name, label in self.steps.items():
            if label.cget("text").startswith("…"):  # a layer below failed, so this one was not tested
                label.configure(text=f"–  {name}: not tested")
        self.details.configure(text="  ·  ".join(verdict.evidence) +
                                    f"\nRecommended: {verdict.action}   (OSI layer {verdict.layer})")

    def show_error(self, error):
        self.strip.configure(fg_color=theme.RED)
        self.headline.configure(text=str(error), text_color=theme.RED)
