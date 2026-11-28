"""Modal sign-in and first-run administrator setup."""
import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.worker import run_async

WIDTH = 352


def clear(*entries):
    """Clear populated entries without resetting their CustomTkinter placeholders."""
    for entry in entries:
        if entry.get():
            entry.delete(0, "end")


class LoginView(ctk.CTkToplevel):
    def __init__(self, parent, title, description, submit, on_success, on_cancel, admin_only=False):
        super().__init__(parent, fg_color=theme.SURFACE)
        self.withdraw()
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", self._cancel)
        self.on_success, self.on_cancel = on_success, on_cancel
        self.admin_only = admin_only
        self.setup = self.busy = False
        self.lock_job = None
        self.submit_text = submit

        card = ctk.CTkFrame(self, fg_color="transparent")
        card.pack(padx=24, pady=24)
        theme.icon_badge(card, "lock", 44, theme.LIME_SOFT, theme.INK, 22).pack(anchor="w")
        self.heading = ctk.CTkLabel(card, text=title, font=theme.TITLE_FONT, anchor="w")
        self.heading.pack(fill="x", pady=(12, 2))
        self.description = ctk.CTkLabel(card, text=description or (
            "Scanning, port checks, watch mode and accounts need an administrator. "
            "Everything else works without signing in."), text_color=theme.TEXT_2,
            anchor="w", justify="left", wraplength=WIDTH)
        self.description.pack(fill="x", pady=(0, 12))
        self.username = self._field(card, "Username")
        self.password = self._field(card, "Password", password=True, reveal=True)
        self.confirm_row = ctk.CTkFrame(card, fg_color="transparent")
        self.confirm = self._field(self.confirm_row, "Confirm password", password=True)

        self.error = ctk.CTkLabel(card, text="", text_color=theme.RED, anchor="w",
                                  justify="left", wraplength=WIDTH)
        self.hint = ctk.CTkLabel(card, text="", text_color=theme.MUTED, anchor="w", wraplength=WIDTH)
        self.hint.pack(fill="x")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", pady=(12, 0))
        self.cancel = theme.ActionButton(actions, width=170, height=44, corner_radius=22,
                                    text="Cancel", command=self._cancel)
        self.cancel.pack(side="left")
        self.button = theme.ActionButton(actions, width=170, height=44, corner_radius=22,
                                    text="Checking account…", state="disabled", command=self.submit,
                                    image=theme.icon("radar" if submit == "Sign in and scan" else "log-in",
                                                     theme.SURFACE), **theme.PRIMARY)
        self.button.pack(side="right")
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.grab_set()
        self.after_idle(self.username.focus_set)
        run_async(services.needs_setup, on_done=self._set_mode, on_error=self.show_error)

    def _field(self, parent, label, password=False, reveal=False):
        ctk.CTkLabel(parent, text=label, font=theme.CAPTION_FONT, anchor="w").pack(fill="x")
        row = ctk.CTkFrame(parent, fg_color=theme.SURFACE, corner_radius=12,
                           border_width=1, border_color=theme.BORDER_CONTROL)
        row.pack(fill="x", pady=(2, 10))
        entry = ctk.CTkEntry(row, width=WIDTH - (36 if reveal else 12), height=34,
                             border_width=0, show="•" if password else "")
        entry.pack(side="left", fill="x", expand=True, padx=(6, 0 if reveal else 6), pady=(3, 3))
        entry.bind("<Return>", lambda _: self.submit())
        entry.bind("<FocusIn>", lambda _: row.configure(border_color=theme.INK, border_width=2), add="+")
        entry.bind("<FocusOut>", lambda _: row.configure(border_color=theme.BORDER_CONTROL, border_width=1), add="+")
        if reveal:
            theme.ActionButton(row, text="", image=theme.icon("eye", theme.TEXT_2, 16), width=28, height=28,
                               command=self._toggle_password, **theme.GHOST).pack(side="right", padx=4)
            entry.bind("<Control-r>", lambda _: self._toggle_password())
        return entry

    def _toggle_password(self):
        self.password.configure(show="" if self.password.cget("show") else "•")

    def _set_mode(self, setup):
        if not self.winfo_exists():
            return
        self.setup = setup
        if setup:
            self.heading.configure(text="Create an administrator")
            self.description.configure(text="Set up the first account to unlock administrator actions.")
            self.confirm_row.pack(before=self.hint, fill="x")
            self.submit_text = "Create account"
        else:
            self.hint.configure(text=f"After {config.LOGIN_MAX_FAILURES} wrong passwords, sign-in pauses "
                                     f"for {config.LOGIN_LOCK_S} seconds.")
        self._sync_lock()

    def _sync_lock(self):
        wait = 0 if self.setup else services.login_lock_seconds()
        self.button.configure(text=f"Try again in {wait} s" if wait else self.submit_text,
                              state="disabled" if wait else "normal")
        self.lock_job = self.after(250, self._sync_lock) if wait else None

    def submit(self):
        """Send credentials once and wait for the account check on the worker."""
        if self.button.cget("state") == "disabled":
            return
        self.busy = True
        self.button.configure(state="disabled")
        self.cancel.configure(state="disabled")
        self.error.pack_forget()
        credentials = (self.username.get(), self.password.get())
        if self.setup:
            run_async(services.create_first_admin, *credentials, self.confirm.get(),
                      on_done=self.on_success, on_error=self.show_error)
        else:
            run_async(services.login, *credentials, self.admin_only, on_done=self.on_success, on_error=self.show_error)

    def show_error(self, error):
        """Show the account error under the fields and respect the service lockout."""
        if not self.winfo_exists():
            return
        self.busy = False
        self.error.configure(text=str(error), image=theme.icon("alert", theme.RED, 14), compound="left")
        self.error.pack(before=self.hint, fill="x")
        clear(self.password, self.confirm)
        self.password.configure(show="•")
        self.cancel.configure(state="normal")
        self._sync_lock()

    def _cancel(self, event=None):
        if not self.busy:
            self.on_cancel()

    def destroy(self):
        if self.lock_job is not None:
            self.after_cancel(self.lock_job)
        super().destroy()
