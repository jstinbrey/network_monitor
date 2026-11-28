"""Colours, fonts, icons and table styling shared by every view.

The values come from DESIGN.md and its light and dark palettes. CustomTkinter accepts paired colors.
Tk and matplotlib resolve the same pairs for the current appearance.
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

CANVAS, SURFACE, SUBTLE = ("#F1F2EE", "#0F1113"), ("#FFFFFF", "#181B1E"), ("#F6F7F3", "#22262A")
INK, INK_HOVER = ("#16191B", "#ECEDE8"), ("#2D3337", "#D6D9D1")
BORDER, BORDER_STRONG, BORDER_CONTROL = ("#E3E5DF", "#2C3136"), ("#CBD0C7", "#3B4147"), ("#828881", "#7A828A")
TEXT, TEXT_2, MUTED = ("#16191B", "#ECEDE8"), ("#555B62", "#B3B8BE"), ("#676D75", "#9198A0")
ON_INK, LIME_ON_INK = ("#FFFFFF", "#16191B"), ("#C8F05A", "#44600F")
LIME, ON_LIME, LIME_SOFT = "#C8F05A", "#16191B", ("#EEF9CF", "#2A3314")
GREEN, AMBER, RED, BLUE = ("#1A7A46", "#5FCF8E"), ("#9B5E0A", "#F0B455"), ("#BB3636", "#F28585"), ("#2B5FCC", "#86AAF7")
GREEN_SOFT, AMBER_SOFT = ("#E1F3E8", "#11301F"), ("#FCEFD8", "#372914")
RED_SOFT, BLUE_SOFT = ("#FBE4E2", "#3A1A1A"), ("#E3EBFA", "#172440")
# Chart paper: live instruments (heart monitor, bandwidth, diagnosis) stay dark in both modes.
PAPER, PAPER_GRID, PAPER_TEXT, PAPER_MUTED = "#16191B", "#2A3034", "#FFFFFF", "#A3A9AE"
PAPER_WARN, PAPER_BAD, PAPER_SERIES_2 = "#F0B455", "#F28585", "#86AAF7"   # readable on PAPER

TAG_COLORS = {"good": GREEN, "warn": AMBER, "bad": RED}   # row and status text colours
STATUS_TAGS = {"online": "good", "degraded": "warn", "no-icmp": "warn", "offline": "bad"}
PAD = 16

# --- Buttons: the theme makes every button secondary; one per screen gets PRIMARY ------------------
PRIMARY = dict(fg_color=INK, hover_color=INK_HOVER, text_color=ON_INK, border_width=0)
DANGER = dict(fg_color=SURFACE, hover_color=RED_SOFT, text_color=RED, border_color=RED, border_width=1)
GHOST = dict(fg_color="transparent", hover_color=SUBTLE, text_color=TEXT, border_width=0)


def color(token):
    """Resolve a paired token for native Tk widgets and matplotlib."""
    return token[ctk.get_appearance_mode() == "Dark"] if isinstance(token, tuple) else token


def appearance_callback(widget, callback):
    """Refresh native drawing when the theme changes and unsubscribe on destroy."""
    def unsubscribe(event):
        if event.widget is widget:
            ctk.AppearanceModeTracker.remove(callback)

    ctk.AppearanceModeTracker.add(callback, widget)
    tk.Misc.bind(widget, "<Destroy>", unsubscribe, add="+")


class ActionButton(ctk.CTkButton):
    """A button that participates in Tk's keyboard focus and activation."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # The CustomTkinter button is a Tk frame with its mouse targets inside it.
        tk.Frame.configure(self, takefocus=lambda _: int(self.winfo_viewable() and self.cget("state") != "disabled"))
        tk.Frame.bind(self, "<Return>", self._activate)
        tk.Frame.bind(self, "<space>", self._activate)
        tk.Frame.bind(self, "<FocusIn>", self._focus_in)
        tk.Frame.bind(self, "<FocusOut>", self._focus_out)

    def _activate(self, event):
        self.invoke()
        return "break"

    def _focus_in(self, event):
        self._resting_border = self.cget("border_width"), self.cget("border_color")
        self.configure(border_width=2, border_color=ON_INK if self.cget("fg_color") == INK else INK)
        parent = self.master
        while parent and not isinstance(parent, ctk.CTkScrollableFrame):
            parent = parent.master
        if parent:
            canvas = parent._parent_canvas
            top = self.winfo_rooty() - canvas.winfo_rooty()
            bottom = top + self.winfo_height() - canvas.winfo_height()
            delta = top if top < 0 else max(0, bottom)
            region = canvas.bbox("all")
            if delta and region:
                canvas.yview_moveto(canvas.yview()[0] + delta / max(1, region[3] - region[1]))

    def _focus_out(self, event):
        if hasattr(self, "_resting_border"):
            width, color = self._resting_border
            self.configure(border_width=width, border_color=color)
            del self._resting_border


def _keyboard_control(widget, keys):
    """A single tab stop and a focus outline for a composite control."""
    tk.Frame.configure(widget, takefocus=lambda _: int(widget.winfo_viewable() and widget.cget("state") != "disabled"))
    for key, action in keys.items():
        def activate(event, action=action):
            if widget.cget("state") != "disabled":
                action()
            return "break"
        tk.Frame.bind(widget, key, activate)
    tk.Frame.bind(widget, "<FocusIn>", lambda _: tk.Frame.configure(
        widget, highlightthickness=2, highlightcolor=color(INK), highlightbackground=color(INK)))
    tk.Frame.bind(widget, "<FocusOut>", lambda _: tk.Frame.configure(widget, highlightthickness=0))


def _keyboard_segments(widget):
    def change(step):
        values = widget.cget("values")
        if values:
            current = widget.get()
            index = values.index(current) if current in values else -1
            widget.set(values[(index + step) % len(values)], from_button_callback=True)
    _keyboard_control(widget, {"<Left>": lambda: change(-1), "<Right>": lambda: change(1)})


class SegmentedButton(ctk.CTkSegmentedButton):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        _keyboard_segments(self)


class Switch(ctk.CTkSwitch):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        _keyboard_control(self, {"<space>": self.toggle, "<Return>": self.toggle})


class ComboBox(ctk.CTkComboBox):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.bind("<Alt-Down>", self._show_choices)

    def _show_choices(self, event):
        if self.cget("state") != "disabled":
            self._open_dropdown_menu()
        return "break"


class WrappedLabel(ctk.CTkLabel):
    """A label whose text wraps to the space its layout actually provides."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, anchor="w", justify="left", wraplength=300, **kwargs)
        tk.Misc.bind(self, "<Configure>", self._wrap, add="+")

    def _wrap(self, event):
        width = max(40, int(event.width / ctk.ScalingTracker.get_widget_scaling(self)) - 4)
        if self.cget("wraplength") != width:
            self.configure(wraplength=width)


def page_heading(parent, title, subtitle):
    """Lay out a page title and subtitle with its primary actions at the right."""
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.pack(fill="x", padx=PAD, pady=(12, 12))
    actions = ctk.CTkFrame(header, width=1, height=1, fg_color="transparent")
    actions.pack(side="right", anchor="n", padx=(8, 0))
    ctk.CTkLabel(header, text=title, font=TITLE_FONT, anchor="w").pack(fill="x")
    caption = WrappedLabel(header, text=subtitle, text_color=MUTED)
    caption.pack(fill="x")
    return actions, caption


def tooltip(widget, title):
    """Label an icon when it receives pointer hover or keyboard focus."""
    job = tip = None

    def hide(event=None):
        nonlocal job, tip
        if job:
            widget.after_cancel(job)
            job = None
        if tip:
            tip.destroy()
            tip = None

    def show():
        nonlocal job, tip
        job = None
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height() + 4}")
        tk.Label(tip, text=title, font=CAPTION_FONT, background=color(INK), foreground=color(ON_INK),
                 padx=8, pady=4).pack()

    def schedule(event=None):
        nonlocal job
        hide()
        job = widget.after(450, show)

    widget.bind("<Enter>", schedule, add="+")
    widget.bind("<Leave>", hide, add="+")
    tk.Misc.bind(widget, "<FocusIn>", schedule, add="+")
    tk.Misc.bind(widget, "<FocusOut>", hide, add="+")
    tk.Misc.bind(widget, "<Destroy>", hide, add="+")


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


def device_icon(device):
    """Choose a bundled icon from the device role or its advertised name."""
    if device.is_gateway:
        return "router"
    if device.is_self:
        return "laptop"
    name = (device.alias or device.hostname).lower()
    for icon_name, words in (
        ("printer", ("printer", "laserjet", "deskjet")),
        ("phone", ("phone", "galaxy", "pixel")),
        ("tablet", ("ipad", "tablet")),
        ("tv", ("tv", "television")),
        ("server", ("nas", "server")),
        ("laptop", ("laptop", "notebook", "macbook")),
    ):
        if any(word in name for word in words):
            return icon_name
    return "devices"

# --- Fonts: setup() swaps in Segoe UI / Consolas if the bundled or system fonts are missing ---------
SANS, SANS_MEDIUM, SANS_SEMIBOLD, MONO = "Plus Jakarta Sans", "Plus Jakarta Sans Medium", "Plus Jakarta Sans SemiBold", "Cascadia Mono"
TITLE_FONT = (SANS_SEMIBOLD, 24)      # page titles
CARD_FONT = (SANS_SEMIBOLD, 15)       # card and section titles
STAT_FONT = (SANS_SEMIBOLD, 24)       # big numbers in tiles
BODY_FONT = (SANS_MEDIUM, 13)         # emphasised body text
CAPTION_FONT = (SANS_MEDIUM, 12)      # group labels, metadata
MONO_FONT = (MONO, 12)                # IPs, MACs, times, ping output


def load():
    """Register bundled fonts and follow the Windows app appearance preference."""
    for path in sorted((RESOURCES / "fonts").glob("*.ttf")):
        ctk.FontManager.load_font(str(path))       # Windows: private to this process
        font_manager.fontManager.addfont(str(path))   # so matplotlib can use it too
    ctk.set_appearance_mode("system")
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
    style_tables(root)
    appearance_callback(root, lambda _: style_tables(root))


def style_tables(root):
    """ttk.Treeview is not a CustomTkinter widget, so it is styled here to match the cards it sits in."""
    style = ttk.Style(root)
    style.theme_use("clam")
    surface, subtle = color(SURFACE), color(SUBTLE)
    style.configure("Treeview", background=surface, fieldbackground=surface, foreground=color(TEXT), rowheight=34,
                    borderwidth=0, font=(SANS, 10), bordercolor=surface, lightcolor=surface, darkcolor=surface)
    style.configure("Treeview.Heading", background=subtle, foreground=color(MUTED), relief="flat",
                    font=(SANS_MEDIUM, 9), padding=(6, 6), bordercolor=subtle, lightcolor=subtle, darkcolor=subtle)
    style.map("Treeview", background=[("selected", color(LIME_SOFT))], foreground=[("selected", color(TEXT))])
    style.map("Treeview.Heading", background=[("active", color(BORDER))])


@functools.lru_cache(maxsize=None)
def icon(name, color=TEXT, size=18):
    """A Lucide icon from resources/icons in any colour. The PNGs hold only the shape (alpha), drawn at 3x."""
    shape = Image.open(RESOURCES / "icons" / f"{name}.png").getchannel("A")
    def tinted(value):
        image = Image.new("RGBA", shape.size, value)
        image.putalpha(shape)
        return image
    light, dark = color if isinstance(color, tuple) else (color, color)
    light_image = tinted(light)
    return ctk.CTkImage(light_image=light_image, dark_image=tinted(dark) if light != dark else light_image,
                        size=(size, size))
