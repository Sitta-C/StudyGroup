"""Focus layout rendered with native Tk controls and prototype-sized geometry."""

from datetime import datetime
import tkinter as tk
from tkinter import font

from client.ui import theme
from client.ui.widgets import ActionButton, RoundedPanel, ScrollArea, Tooltip, avatar, ellipsis, icon, rounded_rect

MONTHS = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


class ChatView(tk.Frame):
    def __init__(self, parent, controller, family):
        super().__init__(parent, bg=theme.CHAT)
        self.controller, self.family = controller, family
        self._room_id = None
        self._render_signature = None
        self._editing = False
        self._render_job = None
        self._rendered_width = 0
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        header = tk.Frame(self, bg=theme.WHITE, height=83)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.columnconfigure(1, weight=1)
        self.room_icon = tk.Canvas(header, width=39, height=39, bg=theme.WHITE, highlightthickness=0)
        self.room_icon.grid(row=0, column=0, rowspan=2, padx=(25, 11), pady=(22, 16))
        self.title = tk.Label(header, text="เริ่มบทสนทนา", font=theme.text_font(self, 17, "bold"),
                              bg=theme.WHITE, fg=theme.INK, anchor="w", justify="left")
        self.title.grid(row=0, column=1, sticky="sw", pady=(20, 0))
        self.title_hint = Tooltip(self.title, "")
        self.subtitle = tk.Label(header, text="เลือกเพื่อนหรือห้องกลุ่มจากด้านซ้าย", font=theme.text_font(self, 11),
                                 bg=theme.WHITE, fg=theme.MUTED, anchor="w")
        self.subtitle.grid(row=1, column=1, sticky="nw", pady=(0, 15))
        actions = tk.Frame(header, bg=theme.WHITE)
        actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=(12, 25))
        self.members = ActionButton(actions, glyph="users", kind="plain", width=32, height=35,
                                    command=self.show_members, tooltip="ดูสมาชิก")
        self.members.pack(side="left")
        self.ai_button = ActionButton(actions, text="สรุปด้วย AI", glyph="sparkles", kind="soft", width=104, height=35,
                                      tooltip="AI สรุปบทสนทนายังไม่เปิดใช้งาน")
        self.ai_button.configure(state="disabled")
        self.ai_button.pack(side="left", padx=(7, 0))
        tabs = tk.Frame(self, bg=theme.WHITE, height=40)
        tabs.grid(row=1, column=0, sticky="ew")
        tabs.grid_propagate(False)
        tk.Frame(tabs, bg=theme.LINE, height=1).pack(side="bottom", fill="x")
        self.chat_tab = tk.Frame(tabs, bg=theme.WHITE, width=23)
        self.chat_tab.pack(side="left", fill="y", padx=(25, 22))
        tk.Label(self.chat_tab, text="แชต", bg=theme.WHITE, fg=theme.ACCENT,
                 font=theme.text_font(self, 12)).pack(expand=True)
        tk.Frame(self.chat_tab, height=2, bg=theme.ACCENT).pack(side="bottom", fill="x")
        self.files_button = ActionButton(tabs, text="ไฟล์", kind="muted", width=35, height=37,
                                         tooltip="การส่งไฟล์ยังไม่เปิดใช้งาน")
        self.files_button.configure(state="disabled")
        self.files_button.pack(side="left")
        self.search_button = ActionButton(tabs, text="ค้นหาข้อความ", glyph="search", size=11, kind="muted", width=110,
                                          height=37, tooltip="การค้นหาประวัติยังไม่เปิดใช้งาน")
        self.search_button.configure(state="disabled")
        self.search_button.pack(side="right", padx=(0, 25))
        self.area = ScrollArea(self)
        self.area.grid(row=3, column=0, sticky="nsew")
        self.canvas = self.area.canvas
        self.canvas.bind("<Configure>", self._canvas_size)
        self.join_button = ActionButton(self.canvas, text="เข้าร่วมด้วยตัวเอง", glyph="plus", kind="primary",
                                        width=172, command=self.join, background=theme.WHITE)
        self.compose_wrap = tk.Frame(self, bg=theme.CHAT)
        self.compose_wrap.grid(row=5, column=0, sticky="ew", padx=25, pady=(0, 19))
        self.compose_wrap.columnconfigure(0, weight=1)
        self.compose_panel = RoundedPanel(self.compose_wrap, height=96, padding=12)
        self.compose_panel.grid(row=0, column=0, sticky="ew")
        body = self.compose_panel.body
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.composer = tk.Text(body, height=1, wrap="word", font=theme.text_font(self, 12),
                                background=theme.WHITE, foreground=theme.INK, insertbackground=theme.ACCENT,
                                relief="flat", padx=2, pady=1, undo=True, highlightthickness=0, borderwidth=0)
        self.composer.grid(row=0, column=0, sticky="nsew")
        self.composer.bind("<<Modified>>", self._draft_changed)
        self.composer.bind("<Return>", self._enter)
        self.composer.bind("<Shift-Return>", self._newline)
        self.composer.bind("<FocusIn>", lambda event: self._compose_focus(True))
        self.composer.bind("<FocusOut>", lambda event: self._compose_focus(False))
        self.placeholder = tk.Label(body, text="พิมพ์ข้อความถึงทีม…", font=theme.text_font(self, 12),
                                     bg=theme.WHITE, fg=theme.MUTED, cursor="xterm", padx=2, pady=1)
        self.placeholder.place(x=0, y=0)
        self.placeholder.bind("<Button-1>", lambda event: self.composer.focus_set())
        toolbar = tk.Frame(body, bg=theme.WHITE, height=31)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        toolbar.columnconfigure(1, weight=1)
        self.attach_button = ActionButton(toolbar, glyph="paperclip", width=29, height=31, kind="plain",
                                          tooltip="การแนบไฟล์ยังไม่เปิดใช้งาน")
        self.attach_button.configure(state="disabled")
        self.attach_button.grid(row=0, column=0)
        self.compose_hint = tk.Label(toolbar, text="Enter เพื่อส่ง · Shift + Enter ขึ้นบรรทัดใหม่",
                                     background=theme.WHITE, foreground=theme.MUTED, font=theme.text_font(self, 10), anchor="w")
        self.compose_hint.grid(row=0, column=1, sticky="w", padx=(3, 5))
        self.send_button = ActionButton(toolbar, text="ส่ง ↑", width=56, height=31, size=11, radius=7,
                                        kind="primary", command=self.send)
        self.send_button.grid(row=0, column=2, sticky="e")
        foot = tk.Frame(self.compose_wrap, bg=theme.CHAT)
        foot.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        foot.columnconfigure(0, weight=1)
        self.delivery = tk.Label(foot, text="ข้อความที่รับระหว่างเปิดแอปครั้งนี้", bg=theme.CHAT,
                                 fg=theme.MUTED, font=theme.text_font(self, 10), anchor="w", justify="left")
        self.delivery.grid(row=0, column=0, sticky="w")
        self.saved = tk.Label(foot, text="", bg=theme.CHAT, fg=theme.GREEN, font=theme.text_font(self, 10))
        self.saved.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.bind("<Configure>", self._resize)
        self._copy_text = ""
        self.copy_menu = tk.Menu(self, tearoff=False)
        self.copy_menu.add_command(label="คัดลอกข้อความ", command=self._copy_message)
        self._bubble_text = {}
        self.canvas.bind("<Button-3>", self._message_menu)
        self.canvas.bind("<Control-Button-1>", self._message_menu)
    def _compose_focus(self, active):
        self.compose_panel.outline = theme.ACCENT if active else theme.LINE
        self.compose_panel.draw()
    def _resize(self, event):
        width = max(160, event.width - 50)
        self.delivery.configure(wraplength=max(100, width - 110))
        self._heading_width = max(100, width - (230 if self.ai_button.winfo_manager() else 120))
        if hasattr(self, "_heading_title"):
            self._fit_heading()
        self.compose_hint.configure(text="Enter เพื่อส่ง · Shift + Enter ขึ้นบรรทัดใหม่" if width > 450 else "Enter ส่ง · Shift + Enter ขึ้นบรรทัดใหม่")

    def _fit_heading(self):
        width = getattr(self, "_heading_width", 420)
        self.title.configure(text=ellipsis(self, self._heading_title, width, 17))
        self.subtitle.configure(text=ellipsis(self, self._heading_detail, width, 11))
        self.title_hint.text = self._heading_title + "\n" + self._heading_detail
    def _canvas_size(self, event):
        if event.width != self._rendered_width:
            self._schedule_render()
    def _schedule_render(self):
        if self._render_job is None:
            self._render_job = self.after_idle(self._render)
    def destroy(self):
        if self._render_job is not None:
            self.after_cancel(self._render_job)
            self._render_job = None
        super().destroy()
    def _draft_changed(self, _event=None):
        if self.composer.edit_modified():
            if not self._editing and self._room_id is not None:
                self.controller.state.drafts[self._room_id] = self.composer.get("1.0", "end-1c")
            self.composer.edit_modified(False)
        self._placeholder()
    def _placeholder(self):
        if not self.composer.get("1.0", "end-1c"):
            self.placeholder.place(x=0, y=0)
        else:
            self.placeholder.place_forget()
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
        frame = tk.Frame(dialog, bg=theme.WHITE, padx=24, pady=24)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=f'สมาชิก · {len(room["members"])} คน', bg=theme.WHITE, fg=theme.INK,
                 font=theme.text_font(self, 17, "bold")).pack(anchor="w", pady=(0, 16))
        # A native list preserves text selection and keyboard accessibility.
        listing = tk.Listbox(frame, relief="flat", borderwidth=0, highlightthickness=0,
                             background=theme.WHITE, foreground=theme.INK, font=theme.text_font(self, 12))
        listing.pack(fill="both", expand=True)
        for member in room["members"]:
            listing.insert("end", member["username"])
    def refresh(self):
        controller, state = self.controller, self.controller.state
        room_id = state.active_room
        room = state.rooms.get(room_id)
        member = state.is_member(room_id)
        room_changed = room_id != self._room_id
        self._room_id = room_id
        self.room_icon.delete("all")
        rounded_rect(self.room_icon, 0, 0, 39, 39, 11, fill=theme.SOFT)
        icon(self.room_icon, "hash" if room and room["kind"] == "group" else "lock" if room else "message",
             10, 10, size=19, color=theme.ACCENT)
        if room:
            self._heading_title = state.room_title(room_id)
            names = ", ".join(m["username"] for m in room["members"])
            detail = f'{len(room["members"])} สมาชิก · {names}' if room["kind"] == "group" else "แชตส่วนตัว · เฉพาะคุณและ " + state.room_title(room_id)
            self._heading_detail = detail
        else:
            self._heading_title = "เริ่มบทสนทนา"
            self._heading_detail = "เลือกเพื่อนหรือห้องกลุ่มจากด้านซ้าย"
        self._heading_width = max(100, self.winfo_width() - (280 if room and room["kind"] == "group" else 170))
        self._fit_heading()
        self.members.configure(state="normal" if room else "disabled")
        if room and room["kind"] == "group":
            self.ai_button.pack(side="left", padx=(7, 0))
        else:
            self.ai_button.pack_forget()
        draft = state.drafts.get(room_id, "")
        self.composer.configure(state="normal")
        if room_changed or self.composer.get("1.0", "end-1c") != draft:
            self._editing = True
            self.composer.delete("1.0", "end")
            self.composer.insert("1.0", draft)
            self.composer.edit_reset()
            self.composer.edit_modified(False)
            self._editing = False
        self._placeholder()
        self.composer.configure(state="normal" if member else "disabled")
        if room and not member:
            self.compose_wrap.grid_remove()
        else:
            self.compose_wrap.grid()
        self.join_button.configure(state="normal" if controller.authenticated else "disabled")
        pending = any(item[0] == room_id for item in controller.pending_sends.values())
        self.send_button.configure(text="กำลังส่ง…" if pending else "ส่ง ↑",
                                   state="normal" if member and controller.authenticated and not pending else "disabled")
        notice = state.notices.get(room_id, "")
        self.delivery.configure(text=notice or ("ขาดการเชื่อมต่อ · พิมพ์ร่างต่อได้" if room and not controller.authenticated else "ข้อความที่รับระหว่างเปิดแอปครั้งนี้"),
                                fg=theme.ERROR if notice else theme.MUTED)
        self.saved.configure(text="กำลังส่ง…" if pending else "บันทึกแล้ว" if member and controller.authenticated and state.messages.get(room_id) else "",
                             fg=theme.MUTED if pending else theme.GREEN)
        messages = state.messages.get(room_id, {})
        signature = (room_id, tuple(messages), repr(room and room["members"]), member)
        if signature != self._render_signature:
            self._render_signature = signature
            self._schedule_render()
        if room_changed and member:
            self.composer.focus_set()
    def _day(self, date, y, width):
        today = datetime.now().astimezone().date()
        value = f'{date.day} {MONTHS[date.month - 1]} {date.year + 543}'
        if date == today:
            value = "วันนี้ · " + value
        metrics = font.Font(self, font=theme.text_font(self, 10))
        half = metrics.measure(value) / 2
        self.canvas.create_line(25, y, width / 2 - half - 14, y, fill=theme.LINE)
        self.canvas.create_line(width / 2 + half + 14, y, width - 25, y, fill=theme.LINE)
        self.canvas.create_text(width / 2, y, text=value, font=theme.text_font(self, 10), fill=theme.MUTED)
    def _render(self):
        self._render_job = None
        canvas, state = self.canvas, self.controller.state
        width = max(250, canvas.winfo_width())
        at_bottom = canvas.yview()[1] >= 0.97
        old_top = canvas.canvasy(0)
        room_changed = getattr(self, "_painted_room", None) != self._room_id
        self._painted_room = self._room_id
        self._rendered_width = width
        canvas.delete("all")
        self._bubble_text.clear()
        room = state.rooms.get(self._room_id)
        if not room:
            icon(canvas, "message", width / 2 - 14, 80, size=28, color=theme.MUTED)
            canvas.create_text(width / 2, 134, text="เลือกคนออนไลน์เพื่อเริ่มแชต\nหรือสร้างกลุ่มสำหรับทีมของคุณ",
                               font=theme.text_font(self, 12), fill=theme.MUTED, justify="center")
            canvas.configure(scrollregion=(0, 0, width, 200))
            return
        if not state.is_member(self._room_id):
            canvas.create_text(width / 2, 62, text="เข้าร่วมก่อนจึงจะอ่านและส่งข้อความในห้องนี้ได้",
                               font=theme.text_font(self, 12), fill=theme.MUTED, width=width - 70)
            rounded_rect(canvas, 25, 105, width - 25, 247, 12, fill=theme.WHITE, outline=theme.LINE)
            canvas.create_text(width / 2, 137, text="เข้าร่วม " + room["name"], width=width - 94,
                               font=theme.text_font(self, 15, "bold"), fill=theme.INK)
            canvas.create_text(width / 2, 168, text="รับข้อความใหม่ตั้งแต่เวลาที่เข้าร่วม", font=theme.text_font(self, 11), fill=theme.MUTED)
            canvas.create_window(width / 2, 210, window=self.join_button)
            canvas.configure(scrollregion=(0, 0, width, 272))
            return
        messages = state.messages.get(self._room_id, {})
        if not messages:
            canvas.create_text(width / 2, 100, text="ยังไม่มีข้อความใหม่ในห้องนี้", font=theme.text_font(self, 12), fill=theme.MUTED)
            canvas.configure(scrollregion=(0, 0, width, 160))
            return
        names = {m["id"]: m["username"] for m in room["members"]}
        y, previous_date = 31, None
        metrics = font.Font(self, font=theme.text_font(self, 12))
        meta_font = font.Font(self, font=theme.text_font(self, 10))
        for message_id in sorted(messages):
            message = messages[message_id]
            date = datetime.fromisoformat(message["created_at"]).astimezone()
            if date.date() != previous_date:
                self._day(date.date(), y, width)
                previous_date = date.date()
                y += 32
            own = message["sender_id"] == state.user["id"]
            author = "คุณ" if own else names.get(message["sender_id"], str(message["sender_id"]))
            max_text = max(120, int((width - 50) * .92) - (0 if own else 37) - 26)
            text_width = min(max_text, max(metrics.measure(part) for part in message["text"].split("\n")))
            text_width = max(1, text_width)
            # Measure with the same Canvas renderer used to draw the bubble.
            text = canvas.create_text(0, 0, anchor="nw", text=message["text"], font=theme.text_font(self, 12), width=text_width,
                                       fill=theme.WHITE if own else theme.INK, justify="left")
            bounds = canvas.bbox(text)
            bubble_width = min(max_text + 26, bounds[2] - bounds[0] - 2 + 26)
            # Canvas text has a tighter line box than CSS line-height:1.65.
            bubble_height = bounds[3] - bounds[1] + 24
            x = width - 25 - bubble_width if own else 62
            top = y + 21
            bubble = rounded_rect(canvas, x, top, x + bubble_width, top + bubble_height, 12,
                                   corners=(12, 0, 12, 12) if own else (0, 12, 12, 12),
                                   fill=theme.OUTGOING if own else theme.WHITE, outline="" if own else theme.LINE)
            canvas.coords(text, x + 13, top + 12)
            canvas.tag_raise(text)
            self._bubble_text[text] = self._bubble_text[bubble] = message["text"]
            time_text = date.strftime("%H:%M")
            if own:
                time_width = meta_font.measure(time_text)
                canvas.create_text(width - 25, y + 6, anchor="e", text=time_text, font=theme.text_font(self, 10), fill=theme.MUTED)
                canvas.create_text(width - 25 - time_width - 8, y + 6, anchor="e", text=author, font=theme.text_font(self, 11), fill=theme.INK)
            else:
                avatar(canvas, author, 25, y + 2, size=28, background=theme.CHAT)
                canvas.create_text(62, y + 6, anchor="w", text=author, font=theme.text_font(self, 11), fill=theme.INK)
                name_width = font.Font(self, font=theme.text_font(self, 11)).measure(author)
                canvas.create_text(62 + name_width + 8, y + 6, anchor="w", text=time_text, font=theme.text_font(self, 10), fill=theme.MUTED)
            y = top + bubble_height + 20
        canvas.configure(scrollregion=(0, 0, width, y))
        canvas.yview_moveto(1 if at_bottom or room_changed else old_top / max(1, y))
    def _message_menu(self, event):
        items = self.canvas.find_withtag("current")
        if items and items[0] in self._bubble_text:
            self._copy_text = self._bubble_text[items[0]]
            self.copy_menu.tk_popup(event.x_root, event.y_root)
    def _copy_message(self):
        self.clipboard_clear()
        self.clipboard_append(self._copy_text)
