"""Shared GUI behavior for keyboard focus and appearance changes."""
import tkinter as tk

import customtkinter as ctk
import pytest

from netmonitor.gui.theme import ActionButton, appearance_callback


@pytest.fixture(scope="module")
def root():
    root = tk.Tk()
    try:
        yield root
    finally:
        root.destroy()


def test_action_button_only_participates_in_tab_order_when_available(root):
    view = ctk.CTkFrame(root)
    view.pack()
    button = ActionButton(view, text="Open report")
    button.pack()
    root.update()
    assert root.tk_focusNext() is button

    button.configure(state="disabled")
    assert root.tk_focusNext() is not button

    button.configure(state="normal")
    view.pack_forget()
    root.update_idletasks()
    assert root.tk_focusNext() is not button
    view.destroy()


def test_root_appearance_callback_survives_destruction_of_a_child(root):
    original_mode = ctk.get_appearance_mode()
    updates = []
    try:
        appearance_callback(root, updates.append)
        tk.Frame(root).destroy()
        next_mode = "Dark" if original_mode == "Light" else "Light"
        ctk.set_appearance_mode(next_mode)
        assert updates == [next_mode]
    finally:
        ctk.set_appearance_mode(original_mode)
