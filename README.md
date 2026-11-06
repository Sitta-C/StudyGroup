# StudyGroup

โปรเจกต์ Desktop Chat สำหรับงานกลุ่มนักศึกษา ใช้ Python, Tkinter และ TCP Socket พร้อม AI สรุปบทสนทนา ส่งไฟล์ ค้นหาประวัติ และ Cloud Server

**สถานะ:** มี Packages, Config แยก Client/Server และ Socket Protocol พร้อม Tests แล้ว
ยังไม่มีหน้าจอแอปหรือ Socket Server ที่เปิดใช้งานได้

**Environment:** เตรียม Local environment ด้วย **uv** แล้ว ใช้ Python 3.14.10,
Tkinter, `argon2-cffi` และ `pytest` พร้อม `uv.lock` ดู
[วิธี setup และคำสั่งใช้งาน](docs/setup.md)

```bash
uv sync --locked
uv run --locked python -m tkinter
```

สำหรับเครื่องใหม่ให้เตรียม Python/Tkinter ตามคู่มือก่อน `uv sync`

- [แผนพัฒนาและ checkpoint กลาง](DEVELOPMENT.md) — อ่านก่อนเริ่มแต่ละ session และอัปเดตความคืบหน้าเมื่อจบ
- [ข้อกำหนดใน HANDOFF.md](HANDOFF.md) — Project Structure สถาปัตยกรรม Auth/Database/Protocol และเกณฑ์ส่งงาน
- [สัญญา Socket Protocol](docs/protocol.md) — Framing, Request/Response/Event, Validation และการใช้ API
- [เปิด Prototype GUI](docs/prototypes/studygroup-desktop.html) — เปิดไฟล์นี้ใน Browser เพื่อทดลองหน้าตา Desktop
- [รายละเอียด Prototype](docs/prototypes/README.md) — วิธีใช้งานและส่วนที่ยังจำลองอยู่
- [โจทย์ Term Project](docs/reference/socket-programming-assignment.pdf)

Prototype เป็น HTML เพื่อทดลองหน้าจอเท่านั้น แอปที่ต้องพัฒนาจริงเป็น Desktop ด้วย Tkinter การส่งแชตใช้ Socket และ Database อยู่บน Cloud เดียวกับ Server
