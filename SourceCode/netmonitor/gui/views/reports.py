"""Create a report and reopen saved files from the same screen."""
from datetime import datetime
import os

import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.worker import run_async

FORMATS = {
    "HTML": ("file-html", "Web page with charts"),
    "CSV": ("file-csv", "Spreadsheet"),
    "PDF": ("reports", "Print or submit"),
}
INCLUDED = ("Date, time, and the last diagnosis", "Wi-Fi and today’s data use", "Devices and open ports",
            "Latest ping results and performance", "Security findings and recent alerts")


class ReportsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        actions, _ = theme.page_heading(self, "Reports", "Save a snapshot of the network to share or hand in.")
        theme.ActionButton(actions, text="Open folder", width=132, height=40, corner_radius=20,
                           image=theme.icon("folder", size=16),
                           command=lambda: self._open(config.OUTPUT_DIR)).pack()

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, 12))
        columns.grid_columnconfigure(0, weight=3, uniform="reports")
        columns.grid_columnconfigure(1, weight=5, uniform="reports")
        columns.grid_rowconfigure(0, weight=1)
        form = ctk.CTkFrame(columns, fg_color=theme.SURFACE)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ctk.CTkLabel(form, text="New report", font=theme.CARD_FONT).pack(anchor="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(form, text="Format", text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(anchor="w", padx=20)
        self.formats = {}
        for name, (icon, caption) in FORMATS.items():
            button = theme.ActionButton(form, text=f"{name}\n{caption}", anchor="w", height=48, corner_radius=12,
                                        image=theme.icon(icon, theme.TEXT_2, 16),
                                        command=lambda value=name: self._choose(value))
            # shortcut: CustomTkinter has no public justify option, use it once exposed.
            button._text_label.configure(justify="left")
            button.pack(fill="x", padx=20, pady=(6, 0))
            self.formats[name] = button
        self._choose("HTML")

        self.generate_button = theme.ActionButton(form, text="Generate report", height=44, corner_radius=22,
                                                   image=theme.icon("download", theme.ON_INK, 16),
                                                   command=self.generate, **theme.PRIMARY)
        self.generate_button.pack(side="bottom", fill="x", padx=20, pady=(12, 20))
        ctk.CTkLabel(form, text="Included", text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(
            anchor="w", padx=20, pady=(12, 2))
        for detail in INCLUDED:
            theme.WrappedLabel(form, text=detail, font=theme.CAPTION_FONT, text_color=theme.TEXT_2,
                               image=theme.icon("check", theme.GREEN, 12), compound="left").pack(fill="x", padx=20)

        saved = ctk.CTkFrame(columns, fg_color=theme.SURFACE)
        saved.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(saved, text="Saved reports", font=theme.CARD_FONT).pack(anchor="w", padx=20, pady=(16, 0))
        self.count = ctk.CTkLabel(saved, text="", text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.count.pack(anchor="w", padx=20)
        self.banner = ctk.CTkFrame(saved, corner_radius=12)
        self.saved_path = None
        self.open_saved = theme.ActionButton(self.banner, text="Open", width=70, height=30,
                                              image=theme.icon("external", size=14), command=self._open_latest,
                                              **theme.GHOST)
        self.open_saved.pack(side="right", padx=4)
        self.status = theme.WrappedLabel(self.banner, text="", font=theme.CAPTION_FONT)
        self.status.pack(side="left", fill="x", expand=True, padx=12, pady=4)
        self.list = ctk.CTkScrollableFrame(saved, fg_color=theme.SURFACE, corner_radius=0)
        self.list.pack(fill="both", expand=True, padx=(16, 8), pady=(4, 12))

    def _choose(self, name):
        self.format = name
        for label, button in self.formats.items():
            active = name == label
            button.configure(border_color=theme.INK if active else theme.BORDER,
                             border_width=2 if active else 1, fg_color=theme.SUBTLE if active else theme.SURFACE)

    def on_show(self):
        run_async(services.reports, on_done=self._show_reports, on_error=self._show_error)

    def generate(self):
        self.saved_path = None
        self.generate_button.configure(state="disabled")
        self._notice("Generating report…", theme.SUBTLE, theme.MUTED)
        run_async(services.generate_report, self.format.lower(), on_done=self._generated, on_error=self._show_error)

    def _notice(self, message, background, foreground):
        self.banner.configure(fg_color=background)
        self.status.configure(text=message, text_color=foreground)
        if self.saved_path:
            self.open_saved.pack(side="right", padx=4)
        else:
            self.open_saved.pack_forget()
        self.banner.pack(before=self.list._parent_frame, fill="x", padx=20, pady=6)

    def _generated(self, path):
        self.saved_path = path
        self._notice(f"Saved {path.name}", theme.GREEN_SOFT, theme.GREEN)
        self.generate_button.configure(state="normal")
        self.on_show()

    def _show_reports(self, paths):
        for row in self.list.winfo_children():
            row.destroy()
        count = 0
        for path in paths:
            try:
                file = path.stat()
            except OSError:
                continue
            count += 1
            row = ctk.CTkFrame(self.list, fg_color=theme.SUBTLE if count % 2 == 0 else theme.SURFACE, corner_radius=12)
            row.pack(fill="x", pady=(0, 2))
            fmt = path.suffix[1:].upper()
            icon = FORMATS.get(fmt, ("reports", ""))[0]
            theme.icon_badge(row, icon, 32, theme.SUBTLE, theme.TEXT_2, 16).pack(side="left", padx=(8, 10), pady=6)
            theme.ActionButton(row, text="Open", width=86, height=34, corner_radius=17,
                               image=theme.icon("external", size=14), command=lambda item=path: self._open(item)).pack(
                side="right", padx=(8, 6))
            ctk.CTkLabel(row, text=fmt, width=36, font=theme.CAPTION_FONT, text_color=theme.MUTED).pack(side="right")
            details = ctk.CTkFrame(row, fg_color="transparent")
            details.pack(side="left", fill="x", expand=True, pady=6)
            theme.WrappedLabel(details, text=path.name, font=theme.MONO_FONT, height=18).pack(fill="x")
            created = datetime.fromtimestamp(file.st_mtime).strftime("%d %b %H:%M")
            size = f"{file.st_size:,} B" if file.st_size < 1024 else f"{file.st_size / 1024:,.1f} KB"
            theme.WrappedLabel(details, text=f"{created} · {size}",
                               text_color=theme.MUTED, font=theme.CAPTION_FONT, height=18).pack(fill="x")
        self.count.configure(text=f"{count} {'file' if count == 1 else 'files'} · newest first")
        if count == 0:
            ctk.CTkLabel(self.list, text="No reports yet.", text_color=theme.MUTED).pack(anchor="w", pady=8)

    def _open_latest(self):
        if self.saved_path:
            self._open(self.saved_path)

    def _open(self, path):
        """Open a saved report or its folder in Windows."""
        try:
            config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except OSError:
            self._show_error(f"Could not open {path.name}. It may have been moved or deleted.")
            self.on_show()

    def _show_error(self, error):
        self.saved_path = None
        self._notice(str(error), theme.RED_SOFT, theme.RED)
        self.generate_button.configure(state="normal")
