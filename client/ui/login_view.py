"""Login, registration, and explicit server trust settings."""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from client.config import ClientConfig
from client.ui import theme
from client.ui.widgets import ActionButton
from shared.message_types import RequestType as R


class AuthView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=16)
        self.controller = controller
        self.mode = R.LOGIN
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=theme.BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self, command=self.canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scroll.set)
        content = ttk.Frame(self.canvas)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)
        window = self.canvas.create_window((0, 0), window=content, anchor="nw")
        card = ttk.Frame(content, padding=(12, 16))
        card.grid(row=1, column=0)

        def resize(_event=None):
            self.canvas.itemconfigure(window, width=self.canvas.winfo_width(),
                                      height=max(self.canvas.winfo_height(), card.winfo_reqheight()))
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.canvas.bind("<Configure>", resize)
        card.bind("<Configure>", resize)
        ttk.Label(card, text="StudyGroup", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="พื้นที่คุยงานของทีมคุณ", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(3, 20))
        self.heading = ttk.Label(card, text="เข้าสู่ระบบ", style="Heading.TLabel")
        self.heading.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.confirm = tk.StringVar()
        self.entries = []
        for row, (label, variable, secret) in enumerate([
            ("ชื่อผู้ใช้", self.username, False), ("รหัสผ่าน", self.password, True),
            ("ยืนยันรหัสผ่าน", self.confirm, True),
        ], start=3):
            field_label = ttk.Label(card, text=label)
            field_label.grid(row=row, column=0, sticky="w", padx=(0, 20), pady=6)
            entry = ttk.Entry(card, textvariable=variable, show="•" if secret else "", width=35)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            entry.bind("<Return>", lambda event: self.submit())
            self.entries.append((field_label, entry))
        self.hint = ttk.Label(card, text="ชื่อผู้ใช้: A–Z, 0–9, _ จำนวน 3–24 ตัว\nรหัสผ่าน: 8–128 ตัวอักษร",
                              style="Muted.TLabel")
        self.hint.grid(row=6, column=0, columnspan=2, sticky="w", pady=(2, 12))
        settings = ttk.LabelFrame(card, text="การเชื่อมต่อ Server", padding=12)
        settings.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        settings.columnconfigure(1, weight=1)
        self.host = tk.StringVar(value=os.environ.get("STUDYGROUP_HOST", "127.0.0.1"))
        self.port = tk.StringVar(value=os.environ.get("STUDYGROUP_PORT", "5000"))
        self.ca = tk.StringVar(value=os.environ.get("STUDYGROUP_TLS_CA", "certs/ca.crt"))
        self.settings_entries = []
        for row, (label, variable) in enumerate([("Host", self.host), ("Port", self.port), ("ไฟล์ CA", self.ca)]):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=3)
            entry = ttk.Entry(settings, textvariable=variable, width=30)
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self.settings_entries.append(entry)
        self.browse = ActionButton(settings, text="เลือกไฟล์", width=76, command=self.choose_ca)
        self.browse.grid(row=2, column=2, padx=(8, 0))
        ttk.Label(settings, text="เว้น CA ว่างเพื่อใช้ใบรับรองที่ระบบเชื่อถือ", style="Muted.TLabel").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.message = ttk.Label(card, text="", wraplength=490)
        self.message.grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.submit_button = ActionButton(card, text="เข้าสู่ระบบ", kind="primary", height=38, command=self.submit)
        self.submit_button.grid(row=9, column=0, columnspan=2, sticky="ew")
        self.switch_button = ActionButton(card, text="ยังไม่มีบัญชี? สมัครสมาชิก", kind="link", command=self.toggle)
        self.switch_button.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._apply_mode()

    def choose_ca(self):
        path = filedialog.askopenfilename(parent=self, title="เลือกใบรับรอง CA", filetypes=[("Certificates", "*.crt *.pem"), ("All files", "*")])
        if path:
            self.ca.set(path)

    def toggle(self):
        self.mode = R.REGISTER if self.mode == R.LOGIN else R.LOGIN
        self.password.set("")
        self.confirm.set("")
        self.controller.error = self.controller.info = ""
        self._apply_mode()
        self.refresh()

    def _apply_mode(self):
        registering = self.mode == R.REGISTER
        for widget in self.entries[2]:
            widget.grid() if registering else widget.grid_remove()
        self.heading.configure(text="สมัครสมาชิก" if registering else "เข้าสู่ระบบ")
        self.switch_button.configure(text="มีบัญชีแล้ว? เข้าสู่ระบบ" if registering else "ยังไม่มีบัญชี? สมัครสมาชิก")

    def submit(self):
        if self.controller.auth_busy:
            return "break"
        try:
            config = ClientConfig.from_env({
                "STUDYGROUP_HOST": self.host.get(), "STUDYGROUP_PORT": self.port.get(),
                "STUDYGROUP_TLS_CA": self.ca.get(),
            })
        except ValueError as error:
            self.message.configure(text=str(error), style="Error.TLabel")
            return "break"
        if not self.username.get() or not self.password.get():
            self.message.configure(text="กรุณากรอกชื่อผู้ใช้และรหัสผ่าน", style="Error.TLabel")
            return "break"
        self.controller.authenticate(self.mode, config, self.username.get(), self.password.get(), self.confirm.get())
        self.password.set("")
        self.confirm.set("")
        return "break"

    def refresh(self):
        controller = self.controller
        busy = controller.auth_busy
        for widget in [*(entry for _, entry in self.entries), *self.settings_entries,
                       self.browse, self.submit_button, self.switch_button]:
            widget.configure(state="disabled" if busy else "normal")
        label = "สมัครสมาชิก" if self.mode == R.REGISTER else "เข้าสู่ระบบ"
        self.submit_button.configure(text="กำลังเชื่อมต่อ…" if busy else label)
        self.message.configure(text=controller.error or controller.info,
                               style="Error.TLabel" if controller.error else "Success.TLabel")
        if controller.info.startswith("สมัครสมาชิก") and self.mode == R.REGISTER:
            self.mode = R.LOGIN
            self._apply_mode()
            self.submit_button.configure(text="เข้าสู่ระบบ")
