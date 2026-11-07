# StudyGroup

แอปแชตกลุ่มนักศึกษา **React → WebSocket → Python Server → SQLite**
ใช้หน้าตา Minimal ที่ผู้ใช้เลือก ภาษาไทย และเปิดจาก Browser ได้ทั้งคอมพิวเตอร์และมือถือ
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
Web จำการเข้าสู่ระบบ 7 วันด้วย resume token ใน localStorage จึง refresh/ปิดเปิด browser ได้
โดยไม่กรอกรหัสผ่านใหม่ Logout ล้าง token และ restart server ต้อง Login ใหม่

มีออนไลน์/แชตส่วนตัว/สร้างกลุ่ม/ดูสมาชิก/Join เอง/ข้อความสด/Draft และแจ้งเมื่อหลุดแล้ว
ผู้ใช้ตรวจรับ CP06 แล้ว CP07 โหลดประวัติหลังเปิดใหม่/โหลดหน้าเก่า/ค้นหาด้วยคำและวันที่
และ CP08 ส่ง-ดาวน์โหลดไฟล์ ≤ 5 MB แบบ Chunk พร้อมตรวจ SHA-256 ใช้งานได้แล้ว (ผ่านการทดสอบ Local)
CP09 สรุปบทสนทนากลุ่มด้วย AI (Anthropic) ใช้ได้เมื่อใส่ `STUDYGROUP_AI_API_KEY` ใน `.env` ดู [docs/ai.md](docs/ai.md)
Deploy บน Railway พร้อม Volume แล้ว ดู [คู่มือ Cloud และ Backup/Restore](docs/railway.md)
รายละเอียดหลักฐานสองเครื่องสำหรับเดโมเก็บต่อใน CP11

- [วิธีติดตั้ง รัน พัฒนา React และตั้งค่า HTTPS/WSS](docs/setup.md)
- [Railway และการสำรอง/กู้คืน SQLite พร้อมไฟล์แนบ](docs/railway.md)
- [สถาปัตยกรรม](docs/architecture.md) · [Protocol](docs/protocol.md) · [ประวัติ/ค้นหา/ไฟล์](docs/history-files.md) · [AI](docs/ai.md)
- [Checklist R1–R11 และการตรวจสองเครื่อง](docs/demo-checklist.md)
- [Checkpoint และผลทดสอบล่าสุด](DEVELOPMENT.md) · [ข้อกำหนด](HANDOFF.md)
- [ต้นแบบ Focus/Workspace](docs/prototypes/README.md)

```bash
uv run --locked pytest -q --tb=short -W error
npm --prefix web run build
npm --prefix web run test:e2e
```

ใช้ Python 3.14 + uv, Node.js 22.12+ หรือ 24 LTS และ Chrome สำหรับ Browser tests
