"""Run the desktop app with: uv run --locked --env-file .env python -m client.main."""


def main():
    try:
        import tkinter as tk
        from client.app import Application
    except ImportError:
        raise SystemExit("Tkinter ไม่พร้อมใช้งาน กรุณาติดตั้ง Python พร้อม Tcl/Tk ตาม docs/setup.md") from None
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
