"""Colours, fonts, icons and table styling shared by every view.

The values come from DESIGN.md ("The Network Check-up"): a light grey canvas, white cards, one dark
"ink" primary action, Signal Lime for live and selected things, and status colours that always sit
next to a word. CustomTkinter widgets get their defaults from theme.json; matplotlib charts, the
ttk tables and the map canvas cannot read that file, so they use the plain hex values below.
"""
import functools
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import customtkinter as ctk
import matplotlib
from matplotlib import font_manager
from PIL import Image

RESOURCES = Path(__file__).resolve().parent.parent / "resources"
THEME_FILE = RESOURCES / "theme.json"   # under resources/, so the release build bundles it

# --- Colours (light mode; DESIGN.md frontmatter) ------------------------------------------------
CANVAS, SURFACE, SUBTLE = "#F1F2EE", "#FFFFFF", "#F6F7F3"          # window, cards, tiles and table headers
INK, INK_HOVER = "#16191B", "#2D3337"                              # primary buttons, active nav item
BORDER, BORDER_STRONG, BORDER_CONTROL = "#E3E5DF", "#CBD0C7", "#828881"
TEXT, TEXT_2, MUTED = "#16191B", "#555B62", "#676D75"              # MUTED is the lightest text colour used
LIME, LIME_SOFT = "#C8F05A", "#EEF9CF"                             # live and selected, never a status
GREEN, AMBER, RED, BLUE = "#1A7A46", "#9B5E0A", "#BB3636", "#2B5FCC"
GREEN_SOFT, AMBER_SOFT, RED_SOFT, BLUE_SOFT = "#E1F3E8", "#FCEFD8", "#FBE4E2", "#E3EBFA"
# Chart paper: live instruments (heart monitor, bandwidth, diagnosis) stay dark in both modes.
PAPER, PAPER_GRID, PAPER_TEXT, PAPER_MUTED = "#16191B", "#2A3034", "#FFFFFF", "#A3A9AE"
PAPER_WARN, PAPER_BAD, PAPER_SERIES_2 = "#F0B455", "#F28585", "#86AAF7"   # readable on PAPER

TAG_COLORS = {"good": GREEN, "warn": AMBER, "bad": RED}   # row and status text colours
STATUS_TAGS = {"online": "good", "degraded": "warn", "no-icmp": "warn", "offline": "bad"}
PAD = 16

# --- Buttons: the theme makes every button secondary; one per screen gets PRIMARY ------------------
PRIMARY = dict(fg_color=INK, hover_color=INK_HOVER, text_color=SURFACE, border_width=0)
DANGER = dict(fg_color=SURFACE, hover_color=RED_SOFT, text_color=RED, border_color=RED, border_width=1)
GHOST = dict(fg_color="transparent", hover_color=SUBTLE, text_color=TEXT, border_width=0)


class ActionButton(ctk.CTkButton):
    """A button that participates in Tk's keyboard focus and activation."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # The CustomTkinter button is a Tk frame with its mouse targets inside it.
        tk.Frame.configure(self, takefocus=lambda _: int(self.cget("state") != "disabled"))
        tk.Frame.bind(self, "<Return>", self._activate)
        tk.Frame.bind(self, "<space>", self._activate)
        tk.Frame.bind(self, "<FocusIn>", self._focus_in)
        tk.Frame.bind(self, "<FocusOut>", self._focus_out)

    def _activate(self, event):
        self.invoke()
        return "break"

    def _focus_in(self, event):
        self._resting_border = self.cget("border_width"), self.cget("border_color")
        self.configure(border_width=2, border_color=SURFACE if self.cget("fg_color") == INK else INK)

    def _focus_out(self, event):
        if hasattr(self, "_resting_border"):
            width, color = self._resting_border
            self.configure(border_width=width, border_color=color)
            del self._resting_border


def locked_button(parent, text, command, **kwargs):
    """A clickable admin action for guests, distinct from a disabled control."""
    return ActionButton(parent, text=text, command=command, image=icon("lock", MUTED), compound="left",
                        height=40, corner_radius=20, fg_color=SUBTLE, hover_color=BORDER,
                        border_color=BORDER, text_color=MUTED, font=BODY_FONT, **kwargs)


def icon_badge(parent, name, size, background, foreground, icon_size):
    """Center an icon in a fixed-size circle."""
    badge = ctk.CTkFrame(parent, width=size, height=size, corner_radius=size // 2, fg_color=background)
    ctk.CTkLabel(badge, text="", image=icon(name, foreground, icon_size)).place(relx=0.5, rely=0.5, anchor="center")
    return badge

# --- Fonts: setup() swaps in Segoe UI / Consolas if the bundled or system fonts are missing ---------
SANS, SANS_MEDIUM, SANS_SEMIBOLD, MONO = "Plus Jakarta Sans", "Plus Jakarta Sans Medium", "Plus Jakarta Sans SemiBold", "Cascadia Mono"
TITLE_FONT = (SANS_SEMIBOLD, 24)      # page titles
CARD_FONT = (SANS_SEMIBOLD, 15)       # card and section titles
STAT_FONT = (SANS_SEMIBOLD, 24)       # big numbers in tiles
BODY_FONT = (SANS_MEDIUM, 13)         # emphasised body text
CAPTION_FONT = (SANS_MEDIUM, 12)      # group labels, metadata
MONO_FONT = (MONO, 12)                # IPs, MACs, times, ping output


def load():
    """Before the window exists: register the bundled fonts and load theme.json. Light mode for now."""
    for path in sorted((RESOURCES / "fonts").glob("*.ttf")):
        ctk.FontManager.load_font(str(path))       # Windows: private to this process
        font_manager.fontManager.addfont(str(path))   # so matplotlib can use it too
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme(str(THEME_FILE))


def setup(root):
    """Once the window exists: fall back to Windows fonts where needed, then style tables and charts."""
    global SANS, SANS_MEDIUM, SANS_SEMIBOLD, MONO, TITLE_FONT, CARD_FONT, STAT_FONT, BODY_FONT, CAPTION_FONT, MONO_FONT
    have = lambda family: tkfont.Font(root=root, family=family, size=12).actual("family") == family
    if not have(SANS):                              # the font files were deleted or could not load
        SANS = SANS_MEDIUM = SANS_SEMIBOLD = "Segoe UI"
    if not have(MONO):
        MONO = "Consolas"
    ctk.ThemeManager.theme["CTkFont"]["family"] = SANS   # load_theme already picked this platform's entry
    TITLE_FONT, CARD_FONT, STAT_FONT = (SANS_SEMIBOLD, 24), (SANS_SEMIBOLD, 15), (SANS_SEMIBOLD, 24)
    BODY_FONT, CAPTION_FONT, MONO_FONT = (SANS_MEDIUM, 13), (SANS_MEDIUM, 12), (MONO, 12)
    matplotlib.rcParams["font.family"] = [SANS, "DejaVu Sans"]
    style_tables()


def style_tables():
    """ttk.Treeview is not a CustomTkinter widget, so it is styled here to match the cards it sits in."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, rowheight=34,
                    borderwidth=0, font=(SANS, 10), bordercolor=SURFACE, lightcolor=SURFACE, darkcolor=SURFACE)
    style.configure("Treeview.Heading", background=SUBTLE, foreground=MUTED, relief="flat",
                    font=(SANS_MEDIUM, 9), padding=(6, 6), bordercolor=SUBTLE, lightcolor=SUBTLE, darkcolor=SUBTLE)
    style.map("Treeview", background=[("selected", LIME_SOFT)], foreground=[("selected", TEXT)])
    style.map("Treeview.Heading", background=[("active", BORDER)])


@functools.lru_cache(maxsize=None)
def icon(name, color=TEXT, size=18):
    """A Lucide icon from resources/icons in any colour. The PNGs hold only the shape (alpha), drawn at 3x."""
    shape = Image.open(RESOURCES / "icons" / f"{name}.png").getchannel("A")
    image = Image.new("RGBA", shape.size, color)
    image.putalpha(shape)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
