"""Explicit real-window checks: uv run --locked pytest tests/gui_checks.py -q.

Not collected by the normal headless suite; requires a desktop/display and
loopback TCP permission. Uses temporary accounts, database, and certificates.
"""

import time
import gc
import tkinter as tk
from tkinter import ttk

import pytest

from client.app import Application
from client.config import ClientConfig
from client.controller import ClientController
from client.ui.widgets import ActionButton
from client.ui.sidebar import SidebarRow
from shared.message_types import RequestType as R

PASSWORD = "gui check password🔑"


def wait_for(root, predicate, *peers):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        root.update()
        for peer in peers:
            peer.pump()
        if predicate():
            return
        time.sleep(0.005)
    pytest.fail("Desktop did not reach the expected state")


@pytest.fixture
def desktop():
    root = tk.Tk()
    errors = []
    root.report_callback_exception = lambda *error: errors.append(error)
    app = Application(root)
    root.update()
    yield root, app
    worker = app.controller.worker
    app.close()
    if worker:
        worker.thread.join(6)
        assert not worker.thread.is_alive()
    assert not errors, errors
    gc.collect()  # Finalize any Tcl/Python callback cycles on the GUI thread.


def configure_auth(app, config, username):
    auth = app.auth
    auth.host.set(config.host)
    auth.port.set(str(config.port))
    auth.ca.set(str(config.tls_ca))
    auth.username.set(username)
    auth.password.set(PASSWORD)


@pytest.mark.parametrize("geometry", ["850x700", "1120x800"])
def test_auth_layout_and_config_validation(desktop, geometry):
    root, app = desktop
    root.geometry(geometry)
    app.auth.toggle()
    root.update()
    app.auth.canvas.yview_moveto(0)
    root.update()
    for widget in (app.auth.entries[0][1], app.auth.entries[2][1]):
        assert widget.winfo_rooty() >= root.winfo_rooty()
        assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
    app.auth.canvas.yview_moveto(1)
    root.update()
    for widget in (app.auth.submit_button, app.auth.switch_button):
        assert widget.winfo_rooty() >= root.winfo_rooty()
        assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
    app.auth.port.set("bad-port")
    app.auth.submit_button.invoke()
    assert app.controller.worker is None
    assert "PORT" in app.auth.message.cget("text")


def test_real_widgets_private_group_drafts_disconnect_and_account_switch(desktop, server, certificates):
    root, app = desktop
    config = ClientConfig("127.0.0.1", server.address[1], certificates / "ca.crt")
    peers = [ClientController(), ClientController()]
    try:
        for peer, username in zip(peers, ("Bob", "Carol")):
            peer.authenticate(R.REGISTER, config, username, PASSWORD, PASSWORD)
            wait_for(root, lambda: not peer.auth_busy, *peers)
            peer.authenticate(R.LOGIN, config, username, PASSWORD)
            wait_for(root, lambda: peer.authenticated, *peers)
        configure_auth(app, config, "Alice")
        app.auth.toggle()
        app.auth.password.set(PASSWORD)
        app.auth.confirm.set(PASSWORD)
        app.auth.submit_button.invoke()
        assert app.auth.password.get() == app.auth.confirm.get() == ""
        wait_for(root, lambda: not app.controller.auth_busy, *peers)
        assert app.auth.mode == R.LOGIN
        app.auth.password.set(PASSWORD)
        app.auth.submit_button.invoke()
        wait_for(root, lambda: app.controller.authenticated and len(app.controller.state.users) == 3, *peers)
        assert app.main.winfo_ismapped()
        assert not app.auth.winfo_ismapped()
        root.geometry("850x700")
        root.update()
        for widget in (app.chat.send_button, app.sidebar.account_button):
            assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
            assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width()

        bob, carol = peers
        app.sidebar.rows[f'user:{bob.state.user["id"]}'].invoke()
        wait_for(root, lambda: app.controller.state.active_room is not None, *peers)
        private_id = app.controller.state.active_room
        composer = app.chat.composer
        composer.insert("1.0", "สวัสดี 👋")
        root.update()
        root.focus_force()
        composer.focus_set()
        root.update()
        composer.event_generate("<Shift-Return>")
        root.update()
        assert composer.get("1.0", "end-1c").endswith("\n")
        composer.insert("end", "บรรทัดที่สอง")
        root.update()
        composer.event_generate("<Return>")
        wait_for(root, lambda: private_id in bob.state.messages and not app.controller.pending_sends, *peers)
        assert next(iter(bob.state.messages[private_id].values()))["text"] == "สวัสดี 👋\nบรรทัดที่สอง"
        assert composer.get("1.0", "end-1c") == ""
        assert len(app.controller.state.messages[private_id]) == 1
        assert not carol.state.messages

        # The Canvas transcript must wrap the largest accepted Unicode message
        # without drawing outside the room or freezing Tk's event loop.
        app.controller.send(private_id, "🙂" * 4000)
        wait_for(root, lambda: not app.controller.pending_sends, *peers)
        root.update()
        bounds = app.chat.canvas.bbox("all")
        assert 0 <= bounds[0] < bounds[2] <= app.chat.canvas.winfo_width()
        callbacks = set(app.controller._callbacks)
        for unavailable in (app.chat.ai_button, app.chat.files_button,
                            app.chat.search_button, app.chat.attach_button):
            unavailable.invoke()
        assert set(app.controller._callbacks) == callbacks

        composer.insert("1.0", "ร่างห้องส่วนตัว")
        root.update()
        app.sidebar.create.invoke()
        root.update()
        dialog = next(widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel))
        frame = dialog.winfo_children()[0]
        entry = next(widget for widget in frame.winfo_children() if isinstance(widget, ttk.Entry))
        entry.insert(0, "กลุ่มงานภาษาไทย")
        next(widget for widget in frame.winfo_children() if isinstance(widget, ActionButton)).invoke()
        wait_for(root, lambda: app.controller.state.active_room != private_id and len(carol.state.rooms) == 1, *peers)
        own_group = app.controller.state.active_room
        assert len(app.controller.state.rooms[own_group]["members"]) == 1
        app.sidebar.room_row(private_id).invoke()
        wait_for(root, lambda: app.controller.state.active_room == private_id, *peers)
        assert composer.get("1.0", "end-1c") == "ร่างห้องส่วนตัว"

        carol.create_group("กลุ่มของ Carol")
        wait_for(root, lambda: len(app.controller.state.rooms) == 3, *peers)
        other_group = carol.state.active_room
        app.sidebar.room_row(other_group).invoke()
        wait_for(root, lambda: app.controller.state.active_room == other_group, *peers)
        assert app.chat.join_button.winfo_ismapped()
        assert str(composer.cget("state")) == "disabled"
        app.chat.join_button.invoke()
        wait_for(root, lambda: app.controller.state.is_member(other_group), *peers)
        assert not app.chat.join_button.winfo_ismapped()
        assert str(composer.cget("state")) == "normal"
        app.chat.members.invoke()
        root.update()
        members_dialog = next(widget for widget in app.chat.winfo_children() if isinstance(widget, tk.Toplevel))
        listing = next(widget for widget in members_dialog.winfo_children()[0].winfo_children() if isinstance(widget, tk.Listbox))
        assert set(listing.get(0, "end")) == {"Alice", "Carol"}
        members_dialog.destroy()

        app.sidebar.directory.invoke()
        root.update()
        directory = next(widget for widget in app.sidebar.winfo_children() if isinstance(widget, tk.Toplevel))
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        cards = [widget for widget in descendants(directory) if isinstance(widget, SidebarRow)]
        assert {row.title for row in cards} == {"กลุ่มงานภาษาไทย", "กลุ่มของ Carol"}
        next(row for row in cards if row.title == "กลุ่มของ Carol").invoke()
        root.update()
        assert not directory.winfo_exists()

        previous = app.controller.state.active_room
        long_name = "ก" * 100
        app.controller.create_group(long_name)
        wait_for(root, lambda: app.controller.state.active_room != previous, *peers)
        assert app.chat.title.cget("text").endswith("…")
        assert long_name in app.chat.title_hint.text
        assert app.chat.title.winfo_rootx() + app.chat.title.winfo_width() <= app.chat.members.winfo_rootx()

        composer.insert("1.0", "ร่างก่อนหลุด")
        root.update()
        app.controller.worker.close()
        wait_for(root, lambda: app.controller.phase == "disconnected", *peers)
        assert composer.get("1.0", "end-1c") == "ร่างก่อนหลุด"
        assert str(app.chat.send_button.cget("state")) == "disabled"
        assert app.sidebar.reconnect_button.winfo_ismapped()
        assert app.error.cget("text")
        app.sidebar.reconnect_button.invoke()
        root.update()
        assert app.auth.winfo_ismapped()
        app.auth.password.set(PASSWORD)
        app.auth.submit_button.invoke()
        wait_for(root, lambda: app.controller.authenticated and not app.controller.groups_loading, *peers)
        assert composer.get("1.0", "end-1c") == "ร่างก่อนหลุด"
        app.sidebar.account_menu.invoke("ออกจากระบบ")
        wait_for(root, lambda: app.controller.state.user is None, *peers)
        assert app.auth.winfo_ismapped()
        assert not app.controller.state.drafts
    finally:
        for peer in peers:
            peer.close()
            if peer.worker:
                peer.worker.thread.join(6)
