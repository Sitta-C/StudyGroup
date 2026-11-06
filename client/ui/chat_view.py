"""Focus chat room with member preview, live messages, and per-room drafts."""

from datetime import datetime
import tkinter as tk
from tkinter import ttk

from client.ui import theme


class ChatView(ttk.Frame):
    def __init__(self, parent, controller, family):
        super().__init__(parent, padding=(24, 20))
        self.controller = controller
        self.family = family
        self._room_id = None
        self._render_signature = None
        self._editing = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        self.title = ttk.Label(header, text="เริ่มบทสนทนา", style="Heading.TLabel")
        self.title.grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(header, text="เลือกเพื่อนหรือห้องกลุ่มจากด้านซ้าย", style="Muted.TLabel", wraplength=470)
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.members = ttk.Button(header, text="สมาชิก", command=self.show_members)
        self.members.grid(row=0, column=1, rowspan=2, padx=(14, 0))
        ttk.Separator(self).grid(row=1, column=0, sticky="ew")
        self.notice = ttk.Label(self, text="", style="Muted.TLabel", wraplength=650)
        self.notice.grid(row=2, column=0, sticky="ew", pady=(12, 8))
        transcript = ttk.Frame(self)
        transcript.grid(row=3, column=0, sticky="nsew")
        transcript.columnconfigure(0, weight=1)
        transcript.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(transcript, background=theme.BG, highlightthickness=0, width=450)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(transcript, orient="vertical", command=self.canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.messages_frame = tk.Frame(self.canvas, background=theme.BG)
        self._canvas_window = self.canvas.create_window((0, 0), window=self.messages_frame, anchor="nw")
        self.messages_frame.bind("<Configure>", self._content_size)
        self.canvas.bind("<Configure>", self._canvas_size)
        self.canvas.bind("<MouseWheel>", self._scroll)
        self.canvas.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda event: self.canvas.yview_scroll(3, "units"))
        self.join_button = ttk.Button(self, text="เข้าร่วมกลุ่มด้วยตัวเอง", style="Accent.TButton", command=self.join)
        self.join_button.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        composer = ttk.Frame(self, padding=12, style="Card.TFrame")
        composer.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        composer.columnconfigure(0, weight=1)
        self.composer = tk.Text(composer, height=3, wrap="word", font=(family, 12),
                                background=theme.WHITE, foreground=theme.INK, insertbackground=theme.ACCENT,
                                relief="flat", padx=4, pady=4, undo=True, highlightthickness=1,
                                highlightbackground=theme.LINE, highlightcolor=theme.ACCENT)
        self.composer.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.composer.bind("<<Modified>>", self._draft_changed)
        self.composer.bind("<Return>", self._enter)
        self.composer.bind("<Shift-Return>", self._newline)
        ttk.Label(composer, text="Enter เพื่อส่ง · Shift + Enter ขึ้นบรรทัดใหม่", background=theme.WHITE,
                  foreground=theme.MUTED, font=(family, 10)).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.send_button = ttk.Button(composer, text="ส่ง ↑", style="Accent.TButton", command=self.send)
        self.send_button.grid(row=1, column=1, sticky="e", padx=(8, 0), pady=(8, 0))
        self.delivery = ttk.Label(self, text="", style="Muted.TLabel", wraplength=650)
        self.delivery.grid(row=6, column=0, sticky="w", pady=(8, 0))
        self.bind("<Configure>", self._resize_labels)

    def _resize_labels(self, event):
        width = max(220, event.width - 50)
        self.notice.configure(wraplength=width)
        self.delivery.configure(wraplength=width)
        self.subtitle.configure(wraplength=max(160, width - 110))
        self.title.configure(wraplength=max(160, width - 110))

    def _content_size(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_size(self, event):
        self.canvas.itemconfigure(self._canvas_window, width=event.width)
        for row in self.messages_frame.winfo_children():
            for widget in row.winfo_children():
                if isinstance(widget, tk.Label) and getattr(widget, "bubble", False):
                    widget.configure(wraplength=max(180, int(event.width * 0.78)))

    def _scroll(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _draft_changed(self, _event=None):
        if self.composer.edit_modified():
            if not self._editing and self._room_id is not None:
                self.controller.state.drafts[self._room_id] = self.composer.get("1.0", "end-1c")
            self.composer.edit_modified(False)

    def _enter(self, _event=None):
        self.send()
        return "break"

    def _newline(self, _event=None):
        if str(self.composer.cget("state")) == "normal":
            self.composer.insert("insert", "\n")
        return "break"

    def send(self):
        if self._room_id is not None:
            self.controller.send(self._room_id, self.composer.get("1.0", "end-1c"))

    def join(self):
        if self._room_id is not None:
            self.controller.join_group(self._room_id)

    def show_members(self):
        room = self.controller.state.rooms.get(self._room_id)
        if not room:
            return
        dialog = tk.Toplevel(self)
        dialog.title("StudyGroup — สมาชิก")
        dialog.geometry("380x350")
        dialog.transient(self.winfo_toplevel())
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f'สมาชิก · {len(room["members"])} คน', style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        listing = tk.Listbox(frame, relief="flat", background=theme.BG, foreground=theme.INK, font=(self.family, 12))
        listing.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, command=listing.yview)
        scroll.pack(side="right", fill="y")
        listing.configure(yscrollcommand=scroll.set)
        for member in room["members"]:
            listing.insert("end", member["username"])

    def refresh(self):
        controller, state = self.controller, self.controller.state
        room_id = state.active_room
        room = state.rooms.get(room_id)
        member = state.is_member(room_id)
        room_changed = room_id != self._room_id
        draft = state.drafts.get(room_id, "")
        self._room_id = room_id
        if room:
            self.title.configure(text=("# " if room["kind"] == "group" else "") + state.room_title(room_id))
            names = ", ".join(m["username"] for m in room["members"])
            self.subtitle.configure(text=f'{len(room["members"])} สมาชิก · {names}')
            self.members.configure(state="normal")
        else:
            self.title.configure(text="เริ่มบทสนทนา")
            self.subtitle.configure(text="เลือกเพื่อนหรือห้องกลุ่มจากด้านซ้าย")
            self.members.configure(state="disabled")
        if room and room["kind"] == "group" and not member:
            self.join_button.grid()
            self.join_button.configure(state="normal" if controller.authenticated else "disabled")
            notice = "คุณยังไม่ได้เข้าร่วมกลุ่มนี้ เข้าร่วมเพื่อรับข้อความใหม่ตั้งแต่เวลาที่เข้าร่วม"
        else:
            self.join_button.grid_remove()
            notice = "แสดงข้อความที่ได้รับระหว่างเปิดแอปครั้งนี้" if room else ""
        self.notice.configure(text=notice)
        pending = any(item[0] == room_id for item in controller.pending_sends.values())
        can_write = bool(room and member)
        self.composer.configure(state="normal")
        if room_changed or self.composer.get("1.0", "end-1c") != draft:
            self._editing = True
            self.composer.delete("1.0", "end")
            self.composer.insert("1.0", draft)
            self.composer.edit_reset()
            self.composer.edit_modified(False)
            self._editing = False
        self.composer.configure(state="normal" if can_write else "disabled")
        self.send_button.configure(text="กำลังส่ง…" if pending else "ส่ง ↑",
                                   state="normal" if can_write and controller.authenticated and not pending else "disabled")
        text = state.notices.get(room_id, "")
        if pending:
            text = "กำลังรอ Server ยืนยันการส่ง…"
        elif not controller.authenticated and room:
            text = text or "ขาดการเชื่อมต่อ · พิมพ์ร่างต่อได้ แล้วเข้าสู่ระบบใหม่เพื่อส่ง"
        self.delivery.configure(text=text)
        messages = state.messages.get(room_id, {}) if member else {}
        signature = repr((room_id, messages, room and room["members"], member))
        if signature != self._render_signature:
            self._render_signature = signature
            at_bottom = self.canvas.yview()[1] >= 0.97
            old_scroll = self.canvas.yview()[0]
            for child in self.messages_frame.winfo_children():
                child.destroy()
            if not messages:
                label = tk.Label(self.messages_frame, text="ยังไม่มีข้อความใหม่ในห้องนี้" if room else "เลือกคนออนไลน์เพื่อเริ่มแชต\nหรือสร้างกลุ่มสำหรับทีมของคุณ",
                                 background=theme.BG, foreground=theme.MUTED, font=(self.family, 13), pady=60)
                label.pack(fill="x")
            names = {m["id"]: m["username"] for m in room["members"]} if room else {}
            for message_id in sorted(messages):
                message = messages[message_id]
                own = message["sender_id"] == state.user["id"]
                row = tk.Frame(self.messages_frame, background=theme.BG, padx=2, pady=9)
                row.pack(fill="x")
                author = "คุณ" if own else names.get(message["sender_id"], f'ผู้ใช้ {message["sender_id"]}')
                timestamp = datetime.fromisoformat(message["created_at"]).astimezone().strftime("%d/%m %H:%M")
                meta = tk.Label(row, text=f"{author}   {timestamp}", font=(self.family, 10), background=theme.BG, foreground=theme.MUTED)
                meta.pack(anchor="e" if own else "w", pady=(0, 4))
                bubble = tk.Label(row, text=message["text"], justify="left", anchor="w", font=(self.family, 12),
                                  background=theme.ACCENT if own else theme.WHITE, foreground=theme.WHITE if own else theme.INK,
                                  padx=14, pady=11, wraplength=max(180, int(self.canvas.winfo_width() * 0.78)))
                bubble.bubble = True
                bubble.pack(anchor="e" if own else "w")
                for widget in (row, meta, bubble):
                    widget.bind("<MouseWheel>", self._scroll)
            self.update_idletasks()
            self._content_size()
            self.canvas.yview_moveto(1 if room_changed or at_bottom else old_scroll)
        if room_changed and can_write:
            self.composer.focus_set()
