"""Focus sidebar: compact avatar rows, rounded selection, and an account footer."""

import tkinter as tk

from client.ui import theme
from client.ui.widgets import ActionButton, ScrollArea, Tooltip, avatar, ellipsis, icon, rounded_rect


class SidebarRow(tk.Canvas):
    def __init__(self, parent, *, title, detail, command, group=False, own=False,
                 online=False, active=False, join=False, unread=0):
        super().__init__(parent, height=61, bg=theme.PANEL, highlightthickness=0,
                         borderwidth=0, takefocus=True, cursor="hand2")
        self.title, self.detail, self.command = title, detail, command
        self.group, self.own, self.online, self.active = group, own, online, active
        self.join, self.unread, self.hover, self.focused = join, unread, False, False
        self.bind("<Configure>", self.draw)
        self.bind("<Button-1>", lambda event: self.invoke())
        self.bind("<Return>", self._key)
        self.bind("<space>", self._key)
        self.bind("<Enter>", lambda event: self._hover(True))
        self.bind("<Leave>", lambda event: self._hover(False))
        self.bind("<FocusIn>", lambda event: self._focus(True))
        self.bind("<FocusOut>", lambda event: self._focus(False))
        self.tooltip = Tooltip(self, f"{title}\n{detail}")
    def invoke(self):
        return self.command()
    def _key(self, _event):
        self.invoke()
        return "break"
    def _hover(self, active):
        self.hover = active
        self.draw()
    def _focus(self, active):
        self.focused = active
        self.draw()
    def draw(self, _event=None):
        self.delete("all")
        w = self.winfo_width()
        fill = theme.SOFT if self.active else theme.LINE if self.hover else theme.PANEL
        rounded_rect(self, 0, 0, w, 61, 8, fill=fill,
                     outline=theme.ACCENT if self.focused else "")
        if self.group:
            rounded_rect(self, 8, 15, 37, 44, 8, fill=theme.WHITE,
                         outline="" if self.active else theme.LINE)
            icon(self, "hash", 14, 21, color=theme.ACCENT if self.active else theme.MUTED)
        else:
            avatar(self, self.title, 8, 15, own=self.own, online=self.online, background=fill)
        badge = 40 if self.join else 23 if self.unread else 0
        available = max(15, w - 57 - badge)
        title = self.title + (" (คุณ)" if self.own else "")
        self.create_text(49, 14, text=ellipsis(self, title, available), anchor="nw",
                         font=theme.text_font(self, 12), fill=theme.ACCENT if self.active else theme.INK)
        self.create_text(49, 35, text=ellipsis(self, self.detail, max(15, w - 57), 11), anchor="nw",
                         font=theme.text_font(self, 11), fill=theme.MUTED)
        if self.join:
            rounded_rect(self, w - 47, 22, w - 8, 40, 4, fill=theme.LINE)
            self.create_text(w - 27, 31, text="เข้าร่วม", font=theme.text_font(self, 10), fill=theme.MUTED)
        elif self.unread:
            rounded_rect(self, w - 29, 21, w - 8, 41, 7, fill=theme.ACCENT)
            self.create_text(w - 18, 31, text=str(min(99, self.unread)), font=theme.text_font(self, 10), fill=theme.WHITE)


class Sidebar(tk.Frame):
    def __init__(self, parent, controller, create_group, reconnect, logout):
        super().__init__(parent, width=218, bg=theme.PANEL)
        self.grid_propagate(False)
        self.controller = controller
        self._reconnect, self._logout = reconnect, logout
        self._signature = None
        self._active_room = None
        self.rows = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        tk.Frame(self, width=1, bg=theme.LINE).grid(row=0, column=1, rowspan=4, sticky="ns")
        top = tk.Frame(self, bg=theme.PANEL)
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(23, 0))
        top.columnconfigure(0, weight=1)
        brand = tk.Canvas(top, height=44, bg=theme.PANEL, highlightthickness=0, width=190)
        brand.grid(row=0, column=0, sticky="ew")
        rounded_rect(brand, 5, 6, 38, 39, 10, fill=theme.ACCENT)
        icon(brand, "layers", 12, 13, size=19, color=theme.WHITE)
        brand.create_text(48, 3, text="StudyGroup", anchor="nw", font=theme.text_font(self, 19, "bold"), fill=theme.INK)
        brand.create_text(48, 29, text="พื้นที่คุยงานของทีมคุณ", anchor="nw", font=theme.text_font(self, 11), fill=theme.MUTED)
        self.create = ActionButton(top, text="สร้างกลุ่มใหม่", glyph="plus", height=38,
                                   kind="primary", command=create_group, background=theme.PANEL)
        self.create.grid(row=1, column=0, sticky="ew", pady=(23, 23))
        self.list = ScrollArea(self, background=theme.PANEL)
        self.list.grid(row=2, column=0, sticky="nsew", padx=14)
        self.content = tk.Frame(self.list.canvas, bg=theme.PANEL)
        self._window = self.list.canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.content.bind("<Configure>", lambda event: self.list.canvas.configure(scrollregion=self.list.canvas.bbox("all")))
        self.list.canvas.bind("<Configure>", lambda event: self.list.canvas.itemconfigure(self._window, width=event.width))
        self._create_group = create_group
        bottom = tk.Frame(self, height=102, bg=theme.PANEL)
        bottom.grid(row=3, column=0, sticky="ew", padx=14, pady=(10, 14))
        bottom.columnconfigure(0, weight=1)
        tk.Frame(bottom, height=1, bg=theme.LINE).grid(row=0, column=0, sticky="ew")
        self.reconnect_button = ActionButton(bottom, height=33, text="เชื่อมต่อ Server", kind="muted", size=11,
                                             background=theme.PANEL, command=self.show_connection, align="left")
        self.reconnect_button.grid(row=1, column=0, sticky="ew", pady=(6, 4))
        self.reconnect_button.draw = self._connection_draw
        self.account_button = tk.Canvas(bottom, height=45, bg=theme.PANEL, highlightthickness=0,
                                        takefocus=True, cursor="hand2")
        self.account_button.grid(row=2, column=0, sticky="ew")
        self.account_button.bind("<Configure>", self._draw_account)
        self.account_button.bind("<Button-1>", self.show_account)
        self.account_button.bind("<Return>", self.show_account)
        self.account_button.bind("<space>", self.show_account)
        self.account_button.bind("<FocusIn>", self._draw_account)
        self.account_button.bind("<FocusOut>", self._draw_account)
        Tooltip(self.account_button, "บัญชีของคุณ · ตั้งค่าและออกจากระบบ")
        self.account_menu = tk.Menu(self, tearoff=False, font=theme.text_font(self, 12))
        self.account_menu.add_command(label="ตั้งค่าการเชื่อมต่อ", command=self.show_connection)
        self.account_menu.add_separator()
        self.account_menu.add_command(label="ออกจากระบบ", command=logout)
    def _draw_account(self, _event=None):
        canvas = self.account_button
        canvas.delete("all")
        user = self.controller.state.user
        if not user:
            return
        rounded_rect(canvas, 0, 0, canvas.winfo_width(), 45, 8, fill=theme.PANEL,
                     outline=theme.ACCENT if canvas.focus_get() is canvas else "")
        avatar(canvas, user["username"], 5, 6, own=True)
        canvas.create_text(45, 2, text=ellipsis(canvas, user["username"], 112), anchor="nw",
                           font=theme.text_font(self, 12), fill=theme.INK)
        canvas.create_text(45, 25, text="บัญชีของคุณ", anchor="nw", font=theme.text_font(self, 11), fill=theme.MUTED)
        icon(canvas, "settings", max(5, canvas.winfo_width() - 22), 15, size=16)
    def _connection_draw(self, _event=None):
        canvas = self.reconnect_button
        canvas.delete("all")
        online = self.controller.authenticated
        color = theme.GREEN if online else theme.ERROR
        canvas.create_oval(6, 14, 12, 20, fill=color, outline="")
        canvas.create_text(18, 17, anchor="w", text="เชื่อมต่อ Server" if online else "ขาดการเชื่อมต่อ", font=theme.text_font(self, 11), fill=color)
        icon(canvas, "chevron", 137, 10, size=14, color=color)
    def show_account(self, _event=None):
        self.account_menu.tk_popup(self.account_button.winfo_rootx(), self.account_button.winfo_rooty())
        return "break"
    def show_connection(self):
        if not self.controller.authenticated:
            self._reconnect()
            return
        dialog = tk.Toplevel(self)
        dialog.title("StudyGroup — การเชื่อมต่อ")
        dialog.transient(self.winfo_toplevel())
        frame = tk.Frame(dialog, bg=theme.WHITE, padx=24, pady=24)
        frame.pack(fill="both", expand=True)
        config = self.controller.config
        tk.Label(frame, text="เชื่อมต่อแล้ว", bg=theme.WHITE, fg=theme.GREEN,
                 font=theme.text_font(self, 17, "bold")).pack(anchor="w")
        tk.Label(frame, text=f"{config.host}:{config.port}\nการเชื่อมต่อเข้ารหัส TLS", justify="left", bg=theme.WHITE,
                 fg=theme.MUTED, font=theme.text_font(self, 12), pady=14).pack(anchor="w")
        ActionButton(frame, text="ปิด", command=dialog.destroy, kind="primary").pack(anchor="e")
    def _section(self, title, detail="", create=False):
        frame = tk.Frame(self.content, height=25 if not create else 31, bg=theme.PANEL)
        frame.pack(fill="x")
        frame.pack_propagate(False)
        tk.Label(frame, text=title, font=theme.text_font(self, 11), bg=theme.PANEL, fg=theme.MUTED).pack(side="left", padx=7)
        if create:
            ActionButton(frame, glyph="plus", width=30, height=28, kind="muted", command=self._create_group,
                         background=theme.PANEL, tooltip="สร้างกลุ่มใหม่").pack(side="right")
        elif detail:
            tk.Label(frame, text=detail, font=theme.text_font(self, 11), bg=theme.PANEL, fg=theme.MUTED).pack(side="right", padx=7)
    def _row(self, key, **options):
        row = SidebarRow(self.content, **options)
        row.pack(fill="x")
        self.rows[key] = row
    def room_row(self, room_id):
        room = self.controller.state.rooms[room_id]
        if room["kind"] == "private":
            peer = next(m["id"] for m in room["members"] if m["id"] != self.controller.state.user["id"])
            return self.rows.get(f"user:{peer}") or self.rows[f"room:{room_id}"]
        return self.rows[f"room:{room_id}"]
    def refresh(self):
        controller, state = self.controller, self.controller.state
        self.create.configure(state="normal" if controller.authenticated else "disabled")
        self._connection_draw()
        self._draw_account()
        signature = repr((state.users, state.rooms, state.unread, state.active_room, controller.groups_loading))
        if signature == self._signature:
            return
        self._signature = signature
        scroll = self.list.canvas.yview()[0]
        for child in self.content.winfo_children():
            child.destroy()
        self.rows.clear()
        self._section("ออนไลน์", f"{len(state.users)} คน")
        private_by_peer = {}
        for room in state.rooms.values():
            if room["kind"] == "private":
                peer = next(m for m in room["members"] if m["id"] != state.user["id"])
                private_by_peer[peer["id"]] = (peer, room["id"])
        online_ids = set()
        for user in state.users:
            user_id = user["id"]
            online_ids.add(user_id)
            own = user_id == state.user["id"]
            room_id = private_by_peer.get(user_id, (None, None))[1]
            self._row(f"user:{user_id}", title=user["username"], detail="พร้อมคุยงาน" if own else "ส่งข้อความส่วนตัว",
                      own=own, online=True, active=room_id is not None and room_id == state.active_room,
                      unread=state.unread.get(room_id, 0),
                      command=self.show_account if own else lambda peer=user_id: controller.open_private(peer))
        offline = [(peer, room_id) for peer, room_id in private_by_peer.values() if peer["id"] not in online_ids]
        if offline:
            tk.Frame(self.content, bg=theme.PANEL, height=14).pack()
            self._section("แชตส่วนตัว")
            for peer, room_id in offline:
                self._row(f"room:{room_id}", title=peer["username"], detail="ออฟไลน์", active=room_id == state.active_room,
                          unread=state.unread.get(room_id, 0), command=lambda rid=room_id: controller.select_room(rid))
        tk.Frame(self.content, bg=theme.PANEL, height=23).pack()
        self._section("ห้องกลุ่ม", create=True)
        for room in state.rooms.values():
            if room["kind"] == "group":
                room_id = room["id"]
                self._row(f"room:{room_id}", title=room["name"], detail=", ".join(m["username"] for m in room["members"]),
                          group=True, join=not state.is_member(room_id), active=room_id == state.active_room,
                          unread=state.unread.get(room_id, 0), command=lambda rid=room_id: controller.select_room(rid))
        self.directory = ActionButton(self.content, text="สำรวจกลุ่มทั้งหมด", glyph="compass", size=11,
                                      kind="link", height=34, background=theme.PANEL, align="left", command=self.show_directory)
        self.directory.pack(fill="x", pady=(7, 0))
        self.list.bind_wheel(self.content)
        self.content.update_idletasks()
        self.list.canvas.configure(scrollregion=self.list.canvas.bbox("all"))
        self.list.canvas.yview_moveto(scroll)
        if state.active_room != self._active_room and state.active_room in state.rooms:
            row = self.room_row(state.active_room)
            y, h = row.winfo_y(), self.list.canvas.winfo_height()
            top = self.list.canvas.canvasy(0)
            if y < top or y + 61 > top + h:
                self.list.canvas.yview_moveto(max(0, y - h + 61) / max(1, self.content.winfo_height()))
        self._active_room = state.active_room
    def show_directory(self):
        self.controller.refresh_groups()
        self.controller.on_change()
        dialog = tk.Toplevel(self)
        dialog.title("StudyGroup — สำรวจกลุ่มทั้งหมด")
        dialog.geometry("510x480")
        dialog.transient(self.winfo_toplevel())
        frame = tk.Frame(dialog, bg=theme.WHITE, padx=24, pady=24)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="ทุกกลุ่มใน StudyGroup", font=theme.text_font(self, 17, "bold"), bg=theme.WHITE, fg=theme.INK).pack(anchor="w")
        tk.Label(frame, text="เห็นรายชื่อสมาชิกก่อนเข้าร่วม", font=theme.text_font(self, 11), bg=theme.WHITE, fg=theme.MUTED).pack(anchor="w", pady=(4, 16))
        area = ScrollArea(frame, background=theme.WHITE)
        area.pack(fill="both", expand=True)
        content = tk.Frame(area.canvas, bg=theme.WHITE)
        window = area.canvas.create_window(0, 0, anchor="nw", window=content)
        area.canvas.bind("<Configure>", lambda event: area.canvas.itemconfigure(window, width=event.width))
        content.bind("<Configure>", lambda event: area.canvas.configure(scrollregion=area.canvas.bbox("all")))
        for room in self.controller.state.rooms.values():
            if room["kind"] != "group":
                continue
            joined = self.controller.state.is_member(room["id"])
            def select(rid=room["id"], member=joined):
                self.controller.select_room(rid) if member else self.controller.join_group(rid)
                dialog.destroy()
            row = SidebarRow(content, title=room["name"], detail=", ".join(m["username"] for m in room["members"]),
                             group=True, join=not joined, command=select)
            row.pack(fill="x", pady=4)
        area.bind_wheel(content)
