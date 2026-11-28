"""Dashboard diagnosis and the health score, using live steps and current findings."""
import tkinter as tk

import customtkinter as ctk

from netmonitor.gui import theme

STEPS = ("This PC", "Router", "Internet", "DNS")
HEADLINE_COLORS = {"good": theme.PAPER_TEXT, "warn": theme.PAPER_WARN, "bad": theme.PAPER_BAD}
CRITICAL_SCORE_CAP = 59


class VerdictCard(ctk.CTkFrame):
    def __init__(self, parent, open_security):
        super().__init__(parent, fg_color=theme.PAPER, border_width=1, border_color=theme.BORDER_STRONG)
        self.findings = (0, 0)
        self.verdict = None
        self.running = False
        self.error = ""

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(16, 10))
        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.pack(side="right", anchor="n", padx=(16, 0))
        theme.ActionButton(actions, text="Open Security", width=144, height=32, corner_radius=16,
                      image=theme.icon("arrow-up-right", size=14), command=open_security).pack(anchor="e")
        self.health = ctk.CTkLabel(actions, text="Health · No data", fg_color=theme.PAPER_GRID,
                                   text_color=theme.PAPER_TEXT, corner_radius=12, height=22,
                                   font=theme.CAPTION_FONT, padx=8)
        self.health.pack(anchor="e", pady=(8, 0))
        body = ctk.CTkFrame(top, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True)
        self.headline = ctk.CTkLabel(body, text="", font=theme.TITLE_FONT, text_color=theme.PAPER_TEXT,
                                     anchor="w", justify="left")
        self.headline.pack(fill="x")
        self.details = ctk.CTkLabel(body, text="", anchor="w", justify="left", text_color=theme.PAPER_MUTED)
        self.details.pack(fill="x")
        body.bind("<Configure>", self._wrap)

        chain = ctk.CTkFrame(self, fg_color="transparent")
        chain.pack(fill="x", padx=24, pady=(0, 16))
        self.steps, self.links = {}, {}
        for i, name in enumerate(STEPS):
            column = i * 2
            circle = ctk.CTkFrame(chain, width=28, height=28, corner_radius=14)
            circle.grid(row=0, column=column, sticky="w")
            mark = ctk.CTkLabel(circle, text="–", width=0, height=0)
            mark.place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(chain, text=name, anchor="w", text_color=theme.PAPER_TEXT,
                         font=theme.BODY_FONT).grid(row=1, column=column, sticky="w", pady=(4, 0))
            detail = ctk.CTkLabel(chain, text="", width=100, wraplength=100, anchor="w", justify="left",
                                  text_color=theme.PAPER_MUTED, font=theme.MONO_FONT)
            detail.grid(row=2, column=column, sticky="w")
            self.steps[name] = mark, detail
            if i < len(STEPS) - 1:
                chain.grid_columnconfigure(column + 1, weight=1)
                line = tk.Frame(chain, bg=theme.PAPER_GRID, height=2)
                line.grid(row=0, column=column + 1, sticky="ew", padx=(0, 8))
                self.links[name] = line
            self._step(name, None, "Not tested")
        self._render()

    def _wrap(self, event):
        logical_width = event.width / ctk.ScalingTracker.get_widget_scaling(self)
        for label in (self.headline, self.details):
            label.configure(wraplength=max(160, int(logical_width - 4)))

    def set_summary(self, score, critical, warnings):
        """Cap displayed health when a critical finding needs attention."""
        self.findings = critical, warnings
        text, background, color = "Health · No data", theme.PAPER_GRID, theme.PAPER_TEXT
        if score is not None:
            text = f"Health {min(score, CRITICAL_SCORE_CAP) if critical else score} / 100"
            if critical:
                background, color = theme.RED_SOFT, theme.RED
        self.health.configure(text=text, fg_color=background, text_color=color)
        self._render()

    def start(self):
        """Reset the visible steps before running a new diagnosis."""
        self.running, self.verdict, self.error = True, None, ""
        for name in STEPS:
            self._step(name, None, "Not tested")
        self._render()

    def _step(self, name, ok, detail):
        mark, label = self.steps[name]
        if ok is None:
            mark.master.configure(fg_color=theme.PAPER_GRID)
            mark.configure(text="–", image=None, text_color=theme.PAPER_MUTED)
        else:
            background = theme.LIME if ok else theme.RED[0]
            foreground = theme.ON_LIME if ok else theme.PAPER_TEXT
            mark.master.configure(fg_color=background)
            mark.configure(text="", image=theme.icon("check" if ok else "x", foreground, 15))
        label.configure(text=detail)
        if name in self.links:
            self.links[name].configure(bg=theme.LIME if ok else theme.PAPER_GRID)

    def add_step(self, step):
        """Show each measurement when the diagnosis worker reports it."""
        if step.name != "Wi-Fi":
            name = "This PC" if step.name == "Adapter" else step.name
            detail = step.detail.rsplit(", ", 1)[-1] if name == "This PC" else step.detail
            self._step(name, step.ok, detail)

    def show(self, verdict):
        """Show what the diagnosis found and the recommended action."""
        self.running, self.verdict = False, verdict
        self._render()

    def show_error(self, error):
        """Report a failure to run the diagnosis."""
        self.running, self.error = False, str(error)
        self._render()

    def _render(self):
        critical, warnings = self.findings
        headline, color = "Check your network", theme.PAPER_TEXT
        detail = "Run Diagnose network to test this PC, the router, internet access and DNS."
        if self.running:
            headline, detail = "Diagnosing network…", "Checking each connection in order."
        elif self.error:
            headline, color, detail = "Diagnosis could not finish", theme.PAPER_BAD, self.error
        elif self.verdict:
            headline, color = self.verdict.headline, HEADLINE_COLORS[self.verdict.status]
            detail = " · ".join(self.verdict.evidence) + f"\n{self.verdict.action} (OSI layer {self.verdict.layer})"
        if (critical or warnings) and not self.running and not self.error and (
                critical or not self.verdict or self.verdict.status == "good"):
            if critical:
                headline = "1 critical finding" if critical == 1 else f"{critical} critical findings"
            else:
                headline = "1 warning needs attention" if warnings == 1 else f"{warnings} warnings need attention"
            color = theme.PAPER_TEXT
            detail = f"Review the findings in Security. {detail}"
        self.headline.configure(text=headline, text_color=color)
        self.details.configure(text=detail)
