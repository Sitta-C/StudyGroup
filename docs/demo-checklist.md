# CP06 — Desktop demo checklist

CP06 ยังเป็น `IN_PROGRESS` หลักฐานด้านล่างเป็นการตรวจ Local บน macOS เครื่องเดียว
ยังไม่ใช่การตรวจรับคอมพิวเตอร์จริงสองเครื่องหรือ Cloud

## เริ่มรัน

เตรียม Environment ตาม [setup.md](setup.md) แล้วเปิดสอง Terminal:

```bash
uv run --locked --env-file .env python -m server.main
```

```bash
uv run --locked --env-file .env python -m client.main
```

เปิด Client เพิ่มจาก Terminal ใหม่ ใช้บัญชี A/B/C คนละบัญชี
สมัครสมาชิกแล้ว Login แยก กรอก Server และ CA ในหน้า Login ได้ ค่าที่แก้ใน UI ไม่เขียนทับ `.env`

## ผล Local และรายการตรวจรับ R1–R11

| ข้อ | วิธีตรวจ | หลักฐาน Local | สองเครื่องจริง |
| --- | --- | --- | --- |
| R1 | อธิบายสถาปัตยกรรม; Client A/B อยู่คนละคอมพิวเตอร์ | มี architecture.md; ยังไม่ได้เดโมสองเครื่อง | รอตรวจ |
| R2 | ส่งข้อความผ่าน TCP Socket + TLS | Client integration และ GUI ใช้ TLSServer จริง | รอตรวจ |
| R3 | สมัครชื่อซ้ำ รวมตัวพิมพ์เล็ก/ใหญ่ แล้ว Login | Auth/TLS tests เดิม และ GUI สมัคร/Login จริง | รอตรวจ |
| R4 | A/B/C Login; รายชื่อรวมตนเอง; B Logout/หลุด แล้วรายชื่ออัปเดต | Client integration และ GUI | รอตรวจ |
| R5 | เปิด A–B, A–C และหลายกลุ่ม; สลับแล้วไม่ปนห้อง | Server tests เดิม, Client integration และ GUI สลับห้อง | รอตรวจ |
| R6 | แต่ละห้องมีช่องพิมพ์/ข้อความเข้าออก; ไทย/Emoji/หลายบรรทัด | GUI และภาพ private-chat.png | รอตรวจ |
| R7 | A ส่งหา B; C ต้องไม่เห็นข้อความ/Private metadata | Client A/B/C ผ่าน TLS จริง | รอตรวจ |
| R8 | A สร้างมากกว่าหนึ่งกลุ่ม; เริ่มมี A คนเดียว | Client integration และ GUI สร้างกลุ่ม | รอตรวจ |
| R9 | C เห็นทุกกลุ่มและสมาชิก ทั้งที่ยังไม่ Join | Client integration รวม Pagination; GUI Dialog สมาชิก | รอตรวจ |
| R10 | C เลือกกลุ่มที่ยังไม่เป็นสมาชิก; ช่องพิมพ์ปิด; กด Join เอง | GUI ตรวจปุ่ม Join และการเปิดช่องพิมพ์หลังสำเร็จ | รอตรวจ |
| R11 | A/B ส่งในกลุ่ม; C ไม่ Join ต้องไม่เห็น; สมาชิกใหม่ไม่เห็นข้อความก่อน Join | Client integration และสิทธิ์ฝั่ง Server | รอตรวจ |

ภาพ [private-chat.png](evidence/cp06/private-chat.png) จับจากหน้าต่าง Tkinter จริง
บัญชี Alice/Bob/Carol และ SQLite เป็นข้อมูลทดสอบใน Temporary directory
ภาพแสดงภาษาไทยที่ส่งและคำตอบผ่าน Server จริงในเครื่องเดียว ไม่ใช่ Prototype HTML

## คำสั่งตรวจซ้ำ

```bash
uv run --locked pytest -q --tb=short
# ต้องมี Desktop/Display และสิทธิ์ TCP Loopback:
uv run --locked pytest tests/gui_checks.py -q --tb=short -W error
```

`gui_checks.py` ไม่ถูกเก็บในชุด Headless ปกติ ต้องเรียกเจาะจง
ทดสอบ Widgets จริง ไม่ Skip เมื่อไม่มี Display ผู้รันต้องจัด Environment ให้พร้อม
ครอบคลุมขนาด 850×700 / 1120×800, Register/Login, เลือกห้อง, Enter/Shift+Enter,
Draft แยกห้อง, สร้าง/Join กลุ่ม, Dialog สมาชิก, Disconnect/Re-login และ Logout

รายการผิดปกติที่ต้องตรวจเพิ่มด้วยคน:

- พิมพ์ด้วย Thai IME จริง รวมวรรณยุกต์ และ Copy/Paste ของ OS
- ลองชื่อซ้ำ รหัสผ่านผิด Login ซ้อน และ Host/Port/CA ผิด หน้าจอต้องอธิบายข้อผิดพลาด
- ตัด Wi-Fi/หยุด Server ระหว่างส่ง: ห้ามแสดงสำเร็จโดยไม่ได้รับคำยืนยัน
  ร่างยังอยู่ ไม่ส่งใหม่เอง หลัง Login บัญชีเดิมให้ตรวจข้อความก่อนส่งซ้ำ
- สลับบัญชี/Server: ไม่เห็นข้อความและร่างของ Session เดิม
- Resize, Scroll และหน้าจอเล็กบน OS ที่จะใช้เดโมจริง

## เตรียม LAN สำหรับคอมพิวเตอร์สองเครื่อง

1. ให้ Server และ Client อยู่ในเครือข่ายที่ถึงกันได้ เลือก IP/ชื่อจริงของ Server
   ตัวอย่างต่อไปใช้ `192.168.1.20` ต้องเปลี่ยนให้ตรงกับเครื่องจริง
2. หลังมี Local CA จาก `generate-dev-certs.sh` แล้ว ออกใบรับรองเพิ่ม:

```bash
bash scripts/generate-lan-cert.sh IP:192.168.1.20
# เพิ่ม DNS:studygroup.local ได้เมื่อชื่อนั้น resolve ถึง Server จริง
```

สคริปต์สร้าง `certs/lan/server.crt` และ `server.key` ด้วย CA เดิม
ไม่แทนไฟล์ Localhost เดิม และหยุดถ้า `certs/lan` มีอยู่แล้ว

3. เปิด Server โดย Bind ทุก Interface ด้วยใบรับรอง LAN:

```bash
STUDYGROUP_HOST=0.0.0.0 \
STUDYGROUP_TLS_CERT=certs/lan/server.crt \
STUDYGROUP_TLS_KEY=certs/lan/server.key \
uv run --locked --env-file .env python -m server.main
```

4. ติดตั้ง Python/Tkinter/uv และ Sync โปรเจกต์บน Client อีกเครื่อง
   คัดลอก **เฉพาะ `ca.crt`** ไปเครื่องนั้น เปิดแอปได้โดยไม่ต้องมี Server `.env`:

```bash
uv run --locked python -m client.main
```

ในหน้า Login ตั้ง Host เป็น `192.168.1.20`, Port เป็น `5000`, เลือก CA ที่คัดลอกมา
ไม่ใช้ `0.0.0.0` เป็นที่อยู่ Client และไม่ปิด Hostname/Certificate verification
Client ไม่ต้องมี Server key, CA key หรือ AI key

5. หาก Firewall ถาม ให้ผู้ดูแลอนุญาต TCP Port ของ Server เฉพาะเครือข่ายที่ใช้เดโม
6. ใช้ Client A/B คนละคอมพิวเตอร์จริง และ C อีกหน้าต่างเพื่อทดสอบคนนอกห้อง

## หลักฐานที่ยังต้องเติมก่อนปิด CP06

- [ ] บันทึกวันเวลา รุ่น/OS ของเครื่อง A/B และตำแหน่ง Server
- [ ] บันทึกเครือข่าย, Host/Port และ SAN ที่ใช้จริง โดยไม่แนบ Private keys
- [ ] เดโม R1–R11 ทีละข้อ พร้อมผลและภาพจากเครื่อง A/B/C
- [ ] ตรวจ TLS ชื่อผิด/CA ผิดและการหลุดบน LAN จริง
- [ ] อัปเดต DEVELOPMENT.md เป็น DONE เมื่อเกณฑ์ครบ แล้วเริ่ม CP07
