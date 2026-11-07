# รัน StudyGroup Web

สถาปัตยกรรมปัจจุบันคือ **React → WebSocket → Python → SQLite**
Python เสิร์ฟทั้งหน้าเว็บที่ build แล้วและ `/ws` บนพอร์ตเดียว
Browser ไม่ต้องติดตั้ง Python/Tkinter และไม่ต้องกรอก Host/Port/CA ในหน้า Login

## เตรียมครั้งแรก

ติดตั้ง [uv](https://docs.astral.sh/uv/getting-started/installation/),
Python 3.14 ตาม `.python-version` และ [Node.js](https://nodejs.org/en/download)
รุ่น 22.12+ หรือ 24 LTS พร้อม npm ใช้ Chrome สำหรับ Browser tests
จาก root โปรเจกต์:

```bash
uv sync --locked
npm --prefix web ci
npm --prefix web run build
```

เครื่องที่มี `.env` อยู่แล้วใช้ไฟล์เดิมได้เลย ไม่ต้องสร้าง certificates สำหรับ localhost HTTP
เครื่องใหม่คัดลอก `.env.example` เป็น `.env` และอย่านำไฟล์ที่มี secrets เข้า Git
`uv run` อ่านไฟล์นี้เฉพาะเมื่อระบุ `--env-file .env`

## เปิดใช้งาน

```bash
uv run --locked --env-file .env python -m server.web
```

เปิด **http://127.0.0.1:8000** สมัครแล้วเข้าสู่ระบบ กด Ctrl+C ที่ Terminal เพื่อหยุด
เปิด Browser profile / Incognito แยกสำหรับ A/B/C คนละบัญชี
หนึ่งบัญชีออนไลน์ได้ครั้งละหนึ่ง Connection รวมทุกแท็บ

บัญชีและข้อความอยู่ที่ **`data/studygroup.db`** บนเครื่องที่รัน Python
ใช้ `STUDYGROUP_DATA_DIR` เดิมได้ ไม่ย้าย Database หรือสร้างบัญชีใหม่เพียงเพราะเปลี่ยน UI
รหัสผ่านเก็บเป็น Argon2id hash; Browser เก็บสถานะแชต/ร่างในหน่วยความจำเท่านั้น
หลัง Refresh ต้อง Login ใหม่ แล้ว UI โหลดประวัติจาก Server (CP07)
ไฟล์แนบเก็บที่ `data/uploads/` ข้าง Database; Backup ต้องเก็บทั้งสองอย่างพร้อมกัน

## ระหว่างพัฒนา React

เปิด Python Server ตามด้านบน แล้วเปิด Terminal อีกอัน:

```bash
npm --prefix web run dev
```

เปิด http://127.0.0.1:5173; Vite ส่ง `/ws` ไป Python พอร์ต 8000
แก้ CSS/React แล้วดูผลได้ทันที ไม่ต้อง build ทุกครั้ง
ถ้า Python ใช้พอร์ตอื่น ตั้ง `STUDYGROUP_WEB_PROXY=ws://127.0.0.1:8001`
ตอนรัน npm ด้วย หน้าเว็บ production ให้เปิดจาก Python พอร์ต 8000
`npm run preview` เป็นเครื่องมือ preview ของ Vite และไม่ได้ตั้ง WebSocket proxy

## Config สำหรับ Web

| ตัวแปร | ค่าเริ่มต้น / หน้าที่ |
| --- | --- |
| `STUDYGROUP_WEB_HOST` | `127.0.0.1`; ที่อยู่ที่ Python รับการเชื่อมต่อ |
| `STUDYGROUP_WEB_PORT` | `8000`; แยกจากพอร์ต TCP เดิม |
| `STUDYGROUP_WEB_ORIGINS` | ถ้าไม่กำหนด รับ `http://localhost:<port>`, `http://127.0.0.1:<port>` (https หากตั้ง Web TLS) และ http localhost/127.0.0.1:5173; ถ้ากำหนดจะใช้รายการนั้นแทนทั้งหมด |
| `STUDYGROUP_WEB_STATIC_DIR` | `web/dist`; เสิร์ฟเฉพาะไฟล์ใน directory นี้ |
| `STUDYGROUP_WEB_TLS_CERT` | ไม่กำหนด = HTTP สำหรับ loopback / หลัง reverse proxy; ต้องตั้งคู่กับ KEY |
| `STUDYGROUP_WEB_TLS_KEY` | private key ฝั่ง Server เท่านั้น |
| `STUDYGROUP_DATA_DIR` | `data`; SQLite ที่ `<directory>/studygroup.db` และไฟล์แนบที่ `<directory>/uploads/` |
| `STUDYGROUP_AI_API_KEY` | Anthropic API key ฝั่ง Server เท่านั้น ใส่ใน `.env` ไม่เข้า Git; ไม่ตั้ง = ปิด AI (ดู [ai.md](ai.md)) |
| `STUDYGROUP_AI_MODEL` | `claude-haiku-5-5` (ค่าเริ่มต้น) หรือรุ่นอื่น เช่น `claude-sonnet-5-5` |
| `STUDYGROUP_AI_PROVIDER` | ว่าง = `anthropic` เมื่อมี Key; `mock` สำหรับ Test/Demo ที่ติดป้ายเท่านั้น |
| `STUDYGROUP_AI_TIMEOUT` | `45` วินาที (5–120) |
| `STUDYGROUP_WEB_PROXY` | Vite development เท่านั้น; เปลี่ยนปลายทาง `/ws` |

Origins เป็นรายการ URL คั่นด้วย comma เช่น `https://chat.example.com` ไม่มี path
ไม่รับ `*`, `null` หรือ URL ที่มี username/password และต้องตรง scheme/host/port ที่ Browser เปิดจริง
Relative paths อ้างจาก root โปรเจกต์ ค่าที่ผิดรายงานชื่อตัวแปรแล้วหยุดเริ่ม Server
`STUDYGROUP_HOST/PORT/TLS_CERT/TLS_KEY/TLS_CA` เป็นของ TCP/Tkinter เดิม
จึงไม่ส่งผลต่อ Web Server; `STUDYGROUP_PORT=5001` เดิมไม่ต้องเปลี่ยนกลับ

## ใช้สองเครื่อง / เตรียม Deploy

ใช้ **HTTPS + WSS** เมื่อส่งรหัสผ่านผ่าน LAN หรืออินเทอร์เน็ต:

1. ตั้ง `STUDYGROUP_WEB_HOST=0.0.0.0` และเปิดพอร์ตที่ใช้เฉพาะเครือข่ายที่ตั้งใจ
2. ใช้ HTTPS reverse proxy ที่รองรับ WebSocket Upgrade ชี้ไป `127.0.0.1:8000`
   หรือกำหนด `STUDYGROUP_WEB_TLS_CERT/KEY` ให้ Python รับ HTTPS/WSS โดยตรง
3. Certificate ต้องมี DNS/IP ของ URL จริงและได้รับความเชื่อถือจาก Browser
   สำหรับ LAN ใช้ `scripts/generate-lan-cert.sh` ตามส่วนถัดไป
4. ตั้ง `STUDYGROUP_WEB_ORIGINS=https://<ชื่อหรือ-IP-จริง>:8000` หากใช้ TLS ตรงพอร์ต 8000
   ถ้า HTTPS proxy เปิดพอร์ต 443 ใช้ `https://<domain>` ไม่ใส่ `:8000`
5. เครื่อง Client เปิด URL เดียวกัน Browser เลือก `wss://.../ws` อัตโนมัติ
   ไม่ส่ง `.env`, Database, private keys หรือ AI key ไป Client

ตัวอย่าง TLS ตรงบน LAN (แทน IP ให้ตรงเครื่อง Server):

```bash
bash scripts/generate-lan-cert.sh IP:192.168.1.25 DNS:studygroup.local
STUDYGROUP_WEB_HOST=0.0.0.0 \
STUDYGROUP_WEB_ORIGINS=https://192.168.1.25:8000 \
STUDYGROUP_WEB_TLS_CERT=certs/lan/server.crt \
STUDYGROUP_WEB_TLS_KEY=certs/lan/server.key \
uv run --locked --env-file .env python -m server.web
```

สคริปต์ต้องมี CA เดิมจาก `bash scripts/generate-dev-certs.sh` และไม่เขียนทับใบรับรองเก่า
Client ต้องเชื่อถือ CA สำหรับ LAN ตามวิธีของ OS/Browser ก่อนใช้ ไม่กดข้าม certificate error
ส่งเฉพาะ `certs/ca.crt` ไปเครื่องที่ตั้งใจเชื่อถือ CA นี้ เก็บ `ca.key/server.key` ไว้ที่ Server
ถ้าใช้ public domain ให้ใช้ certificate ที่ Browser เชื่อถืออยู่แล้ว

Production ใช้ Python process เดียวกับ SQLite บน persistent disk, สำรอง `data/`
และเสิร์ฟ build เดียวกับรุ่น backend ตั้ง reverse proxy ให้ส่ง Upgrade/Origin และมี idle timeout
ยาวกว่า WebSocket ping 20 วินาที ปัจจุบัน Deploy บน Railway Trial + Volume แล้ว
ใช้ HTTPS/WSS ของ Provider ดู [Config, Backup/Restore และผลตรวจ Cloud](railway.md)

## ตรวจเมื่อเปิดไม่ได้

- หน้า `/` แจ้ง 503 “Build the frontend first”: รัน `npm --prefix web ci` และ `npm --prefix web run build`
- เปิด URL ไม่ได้: ดู Terminal ว่า Python ยังรันอยู่และพอร์ตตรงกัน ตรวจ `http://127.0.0.1:8000/health`
  ควรได้ `{"status":"ok"}` ไม่ใช้พอร์ต 5000 ของแอปเดิม
- หน้าเว็บขึ้นแต่ Login เชื่อมต่อไม่ได้: ตรวจ Browser Network `/ws` ต้อง Upgrade 101
  ถ้า 403 ให้ตั้ง Origin ตรง URL; ถ้า TLS error ให้แก้ certificate/trust
  ถ้าผ่าน proxy ให้เปิด WebSocket Upgrade และอย่าเขียน Origin ทับ
- Server ไม่ตอบทันเวลา: ปุ่มแจ้งข้อผิดพลาดและไม่ส่งซ้ำเอง ตรวจ Server/URL/พอร์ต/proxy
  แล้ว Login ใหม่ ร่างยังอยู่ในแท็บเดิม; Refresh จะล้างร่าง
- บัญชีออนไลน์อยู่แล้ว: Logout/ปิดแท็บเก่าก่อน ใช้คนละบัญชีสำหรับแต่ละ Client

## ตรวจโค้ด

```bash
uv run --locked pytest -q --tb=short -W error
npm --prefix web run build
npm --prefix web run test:e2e
```

Python tests ต้องเปิด loopback และมี OpenSSL; Playwright ใช้ Chrome ที่ติดตั้งไว้
หรือ `PLAYWRIGHT_CHANNEL=chromium` หลังติดตั้งด้วย `cd web && npx playwright install chromium`
Browser tests เปิด server พอร์ต 8765 และใช้ SQLite ชั่วคราว ไม่แตะ `data/` จริง
ทดสอบแชตหลาย Browser contexts, privacy, disconnect, draft, IME และมือถือ
ไม่แทนการตรวจสองเครื่องจริงตาม [demo-checklist.md](demo-checklist.md)

โค้ดเดิม `client/` และ `server.main` เก็บไว้สำหรับ compatibility และการทดสอบเดิม
วิธีรันอยู่ใน [legacy-desktop.md](legacy-desktop.md) อย่ารัน Server เดิมและ Web Server
กับ Database เดียวพร้อมกัน เพราะ registry ของแต่ละ process แยกกัน
