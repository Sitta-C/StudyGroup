"""Online users, existing private conversations, and every public group roster."""

from tkinter import ttk


class Sidebar(ttk.Frame):
    def __init__(self, parent, controller, create_group, reconnect, logout):
        super().__init__(parent, style="Panel.TFrame", padding=(16, 20), width=270)
        self.controller = controller
        self._signature = None
        self._active_room = None
        self._populating = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        ttk.Label(self, text="StudyGroup", style="Panel.TLabel", font=("", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="พื้นที่คุยงานของทีมคุณ", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 18))
        self.create = ttk.Button(self, text="＋ สร้างกลุ่มใหม่", style="Accent.TButton", command=create_group)
        self.create.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        tree_frame = ttk.Frame(self, style="Panel.TFrame")
        tree_frame.grid(row=3, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree.column("#0", width=225, minwidth=160, stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.selected)
        self.reload = ttk.Button(self, text="รีเฟรชรายชื่อกลุ่ม", command=self.refresh_groups)
        self.reload.grid(row=4, column=0, sticky="ew", pady=(10, 12))
        ttk.Separator(self).grid(row=5, column=0, sticky="ew", pady=(0, 10))
        self.connection = ttk.Label(self, text="", style="PanelMuted.TLabel", wraplength=230)
        self.connection.grid(row=6, column=0, sticky="w")
        self.account = ttk.Label(self, text="", style="Panel.TLabel")
        self.account.grid(row=7, column=0, sticky="w", pady=(8, 8))
        self.reconnect_button = ttk.Button(self, text="เชื่อมต่อใหม่ / ตั้งค่า Server", command=reconnect)
        self.reconnect_button.grid(row=8, column=0, sticky="ew", pady=(0, 5))
        self.logout_button = ttk.Button(self, text="ออกจากระบบ", command=logout)
        self.logout_button.grid(row=9, column=0, sticky="ew")

    def refresh_groups(self):
        self.controller.refresh_groups()
        self.controller.on_change()

    def selected(self, _event=None):
        if self._populating:
            return
        selected = self.tree.selection()
        if not selected:
            return
        prefix, _, value = selected[0].partition(":")
        if prefix == "user" and int(value) != self.controller.state.user["id"]:
            self.controller.open_private(int(value))
        elif prefix == "room":
            if int(value) != self.controller.state.active_room:
                self.controller.select_room(int(value))

    def refresh(self):
        controller, state = self.controller, self.controller.state
        online = controller.authenticated
        self.create.configure(state="normal" if online else "disabled")
        self.reload.configure(text="กำลังโหลดกลุ่ม…" if controller.groups_loading else "รีเฟรชรายชื่อกลุ่ม",
                              state="normal" if online and not controller.groups_loading else "disabled")
        endpoint = f"{controller.config.host}:{controller.config.port}" if controller.config else ""
        self.connection.configure(text=f"{'● เชื่อมต่อแล้ว' if online else '○ ขาดการเชื่อมต่อ'}\n{endpoint}")
        self.account.configure(text=state.user["username"] if state.user else "")
        if online:
            self.reconnect_button.grid_remove()
        else:
            self.reconnect_button.grid()
        signature = repr((state.users, state.rooms, state.unread, state.active_room))
        if signature == self._signature:
            return
        self._signature = signature
        old_scroll = self.tree.yview()
        self._populating = True
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("", "end", iid="online", text=f"ออนไลน์ · {len(state.users)} คน", open=True)
        for user in state.users:
            own = user["id"] == state.user["id"]
            self.tree.insert("online", "end", iid=f'user:{user["id"]}', text=f'● {user["username"]}' + (" (คุณ)" if own else ""))
        self.tree.insert("", "end", iid="private", text="แชตส่วนตัว", open=True)
        self.tree.insert("", "end", iid="groups", text="กลุ่มทั้งหมด", open=True)
        for room in state.rooms.values():
            room_id = room["id"]
            title = state.room_title(room_id)
            count = state.unread.get(room_id, 0)
            if room["kind"] == "group":
                detail = ", ".join(m["username"] for m in room["members"])
                if not state.is_member(room_id):
                    title += " · เข้าร่วม"
                parent = "groups"
                title = "# " + title
            else:
                detail = "แชตส่วนตัว"
                parent = "private"
            if count:
                title += f" ({count})"
            self.tree.insert(parent, "end", iid=f"room:{room_id}", text=f"{title}\n{detail}")
        active = f"room:{state.active_room}"
        if self.tree.exists(active):
            self.tree.selection_set(active)
        if old_scroll:
            self.tree.yview_moveto(old_scroll[0])
        if state.active_room != self._active_room and self.tree.exists(active):
            self.tree.see(active)
        self._active_room = state.active_room
        self._populating = False
