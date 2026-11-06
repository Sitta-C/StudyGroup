"""StudyGroup native application. Owns Tk and pumps network events via after()."""

import tkinter as tk
from tkinter import ttk

from client.controller import ClientController
from client.ui.chat_view import ChatView
from client.ui.login_view import AuthView
from client.ui.sidebar import Sidebar
from client.ui.theme import apply_theme
from client.ui.widgets import ActionButton


class Application:
    def __init__(self, root):
        self.root = root
        self.root.title("StudyGroup")
        self.root.geometry("1048x770")
        self.root.minsize(850, 650)
        self.family = apply_theme(root)
        self.controller = ClientController(self.refresh)
        self._auth_requested = False
        self._closed = False
        self._after_id = None
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.auth = AuthView(root, self.controller)
        self.auth.grid(row=0, column=0, sticky="nsew")
        self.main = ttk.Frame(root)
        self.main.grid(row=0, column=0, sticky="nsew")
        self.main.columnconfigure(0, minsize=218)
        self.main.columnconfigure(1, weight=1)
        self.main.rowconfigure(1, weight=1)
        self.sidebar = Sidebar(self.main, self.controller, self.create_group, self.show_auth, self.controller.logout)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.error = ttk.Label(self.main, text="", style="Error.TLabel", wraplength=620, padding=(24, 10))
        self.error.grid(row=0, column=1, sticky="ew")
        self.chat = ChatView(self.main, self.controller, self.family)
        self.chat.grid(row=1, column=1, sticky="nsew")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self._tick()

    def _tick(self):
        if self._closed:
            return
        self.controller.pump()
        self._after_id = self.root.after(40, self._tick)

    def refresh(self):
        if self._closed:
            return
        if self.controller.authenticated:
            self._auth_requested = False
        if self.controller.state.user and not self._auth_requested:
            self.auth.grid_remove()
            self.main.grid()
            self.root.title(f'StudyGroup — {self.controller.state.user["username"]}')
            self.error.configure(text=self.controller.error)
            if self.controller.error:
                self.error.grid()
            else:
                self.error.grid_remove()
            self.sidebar.refresh()
            self.chat.refresh()
        else:
            self.main.grid_remove()
            self.auth.grid()
            self.root.title("StudyGroup — เข้าสู่ระบบ")
            self.auth.refresh()

    def show_auth(self):
        self._auth_requested = True
        self.auth.username.set(self.controller.state.user["username"] if self.controller.state.user else "")
        self.refresh()

    def create_group(self):
        if not self.controller.authenticated:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("StudyGroup — สร้างกลุ่ม")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="สร้างกลุ่มใหม่", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text="เริ่มจากคุณคนเดียว เพื่อนเลือกเข้าร่วมได้เอง", style="Muted.TLabel").pack(anchor="w", pady=(4, 16))
        name = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=name, width=40)
        entry.pack(fill="x")
        error = ttk.Label(frame, text="", style="Error.TLabel")
        error.pack(anchor="w", pady=8)

        def submit(_event=None):
            if not name.get().strip() or len(name.get()) > 100 or "\x00" in name.get():
                error.configure(text="กรุณาตั้งชื่อกลุ่ม 1–100 ตัวอักษร")
                return "break"
            self.controller.create_group(name.get())
            dialog.destroy()
            return "break"

        ActionButton(frame, text="สร้างกลุ่ม", kind="primary", command=submit, height=38).pack(fill="x")
        entry.bind("<Return>", submit)
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.grab_set()
        entry.focus_set()

    def close(self):
        self._closed = True
        # Release the controller -> bound Tk callback cycle on the main thread.
        # A later GC pass in a network thread must not finalize Tk Variables.
        self.controller.on_change = lambda: None
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self.controller.close()
        self.auth.password.set("")
        self.auth.confirm.set("")
        self.root.destroy()
