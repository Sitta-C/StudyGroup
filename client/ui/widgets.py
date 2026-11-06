"""Small native Canvas controls matching the prototype's rounded surfaces."""

import math
import tkinter as tk
from tkinter import font

from client.ui import theme


def rounded_rect(canvas, x1, y1, x2, y2, radius=8, *, fill, outline="", corners=None, **kwargs):
    radii = corners or (radius,) * 4
    points = []
    for cx, cy, start, r in (
        (x1 + radii[0], y1 + radii[0], 180, radii[0]),
        (x2 - radii[1], y1 + radii[1], 270, radii[1]),
        (x2 - radii[2], y2 - radii[2], 0, radii[2]),
        (x1 + radii[3], y2 - radii[3], 90, radii[3]),
    ):
        for step in range(9):
            angle = math.radians(start + step * 90 / 8)
            points.extend((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return canvas.create_polygon(*points, fill=fill, outline=outline, width=1, smooth=True, splinesteps=36, **kwargs)


def icon(canvas, name, x, y, *, size=17, color=theme.INK, width=1.4, tags=()):
    """Lucide-style line glyphs, drawn natively without bitmap dependencies."""
    scale = size / 24
    def line(*coords):
        return canvas.create_line(*[v * scale + (x if i % 2 == 0 else y) for i, v in enumerate(coords)],
                                  fill=color, width=width, capstyle="round", joinstyle="round", tags=tags)
    def oval(a, b, c, d):
        return canvas.create_oval(x + a * scale, y + b * scale, x + c * scale, y + d * scale,
                                  outline=color, width=width, tags=tags)
    if name == "plus":
        line(12, 5, 12, 19); line(5, 12, 19, 12)
    elif name == "hash":
        line(10, 3, 8, 21); line(17, 3, 15, 21); line(4, 9, 21, 9); line(3, 15, 20, 15)
    elif name == "layers":
        line(12, 3, 22, 8, 12, 13, 2, 8, 12, 3)
        line(2, 12, 12, 17, 22, 12); line(2, 16, 12, 21, 22, 16)
    elif name == "users":
        oval(5, 3, 13, 11); line(2, 21, 2, 18, 4, 15, 14, 15, 16, 18, 16, 21)
        line(16, 4, 19, 6, 19, 9, 17, 11); line(19, 15, 22, 17, 22, 21)
    elif name == "search":
        oval(3, 3, 17, 17); line(16, 16, 22, 22)
    elif name == "sparkles":
        line(12, 3, 14.5, 9.5, 21, 12, 14.5, 14.5, 12, 21, 9.5, 14.5, 3, 12, 9.5, 9.5, 12, 3)
        line(20, 1, 20, 7); line(17, 4, 23, 4); line(3, 18, 3, 22); line(1, 20, 5, 20)
    elif name == "paperclip":
        line(21, 11, 12, 20, 8, 22, 4, 20, 2, 16, 4, 12, 13, 3, 16, 2, 19, 4, 19, 7, 10, 16, 8, 16, 7, 14, 15, 6)
    elif name == "arrow-up":
        line(12, 20, 12, 4); line(6, 10, 12, 4, 18, 10)
    elif name == "chevron":
        line(9, 5, 16, 12, 9, 19)
    elif name == "settings":
        line(3, 6, 8, 6); line(13, 6, 21, 6); oval(8, 3.5, 13, 8.5)
        line(3, 17, 13, 17); line(18, 17, 21, 17); oval(13, 14.5, 18, 19.5)
    elif name == "compass":
        oval(2, 2, 22, 22); line(16, 8, 13, 13, 8, 16, 11, 11, 16, 8)
    elif name == "lock":
        line(7, 10, 7, 6, 9, 3, 15, 3, 17, 6, 17, 10)
        rounded_rect(canvas, x + 4 * scale, y + 10 * scale, x + 20 * scale, y + 22 * scale,
                     2 * scale, fill="", outline=color, tags=tags)
        line(12, 15, 12, 18)
    elif name == "message":
        line(4, 3, 20, 3, 22, 5, 22, 17, 20, 19, 8, 19, 2, 23, 2, 5, 4, 3)
    elif name == "refresh":
        line(20, 10, 18, 5, 13, 3, 7, 4, 3, 9)
        line(3, 4, 3, 9, 8, 9); line(4, 14, 6, 19, 11, 21, 17, 20, 21, 15)
        line(16, 15, 21, 15, 21, 20)
    elif name == "close":
        line(6, 6, 18, 18); line(18, 6, 6, 18)


def initials(name):
    return name[:2].upper()


def avatar(canvas, name, x, y, *, size=31, own=False, online=False, background=theme.PANEL):
    rounded_rect(canvas, x, y, x + size, y + size, min(10, size / 3),
                 fill=theme.SOFT if own else theme.AVATAR)
    canvas.create_text(x + size / 2, y + size / 2, text=initials(name),
                       font=theme.text_font(canvas, 10 if size < 30 else 11, "bold"),
                       fill=theme.ACCENT if own else theme.INK)
    if online:
        canvas.create_oval(x + size - 6, y + size - 6, x + size + 1, y + size + 1,
                          fill=theme.GREEN, outline=background, width=2)


def ellipsis(widget, value, width, size=12):
    metrics = font.Font(widget, font=theme.text_font(widget, size))
    if metrics.measure(value) <= width:
        return value
    while value and metrics.measure(value + "…") > width:
        value = value[:-1]
    return value + "…"


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self.job = self.window = None
        widget.bind("<Enter>", self.enter, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def enter(self, _event=None):
        if self.text:
            self.job = self.widget.after(650, self.show)

    def show(self):
        self.job = None
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry(f'+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty() + self.widget.winfo_height() + 5}')
        tk.Label(self.window, text=self.text, bg=theme.INK, fg=theme.WHITE,
                 padx=9, pady=5, font=theme.text_font(self.widget, 11), wraplength=320).pack()

    def hide(self, _event=None):
        if self.job is not None:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.window is not None:
            self.window.destroy()
            self.window = None


class ActionButton(tk.Canvas):
    """Rounded button with focus/keyboard support and real disabled semantics."""
    def __init__(self, parent, *, text="", command=None, width=100, height=35, kind="soft",
                 glyph=None, size=12, radius=8, background=theme.WHITE, tooltip="", align="center"):
        super().__init__(parent, width=width, height=height, background=background,
                         highlightthickness=0, borderwidth=0, takefocus=True, cursor="hand2")
        self.text, self.command, self.kind = text, command, kind
        self.glyph, self.size, self.radius, self.align = glyph, size, radius, align
        self._state, self.hover, self.focused = "normal", False, False
        self.bind("<Configure>", self.draw)
        self.bind("<Enter>", lambda event: self._hover(True))
        self.bind("<Leave>", lambda event: self._hover(False))
        self.bind("<FocusIn>", lambda event: self._focus(True))
        self.bind("<FocusOut>", lambda event: self._focus(False))
        self.bind("<Button-1>", lambda event: self.invoke())
        self.bind("<Return>", self._key)
        self.bind("<space>", self._key)
        self.tooltip = Tooltip(self, tooltip)
        self.draw()
    def _key(self, _event):
        self.invoke()
        return "break"
    def _hover(self, active):
        self.hover = active
        self.draw()
    def _focus(self, active):
        self.focused = active
        self.draw()
    def invoke(self):
        if self._state != "disabled" and self.command:
            return self.command()
    def configure(self, cnf=None, **kwargs):
        for key in ("text", "state", "command", "kind"):
            if key in kwargs:
                setattr(self, "_state" if key == "state" else key, kwargs.pop(key))
                if key == "state":
                    kwargs["takefocus"] = self._state != "disabled"
                    kwargs["cursor"] = "arrow" if self._state == "disabled" else "hand2"
        if cnf is not None or kwargs:
            super().configure(cnf, **kwargs)
        if hasattr(self, "kind"):
            self.draw()
    config = configure
    def cget(self, key):
        if key in ("text", "state"):
            return self.text if key == "text" else self._state
        return super().cget(key)
    def draw(self, _event=None):
        self.delete("all")
        w = self.winfo_width() if self.winfo_width() > 1 else int(super().cget("width"))
        h = self.winfo_height() if self.winfo_height() > 1 else int(super().cget("height"))
        disabled = self._state == "disabled"
        color = theme.WHITE if self.kind == "primary" else theme.ACCENT if self.kind in ("soft", "link") else theme.MUTED if self.kind == "muted" else theme.INK
        fill = theme.ACCENT if self.kind == "primary" else theme.SOFT if self.kind == "soft" else self.cget("background")
        if disabled:
            color = "#9b96ca" if self.kind == "soft" else theme.MUTED
            if self.kind == "primary":
                fill, color = "#c5c0eb", theme.WHITE
        elif self.hover:
            fill = "#554bc7" if self.kind == "primary" else theme.SOFT
        rounded_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=fill,
                     outline=theme.ACCENT if self.focused and not disabled else "")
        metrics = font.Font(self, font=theme.text_font(self, self.size))
        text_width = metrics.measure(self.text)
        content = text_width + (24 if self.glyph and self.text else 17 if self.glyph else 0)
        x = 7 if self.align == "left" else (w - content) / 2
        if self.glyph:
            icon(self, self.glyph, x, (h - 17) / 2, color=color)
            x += 24 if self.text else 17
        if self.text:
            self.create_text(x, h / 2, anchor="w", text=self.text, font=theme.text_font(self, self.size), fill=color)


class RoundedPanel(tk.Canvas):
    def __init__(self, parent, *, height=96, radius=11, background=theme.CHAT,
                 fill=theme.WHITE, outline=theme.LINE, padding=12):
        super().__init__(parent, height=height, highlightthickness=0, borderwidth=0, background=background)
        self.radius, self.fill, self.outline, self.padding = radius, fill, outline, padding
        self.body = tk.Frame(self, bg=fill)
        self.window = self.create_window(padding, padding, anchor="nw", window=self.body)
        self.bind("<Configure>", self.draw)
    def draw(self, _event=None):
        self.delete("surface")
        w, h, p = self.winfo_width(), self.winfo_height(), self.padding
        rounded_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, self.radius,
                     fill=self.fill, outline=self.outline, tags="surface")
        self.tag_lower("surface")
        self.itemconfigure(self.window, width=max(1, w - p * 2), height=max(1, h - p * 2))


class ScrollArea(tk.Frame):
    """Borderless scroll region with a thin scrollbar only while it is needed."""
    def __init__(self, parent, background=theme.CHAT):
        super().__init__(parent, bg=background)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg=background, highlightthickness=0, borderwidth=0, width=100)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar = tk.Canvas(self, width=5, bg=background, highlightthickness=0, cursor="arrow")
        self.bar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self._scrollbar)
        self.bar.bind("<Button-1>", self._drag)
        self.bar.bind("<B1-Motion>", self._drag)
        self.bar.bind("<Configure>", lambda event: self._scrollbar(*self.canvas.yview()))
        self.canvas.bind("<MouseWheel>", self.wheel)
        self.canvas.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda event: self.canvas.yview_scroll(3, "units"))
        self._fraction = (0, 1)
    def _scrollbar(self, first, last):
        first, last = float(first), float(last)
        self._fraction = (first, last)
        self.bar.delete("all")
        if first <= 0 and last >= 1:
            self.bar.grid_remove()
        else:
            self.bar.grid()
            h = max(1, self.bar.winfo_height())
            rounded_rect(self.bar, 0, first * h, 4, max(first * h + 14, last * h), 2,
                         fill="#d7d9e5")
    def _drag(self, event):
        self.canvas.yview_moveto(event.y / max(1, self.bar.winfo_height()) - (self._fraction[1] - self._fraction[0]) / 2)
    def wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"
    def bind_wheel(self, widget):
        widget.bind("<MouseWheel>", self.wheel, add="+")
        for child in widget.winfo_children():
            self.bind_wheel(child)
