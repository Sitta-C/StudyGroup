# Development environment (uv)

StudyGroup ใช้ **uv** จัดการ Python environment และ dependencies โดยมี
`pyproject.toml` เป็นรายการ dependency และ `uv.lock` เป็นเวอร์ชันที่ล็อกไว้
ไม่ต้องดูแล `requirements.txt` แยกอีกชุด

Environment รอบนี้ใช้ CPython **3.14.10** ตาม `.python-version` พร้อม Tcl/Tk
มี `argon2-cffi` สำหรับ Argon2id และ `pytest` ในกลุ่ม `dev`
มี Packages และ Config แยก Client/Server พร้อม Tests, TLS Chat Server
และ Desktop Client Tkinter แล้ว ดูสถานะการตรวจรับใน DEVELOPMENT.md

ตรวจบนเครื่องพัฒนาแล้ว: สร้างหน้าต่าง Tkinter ได้, Hash/Verify ด้วย Argon2id ได้,
SQLite ในหน่วยความจำทำงาน และ TLS handshake ผ่านเมื่อเชื่อถือ Local CA และใช้
`localhost` โดยปฏิเสธชื่อ Host ที่ไม่ตรงกับใบรับรอง

## เตรียมเครื่อง

ติดตั้ง uv ตาม [เอกสาร Astral](https://docs.astral.sh/uv/getting-started/installation/)
และ Python ที่ import `tkinter`, `ssl`, `sqlite3` ได้
Tkinter เป็นส่วนของ Python/Tcl/Tk ไม่ใช่ dependency ที่ติดตั้งด้วย `uv add`

บน macOS ที่ใช้ Homebrew:

```bash
brew install python@3.14 python-tk@3.14
uv venv --python "$(brew --prefix python@3.14)/bin/python3.14"
uv sync --locked
```

หาก Homebrew มี patch version ต่างจาก `.python-version` ให้ติดตั้ง Python
เวอร์ชันที่ pin ไว้ หรืออัปเดต pin ด้วย `uv python pin <version>` หลังตรวจว่า
Python ใหม่นั้นใช้ Tkinter และ dependencies ได้แล้ว

บนระบบอื่น ใช้ Python ที่มี Tcl/Tk แล้วระบุ interpreter นั้นให้ `uv venv --python`:

```bash
uv venv --python /path/to/python3.14
uv sync --locked
```

คำสั่งทั้งหมดรันจาก root ของโปรเจกต์ ไม่ต้อง activate `.venv` เมื่อใช้ `uv run`
ในเครื่องที่เตรียมรอบนี้ Python จาก Homebrew อยู่ที่
`/opt/homebrew/opt/python@3.14/bin/python3.14` ส่วนคำสั่ง `python3` ของระบบอาจชี้
คนละเวอร์ชัน จึงควรเรียก Python ของโปรเจกต์ผ่าน uv

## Local config และ TLS

สำหรับ checkout ใหม่ที่ยังไม่มี `.env`:

```bash
cp .env.example .env
chmod 600 .env
mkdir -p data/uploads
bash scripts/generate-dev-certs.sh
```

ถ้ามี `.env` หรือ certificates อยู่แล้ว ให้ใช้ไฟล์เดิม ไม่ต้องคัดลอกทับ
สคริปต์ใบรับรองจะหยุดหากพบไฟล์เดิมเพื่อไม่เปลี่ยน trust โดยไม่ตั้งใจ

สคริปต์ต้องมีคำสั่ง `openssl` และสร้าง:

- `certs/ca.crt`: CA สำหรับให้ Client เชื่อถืออย่างชัดเจน
- `certs/ca.key`: private key ของ CA ใช้เฉพาะการออกใบรับรอง Local
- `certs/server.crt` และ `certs/server.key`: ใบรับรองและ private key ของ Server

ใบรับรอง Server อายุ 365 วัน ใช้กับ `localhost`, `127.0.0.1`, `::1` เท่านั้น
ไม่ได้ติดตั้ง CA ลง system trust store และ Client ต้องเปิด hostname verification
เครื่องอื่นที่เข้าผ่าน IP ของ LAN หรือ Cloud ต้องใช้ใบรับรองที่มีชื่อ/IP ตรงกัน
ห้ามแจก private keys ให้ Client หรือใช้ชุด Local นี้เป็นใบรับรอง Production

`.env` ตั้ง Host เป็น `127.0.0.1`, Port `5000`, ที่เก็บข้อมูล `data/`
และ `STUDYGROUP_TLS_CA=certs/ca.crt` สำหรับ Client
ค่าของ AI ยังเว้นว่างจนกว่าจะเลือก Provider/Model และมี Key จริง
ค่าเหล่านี้อ่านได้แล้วผ่าน `ClientConfig.from_env()` และ `ServerConfig.from_env()`
ใน `client/config.py` และ `server/config.py` ตามลำดับ

### การอ่านและตรวจ Config

Config อ่านจาก Environment ปัจจุบันเมื่อเรียก `from_env()` ไม่โหลด `.env` เอง
และไม่อ่านค่าตอน import จึง import Packages ได้ก่อนมี Certificates
ส่ง Mapping ให้ `from_env({...})` ได้สำหรับการทดสอบ; `{}` หมายถึงใช้ค่าเริ่มต้นทั้งหมด
โดยไม่ดึงค่าจาก Environment จริงมาเติม

| ตัวแปร | ฝั่ง | ค่าเริ่มต้น/เงื่อนไข |
| --- | --- | --- |
| `STUDYGROUP_HOST` | ทั้งสอง | `127.0.0.1`; Hostname หรือ IP ไม่มี URL/Port |
| `STUDYGROUP_PORT` | ทั้งสอง | `5000`; เลขฐานสิบ 1–65535 |
| `STUDYGROUP_TLS_CA` | Client | `certs/ca.crt`; ต้องเป็นไฟล์ที่อ่านได้ หรือกำหนดค่าว่างเพื่อใช้ System trust store |
| `STUDYGROUP_DATA_DIR` | Server | `data`; Directory เดิมหรือ Path ใหม่ที่มี Parent เขียนและเข้าถึงได้ |
| `STUDYGROUP_TLS_CERT` | Server | `certs/server.crt`; ต้องเป็นไฟล์ที่มีอยู่และอ่านได้ |
| `STUDYGROUP_TLS_KEY` | Server | `certs/server.key`; ต้องเป็นไฟล์ที่มีอยู่และอ่านได้ |
| `STUDYGROUP_AI_PROVIDER` | Server | ไม่ตั้งค่าหรือว่างได้; ยังไม่เลือก Provider |
| `STUDYGROUP_AI_MODEL` | Server | ไม่ตั้งค่าหรือว่างได้; ยังไม่เลือก Model |
| `STUDYGROUP_AI_API_KEY` | Server | ไม่ตั้งค่าหรือว่างได้; ซ่อนจาก `repr(ServerConfig)` |

Relative paths อ้างจาก Root โปรเจกต์เสมอ แม้เปลี่ยน Working directory
รองรับ Absolute paths และ `~`; ผู้เรียกกำหนดฐานอื่นด้วย `base_dir=Path(...)` ได้
Config จะคืน Path แบบ Absolute แต่ไม่สร้าง Directory, Database หรือไฟล์ใด ๆ
Server สร้าง/เปิด `data_dir/studygroup.db` เมื่อเริ่มทำงาน;
`data_dir/uploads` ยังรอขั้นส่งไฟล์
Host/Port/Path ที่ผิดจะยก `shared.config.ConfigError` ซึ่งเป็น `ValueError`
พร้อมชื่อตัวแปรและสาเหตุ โดยไม่แสดงค่า AI Key

เมื่อไม่ตั้งตัวแปรใดเลย ค่าตั้งต้นยังต้องใช้ไฟล์ Local TLS ที่สร้างไว้ด้านบน
ถ้าไม่มีไฟล์เหล่านี้ `from_env()` จะรายงานข้อผิดพลาดชัดเจน
Path ของ Server ห้ามกำหนดค่าว่าง ส่วน CA ของ Client ที่กำหนดว่างอย่างชัดเจน
จะใช้ System CA แทน Local CA โดยยังตรวจ Certificate และ Hostname ใน `client.network.connect()`
การตรวจ Config ใน CP01 ตรวจ Path/สิทธิ์อ่านเท่านั้น ยังไม่ตรวจ PEM, คู่ Key/Certificate
หรือ TLS handshake

ทดสอบอ่าน Config Local โดยไม่เปิด Network หรือแสดง Secrets:

```bash
uv run --locked python -c "import client, server, shared; print('Packages OK')"
uv run --locked --env-file .env python -c "from client.config import ClientConfig; from server.config import ServerConfig; ClientConfig.from_env(); ServerConfig.from_env(); print('Config OK')"
uv run --locked pytest
```

สำหรับ Client บนเครื่องอื่น ให้ตั้ง Environment เพียง Host, Port และ Trust เช่น:

```dotenv
STUDYGROUP_HOST=chat.example.com
STUDYGROUP_PORT=5000
# ใช้ System CA เมื่อ Server มีใบรับรองจาก CA ที่ระบบเชื่อถือ
STUDYGROUP_TLS_CA=
```

ถ้าใช้ Local CA ให้คัดลอกเฉพาะ `ca.crt` ไป Client แล้วระบุ Path ของเครื่องนั้น
ห้ามคัดลอก `.env` ฝั่ง Server ที่มี Secrets หรือ private keys ไป Client
Host ฝั่ง Server คือที่อยู่ Bind เช่น `0.0.0.0` หรือ `::` ส่วน Host ฝั่ง Client
ต้องเป็นชื่อ/IP ของ Server ที่เข้าถึงได้และตรงกับใบรับรอง

## ตรวจ environment

```bash
uv run --locked python --version
uv run --locked python -c "import tkinter, ssl, sqlite3, argon2, pytest; print('Imports OK')"
uv run --locked python -m tkinter
uv run --locked pytest --version
openssl verify -CAfile certs/ca.crt -verify_hostname localhost certs/server.crt
```

คำสั่ง Tkinter ต้องเปิดหน้าต่างทดสอบได้ แล้วปิดหน้าต่างเพื่อจบคำสั่ง
SQLite ใช้ผ่าน Python ได้ทันที และจะสร้าง `studygroup.db` เมื่อเปิด Server

## ทำงานต่อ

```bash
uv sync --locked
uv add <runtime-package>
uv add --dev <development-package>
```

Tests ปัจจุบันรันได้ด้วย `uv run --locked pytest` และต้องใช้ OpenSSL CLI
เพื่อสร้างใบรับรองทดสอบชั่วคราว รวมทั้งอนุญาตเปิด TCP Loopback บนเครื่อง
เปิด TLS Chat Server และหยุดด้วย Ctrl+C ได้แล้ว:

```bash
uv run --locked --env-file .env python -m server.main
# เปิด Terminal อีกหน้าสำหรับ Client แต่ละบัญชี
uv run --locked --env-file .env python -m client.main
uv run --locked pytest
```

uv ไม่โหลด `.env` ให้อัตโนมัติ จึงระบุ `--env-file .env` เมื่อคำสั่งต้องใช้ Config
อย่าส่ง AI Key หรือ Server private key ไปกับ Client
สัญญา Register/Login/Logout, Client transport และ Limits อยู่ใน
[authentication.md](authentication.md) และ Chat contract ใน [chat.md](chat.md)
Desktop Client มีหน้า Register/Login/Server settings และ Focus chat แล้ว
ตั้งค่า Host/Port/CA ใน UI ได้โดยไม่เขียนทับ `.env` ไม่เก็บ Password หรือ Retry ข้อความเอง
ดู [architecture.md](architecture.md) และ [demo-checklist.md](demo-checklist.md)
สำหรับการตรวจ GUI และตั้งค่า LAN บนสองเครื่องจริง

ตรวจหน้าต่างจริงเพิ่มเติม (ต้องมี Desktop/Display):

```bash
uv run --locked pytest tests/gui_checks.py -q --tb=short -W error
```

ให้นำ `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example` และสคริปต์เข้า Git
ส่วน `.venv/`, `.env`, `certs/`, `data/` ถูก exclude ใน `.gitignore` แล้ว
Cloud, Docker deployment และ AI API จริงยังไม่ได้ตั้งค่าในรอบเตรียม Local นี้

แนวทาง uv อ้างอิง [Working on projects](https://docs.astral.sh/uv/guides/projects/)
และ [Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
