# TLS และ Authentication (CP04)

## Web app ปัจจุบัน

เปิดด้วย `uv run --locked --env-file .env python -m server.web` หลัง build React
ตาม [setup.md](setup.md) Browser ต่อ `/ws` ที่ origin เดียวกัน ไม่มี Host/CA form
สัญญา Auth/Argon2id/rate limits และ registry ด้านล่างใช้ handlers เดิมทั้งหมด
ตัวตนออนไลน์ผูก WebSocket; Browser เก็บเฉพาะ resume token และวันหมดอายุใน
`localStorage` key `studygroup.session.v1` ไม่เก็บ password หรือข้อมูลแชต
Login ออก opaque token สุ่ม 32 bytes อายุ **7 วันนับจาก password login**;
Resume ไม่ต่ออายุ Server เก็บเฉพาะ SHA-256 digest, user และ expiry ใน memory
ไม่แก้ SQLite และ restart server แล้วต้อง Login ใหม่
Refresh/เปิดแท็บ/เปิด browser ใหม่ใช้ `RESUME_SESSION` คืนตัวตนและโหลดห้อง/ประวัติจาก Server
Token เดียวกันให้ Connection ล่าสุดเข้าแทนตัวเก่าแบบ atomic; password login ซ้อนจาก
browser อื่นยังถูกปฏิเสธ ปิด socket/หลุดล้างเฉพาะออนไลน์และ uploads ที่ยังไม่จบ
Browser Logout ขอ `LOGOUT` เพื่อเพิกถอน token แล้วปิด socket และล้าง localStorage
แท็บอื่นรับ storage event แล้วล้างข้อมูลผู้ใช้โดยไม่ resume กลับมาแย่ง connection
หาก Logout ขณะหลุด Client พยายาม reconnect/resume เพื่อเพิกถอน; หาก Server เข้าไม่ถึง
จะล้าง token ใน Browser ได้เท่านั้น token ฝั่ง Server ยังอยู่จนหมดอายุหรือ restart
Token ผิด/หมดอายุ/Server restart ให้ล้าง storage และกลับหน้า Login;
network error ชั่วคราวเก็บ token ไว้ลองเมื่อเปิดหน้าใหม่ และ storage ถูกบล็อกยัง Login ปกติได้
Token ใน localStorage อ่านได้ด้วย JavaScript จึงต้องรักษา CSP/การป้องกัน XSS เช่นเดิม
HTTP/WS ใช้เฉพาะ loopback dev; LAN/production ใช้ HTTPS/WSS พร้อม certificate ที่เชื่อถือได้
Web config แยก `STUDYGROUP_WEB_*` จาก TLS/TCP config เดิม

## TCP/TLS adapter สำหรับ backend tests

`server.main` และ `server.config.ServerConfig` ยังใช้ตรวจ handlers ผ่าน TCP/TLS จริง
ตัวช่วยเชื่อมต่ออยู่ใน `tests/tls_peer.py` และใช้เฉพาะ integration tests
ตรวจทั้ง Certificate chain และ Hostname ด้วย `ssl.create_default_context()` และ TLS 1.2 ขึ้นไป
Tests สร้าง CA, keys และ SQLite ชั่วคราว ไม่ใช้ `.env` หรือข้อมูลจริง

```bash
uv run --locked pytest tests/test_tls_integration.py tests/test_chat_integration.py -q
```

แอปจริงใช้ `server.web` ตาม [setup.md](setup.md) และให้ Browser จัดการ HTTPS/WSS

## สัญญาคำขอ

ทุกคำขอใช้ Envelope และ Request ID ตาม [protocol.md](protocol.md)
Fields ภายใน `data` ต้องตรงตารางทั้งหมด ไม่รับ Fields เพิ่ม เช่น `user_id`, `sender_id`
หรือ `password_hash` ที่ Client อ้างมา

| Request | `data` | สำเร็จ: `result` |
| --- | --- | --- |
| `REGISTER` | `username`, `password`, `confirm_password` | `{"user":{"id":1,"username":"Alice"}}` |
| `LOGIN` | `username`, `password` | `{"user":{"id":1,"username":"Alice"}}` |
| `RESUME_SESSION` (Web เท่านั้น) | `resume_token` | `user`, `resume_token`, `expires_at` |
| `LOGOUT` | `{}` | `{}` |
| `USERS_LIST` | `{}` | `{"users":[{"id":1,"username":"Alice"}]}` |

Web `LOGIN` เพิ่ม `resume_token` และ `expires_at` (Unix seconds) ใน result;
`RESUME_SESSION` คืนค่าเดียวกันโดยไม่เลื่อน expiry ทั้งสองคำสั่งส่งข้อมูล token ให้เฉพาะ
ผู้ร้องขอ ไม่ใส่ใน online events หนึ่งบัญชีจำ token ปัจจุบันเพียงตัวเดียว
password login ใหม่หลัง offline เพิกถอน token เก่า Legacy TCP ใช้ result เดิมและไม่เปิด resume

- Username: ASCII อังกฤษ/ตัวเลข/`_` ยาว 3–24 ตัว; Lookup และ Unique ใช้ Lowercase
  แต่แสดงตัวพิมพ์เดิมตามที่สมัคร ไม่มีการ Trim หรือแก้ชื่อเงียบ ๆ
- Password: 8–128 Unicode characters, ไม่เกิน 512 UTF-8 bytes, ห้าม NUL;
  ไม่ Trim/Normalize/เปลี่ยนตัวพิมพ์ และ Confirm ต้องตรงกัน สมัครแล้วต้อง Login แยก
- ก่อน Login รับได้เฉพาะ `REGISTER`, `LOGIN` และ Web `RESUME_SESSION`; ทุกคำขออื่นให้ `AUTH_REQUIRED`
  แม้ Packet จะใส่ `user_id` ของผู้อื่น หลัง Login ยึด Actor จาก `connection.user` เท่านั้น
- Connection ที่ Login แล้วสมัครใหม่หรือ Login ซ้ำ/สลับบัญชีให้ `ALREADY_LOGGED_IN`
  บัญชีเดียว Login จากหลาย Connection ได้ผู้ชนะเพียงรายเดียวภายใต้ Registry lock
  Session เดิมไม่ถูกตัด และ Connection ที่แพ้ยังใช้สมัคร/Login บัญชีอื่นได้
  ยกเว้น Web resume ด้วย token ปัจจุบันซึ่งตัด Connection เดิมตามข้อตกลงล่าสุด
- Logout ล้างตัวตนแต่คง TLS connection ไว้ สามารถ Login ใหม่ได้
- คำขอชื่อที่ประกาศแล้วแต่ยังไม่มี Handler ให้ `AUTH_REQUIRED` ก่อน Login
  และ `UNKNOWN_TYPE` หลัง Login ปัจจุบัน Chat/Groups พร้อมใช้ตาม CP05
  ส่วน History/Files/AI ยังไม่มี Handlers

Error ที่ใช้งาน: `INVALID_INPUT`, `AUTH_REQUIRED`, `AUTH_FAILED`, `USERNAME_TAKEN`,
`ALREADY_LOGGED_IN`, `RATE_LIMITED`, `UNKNOWN_TYPE`, `INTERNAL_ERROR`
Login ชื่อไม่มีอยู่/รหัสผิด/ข้อมูล Credentials ผิดรูปแบบใช้ข้อความรวม
`Invalid username or password` ส่วน Fields ขาด/เกินให้ `INVALID_INPUT`
ไม่คืน Password hash, Exception text หรือข้อมูล Key ให้ Client

## Online และวงจร Connection

```json
{"v":1,"type":"USERS_UPDATED","data":{"users":[{"id":1,"username":"Alice"}],"revision":1}}
```

`users` มีเฉพาะผู้ Login บน Connection ที่ยังไม่ Cleanup รวมตัวเอง เรียงตาม User ID
ไม่ใช่รายชื่อบัญชีทั้งหมด `revision` เพิ่มเมื่อ Registry เปลี่ยนและเริ่มใหม่เมื่อเปิด Server ใหม่
Client ใช้ลำดับนี้กับ Event ใน Connection ปัจจุบัน; Response จับคู่ด้วย Request ID

- Login response ถูกเข้าคิวก่อน Event แรกของตน; ผู้ Login ทุกคนได้รับ Snapshot ใหม่
- Logout response มาก่อน Snapshot สุดท้ายที่ไม่รวมตัวผู้ Logout แล้ว; Connection นั้น
  ไม่ได้รับ Broadcast ภายหลังจนกว่าจะ Login ใหม่ ผู้ที่ยังไม่ Login ไม่ได้รับรายชื่อออนไลน์
- EOF ปกติ, Frame ผิดรูป, Frame ไม่ครบ/เกิน Deadline, TLS/Socket error,
  Queue เต็ม, Idle timeout และ Server stop ล้างตัวตนออนไลน์ผ่าน Cleanup เดียวกัน
  Resume token แยกจากออนไลน์และหมดอายุตอนตรวจ resume; ไม่ตัด socket ที่เปิดอยู่เพราะ token หมดอายุ
- Registry ตรวจว่า User ID ยังชี้ Connection เดิมก่อนลบ ป้องกัน Cleanup เก่าไปล้าง Session ใหม่
- Client ส่ง Event/Response ปลอม หรือ Frame/Envelope ผิดรูป Server ปิด Connection
  โดยไม่สร้าง Request ID ปลอม ส่วน Handler validation errors ตอบ Error และอ่านคำขอถัดไปได้

Server ใช้ Listener thread รับ Socket แล้วส่ง Handshake ให้ Worker ของ Connection
แต่ละ Worker เป็นเจ้าของ TLS Handshake/Read/Write เพียงรายเดียว และเปิด SQLite connection ของตน
Workers อื่นส่ง Packet เข้าคิวและปลุกด้วย Socket pair แทนการเขียน TLS ข้าม Thread
Snapshot/Revision และการเข้าคิวถูกเรียงภายใต้ Registry lock โดยไม่มี Network I/O ใน Lock
Worker อ่าน Frame พร้อม Total deadline ป้องกันการหยด Bytes เพื่อต่ออายุ Timeout ไม่สิ้นสุด

## Limits และ Password storage

ค่าตั้งต้นของ `ServerLimits` ใน `server/main.py`:

| รายการ | ค่า |
| --- | --- |
| TLS handshake | 5 วินาที |
| รับหนึ่ง Frame ทั้งหมด / `sendall` หนึ่ง Frame | 5 วินาที |
| Idle ก่อน Login / หลัง Login | 30 วินาที / 30 นาที |
| Connections รวม Handshake ที่ยังค้าง | 128 |
| Outbound queue ต่อ Connection | 128 Packets; เต็มแล้วปิด Connection |
| Hash/Verify พร้อมกัน | 2 งาน; เต็มให้ `RATE_LIMITED` |

`AuthRateLimiter` ร่วมทั้ง Server ใช้ Monotonic rolling window 60 วินาที:
20 Auth attempts ต่อ Source IP รวม Register/Login และ 5 Login attempts ต่อชื่อที่ Normalize
นับทั้งสำเร็จและล้มเหลว ไม่ Reset เมื่อ Reconnect/Logout/สำเร็จ Account budget ร่วมข้าม IP
Web resume ใช้งบ Source IP เดียวกัน รวม token ผิดรูปแบบ แต่ไม่ใช้งบ password ต่อชื่อบัญชี
ชื่อไม่มีอยู่ก็ใช้ Account budget เช่นกัน ลองใหม่หลัง Attempt เก่าหมด Window
เก็บ Bucket ไม่เกิน 4096 Keys; เต็มแล้วปฏิเสธ Key ใหม่จนมีที่ว่าง
Limiter อยู่ใน Memory จึงเริ่มใหม่เมื่อ Restart และผู้ใช้หลัง NAT ใช้งบ Source IP ร่วมกัน
ปรับ Limits/Limiter ผ่าน Constructor ได้โดยยังไม่มี Environment variables เพิ่มใน CP04

`Passwords` ใช้ `argon2-cffi` ค่าเริ่มต้น Argon2id (Memory 64 MiB, Time cost 3,
Parallelism 4) พร้อม Random salt ทุกครั้ง บัญชีที่ไม่มีอยู่ยัง Verify ด้วย Dummy hash
ที่ Cost เดียวกัน เมื่อ Login สำเร็จแล้ว `check_needs_rehash()` ระบุว่า Parameters เก่า
จะสร้าง Hash ใหม่และอัปเดตด้วย Compare-and-update ไม่ส่ง Hash ออกจาก Internal lookup
ไม่ Log Credentials/Request payload หรือ Exception text ที่อาจมี Secrets

## ตรวจรับ

```bash
uv run --locked pytest tests/test_auth.py tests/test_tls_integration.py
uv run --locked pytest
```

Tests สร้าง CA, Server certificates (ปกติ/Hostname ผิด/หมดอายุ), Keys และ SQLite
ใน Temporary directory ด้วย OpenSSL แล้วใช้ TCP/TLS บน `127.0.0.1` จริง
ไม่ใช้ `.env`, ใบรับรองใน `certs/` หรือข้อมูลจริงใน `data/`
มี Tests Login/สมัครพร้อมกัน, Session เก่า, EOF/Error, ขีดจำกัด Auth/Connection/Queue,
การปลอม Actor/ทิศทาง Packet, Deadline และ I/O owner ระหว่าง Response/Event พร้อมกัน
ผลและจำนวน Tests ล่าสุดอยู่ใน [DEVELOPMENT.md](../DEVELOPMENT.md)
ผล Local นี้ยังไม่ใช่การตรวจ GUI, คอมพิวเตอร์สองเครื่อง หรือ Cloud deployment

อ้างอิง API: [Python 3.14 ssl](https://docs.python.org/3.14/library/ssl.html),
[argon2-cffi PasswordHasher](https://argon2-cffi.readthedocs.io/en/stable/api.html)
