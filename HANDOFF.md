# StudyGroup Development Handoff

อัปเดต 2 พฤศจิกายน 2026 · สำหรับ Codex ที่จะพัฒนาแอปต่อจากการออกแบบ

StudyGroup เป็นโปรแกรม Desktop สำหรับนักศึกษาคุยงานกลุ่ม ใช้ Python, Tkinter และ TCP Socket โดยมี Server และ SQLite อยู่บน Cloud เครื่องเดียวกัน ฟีเจอร์พิเศษ 4 ข้อคือ AI สรุปบทสนทนา ส่งไฟล์ ประวัติแชตที่ค้นหาได้ และ Cloud deployment

**สถานะการพัฒนา:** มี Config, Socket Protocol, SQLite, สิทธิ์เข้าถึงข้อมูล,
TLS Server, Authentication, รายชื่อออนไลน์ และ Chat/Group handlers พร้อม Tests แล้ว
มี Desktop entry point/GUI แบบ Focus แล้วใน CP06; การตรวจสองเครื่องและ Deploy ยังต้องทำต่อ
ดูสถานะ checkpoint และผลทดสอบล่าสุดใน [DEVELOPMENT.md](DEVELOPMENT.md)
สัญญา Chat/Group ที่ใช้จริงอยู่ใน [docs/chat.md](docs/chat.md)
โค้ด HTML ใน Prototype เป็นแบบอ้างอิงหน้าจอ ไม่ใช่แอปที่พัฒนาเสร็จแล้ว

**อัปเดต Environment:** เตรียม Local environment ด้วย **uv** ตามคำขอผู้ใช้แล้ว
ใช้ Python 3.14.10 พร้อม Tkinter, `argon2-cffi`, `pytest`, `.env.example`
และสคริปต์สร้าง Local TLS ดู [docs/setup.md](docs/setup.md)
ใช้ `pyproject.toml` และ `uv.lock` แทน `requirements.txt` ในแผนเดิม
การอ่าน Environment และตรวจ Config เริ่มที่ `client/config.py`, `server/config.py`
และ `shared/config.py`

สัญญา Protocol ที่พัฒนาแล้วและขอบเขต Validation อยู่ใน [docs/protocol.md](docs/protocol.md)
ใช้ `PacketConnection` เดียวต่อ Socket; TLS ฝั่ง Server ให้ Worker เจ้าของ Connection
ทำ I/O เพียงรายเดียว ส่วน Thread อื่นส่งผ่าน Outbound queue

Schema, Transaction และ Permission API ที่พัฒนาแล้วอยู่ใน
[docs/database.md](docs/database.md) โดย Handler ต้องผูก Actor กับ Connection ที่ Login

สัญญา Auth, TLS transport, Session registry และ Limits ที่ใช้แล้วอยู่ใน
[docs/authentication.md](docs/authentication.md)

## 1. เริ่มอ่านและทำงานจากตรงนี้

เริ่มทุก session ที่ [DEVELOPMENT.md](DEVELOPMENT.md) เพื่อดูสถานะล่าสุด
งานถัดไปและเกณฑ์ผ่านแต่ละ checkpoint แล้วกลับมาอ่านข้อกำหนดที่เกี่ยวข้องในไฟล์นี้
เมื่อจบ session ให้บันทึกผลจริงและงานต่อใน DEVELOPMENT

1. อ่านไฟล์นี้ทั้งหมด และตรวจคำสั่งใน `AGENTS.md` หากมีในรอบพัฒนา
2. เปิด [Prototype GUI](docs/prototypes/studygroup-desktop.html) ใน Browser เพื่อทดลอง Flow
3. ดู [Focus](docs/prototypes/studygroup-focus.png) และ [Workspace](docs/prototypes/studygroup-workspace.png) เป็นภาพอ้างอิง
4. ตรวจ [โจทย์ต้นฉบับ](docs/reference/socket-programming-assignment.pdf) โดยเฉพาะ R1–R11 และ Part 3
5. พัฒนาตามลำดับในส่วน 11 โดยเริ่มจาก Protocol, Database และ Authentication แล้วทำแชตพื้นฐานให้ครบ

ใช้ชื่อ **StudyGroup** ในชื่อหน้าต่าง เอกสาร ฐานข้อมูล ตัวอย่าง Environment และข้อความใน UI ทั้งหมด ชื่อ Database ที่แนะนำคือ `studygroup.db` โฟลเดอร์โปรเจกต์ปัจจุบันคือ `/Users/testmacbook/cp/network/StudyGroup`

ไม่ต้องสร้าง Chat หรือ Codex Thread ใหม่เพื่อเริ่มพัฒนา ไฟล์ส่งต่อนี้มีบริบทที่จำเป็นอยู่แล้ว

## 2. แยกแหล่งที่มาของข้อกำหนด

### สิ่งที่ผู้ใช้ระบุในบทสนทนา

- เปลี่ยนชื่อโปรเจกต์เป็น StudyGroup
- แอปจริงเป็น Desktop Program ไม่ใช่ Web-based Application
- ทำ Part 3 Special Points ครบ 4 ฟีเจอร์ โดยรวม AI อย่างน้อย 1 ฟีเจอร์
- ส่งต่อ Project Structure และ Prototype ให้ Codex พัฒนาได้

### แนวทางที่ออกแบบร่วมกัน

- Python + Tkinter สำหรับ Desktop GUI
- TCP Socket หุ้ม TLS สำหรับการติดต่อ Client–Server ทั้งข้อความและคำขอฟีเจอร์ต่าง ๆ
- Cloud VM/VPS หนึ่งเครื่องรัน Server และเก็บ SQLite พร้อมไฟล์แนบในพื้นที่ถาวร
- Username + Password โดย Server ตรวจรหัสผ่านและผูกตัวตนกับ Socket
- เรียก AI API จาก Server เพื่อสรุปข้อความในห้องกลุ่ม ไม่ต้องฝึกโมเดลเอง
- เก็บ API Key และกุญแจ TLS ที่ Server เท่านั้น

### ค่าเริ่มต้นเพิ่มเติมสำหรับเริ่มพัฒนา

ข้อเหล่านี้ช่วยปิดรายละเอียดที่ยังไม่เคยกำหนดตายตัว สามารถปรับโดยบันทึกเหตุผลไว้ในเอกสาร:

- ใช้ Focus เป็นหน้าตาเริ่มต้นตามแบบที่เลือกดูใน Prototype เก็บ Workspace เป็นตัวเลือกอ้างอิง ไม่จำเป็นต้องสร้างสอง UI แยกกันใน MVP
- หนึ่งบัญชีล็อกอินได้ครั้งละหนึ่งการเชื่อมต่อ และชื่อผู้ใช้ไม่เปลี่ยนใน MVP
- สมาชิกใหม่เห็นข้อความและไฟล์ที่ส่งตั้งแต่ตนเข้าร่วมกลุ่มเป็นต้นไป ให้ใช้ขอบเขตนี้กับประวัติ การค้นหา และ AI ด้วย
- จำกัดไฟล์แนบไม่เกิน 5 MiB ต่อไฟล์ และสรุปข้อความล่าสุดที่ผู้ใช้มีสิทธิ์ไม่เกิน 50 ข้อความ
- ยังไม่ได้เลือกผู้ให้บริการ AI, รุ่นโมเดล หรือผู้ให้บริการ Cloud ใช้ Config/Adapter แยกไว้ ไม่ผูกข้อมูลลับลงโค้ด
- งาน Python และการทดสอบ Local เริ่มได้ทันที ส่วนการใช้บริการภายนอกจริงต้องมีค่าบริการ/บัญชี/Key/ที่อยู่ Server จากผู้ใช้ตามที่จำเป็น

## 3. เกณฑ์จาก Term Project

โจทย์ต้นฉบับมีคะแนนรวม 12.5 คะแนน: Part 1 = 1.5, Part 2 = 7, Part 3 = 4 ต้องทำ Part 1 ครบก่อนตรวจ Part 2 และทำ Part 2 ครบก่อนตรวจ Part 3 ต้องมีสไลด์ Implementation Explanation พร้อมสาธิตและอธิบายแนวคิดกับโค้ดได้

| เกณฑ์ | พฤติกรรมที่ต้องได้ |
| --- | --- |
| R1 | นำเสนอสถาปัตยกรรม มีอย่างน้อย 2 Clients บนคอมพิวเตอร์จริงคนละเครื่อง Server อยู่หนึ่งในเครื่องเหล่านั้นหรืออีกเครื่อง/Cloud ได้ อธิบายว่าใช้โปรโตคอลอะไร ทำไม และใช้อย่างไร |
| R2 | ข้อความแชตระหว่าง Server และ Client ใช้ Socket Programming |
| R3 | ผู้ใช้แต่ละคนมีชื่อไม่ซ้ำ |
| R4 | ทุก Client เห็นรายชื่อทุกคนที่เชื่อมต่ออยู่ รวมตนเอง และอัปเดตเมื่อเข้า/ออก |
| R5 | แต่ละคู่สนทนาส่วนตัวและแต่ละกลุ่มมีห้องของตนเอง |
| R6 | ทุกห้องมีช่องส่งข้อความและหน้าต่างแสดงข้อความที่ส่งกับข้อความเข้า |
| R7 | ส่งข้อความส่วนตัวหาใครก็ได้ในรายชื่อ โดยมีเพียงผู้ส่งกับผู้รับที่เห็นในฝั่งผู้ใช้ |
| R8 | ทุก Client สร้างได้หลายกลุ่ม เมื่อสร้างแล้วมีเพียงผู้สร้างเป็นสมาชิก |
| R9 | ทุก Client เห็นรายชื่อกลุ่มทั้งหมดพร้อมรายชื่อสมาชิก รวมกลุ่มที่ยังไม่ได้เข้าร่วม |
| R10 | ผู้ใช้เลือกเข้าร่วมกลุ่มด้วยตนเอง ผู้สร้างไม่เพิ่มสมาชิกให้อัตโนมัติ |
| R11 | สมาชิกส่งข้อความในกลุ่มที่เข้าร่วมได้ และมีเพียงสมาชิกที่เห็นเนื้อหา |

Part 3 เปิดให้เลือกฟีเจอร์เอง ไม่ได้ระบุชื่อฟีเจอร์ทั้ง 4 ไว้ล่วงหน้า ต้องมี AI อย่างน้อยหนึ่งข้อ และโจทย์ระบุว่า Cloud deployment นับเป็นหนึ่ง Special Point ได้ ฟีเจอร์อื่นยังขึ้นกับการประเมินของผู้สอน

| ฟีเจอร์พิเศษที่เสนอ | เงื่อนไขสำเร็จ |
| --- | --- |
| AI สรุปบทสนทนา | ปุ่มในห้องกลุ่มเรียกโมเดลจริงผ่าน API แล้วสรุปประเด็น ข้อตกลง ผู้รับผิดชอบ และกำหนดส่งจากข้อมูลที่มีสิทธิ์อ่าน |
| ส่งไฟล์ | ผู้ใช้ส่งและดาวน์โหลดไฟล์จริงผ่าน Socket ได้ มีเพียงผู้มีสิทธิ์ในห้องที่เข้าถึงได้ |
| ประวัติและการค้นหา | ปิดแล้วเปิดแอปใหม่ยังพบข้อความเดิม ค้นหาด้วยคำและวันที่ในห้องที่มีสิทธิ์ได้ เป็นความสามารถเกินกว่าหน้าต่างข้อความ R6 |
| Cloud deployment | Server ใช้งานบน Cloud จริง พร้อมข้อมูลถาวร และ Desktop Clients คนละเครือข่ายสื่อสารกันได้ |

Authentication และ TLS เป็นส่วนพื้นฐานของการออกแบบนี้ ไม่ให้นับแทนฟีเจอร์พิเศษที่ตกลงไว้

## 4. สถาปัตยกรรม

```text
Desktop Client A ── TCP + TLS ──┐
                               │
Desktop Client B ── TCP + TLS ──┼── Cloud VM / VPS
                               │   ├── Python Chat Server
Desktop Client C ── TCP + TLS ──┘   ├── SQLite: data/studygroup.db
                                   └── Files: data/uploads/
                                            │
                                   Server ── HTTPS ── AI API
```

Client ไม่เข้าถึง SQLite และไม่เรียก AI API โดยตรง Server ตรวจตัวตน ตรวจสิทธิ์ อ่าน/เขียนข้อมูล และกระจาย Event ไปยังผู้รับที่ถูกต้อง การใช้ HTTPS จาก Server ไป AI เป็นคนละส่วนกับข้อความแชต Client–Server ที่ใช้ Socket

SQLite เป็นไฟล์ในพื้นที่ถาวรของ Cloud เครื่องเดียวกับ Server ไม่ใช่ Database ที่เปิดให้ Client ต่อข้ามเครือข่าย บันทึกเวลาเป็น UTC แล้วแสดงตามเวลาของผู้ใช้ ข้อมูลวันที่และชื่อใน Prototype เป็นตัวอย่าง ไม่ให้นำไปใช้เป็นค่าคงที่ของแอปจริง

## 5. Project Structure เป้าหมาย

โครงสร้างด้านล่างเป็นเป้าหมายสำหรับรอบพัฒนา ยังไม่ได้สร้างไฟล์แอปทั้งหมด
ไฟล์ที่มีจริงและผลตรวจล่าสุดให้ดูใน DEVELOPMENT

```text
StudyGroup/
├── README.md
├── HANDOFF.md
├── DEVELOPMENT.md             # แผน checkpoint สถานะล่าสุด และบันทึกแต่ละ session
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore
├── client/
│   ├── __init__.py
│   ├── main.py                  # Entry point ของ Desktop Client
│   ├── app.py                   # หน้าจอและวงจรการทำงานของแอป
│   ├── config.py                # Host, port และการตรวจใบรับรอง
│   ├── network.py               # TLS Socket, receive worker และส่ง Event ให้ UI
│   ├── session.py               # ตัวตนผู้ใช้และสถานะเชื่อมต่อ
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── login_view.py
│   │   ├── register_view.py
│   │   ├── chat_view.py
│   │   ├── sidebar.py
│   │   ├── ai_panel.py
│   │   ├── search_dialog.py
│   │   ├── group_dialog.py
│   │   ├── file_dialog.py
│   │   └── theme.py
│   └── assets/icons/
├── server/
│   ├── __init__.py
│   ├── main.py                  # Bind/listen และรับ Client
│   ├── config.py               # Environment ฝั่ง Server
│   ├── connection.py           # ตัวตนต่อ Socket, cleanup และล็อกการเขียน
│   ├── router.py               # Dispatch คำขอไป Handler
│   ├── database.py             # Connection, transaction และ query
│   ├── schema.sql
│   ├── passwords.py            # Argon2id
│   ├── permissions.py          # ตรวจสิทธิ์ร่วมทุกฟีเจอร์
│   ├── ai_service.py           # Adapter เรียก AI API
│   └── handlers/
│       ├── __init__.py
│       ├── auth.py
│       ├── chat.py
│       ├── groups.py
│       ├── files.py
│       ├── history.py
│       └── ai.py
├── shared/
│   ├── __init__.py
│   ├── config.py               # การอ่านและตรวจ Environment ร่วม
│   ├── protocol.py             # Framing, recv_exact และ send_packet
│   ├── message_types.py
│   └── validation.py
├── data/                       # สร้างตอนรัน Server และไม่นำเข้า Git
│   ├── studygroup.db
│   └── uploads/
├── certs/                      # ตั้งค่าภายนอกโค้ด ไม่ commit กุญแจจริง
├── scripts/
│   └── generate-dev-certs.sh   # สร้าง Local CA และ localhost certificate
├── tests/
│   ├── test_config.py
│   ├── test_protocol.py
│   ├── test_auth.py
│   ├── test_permissions.py
│   └── test_chat_integration.py
├── deploy/
│   ├── Dockerfile
│   └── compose.yaml
└── docs/
    ├── setup.md                # เตรียม environment ด้วย uv
    ├── architecture.md
    ├── protocol.md
    ├── demo-checklist.md
    ├── reference/socket-programming-assignment.pdf
    └── prototypes/
        ├── README.md
        ├── THIRD_PARTY_NOTICES.txt
        ├── studygroup-desktop.html
        ├── studygroup-desktop.fragment.html
        ├── studygroup-focus.png
        ├── studygroup-focus-ai.png
        └── studygroup-workspace.png
```

หาก `database.py` โตมากค่อยแยก Repository ไม่ต้องเพิ่ม Layer หรือ Framework ล่วงหน้า ส่วน `work/` ที่มีอยู่เป็นไฟล์ทดลองจากการออกแบบ ไม่ใช่ Application Source และไม่ต้องย้ายเข้า Package จริง

## 6. Authentication และ Authorization

- สมัครด้วย Username, Password, Confirm Password ใช้ `user_id` ถาวรอ้างอิงข้อมูล ชื่อผู้ใช้มีค่า Normalize สำหรับตรวจซ้ำ และมี UNIQUE constraint ในฐานข้อมูล
- เสนอ Username 3–24 ตัว ใช้อักษรอังกฤษ ตัวเลข และ `_` โดยไม่แยกตัวพิมพ์เล็ก/ใหญ่ แสดงชื่อเดิมได้ แต่ไม่สร้างสองบัญชีด้วยชื่อที่ต่างกันแค่ตัวพิมพ์
- Hash Password ด้วย Argon2id ผ่าน `argon2-cffi` ให้ Library สร้าง Salt และตรวจ Hash ฝั่ง Server ห้ามเก็บ Password ตรง ๆ หรือใช้ SHA-256 อย่างเดียว
- Password ยาว 8–128 Unicode characters ไม่เกิน 512 UTF-8 bytes และไม่มี NUL;
  ไม่ Trim/Normalize และ Confirm ต้องตรงกัน สมัครแล้ว Login แยกตามสัญญา CP04
- ส่ง Credentials หลัง TLS handshake และตรวจ Certificate chain/Hostname ของ Server แล้วเท่านั้น สำหรับ Local ให้เชื่อถือ CA ทดสอบอย่างชัดเจน ไม่ปิด Certificate verification
- ก่อน Login อนุญาตเฉพาะคำขอที่จำเป็น เช่น REGISTER และ LOGIN หลัง Login ผูก `user_id` กับ Connection Object ไม่เชื่อ `sender_id` หรือ Username ที่ Client อ้างมาในคำขอแชต
- ปฏิเสธการ Login ซ้อนของบัญชีเดียวกันโดยไม่ตัด Session เดิม การตรวจและลงทะเบียน Session ต้องทำอย่างเป็นอะตอม ภายใต้ Lock
- Logout, Socket EOF และ Error ต้อง Cleanup Session และแจ้งรายชื่อออนไลน์ใหม่ ล้าง Registry เฉพาะเมื่อยังอ้างถึง Connection เดียวกัน ป้องกัน Cleanup เก่าไปล้าง Session ใหม่
- ข้อความ Login ผิดใช้ข้อความรวม จำกัดความถี่การลอง Login และไม่เขียนรหัสผ่าน/Key ลง Log
- MVP ไม่เก็บ Password บนเครื่อง Client และไม่ทำ Remember Password เมื่อเชื่อมต่อใหม่ให้ Login ใหม่ ไม่ต้องมี JWT สำหรับทุก Packet เพราะตัวตนผูกกับ Socket อยู่แล้ว
- รายชื่อออนไลน์หมายถึงผู้ที่ Login และยังมี Connection ไม่ใช่รายชื่อบัญชีทั้งหมดใน Database

ทุกการส่ง/อ่านข้อความ โหลดประวัติ ค้นหาไฟล์ ดาวน์โหลด และสรุป AI ต้องตรวจสิทธิ์ที่ Server ห้องส่วนตัวจำกัดคู่สนทนา ห้องกลุ่มจำกัดสมาชิก รายชื่อกลุ่มและสมาชิกเปิดดูได้ตาม R9 แต่เนื้อหายังต้องตรวจสิทธิ์

## 7. ข้อมูลและการเก็บถาวร

| ตาราง | ข้อมูลหลักและข้อบังคับ |
| --- | --- |
| users | id, username, username_normalized UNIQUE, password_hash, created_at |
| rooms | id, kind: private/group, name, created_by, created_at และคู่ user_id แบบเรียงลำดับสำหรับ private room ที่บังคับไม่ซ้ำ |
| room_members | room_id + user_id เป็นคีย์ร่วม, joined_at, visible_after_message_id เป็นขอบเขตประวัติที่เห็น |
| messages | id แบบเรียงเพิ่ม, room_id, sender_id, kind: text/file, text, created_at |
| attachments | id, message_id, stored_name, original_name, size_bytes, sha256 และสถานะการรับไฟล์ |

ตั้ง Foreign keys และ Index ให้รองรับการค้นตามห้อง/ลำดับข้อความ/วันที่ ห้องส่วนตัวหนึ่งคู่ใช้ห้องเดิมเสมอ ไม่สร้างซ้ำทุกครั้งที่คลิกชื่อ

เมื่อคนใหม่เข้ากลุ่ม ให้บันทึก Message ID ล่าสุดของห้องเป็น `visible_after_message_id` ใน Transaction และคืนเฉพาะข้อความที่ ID มากกว่าขอบเขตนั้น ผู้สร้างห้องและคู่สนทนาส่วนตัวเริ่มที่ 0 ขอบเขตนี้ใช้กับไฟล์แนบและ Input ของ AI ด้วย

ใช้ SQLite บน Disk Local ของ Server ตั้ง Busy timeout และพิจารณา WAL ใช้ Connection แยกตาม Worker/Thread ไม่แชร์ SQLite Connection เดียวข้าม Thread แบบไม่มีการจัดการ ใช้ Parameterized queries และ Transaction สำหรับการสร้างห้อง การ Join และการส่งข้อความ

ข้อมูลใน `data/` ต้องอยู่ต่อหลัง Restart/Recreate Container ให้ Mount Persistent volume และมีขั้นตอน Backup/Restore ที่ครอบคลุม Database กับไฟล์แนบอย่างสอดคล้องกัน ห้ามเก็บข้อมูลจริงไว้เฉพาะใน Container image

## 8. Protocol และงานพร้อมกัน

ใช้ TCP แบบมี Framing: **Header 4 bytes แบบ unsigned big-endian ระบุจำนวน bytes ของ JSON UTF-8 ตามด้วย Body** กำหนดขนาด Frame สูงสุด เช่น 1 MiB และปฏิเสธค่าที่เกินก่อน Allocate Buffer

ต้องมี `recv_exact(n)` รับ Header/Body ให้ครบ รองรับข้อความที่ถูกแบ่งหลาย `recv()` และหลาย Frame ที่มาติดกัน ห้ามถือว่า `recv()` หนึ่งครั้งเท่ากับข้อความหนึ่งรายการ ใช้ `sendall()` และมี Lock หรือ Writer Queue ต่อ Connection เพื่อไม่ให้ Packet จากหลาย Thread แทรกกัน

ตัวอย่างคำขอ:

```json
{"v":1,"id":"req-42","type":"MESSAGE_SEND","data":{"room_id":12,"text":"ประชุมตอนสองทุ่มนะ"}}
```

ตัวอย่างคำตอบ:

```json
{"v":1,"id":"req-42","type":"RESPONSE","data":{"ok":true,"result":{"message_id":205}}}
```

ตัวอย่าง Event:

```json
{"v":1,"type":"MESSAGE_NEW","data":{"message_id":205,"room_id":12,"sender_id":3,"text":"ประชุมตอนสองทุ่มนะ","created_at":"2026-11-02T13:00:00Z"}}
```

ใช้ Request ID ผูกคำตอบกับคำขอ Error มี Code ที่ Client แปลเป็นข้อความที่อ่านรู้เรื่องได้ เช่น `AUTH_REQUIRED`, `FORBIDDEN`, `INVALID_INPUT` และ `AI_UNAVAILABLE`

| กลุ่มคำสั่ง | ตัวอย่าง |
| --- | --- |
| Auth | REGISTER, LOGIN, LOGOUT |
| Users/Rooms | USERS_LIST, PRIVATE_ROOM_OPEN, GROUP_CREATE, GROUP_LIST, GROUP_JOIN |
| Chat/History | MESSAGE_SEND, HISTORY_GET, HISTORY_SEARCH |
| Files | FILE_BEGIN, FILE_CHUNK, FILE_END, FILE_GET |
| AI | AI_SUMMARIZE |
| Events | USERS_UPDATED, GROUPS_UPDATED, MESSAGE_NEW |

Client ใช้ Receive Worker และ `queue.Queue` ส่งผลเข้า Tkinter ผ่าน `after()` แก้ไข Widget ใน Main Thread เท่านั้น งาน Network, File และ AI ต้องไม่ทำให้ GUI ค้าง Server รองรับหลาย Client และแยกงาน AI ที่อาจช้าออกจากวงจรรับคำขอด้วย Worker ที่จำกัดจำนวน

## 9. รายละเอียดฟีเจอร์พิเศษ

**AI:** ส่งเฉพาะข้อความกลุ่มที่ผู้ขอมีสิทธิ์และไม่เกิน 50 ข้อความล่าสุดไปโมเดล โดยเรียงเก่าไปใหม่ ไม่ส่ง Password, API Key หรือห้องอื่นไปด้วย ให้ข้อความแชตเป็นข้อมูลสำหรับสรุป ไม่ใช่คำสั่งเปลี่ยนพฤติกรรมโมเดล สรุปประเด็น ข้อตกลง งาน/ผู้รับผิดชอบ และกำหนดส่ง หากไม่มีข้อมูลให้ระบุว่าไม่ระบุ ห้ามแต่งข้อมูลเพิ่ม ผลสรุปต้องติดป้ายว่าเป็น AI และตรวจสิทธิ์อีกครั้งก่อนส่งผลกลับ ไม่ประกาศผลอัตโนมัติให้ห้องอื่น

ตั้ง Timeout และจำกัดการเรียกซ้ำ เมื่อ API ไม่พร้อมหรือยังไม่ตั้งค่า ให้แสดง Error ที่เหมาะสมและให้แชตใช้งานต่อได้ อนุญาต Mock เฉพาะ Test/Demo mode ที่ติดป้ายชัดเจน แต่จะถือว่าผ่านฟีเจอร์ AI ต่อเมื่อเรียกโมเดลจริงได้ เลือก Provider/Model และกำหนดราคาเมื่อมีบัญชีที่ผู้ใช้ต้องการใช้

**ไฟล์:** จำกัดขนาด 5 MiB ส่งเป็น Chunk ผ่าน Socket เดียวกัน เช่น Binary 32 KiB เข้ารหัส Base64 ใน JSON โดยนับขนาดไฟล์จริงหลัง Decode แยก Transfer ID กับ Message ID กำหนดลำดับ Chunk/ยอดรวมและตรวจ SHA-256 เมื่อครบ ใช้ชื่อจัดเก็บที่ Server สร้างเอง ไม่ใช้ Path จาก Client เมื่อรับครบค่อย Publish Attachment หากหลุดระหว่างทางให้ Cleanup ไฟล์ชั่วคราว คำขอดาวน์โหลดต้องตรวจสมาชิกและขอบเขตข้อความของไฟล์นั้นเสมอ

**ประวัติและค้นหา:** เก็บข้อความก่อนตอบรับสำเร็จ ค้นหาในห้องปัจจุบันตามคำและช่วงวันที่ รองรับ Pagination โดยใช้ Message ID/เวลา แปลงวันที่ของผู้ใช้เป็นช่วง UTC ก่อน Query และใช้เงื่อนไขสิทธิ์เดียวกับประวัติปกติ

**Cloud:** เตรียม Dockerfile และ Compose สำหรับ Server เปิด TCP Port ที่กำหนด เช่น 5000 รองรับ TLS และ Mount `data/` ถาวร SQLite อยู่เครื่องเดียวกับ Server ภายใน Volume ไม่มี Database Port สาธารณะ Deploy จริงเมื่อมี Provider/เครื่อง/Domain/Certificate และสิทธิ์ที่จำเป็น การมีไฟล์ Deploy อย่างเดียวยังไม่ถือว่าทำฟีเจอร์ Cloud สำเร็จ

## 10. GUI ที่ต้องพัฒนา

รายละเอียดการกดต้นแบบและข้อจำกัดอยู่ที่ [Prototype README](docs/prototypes/README.md)

- **Focus:** Sidebar ซ้ายเป็นผู้ใช้ออนไลน์/กลุ่ม ตรงกลางเป็นห้องแชต AI เปิดเมื่อกดและแสดงเป็นแผงในห้อง เป็นแบบเริ่มต้น
- **Workspace:** Sidebar + Chat + AI ด้านขวา เป็นแบบเปรียบเทียบสำหรับหน้าต่างกว้าง
- ใช้สีม่วงเป็น Accent พื้นหลังเรียบ ตัวอักษรอ่านง่าย อวตารย่อชื่อ ปุ่มมี Label/Tooltip และสถานะเชื่อมต่อชัดเจน
- หน้าต่างจริงใช้ Native title bar ของ OS ไม่ต้องวาดปุ่มปิด/ย่อปลอมตามภาพ Prototype
- แยก Private/Group room ทุกห้องมีช่องพิมพ์และข้อความเข้า–ออก Enter ส่ง, Shift+Enter ขึ้นบรรทัดใหม่
- รายชื่อผู้ใช้ออนไลน์รวมตนเอง รายชื่อกลุ่มแสดงสมาชิก ปุ่มสร้างกลุ่มไม่มีช่องเพิ่มสมาชิกอัตโนมัติ
- Tab แชต/ไฟล์ ปุ่มค้นหา ปุ่ม AI และ Dialog สมาชิก/สร้างกลุ่ม/เข้าร่วม/รายละเอียดไฟล์
- เพิ่ม Login/Register และการตั้งค่า Server ก่อนหน้าจอแชต เพราะสองหน้า Auth ยังไม่มีอยู่ใน Prototype เดิม
- UI ต้องมี Loading, Empty, Error, Reconnecting/Disconnected, Progress รับ–ส่งไฟล์ และสถานะ AI ไม่พร้อม
- ขณะ Disconnect ห้ามแสดงว่าข้อความส่งสำเร็จและห้ามส่งซ้ำเงียบ ๆ หลังต่อใหม่ รักษา Draft ให้ผู้ใช้ตัดสินใจส่งใหม่
- ภาษา UI หลักเป็นไทย ใช้ชื่อเทคนิคอังกฤษเมื่อเหมาะสม รองรับข้อความไทย/Unicode จริง
- ไม่ฝัง HTML นี้ใน WebView เพื่อแทนการทำ Tkinter การเปิด HTML ใน Browser เป็นเพียงวิธีตรวจแบบก่อนพัฒนา Desktop

## 11. ลำดับพัฒนาและการตรวจรับ

1. **รากฐาน:** สร้าง Packages, Config, Protocol และ SQLite Schema ทดสอบ TCP Framing ที่แตก/รวม Frame รวมถึง EOF กลาง Frame และขนาดเกิน
2. **Auth:** ทำ TLS, Register/Login/Logout และ Online Registry ทดสอบชื่อซ้ำแบบ Case-insensitive, รหัสผ่านผิด, Login ซ้อน และ Cleanup เมื่อหลุด
3. **แชตพื้นฐาน:** เชื่อม Tkinter กับ Server ทำ Private room, Group create/list/join, Membership check และ Live Events ให้ R1–R11 ครบก่อนฟีเจอร์พิเศษ
4. **ประวัติและค้นหา:** โหลดข้อความหลัง Login ใหม่ เก็บ Draft/UI ไม่ค้าง และตรวจว่าคนนอก/สมาชิกที่ยังไม่ถึงขอบเขตประวัติอ่านข้อมูลไม่ได้
5. **ไฟล์:** ทดสอบส่งและดาวน์โหลดจริง Hash ตรงกัน ตรวจขนาด ไฟล์ไม่ครบ และการเดา Attachment ID ของห้องอื่น
6. **AI:** ทดสอบ Adapter ด้วย Mock ที่แยกชัดเจน จากนั้นสาธิต API จริง ตรวจ Timeout, ขอบเขตข้อความและผลที่ไม่มีการแต่งผู้รับผิดชอบ/วันส่ง
7. **Cloud:** ตั้ง Server บนเครื่องจริงของ Provider, TLS, Volume และ Backup ตรวจว่าข้อมูลยังอยู่หลัง Restart/อัปเดต
8. **เดโม:** ใช้ 3 Clients บนคอมพิวเตอร์จริงอย่างน้อย 2 เครื่อง A/B สนทนา C เป็นคนนอกห้อง เพื่อพิสูจน์สิทธิ์ จากนั้นทดสอบคนละเครือข่ายผ่าน Cloud
9. **ส่งงาน:** อัปเดต README, สถาปัตยกรรม, Protocol, Demo checklist และสไลด์ Implementation Explanation ด้วยผลที่ทดสอบจริง

มี Unit/Integration Tests สำหรับ Protocol, Authentication, Authorization และการส่งข้อมูลจริง ไม่ต้องเขียน Test ที่เพียงตรวจว่าสีหรือข้อความ Static ตรงกับ Prototype และการทดสอบหลาย Process บนเครื่องเดียวไม่แทนข้อกำหนดคอมพิวเตอร์จริงสองเครื่อง

คำสั่งเป้าหมายหลังพัฒนาเสร็จ จาก Root โปรเจกต์:

```bash
uv run --locked --env-file .env python -m server.main
uv run --locked --env-file .env python -m client.main
uv run --locked pytest
```

เปิด `server.main` และ `client.main` ได้แล้ว การตรวจรับ CP06 ดู docs/demo-checklist.md
รัน `uv run --locked pytest` เพื่อตรวจ Config, Protocol, SQLite, สิทธิ์เข้าถึงข้อมูล
และ Authentication ผ่าน TCP/TLS จริงได้

Environment ฝั่ง Server ที่ควรเตรียม: `STUDYGROUP_HOST`, `STUDYGROUP_PORT`, `STUDYGROUP_DATA_DIR`, `STUDYGROUP_TLS_CERT`, `STUDYGROUP_TLS_KEY`, `STUDYGROUP_AI_PROVIDER`, `STUDYGROUP_AI_MODEL`, `STUDYGROUP_AI_API_KEY` และ Timeout/Limit ตามจำเป็น ส่วน Client มีเพียง Host, Port และ Trust configuration ไม่มี AI Key หรือ Server private key

## 12. คำสั่งเริ่มต้นสำหรับ Codex รอบพัฒนา

> อ่าน DEVELOPMENT.md เพื่อดูงานถัดไป แล้วอ่าน HANDOFF.md และ docs/prototypes/README.md จากนั้นพัฒนา StudyGroup เป็น Python Desktop Application ด้วย Tkinter และ TCP Socket + TLS ตามข้อกำหนด R1–R11 และฟีเจอร์พิเศษทั้ง 4 ใช้ Focus เป็นแบบเริ่มต้น เก็บ SQLite และไฟล์บน Server ใช้ Argon2id สำหรับ Password และตรวจสิทธิ์ทุกคำขอ เริ่มทำส่วนที่ทดสอบ Local ได้ก่อน แยก Prototype/Mock ออกจากการทำงานจริง อัปเดตเอกสารตามผลจริงและบันทึก checkpoint/งานต่อใน DEVELOPMENT.md เมื่อจบ session ระบุเฉพาะข้อมูลบริการภายนอกที่ยังต้องการจากผู้ใช้ อย่าเปลี่ยนเป็น Web App หรือแทน Socket ด้วย REST สำหรับการส่งแชต

## 13. แหล่งอ้างอิงทางเทคนิค

- [Python Socket Programming HOWTO](https://docs.python.org/3/howto/sockets.html) — Stream และ Framing
- [Python ssl](https://docs.python.org/3/library/ssl.html) — TLS และการตรวจใบรับรอง
- [Python Tkinter](https://docs.python.org/3/library/tkinter.html) — GUI และ Event loop
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) และ [argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/api.html)
- [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) และ [Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)

ตรวจ API/Dependency ของ Library และ Provider อีกครั้งเมื่อเริ่ม Implementation เวอร์ชัน Dependency สำหรับ Local environment อยู่ใน `pyproject.toml` และ `uv.lock` ส่วน Provider และ Credentials ของบริการภายนอกยังไม่ได้กำหนด
