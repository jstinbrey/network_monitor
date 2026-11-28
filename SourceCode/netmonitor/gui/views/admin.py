"""Admin view: user accounts and stored history. The window builds it only for administrators."""
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from netmonitor import config, models, services
from netmonitor.gui import theme
from netmonitor.gui.views.login import clear
from netmonitor.gui.worker import run_async

ROLES = {"User": models.USER, "Admin": models.ADMIN}   # segmented-button label -> stored role
LIMITS = {"bw_down_mbps": "Download limit (Mbps)", "bw_up_mbps": "Upload limit (Mbps)", "bw_daily_gb": "Daily cap (GB)",
          "watch_min": "Watch every (minutes)"}


class AdminView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        theme.page_heading(self, "Admin", "Accounts, alert limits, and stored history")
        content = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        content.pack(fill="both", expand=True, padx=(theme.PAD, 4), pady=(0, 12))
        content.grid_columnconfigure(0, weight=5, uniform="admin")
        content.grid_columnconfigure(1, weight=3, uniform="admin")
        users = ctk.CTkFrame(content, fg_color=theme.SURFACE)
        users.grid(row=0, column=0, sticky="new", padx=(0, 16))
        account_header = ctk.CTkFrame(users, fg_color="transparent")
        account_header.pack(fill="x", padx=20, pady=(16, 8))
        theme.ActionButton(account_header, text="Add account", width=118, height=36, corner_radius=18,
                           image=theme.icon("plus", size=14), command=self._show_form).pack(side="right", padx=(8, 0))
        ctk.CTkLabel(account_header, text="Accounts", font=theme.CARD_FONT, anchor="w").pack(fill="x")
        theme.WrappedLabel(users, text="Administrators manage the network. Users and guests can view and test it.",
                           text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(fill="x", padx=20, pady=(0, 10))
        listing = ctk.CTkFrame(users, fg_color="transparent")
        listing.pack(fill="x", padx=20)
        self.table = ttk.Treeview(listing, columns=("username", "role"), show="headings", selectmode="browse", height=4)
        for key, title in (("username", "Username"), ("role", "Role")):
            self.table.heading(key, text=title, anchor="w")
            self.table.column(key, width=130, anchor="w")
        scrollbar = ctk.CTkScrollbar(listing, height=1, command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="x", expand=True)
        bar = ctk.CTkFrame(users, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(8, 4))
        self.account_menu = tk.Menu(self, tearoff=False)
        theme.ActionButton(bar, text="Account actions", width=130, height=32, corner_radius=16,
                           image=theme.icon("more", size=14), command=self._account_actions).pack(side="left")
        self.table.bind("<Shift-F10>", self._account_actions)
        self.table.bind("<Menu>", self._account_actions)
        self.table.bind("<Button-3>", self._account_actions)

        self.form = form = ctk.CTkFrame(users, fg_color=theme.SUBTLE, corner_radius=12)
        self.form.pack(fill="x", padx=20, pady=(4, 12))
        self.form_title = ctk.CTkLabel(form, text="New account", font=theme.CARD_FONT, anchor="w")
        self.form_title.pack(fill="x", padx=12, pady=(8, 4))
        fields = ctk.CTkFrame(form, fg_color="transparent")
        fields.pack(fill="x", padx=12, pady=(0, 8))
        self.username = ctk.CTkEntry(fields, width=95, height=36)
        self.password = ctk.CTkEntry(fields, width=95, height=36, show="•")
        self.confirm = ctk.CTkEntry(fields, width=95, height=36, show="•")
        for column, (label, widget) in enumerate(zip(("Username", "Password", "Confirm password"),
                                                      (self.username, self.password, self.confirm))):
            fields.grid_columnconfigure(column, weight=1, uniform="account")
            ctk.CTkLabel(fields, text=label, font=theme.CAPTION_FONT, text_color=theme.MUTED).grid(
                row=0, column=column, sticky="w", padx=(0, 4))
            widget.grid(row=1, column=column, sticky="ew", padx=(0, 6 if column < 2 else 0))
        self.role = theme.SegmentedButton(form, values=list(ROLES))
        self.role.set("User")
        self.role.pack(anchor="w", padx=12, pady=(0, 8))
        form_actions = ctk.CTkFrame(form, fg_color="transparent")
        form_actions.pack(fill="x", padx=12, pady=(2, 10))
        self.account_submit = theme.ActionButton(form_actions, text="Create account", height=38, corner_radius=19,
                                                  command=self.add_user, **theme.PRIMARY)
        self.account_submit.pack(side="right")
        theme.ActionButton(form_actions, text="Cancel", width=70, height=38, corner_radius=19,
                           command=self._clear_form).pack(side="right", padx=(0, 8))
        self.status = theme.WrappedLabel(users, text="", text_color=theme.MUTED, font=theme.CAPTION_FONT)
        self.status.pack(fill="x", padx=20, pady=(0, 8))

        side = ctk.CTkFrame(content, fg_color="transparent")
        side.grid(row=0, column=1, sticky="new")
        settings = ctk.CTkFrame(side, fg_color=theme.SURFACE)
        settings.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(settings, text="Alerts and watch mode", font=theme.CARD_FONT).pack(anchor="w", padx=20, pady=(16, 0))
        theme.WrappedLabel(settings, text=f"0 means no limit. A rate above its limit for {config.BW_SUSTAIN_S} s "
                                          "raises an alert.", text_color=theme.MUTED, font=theme.CAPTION_FONT).pack(
            fill="x", padx=20, pady=(2, 6))
        form = ctk.CTkFrame(settings, fg_color="transparent")
        form.pack(fill="x", padx=20)
        form.grid_columnconfigure(0, weight=1)
        self.limits, self.defaults = {}, {}
        self.saving = False
        for row, (key, label) in enumerate(LIMITS.items()):
            theme.WrappedLabel(form, text=label, font=theme.CAPTION_FONT).grid(
                row=row, column=0, sticky="ew", padx=(0, 6), pady=3)
            self.limits[key] = tk.StringVar()
            entry = ctk.CTkEntry(form, width=60, height=36, textvariable=self.limits[key], justify="right")
            entry.grid(row=row, column=1, pady=3)
        self.save_button = theme.ActionButton(settings, text="Save settings", height=38, corner_radius=19,
                                              state="disabled", command=self.save_limits, **theme.PRIMARY)
        self.save_button.pack(anchor="w", padx=20, pady=(8, 0))
        for variable in self.limits.values():
            variable.trace_add("write", self._settings_changed)
        self.limits_status = theme.WrappedLabel(settings, text="", font=theme.CAPTION_FONT)
        self.limits_status.pack(fill="x", padx=20, pady=(2, 6))

        history = ctk.CTkFrame(side, fg_color=theme.SURFACE)
        history.pack(fill="x")
        ctk.CTkLabel(history, text="Stored history", font=theme.CARD_FONT).pack(anchor="w", padx=20, pady=(16, 0))
        theme.WrappedLabel(history, text="Clear saved devices, ping results, and alerts for the current network. "
                           "Accounts and other networks stay.", text_color=theme.MUTED,
                           font=theme.CAPTION_FONT).pack(fill="x", padx=20, pady=(2, 8))
        theme.ActionButton(history, text="Clear history…", height=38, corner_radius=19,
                           image=theme.icon("trash", theme.RED, 14), command=self.clear_history,
                           **theme.DANGER).pack(anchor="w", padx=20)
        self.settings_status = theme.WrappedLabel(history, text="", font=theme.CAPTION_FONT)
        self.settings_status.pack(fill="x", padx=20, pady=(2, 6))

    def _show_form(self, reset=False):
        self.form_title.configure(text="Reset password for selected account" if reset else "New account")
        self.account_submit.configure(text="Reset password" if reset else "Create account",
                                      command=self.reset_password if reset else self.add_user)
        (self.password if reset else self.username).focus_set()

    def _clear_form(self):
        clear(self.username, self.password, self.confirm)
        self._show_form()

    def _account_actions(self, event=None):
        if event and event.num == 3 and (row := self.table.identify_row(event.y)):
            self.table.selection_set(row)
            self.table.focus(row)
        if not self._selected():
            return "break"
        self.account_menu.configure(background=theme.color(theme.SURFACE), foreground=theme.color(theme.TEXT))
        self.account_menu.delete(0, "end")
        self.account_menu.add_command(label="Reset password…", command=lambda: self._show_form(reset=True))
        self.account_menu.add_command(label="Apply selected role", command=self.set_role)
        self.account_menu.add_separator()
        self.account_menu.add_command(label="Delete account…", command=self.delete_user)
        x = event.x_root if event and event.num == 3 else self.table.winfo_rootx() + 12
        y = event.y_root if event and event.num == 3 else self.table.winfo_rooty() + 32
        try:
            self.account_menu.tk_popup(x, y)
        finally:
            self.account_menu.grab_release()
        return "break"

    def on_show(self):
        run_async(services.users, on_done=self._show_users, on_error=self._show_error)
        run_async(services.settings, on_done=self._show_limits)

    def _show_limits(self, values):
        self.defaults = {key: f"{values[key]:g}" for key in self.limits}
        for key, variable in self.limits.items():
            variable.set(self.defaults[key])
        self._settings_changed()

    def _settings_changed(self, *_args):
        current = {key: variable.get() for key, variable in self.limits.items()}
        self.save_button.configure(state="normal" if self.defaults and not self.saving and
                                   current != self.defaults else "disabled")

    def save_limits(self):
        if self.save_button.cget("state") == "disabled":
            return
        self.saving = True
        self._settings_changed()
        def saved(values):
            self.saving = False
            self._show_limits(values)
            self.limits_status.configure(text="Settings saved.", text_color=theme.GREEN)
        def failed(error):
            self.saving = False
            self._settings_changed()
            self.limits_status.configure(text=str(error), text_color=theme.RED)
        run_async(services.save_settings, {key: variable.get() for key, variable in self.limits.items()},
                  on_done=saved, on_error=failed)

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
