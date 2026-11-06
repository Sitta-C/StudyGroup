"""Design tokens copied from the Focus prototype; sizes are CSS-like pixels."""

from tkinter import font, ttk

from client.ui.fonts import load_bundled_font

WHITE = BG = "#ffffff"
PANEL = "#f6f7fb"
CHAT = "#fcfcfe"
INK = "#272b3b"
MUTED = "#74798b"
ACCENT = "#6056d7"
OUTGOING = "#6258cf"
SOFT = "#eeecff"
AVATAR = "#e4e6f3"
LINE = "#e8eaf1"
ERROR = "#b5404c"
GREEN = "#34765e"

# Tk snapshots the platform font list when its first root is created. Register
# the private font while the GUI modules are imported, before Tk() in main.
load_bundled_font()


def text_font(widget, size=12, weight="normal"):
    # Positive Tk sizes are points (12pt was 16px on this Mac). Negative sizes
    # preserve the prototype's 10–19px hierarchy regardless of Tk scaling.
    root = widget
    while root.master is not None:
        root = root.master
    return (root.studygroup_font, -size, weight)


def apply_theme(root):
    load_bundled_font()
    available = font.families(root)
    # The exported reference's 12px message run measures 401px in Thonburi on
    # macOS. Keep that face where present; bundle the prototype's first CSS
    # fallback for machines without it rather than relying on an arbitrary UI font.
    family = next((name for name in ("Thonburi", "Noto Sans Thai", "Segoe UI") if name in available),
                  font.nametofont("TkDefaultFont").actual("family"))
    root.studygroup_font = family
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        font.nametofont(name).configure(family=family, size=-12, weight="normal")
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(family, -12), background=BG, foreground=INK)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Chat.TFrame", background=CHAT)
    style.configure("Card.TFrame", background=WHITE)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("Muted.TLabel", font=(family, -11), foreground=MUTED)
    style.configure("Error.TLabel", font=(family, -11), foreground=ERROR)
    style.configure("Success.TLabel", font=(family, -11), foreground=GREEN)
    style.configure("Title.TLabel", font=(family, -24, "bold"))
    style.configure("Heading.TLabel", font=(family, -17, "bold"))
    style.configure("Panel.TLabel", background=PANEL)
    style.configure("PanelMuted.TLabel", font=(family, -11), background=PANEL, foreground=MUTED)
    style.configure("TButton", padding=(11, 8), borderwidth=0, background=SOFT, foreground=ACCENT)
    style.map("TButton", background=[("active", "#e6e2ff"), ("disabled", PANEL)],
              foreground=[("disabled", MUTED)])
    style.configure("Accent.TButton", background=ACCENT, foreground=WHITE)
    style.map("Accent.TButton", background=[("active", "#5147c7"), ("disabled", "#cbc6ed")],
              foreground=[("disabled", WHITE)])
    style.configure("TEntry", padding=(10, 8), fieldbackground=WHITE, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, borderwidth=1)
    style.configure("TLabelframe", background=BG, bordercolor=LINE)
    style.configure("TLabelframe.Label", font=(family, -11), background=BG, foreground=MUTED)
    style.configure("TSeparator", background=LINE)
    return family
