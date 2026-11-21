"""Admin view: user accounts and stored history. The window builds it only for administrators."""
from tkinter import messagebox, ttk

import customtkinter as ctk

from netmonitor import config, models, services
from netmonitor.gui import theme
from netmonitor.gui.views.login import clear
from netmonitor.gui.worker import run_async

ROLES = {"User": models.USER, "Admin": models.ADMIN}   # segmented-button label -> stored role
FORM_WIDTH = 260
LIMITS = {"bw_down_mbps": "Download limit (Mbps)", "bw_up_mbps": "Upload limit (Mbps)", "bw_daily_gb": "Daily cap (GB)"}


class AdminView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(self, text="Admin", font=theme.TITLE_FONT).pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 8))
        tabs = ctk.CTkTabview(self, anchor="nw")
        tabs.pack(fill="both", expand=True, padx=theme.PAD, pady=(0, theme.PAD))

        # --- Users tab: the accounts on the left, the form and actions on the right.
        users = tabs.add("Users")
        form = ctk.CTkFrame(users, fg_color="transparent", width=FORM_WIDTH)
        form.pack(side="right", fill="y", padx=(12, 0))
        self.table = ttk.Treeview(users, columns=("username", "role"), show="headings", selectmode="browse")
        for key, title in (("username", "Username"), ("role", "Role")):
            self.table.heading(key, text=title, anchor="w")
        self.table.pack(side="left", fill="both", expand=True)

        self.username = ctk.CTkEntry(form, width=FORM_WIDTH, placeholder_text="Username (for Add user)")
        self.password = ctk.CTkEntry(form, width=FORM_WIDTH, placeholder_text="Password", show="•")
        self.confirm = ctk.CTkEntry(form, width=FORM_WIDTH, placeholder_text="Confirm password", show="•")
        self.role = ctk.CTkSegmentedButton(form, values=list(ROLES))
        self.role.set("User")
        for widget in (self.username, self.password, self.confirm, self.role):
            widget.pack(fill="x", pady=(0, 8))
        for text, command in (("Add user", self.add_user), ("Reset password of selected", self.reset_password),
                              ("Set role of selected", self.set_role)):
            ctk.CTkButton(form, text=text, command=command).pack(fill="x", pady=(0, 8))
        ctk.CTkButton(form, text="Delete selected", fg_color=theme.RED, hover_color="#b52b27",
                      command=self.delete_user).pack(fill="x", pady=(0, 8))
        self.status = ctk.CTkLabel(form, text="", wraplength=FORM_WIDTH, justify="left", anchor="w")
        self.status.pack(fill="x")

        # --- Settings tab. The watch interval (Step 7.6) is added here later.
        settings = tabs.add("Settings")
        ctk.CTkLabel(settings, text="Bandwidth limits", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(settings, text_color=theme.MUTED, justify="left", anchor="w",
                     text=f"0 means no limit. A rate above its limit for {config.BW_SUSTAIN_S} s raises an alert, "
                          "and so do 80% and 100% of the daily cap.").pack(anchor="w", pady=(2, 8))
        form = ctk.CTkFrame(settings, fg_color="transparent")
        form.pack(anchor="w")
        self.limits = {}
        for row, (key, label) in enumerate(LIMITS.items()):
            ctk.CTkLabel(form, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
            self.limits[key] = ctk.CTkEntry(form, width=100)
            self.limits[key].grid(row=row, column=1, pady=3)
        ctk.CTkButton(settings, text="Save limits", command=self.save_limits).pack(anchor="w", pady=(8, 0))
        self.limits_status = ctk.CTkLabel(settings, text="", anchor="w")
        self.limits_status.pack(anchor="w", pady=(4, 16))

        ctk.CTkLabel(settings, text="Clear history for this network", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(settings, text_color=theme.MUTED, justify="left", anchor="w",
                     text="Deletes the devices, ping results and alerts stored for the network this PC is on now.\n"
                          "Accounts and the history of other networks are kept.").pack(anchor="w", pady=(2, 8))
        ctk.CTkButton(settings, text="Clear history", fg_color=theme.RED, hover_color="#b52b27",
                      command=self.clear_history).pack(anchor="w")
        self.settings_status = ctk.CTkLabel(settings, text="", anchor="w")
        self.settings_status.pack(anchor="w", pady=8)

    def on_show(self):
        run_async(services.users, on_done=self._show_users, on_error=self._show_error)
        run_async(services.settings, on_done=self._show_limits)

    def _show_limits(self, values):
        for key, entry in self.limits.items():
            entry.delete(0, "end")
            entry.insert(0, f"{values[key]:g}")

    def save_limits(self):
        def saved(values):
            self._show_limits(values)
            self.limits_status.configure(text="Limits saved.", text_color=theme.GREEN)
        run_async(services.save_settings, {key: entry.get() for key, entry in self.limits.items()}, on_done=saved,
                  on_error=lambda error: self.limits_status.configure(text=str(error), text_color=theme.RED))

    def _show_users(self, users):
        self.table.delete(*self.table.get_children())
        for user in users:
            self.table.insert("", "end", iid=user.username,
                              values=(user.username, "Administrator" if user.is_admin else "User"))

    def _selected(self):
        """The username selected in the table, or None (after saying so)."""
        if self.table.selection():
            return self.table.selection()[0]
        self._show_error("Select a user in the table first.")
        return None

    def _change(self, fn, *args, done):
        """Run one account change in the background, then reload the table and report the result."""
        def finished(_):
            clear(self.username, self.password, self.confirm)
            self.status.configure(text=done, text_color=theme.GREEN)
            self.on_show()
        run_async(fn, *args, on_done=finished, on_error=self._show_error)

    def add_user(self):
        name = self.username.get().strip().lower()
        self._change(services.add_user, name, self.password.get(), self.confirm.get(), ROLES[self.role.get()],
                     done=f"Added {name} as {self.role.get()}.")

    def reset_password(self):
        name = self._selected()
        if name:
            self._change(services.reset_password, name, self.password.get(), self.confirm.get(),
                         done=f"Password of {name} changed.")

    def set_role(self):
        name = self._selected()
        if name:
            self._change(services.set_role, name, ROLES[self.role.get()], done=f"{name} is now {self.role.get()}.")

    def delete_user(self):
        name = self._selected()
        if name and messagebox.askyesno("Delete user", f"Delete the account {name}?", parent=self):
            self._change(services.delete_user, name, done=f"Deleted {name}.")

    def clear_history(self):
        if messagebox.askyesno("Clear history", "Delete every device, ping result and alert stored for this "
                                                "network? This cannot be undone.", parent=self):
            self.settings_status.configure(text="Clearing...", text_color=theme.MUTED)
            run_async(services.clear_history,
                      on_done=lambda network: self.settings_status.configure(text=f"Cleared {network}.",
                                                                             text_color=theme.GREEN),
                      on_error=lambda error: self.settings_status.configure(text=str(error), text_color=theme.RED))

    def _show_error(self, error):
        self.status.configure(text=str(error), text_color=theme.RED)