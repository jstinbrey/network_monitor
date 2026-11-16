"""Reports view (Feature 4): generate a summary report and open earlier ones."""
import os
from datetime import datetime

import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.worker import run_async


class ReportsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="Reports", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))
        ctk.CTkLabel(self, anchor="w", text_color=theme.MUTED,
                     text="A report contains the date and time, the devices detected, the latest ping results, "
                          "the network performance summary, and the security recommendations.").pack(fill="x", padx=theme.PAD)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=12)
        self.format = ctk.CTkSegmentedButton(bar, values=["HTML", "CSV"])
        self.format.set("HTML")
        self.format.pack(side="left")
        self.generate_button = ctk.CTkButton(bar, text="Generate report", command=self.generate)
        self.generate_button.pack(side="left", padx=12)
        self.status = ctk.CTkLabel(bar, text="", text_color=theme.MUTED)
        self.status.pack(side="left")
        ctk.CTkButton(bar, text="Open folder", command=lambda: self._open(config.OUTPUT_DIR)).pack(side="right")

        self.list = ctk.CTkScrollableFrame(self, label_text="Generated reports (click one to open it)")
        self.list.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, theme.PAD))

    def on_show(self):
        run_async(services.reports, on_done=self._show_reports, on_error=self._show_error)

    def generate(self):
        self.generate_button.configure(state="disabled")
        self.status.configure(text="Generating...", text_color=theme.MUTED)
        run_async(services.generate_report, self.format.get().lower(),
                  on_done=self._generated, on_error=self._show_error)

    def _generated(self, path):
        self.status.configure(text=f"Saved {path.name}", text_color=theme.GREEN)
        self.generate_button.configure(state="normal")
        self.on_show()
        self._open(path)

    def _show_reports(self, paths):
        for row in self.list.winfo_children():
            row.destroy()
        if not paths:
            ctk.CTkLabel(self.list, text="No reports yet. Click Generate report.", text_color=theme.MUTED).pack(pady=20)
        for path in paths:
            created = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d  %H:%M:%S")
            ctk.CTkButton(self.list, anchor="w", fg_color="transparent", hover_color=theme.BLUE,
                          text=f"{created}      {path.suffix[1:].upper():<6}{path.name}",
                          command=lambda p=path: self._open(p)).pack(fill="x", pady=1)

    def _open(self, path):
        """Open a report (or the reports folder) with the default Windows program."""
        try:
            config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except OSError:
            self._show_error(f"Could not open {path.name}; it may have been moved or deleted.")
            self.on_show()

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)
        self.generate_button.configure(state="normal")