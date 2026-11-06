"""Focus layout: quiet surfaces, readable Thai, and a purple accent."""

from tkinter import font, ttk

BG = "#fafaff"
PANEL = "#f4f4fa"
WHITE = "#ffffff"
INK = "#292c40"
MUTED = "#73788f"
ACCENT = "#6354d9"
SOFT = "#edeaff"
LINE = "#e3e4ef"
ERROR = "#a63548"
GREEN = "#29755c"


def apply_theme(root):
    family = "Thonburi" if "Thonburi" in font.families(root) else "TkDefaultFont"
    if family == "TkDefaultFont":
        family = font.nametofont("TkDefaultFont").actual("family")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        font.nametofont(name).configure(family=family, size=12)
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(family, 12), background=BG, foreground=INK)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Card.TFrame", background=WHITE)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Error.TLabel", foreground=ERROR)
    style.configure("Success.TLabel", foreground=GREEN)
    style.configure("Title.TLabel", font=(family, 24, "bold"))
    style.configure("Heading.TLabel", font=(family, 16, "bold"))
    style.configure("Panel.TLabel", background=PANEL)
    style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
    style.configure("TButton", padding=(12, 8), borderwidth=0, background=SOFT, foreground=ACCENT)
    style.map("TButton", background=[("active", "#e0dbff"), ("disabled", "#ececf2")],
              foreground=[("disabled", "#9596a8")])
    style.configure("Accent.TButton", background=ACCENT, foreground=WHITE)
    style.map("Accent.TButton", background=[("active", "#5141c3"), ("disabled", "#cbc6ed")],
              foreground=[("disabled", WHITE)])
    style.configure("TEntry", padding=8, fieldbackground=WHITE, bordercolor=LINE)
    style.configure("TLabelframe", background=BG, bordercolor=LINE)
    style.configure("TLabelframe.Label", background=BG, foreground=MUTED)
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                    borderwidth=0, rowheight=48, font=(family, 11))
    style.map("Treeview", background=[("selected", SOFT)], foreground=[("selected", ACCENT)])
    return family
