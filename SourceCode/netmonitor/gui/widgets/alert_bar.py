"""The alert bar: the newest alert in a coloured strip above the view, until it is dismissed."""
import customtkinter as ctk

from netmonitor.gui.widgets.recommendation_card import SEVERITY_COLORS

TEXT_COLORS = {"critical": "#111111", "warning": "#111111", "info": "white"}   # readable on each background


class AlertBar(ctk.CTkFrame):
    def __init__(self, parent, on_view, on_dismiss):
        """on_view(ip) opens a device panel; on_dismiss(event_id) marks the event as seen."""
        super().__init__(parent, corner_radius=0)
        self.event, self.on_dismiss = None, on_dismiss
        self.dismiss_button = ctk.CTkButton(self, text="Dismiss", width=80, fg_color="transparent", border_width=1,
                                            command=self.dismiss)
        self.dismiss_button.pack(side="right", padx=(0, 12), pady=6)
        self.view_button = ctk.CTkButton(self, text="View", width=70, command=lambda: on_view(self.event.ip))
        self.text = ctk.CTkLabel(self, text="", anchor="w", font=("Segoe UI", 13, "bold"))
        self.text.pack(side="left", fill="x", expand=True, padx=12)

    def show(self, event):
        """Show one event; a newer alert replaces the one shown. View appears only for an event about a device."""
        self.event = event
        color = TEXT_COLORS[event.severity]
        self.configure(fg_color=SEVERITY_COLORS[event.severity])
        self.text.configure(text=f"{event.at[11:16]}   {event.detail}", text_color=color)
        self.dismiss_button.configure(text_color=color, border_color=color)
        self.view_button.pack_forget()
        if event.ip:
            self.view_button.pack(side="right", padx=(0, 8), before=self.text)
        self.grid()

    def dismiss(self):
        self.grid_remove()
        self.on_dismiss(self.event.id)
