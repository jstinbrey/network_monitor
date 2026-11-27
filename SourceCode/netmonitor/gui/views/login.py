"""Sign-in screen. On the first run it creates the administrator account instead."""
import customtkinter as ctk

from netmonitor import config, services
from netmonitor.gui import theme
from netmonitor.gui.worker import run_async

WIDTH = 280


def clear(*entries):
    """Empty entries. An empty one is skipped: deleting its placeholder makes CustomTkinter forget show="•"."""
    for entry in entries:
        if entry.get():
            entry.delete(0, "end")


class LoginView(ctk.CTkFrame):
    def __init__(self, parent, on_success, on_cancel):
        """on_success(user) is called on the UI thread once someone has signed in; on_cancel() on Back."""
        super().__init__(parent, fg_color="transparent")
        self.on_success = on_success
        self.setup = False              # True on the first run: the form creates the administrator

        card = ctk.CTkFrame(self)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text=config.APP_TITLE, font=theme.TITLE_FONT).pack(padx=40, pady=(28, 0))
        self.heading = ctk.CTkLabel(card, text="", text_color=theme.MUTED, wraplength=WIDTH)
        self.heading.pack(padx=40, pady=(0, 8))
        self.username = ctk.CTkEntry(card, width=WIDTH, placeholder_text="Username")
        self.password = ctk.CTkEntry(card, width=WIDTH, placeholder_text="Password", show="•")
        self.confirm = ctk.CTkEntry(card, width=WIDTH, placeholder_text="Confirm password", show="•")
        for entry in (self.username, self.password, self.confirm):
            entry.pack(padx=40, pady=(8, 0))
            entry.bind("<Return>", lambda event: self.submit())
        self.button = ctk.CTkButton(card, width=WIDTH, text="Please wait...", state="disabled", command=self.submit, height=40, **theme.PRIMARY)
        self.button.pack(padx=40, pady=(16, 0))
        ctk.CTkButton(card, width=WIDTH, text="Back", height=40,
                      command=on_cancel).pack(padx=40, pady=(8, 0))
        self.error = ctk.CTkLabel(card, text="", text_color=theme.RED, wraplength=WIDTH)
        self.error.pack(padx=40, pady=(8, 20))
        self.reset()

    def reset(self):
        """Empty the form, then ask services whether any account exists yet."""
        clear(self.username, self.password, self.confirm)
        self.error.configure(text="")
        self.button.configure(state="disabled")
        run_async(services.needs_setup, on_done=self._set_mode, on_error=self._failed)

    def _set_mode(self, setup):
        self.setup = setup
        if setup:
            self.heading.configure(text="First run: create the administrator account.")
            self.confirm.pack(after=self.password, padx=40, pady=(8, 0))
            self.button.configure(text="Create account")
        else:
            self.heading.configure(text="Sign in to continue.")
            self.confirm.pack_forget()
            self.button.configure(text="Sign in")
        self.button.configure(state="normal")
        self.username.focus_set()

    def submit(self):
        if self.button.cget("state") == "disabled":     # Enter pressed while a sign-in is already running
            return
        self.button.configure(state="disabled")
        self.error.configure(text="")
        # Hashing takes about 0.2 s, so sign-in runs off the UI thread like every other service call.
        if self.setup:
            run_async(services.create_first_admin, self.username.get(), self.password.get(), self.confirm.get(),
                      on_done=self._signed_in, on_error=self._failed)
        else:
            run_async(services.login, self.username.get(), self.password.get(),
                      on_done=self._signed_in, on_error=self._failed)

    def _signed_in(self, user):
        self.button.configure(state="normal")
        self.on_success(user)

    def _failed(self, error):
        self.error.configure(text=str(error))
        clear(self.password, self.confirm)
        self.button.configure(state="normal")