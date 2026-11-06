# StudyGroup

แอปแชตกลุ่มนักศึกษา **React → WebSocket → Python Server → SQLite**
ใช้หน้าตา Focus ตามต้นแบบ ภาษาไทย และเปิดจาก Browser ได้ทั้งคอมพิวเตอร์และมือถือ
Python ดูแล Login/Register, สิทธิ์สมาชิกและการบันทึกข้อมูลเหมือนเดิม

```bash
uv sync --locked
npm --prefix web ci
npm --prefix web run build
uv run --locked --env-file .env python -m server.web
```

เปิด **http://127.0.0.1:8000** — checkout ใหม่ที่ไม่มี `.env` ให้คัดลอกจาก `.env.example` ก่อน
บัญชีและข้อความอยู่ที่ `data/studygroup.db` ฝั่ง Python ใช้ข้อมูลเดิมได้
ไม่ต้องกรอกที่อยู่ Server ในหน้า Login

มีออนไลน์/แชตส่วนตัว/สร้างกลุ่ม/ดูสมาชิก/Join เอง/ข้อความสด/Draft และแจ้งเมื่อหลุดแล้ว
CP06 ยังรอตรวจสองเครื่องจริง ประวัติหลังเปิดใหม่/ค้นหา, ไฟล์, AI และ Cloud เป็น CP07–CP10
ปุ่มฟีเจอร์เหล่านี้แสดงตามแบบและยังปิดใช้งาน

- [วิธีติดตั้ง รัน พัฒนา React และตั้งค่า HTTPS/WSS](docs/setup.md)
- [สถาปัตยกรรม](docs/architecture.md) · [Protocol](docs/protocol.md)
- [Checklist R1–R11 และการตรวจสองเครื่อง](docs/demo-checklist.md)
- [Checkpoint และผลทดสอบล่าสุด](DEVELOPMENT.md) · [ข้อกำหนด](HANDOFF.md)
- [ต้นแบบ Focus/Workspace](docs/prototypes/README.md)

```bash
uv run --locked pytest -q --tb=short -W error
npm --prefix web run build
npm --prefix web run test:e2e
```

ใช้ Python 3.14 + uv, Node.js 22.12+ หรือ 24 LTS และ Chrome สำหรับ Browser tests
Tkinter/TCP Client เดิมเก็บไว้สำหรับ compatibility; วิธีรันเก่าอยู่ใน
[legacy-desktop.md](docs/legacy-desktop.md)
