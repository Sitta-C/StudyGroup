# แผนพัฒนาและจุดตรวจรับ StudyGroup

ใช้ไฟล์นี้เป็นจุดเริ่มต้นและบันทึกความคืบหน้าของทุก session ตั้งแต่ Local development
จนถึงเดโมและส่งงาน อัปเดตสถานะตามผลที่ทำและทดสอบจริง เพื่อให้ session ถัดไปทำต่อได้ทันที
ข้อกำหนดและรายละเอียดสถาปัตยกรรมอยู่ใน [HANDOFF.md](HANDOFF.md)
ส่วนการเตรียมเครื่องและคำสั่ง uv อยู่ใน [docs/setup.md](docs/setup.md)

## สถานะสำหรับเริ่ม session ถัดไป

- อัปเดตล่าสุด: 6 พฤศจิกายน 2026 ตามเวลา Asia/Bangkok
- ผ่านแล้ว: CP00 เตรียม Local environment ด้วย uv, CP01 Packages และ Config,
  CP02 Socket Protocol, CP03 SQLite/สิทธิ์เข้าถึงข้อมูล, CP04 TLS/Authentication
  และ CP05 Chat Server สำหรับแชตส่วนตัวและกลุ่ม
- งานปัจจุบัน: **CP06 Tkinter และตรวจรับ R1–R11 — IN_PROGRESS**
- สถานะโค้ด: มี Config, Socket Protocol, SQLite Schema/Transaction/สิทธิ์ร่วม,
  TLS Server, Router, Auth/Chat handlers และ Online registry พร้อม Desktop Client Tkinter
  แบบ Focus, Register/Login/Server settings, Private/Group chat, Draft และ Disconnect/Re-login
  ชุดทดสอบหลัก 378 กรณีผ่าน (ชุดเดิม 352 + Client integration 21 + LAN certificate 5)
  และตรวจ GUI จริงแยกอีก 3 กรณีผ่าน ดูบันทึก CP06 ด้านล่าง
- สิ่งที่ยังต้องเลือก: AI Provider/Model และ Cloud Provider
- สิ่งที่ยังต้องเตรียมภายหลัง: AI Key/งบใช้งาน, เครื่อง Cloud/สิทธิ์เข้าถึง/TLS,
  และคอมพิวเตอร์จริงอย่างน้อย 2 เครื่องสำหรับตรวจรับ
- งานถัดไปเพื่อปิด CP06: ทำตาม docs/demo-checklist.md บนคอมพิวเตอร์จริงสองเครื่อง
  เก็บหลักฐาน R1–R11 พร้อมตรวจ Thai IME/Copy-Paste และการหลุดบน LAN จริง
  เตรียม LAN certificate ด้วย scripts/generate-lan-cert.sh ได้แล้ว ไม่ต้องรอบัญชี AI หรือ Cloud

เมื่อจบแต่ละ session ให้แก้ส่วนนี้ ตาราง checkpoint และเพิ่มบันทึก session ด้านล่าง
พร้อมกัน ไม่คัดลอกสถานะไปดูแลหลายชุดใน README หรือ HANDOFF

## วิธีทำงานในแต่ละ session

1. อ่านส่วนสถานะล่าสุด ตาราง checkpoint และบันทึก session ล่าสุดในไฟล์นี้
   ตรวจ `AGENTS.md` หากมี แล้วอ่านหัวข้อใน HANDOFF และ Prototype ที่เกี่ยวข้องกับงาน
2. ตรวจไฟล์จริงและการแก้ไขที่ค้างอยู่ หากมี Git ให้ตรวจ `git status` และ diff
   รักษางานเดิมของผู้ใช้ และเทียบสภาพจริงกับสถานะในเอกสารก่อนเริ่ม
3. เลือก checkpoint แรกที่ยังไม่ผ่านและมี dependency พร้อม เปลี่ยนเป็น `IN_PROGRESS`
   ระบุเป้าหมายย่อยของ session นี้ โดยหนึ่ง checkpoint อาจใช้หลาย session
4. พัฒนาและทดสอบเฉพาะขอบเขตที่เลือก ใช้ `uv add` และ `uv add --dev` เมื่อเพิ่ม dependency
   พร้อมเก็บ `pyproject.toml` และ `uv.lock` ให้ตรงกัน
5. บันทึกคำสั่ง ผลตรวจ และข้อจำกัดจริง ไม่ถือว่ามีไฟล์หรือมี Mock แล้วเท่ากับฟีเจอร์ผ่าน
   รันชุดทดสอบที่มีอยู่และเกี่ยวข้อง รวมการทดสอบส่วนเดิมที่การแก้ไขอาจกระทบ
6. จบ session ด้วยการอัปเดตไฟล์นี้ ระบุไฟล์สำคัญที่เปลี่ยน งานค้าง และก้าวแรกที่ชัดเจน
   สำหรับ session ถัดไป หากตัดสินใจเปลี่ยนข้อกำหนดให้บันทึกเหตุผลและแก้ HANDOFF ให้ตรงกัน

ใช้สถานะ `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE` เท่านั้น
`DONE` หมายถึงเกณฑ์ผ่านครบและมีหลักฐานในบันทึก session
หากมีปัญหาที่ต้องรอข้อมูลหรือบริการภายนอก ให้ใช้ `BLOCKED` พร้อมระบุสิ่งที่ต้องการ
และทำงานส่วนอื่นที่ไม่ขึ้นต่อปัญหานั้นได้ต่อ โดยยังไม่ประกาศว่าขั้นที่ติดขัดผ่านแล้ว

## ตาราง checkpoint

| จุดตรวจรับ | งาน | เริ่มหลัง | สถานะ | หลักฐานหรือสิ่งที่ค้าง |
| --- | --- | --- | --- | --- |
| CP00 | Environment ด้วย uv | ไม่มี | DONE | ผลตรวจรอบ setup อยู่ในบันทึกเริ่มต้นและ docs/setup.md |
| CP01 | Packages และ Config | CP00 | DONE | `tests/test_config.py`: 69 passed; import, defaults และ Config จาก Local `.env` ผ่าน ดูบันทึก CP01 |
| CP02 | Socket Protocol | CP01 | DONE | `tests/test_protocol.py`: 83 passed ผ่าน TCP loopback จริง; ดูสัญญาใน docs/protocol.md และบันทึก CP02 |
| CP03 | SQLite และสิทธิ์เข้าถึงข้อมูล | CP02 | DONE | Database 51 + Permissions 31 passed ด้วย Temporary SQLite; Constraints/Reopen/Rollback/Join contention ผ่าน ดู docs/database.md และบันทึก CP03 |
| CP04 | TLS และ Authentication | CP03 | DONE | Auth 19 + TLS integration 60 passed ผ่าน TCP/TLS จริง รวม CA/Hostname/Expired cert, Login ซ้อน, Cleanup และ CLI; ดู docs/authentication.md และบันทึก CP04 |
| CP05 | Server สำหรับแชตส่วนตัวและกลุ่ม | CP04 | DONE | Chat integration 39 passed ผ่าน TCP/TLS จริงด้วย Clients A/B/C; Private/Group/Join boundary/Actor spoofing/Event isolation/Restart ผ่าน ดู docs/chat.md และบันทึก CP05 |
| CP06 | Tkinter และตรวจรับ R1–R11 | CP05 | IN_PROGRESS | Desktop Client/Worker และ GUI checks ผ่าน Local; มี architecture/demo-checklist/ภาพจริง; ยังรอ R1–R11 บนสองเครื่องจริง |
| CP07 | ประวัติและการค้นหา | CP06 | TODO | ฟีเจอร์พิเศษข้อ 1 |
| CP08 | ส่งและดาวน์โหลดไฟล์ | CP07 | TODO | ฟีเจอร์พิเศษข้อ 2 |
| CP09 | AI สรุปบทสนทนา | CP08 | TODO | ทำ Adapter/Mock ก่อน แล้วตรวจ API จริง |
| CP10 | Cloud deployment | CP09 | TODO | เตรียมไฟล์ Deploy ได้ก่อนเมื่อส่วน Server พร้อม |
| CP11 | เดโมครบระบบ | CP10 | TODO | ต้องมี 3 Clients บนอย่างน้อย 2 เครื่องจริง |
| CP12 | เอกสารและชุดส่งงาน | CP11 | TODO | ต้องอ้างผลตรวจจริง |

คอลัมน์เริ่มหลังคือลำดับหลักสำหรับตรวจรับ พัฒนาเอกสาร ทดสอบ และเตรียม Adapter/Deploy
ควบคู่กับงานที่พร้อมแล้วได้ หาก AI API ยังไม่พร้อม สามารถทำ Cloud ต่อเมื่อ CP08 ผ่าน
และ Server พร้อม โดยคง CP09 ไว้ตามสถานะจริง
การตรวจคะแนนต้องผ่าน Part 1 ก่อน Part 2 และ Part 2 ก่อน Part 3 ตาม HANDOFF

## ขอบเขตและเกณฑ์ผ่านแต่ละ checkpoint

### CP00 Environment ด้วย uv

**งาน:** เตรียม Python/Tkinter, dependencies, Local config, ที่เก็บข้อมูล และ Local TLS

**ผ่านเมื่อ:** uv สร้างและ sync `.venv` ตาม lock ได้, Tkinter สร้างหน้าต่างได้,
Argon2id Hash/Verify และ SQLite ทำงาน, TLS ตรวจ CA/Hostname ได้
พร้อมแยก `.env`, private keys และ runtime data ออกจากไฟล์ที่นำเข้า Git

**หลักฐานที่มีแล้ว:** Python 3.14.10, Tcl/Tk 9.1.0, `argon2-cffi` 25.1.0,
`pytest` 9.2.0, `uv.lock`, `.env.example`, สคริปต์ Local TLS และผลตรวจใน
[คู่มือ setup](docs/setup.md) เป็นผลของ environment ไม่ใช่การตรวจรับแอป

### CP01 Packages และ Config

**งาน:** สร้าง `client/`, `server/`, `shared/` และโครงสร้างทดสอบตามความจำเป็น
เริ่ม `client/config.py` และ `server/config.py` ให้มีค่าเริ่มต้นและตรวจ Config
ใช้ Host/Port/Paths จาก Environment ตาม `.env.example`

**ผ่านเมื่อ:** import Packages ได้, อ่าน Config ได้ทั้งค่าปกติและกรณีข้อมูลไม่ถูกต้อง,
Port/Path ที่ผิดให้ข้อผิดพลาดชัดเจน และ Client ใช้เพียง Host/Port/Trust configuration
โดยไม่ต้องมี AI Key หรือ Server private key
อัปเดตตัวแปร Config ใหม่ใน `.env.example` และคู่มือ setup

**หลักฐาน:** คำสั่งตรวจ import และผลทดสอบ Config รวมกรณีไม่มีตัวแปร/ค่าไม่ถูกต้อง
ยังไม่ต้องสร้างฟีเจอร์แชตหรือเปิด Server เปล่าเพื่อประกาศว่าแอปพร้อมใช้

### CP02 Socket Protocol

**งาน:** ทำ `shared/protocol.py`, ประเภทคำขอ/Event และ Validation
ใช้ Header unsigned big-endian 4 bytes ตามด้วย JSON UTF-8,
`recv_exact`, `sendall`, Request ID และ Error Code
กำหนดขนาด Frame สูงสุด เช่น 1 MiB และ Lock หรือ Writer Queue ต่อ Connection
บันทึกสัญญาการสื่อสารใน `docs/protocol.md`

**ผ่านเมื่อ:** ส่งข้อความไทย/Unicode ได้ รับ Frame ที่แตกหลายส่วนหรือหลาย Frame
ที่มาติดกันได้ แยก EOF ปกติกับ EOF กลาง Frame และปฏิเสธ Frame ใหญ่เกิน/JSON ผิดรูป
โดยไม่ Allocate ตามค่าที่เกิน Limit การเขียนพร้อมกันไม่ทำให้ Packet แทรกกัน

**หลักฐาน:** `tests/test_protocol.py` ทดสอบผ่านด้วยข้อมูลรับส่งจริงผ่าน Socket
พร้อมตัวอย่าง Request/Response/Event ในเอกสาร

### CP03 SQLite และสิทธิ์เข้าถึงข้อมูล

**งาน:** ทำ `server/schema.sql`, `database.py` และส่วนตรวจสิทธิ์ร่วม
ตาราง `users`, `rooms`, `room_members`, `messages`, `attachments`
พร้อม Foreign keys, Index, Parameterized queries และ Transaction
เก็บเวลาตาม UTC และใช้ Connection แยกตาม Worker/Thread

**ผ่านเมื่อ:** Initialize ฐานข้อมูลซ้ำโดยไม่ทำข้อมูลเดิมหาย,
ชื่อผู้ใช้แบบ Normalize ไม่ซ้ำ และคู่สนทนาส่วนตัวมีห้องเดียว
การ Join บันทึก `visible_after_message_id` ใน Transaction
Query สิทธิ์แยกสมาชิก คนนอก และสมาชิกใหม่ได้ตามขอบเขตใน HANDOFF

**หลักฐาน:** ทดสอบ Constraints, Rollback และการเปิด Database เดิมใหม่ด้วยฐานข้อมูล
ชั่วคราวสำหรับทดสอบ ไม่ใช้ข้อมูลจริงใน `data/` เป็น Fixture

### CP04 TLS และ Authentication

**งาน:** ทำ Server รับหลาย Clients ผ่าน TCP/TLS, Router และ Connection lifecycle
รองรับ Register/Login/Logout, Argon2id, Registry ของผู้ที่ Login แล้ว
และ Events รายชื่อออนไลน์

**ผ่านเมื่อ:** Client ตรวจ CA/Hostname ก่อนส่ง Credentials,
คำขอที่ต้องล็อกอินถูกปฏิเสธเมื่อยังไม่ยืนยันตัวตน,
ชื่อซ้ำต่างตัวพิมพ์ถูกปฏิเสธ และรหัสผ่านเก็บเป็น Argon2id Hash
ปฏิเสธ Login ซ้อนอย่างเป็นอะตอมโดยไม่ตัด Session เดิม
Logout/EOF/Error ล้าง Session ถูกตัวและแจ้งออนไลน์ใหม่รวมตัวผู้ใช้เอง
มีข้อจำกัดการลอง Login และไม่บันทึกรหัสผ่านหรือ Key ลง Log

**หลักฐาน:** Unit/Integration Tests ครอบคลุมรหัสผ่านผิด, Login ซ้อนพร้อมกัน,
Certificate ไม่ถูกต้อง, การปลอมตัวตนใน Packet และ Cleanup เก่าไม่ล้าง Session ใหม่
ผลทดสอบ TLS ของ CP00 อย่างเดียวไม่ถือว่าผ่านขั้นนี้

### CP05 Server สำหรับแชตส่วนตัวและกลุ่ม

**งาน:** ทำรายชื่อออนไลน์ เปิดห้องส่วนตัว สร้าง/แสดง/เข้าร่วมกลุ่ม
ส่งข้อความและ Live Events โดยผูกผู้ส่งกับ Connection ที่ Login
บันทึกข้อความก่อนตอบรับสำเร็จและตรวจสิทธิ์ทุกคำขอ

**ผ่านเมื่อ:** ห้องส่วนตัวใช้ห้องเดิมและมีเฉพาะคู่สนทนาเห็นข้อความ
ทุกคนเห็นรายชื่อกลุ่มและสมาชิกได้ ผู้สร้างเป็นสมาชิกคนแรกเพียงคนเดียว
คนอื่นเข้าร่วมด้วยตนเองและเฉพาะสมาชิกเท่านั้นที่ส่ง/อ่านข้อความกลุ่มได้
Client C ที่อยู่นอกห้องไม่ได้รับ Event หรือข้อมูลของห้อง A/B

**หลักฐาน:** Integration Tests หลาย Connections จริง รวมคำขอที่เดา Room ID
และปลอม Sender ID พร้อมตรวจว่าข้อมูลที่ตอบกลับและ Event ไม่รั่วไปยังคนนอก

### CP06 Tkinter และตรวจรับ R1 ถึง R11

**งาน:** ทำหน้า Login/Register, ตั้งค่า Server และหน้าหลักแบบ Focus
เชื่อม Receive Worker กับ `queue.Queue` และ Tkinter `after()`
ทำ Sidebar, ห้องส่วนตัว/กลุ่ม, ช่องพิมพ์, รายชื่อสมาชิกและสถานะเชื่อมต่อ
เริ่ม `docs/architecture.md` และ `docs/demo-checklist.md`

**ผ่านเมื่อ:** ทุก Widget เปลี่ยนจาก Main Thread, Network ไม่ทำ GUI ค้าง,
ข้อความไทยใช้ได้, Enter ส่งและ Shift+Enter ขึ้นบรรทัดใหม่
Loading/Empty/Error/Disconnected แสดงตรงสถานะจริง
เมื่อหลุดเก็บ Draft ไม่แสดงว่าส่งสำเร็จและไม่ส่งซ้ำเงียบ ๆ
ทดสอบ R1–R11 ทีละข้อ โดยมีอย่างน้อย 2 Clients บนคอมพิวเตอร์จริงคนละเครื่อง
และอธิบายสถาปัตยกรรมกับการใช้ Socket ได้

**หลักฐาน:** Checklist R1–R11 พร้อมผลและภาพหน้าจอจริง รายละเอียดเครื่อง/เครือข่าย
และผลทดสอบ Client A/B/C เพื่อตรวจสิทธิ์ หากทดลองได้เพียงหลาย Process บนเครื่องเดียว
ให้บันทึกเป็นผล Local และยังไม่เปลี่ยน CP06 เป็น `DONE`
สำหรับ LAN ให้เตรียม Server certificate ที่ตรงกับชื่อ/IP จริง ไม่ปิดการตรวจ TLS

### CP07 ประวัติและการค้นหา

**งาน:** โหลดประวัติหลัง Login ใหม่ ค้นด้วยคำ/ช่วงวันที่ในห้องปัจจุบัน
รองรับ Pagination และแปลงช่วงวันที่ผู้ใช้เป็น UTC ก่อน Query

**ผ่านเมื่อ:** ปิดและเปิด Client/Server ใหม่แล้วข้อความยังอยู่
Pagination ไม่ข้ามหรือซ้ำข้อความในกรณีทดสอบที่มีข้อความใหม่ระหว่างโหลด
คนนอกห้องและสมาชิกใหม่อ่าน/ค้นข้อความก่อนขอบเขตที่ตนมีสิทธิ์ไม่ได้
GUI ยังคงตอบสนองระหว่างค้นหา

**หลักฐาน:** Tests การเก็บถาวร/ช่วงวันที่/สิทธิ์/ขอบเขตการ Join และผลสาธิต Restart จริง

### CP08 ส่งและดาวน์โหลดไฟล์

**งาน:** ทำ `FILE_BEGIN`, `FILE_CHUNK`, `FILE_END`, `FILE_GET`
ส่งผ่าน Socket เดียวกับแชต แบ่ง Chunk เช่น Binary 32 KiB เข้ารหัส Base64 ใน JSON
แยก Transfer ID, ตรวจลำดับ/ยอดรวม/SHA-256 และแสดง Progress ใน GUI

**ผ่านเมื่อ:** รับส่งไฟล์ไม่เกิน 5 MiB โดยนับขนาดจริงหลัง Decode
ชื่อจัดเก็บสร้างโดย Server ไม่ใช้ Path จาก Client
Publish Attachment หลังรับครบและ Hash ถูกต้องเท่านั้น
การหลุด/ไฟล์ไม่ครบมี Cleanup และไม่ทำให้แชตเสีย
ดาวน์โหลดตรวจสิทธิ์ห้องและขอบเขตข้อความของไฟล์เสมอ

**หลักฐาน:** ส่งและดาวน์โหลดจริงแล้ว Hash ตรงกัน พร้อม Tests ไฟล์เกินขนาด,
Chunk ผิดลำดับ, Hash ผิด, Path traversal, โอนขาดกลางทาง และเดา Attachment ID ของห้องอื่น

### CP09 AI สรุปบทสนทนา

**งาน:** ทำ Provider Adapter และ Worker ที่จำกัดจำนวน พร้อมปุ่ม/แผง AI ในห้องกลุ่ม
แยก Mock สำหรับ Test/Demo ให้เห็นชัด แล้วเชื่อม API จริงเมื่อมี Provider/Model/Key

**ผ่านเมื่อ:** ส่งเฉพาะข้อความที่ผู้ขอมีสิทธิ์ไม่เกิน 50 ข้อความล่าสุด เรียงเก่าไปใหม่
ผลสรุปครอบคลุมประเด็น ข้อตกลง งาน/ผู้รับผิดชอบและกำหนดส่ง
ช่องที่ไม่มีข้อมูลระบุว่าไม่ระบุ และไม่ทำตามคำสั่งที่แทรกในข้อความแชต
ติดป้าย AI ตรวจสิทธิ์อีกครั้งก่อนส่งผลกลับ และไม่ส่งไปห้องอื่น
เมื่อ Key ไม่พร้อม/Timeout/เรียกถี่ แสดง Error ที่เหมาะสมโดยแชตทำงานต่อได้
ต้องเรียกโมเดลจริงได้จึงถือว่าฟีเจอร์ผ่าน

**หลักฐาน:** Tests Adapter ด้วย Mock, ขอบเขตสิทธิ์และข้อความ,
Timeout/Rate limit พร้อมบันทึก Provider/Model และผลเดโม API จริงที่ไม่มีข้อมูลลับ
หากผ่านเฉพาะ Mock ให้บันทึกงานที่เสร็จและคงสถานะที่ยังไม่ `DONE`

### CP10 Cloud deployment

**งาน:** เตรียม Dockerfile/Compose, Server Config, TCP Port/TLS,
Persistent volume สำหรับ SQLite และ uploads บน Cloud เครื่องเดียวกัน
พร้อมขั้นตอน Backup/Restore ที่ครอบคลุมฐานข้อมูลและไฟล์แนบสอดคล้องกัน

**ผ่านเมื่อ:** Deploy และเชื่อม Desktop Clients ไปยัง Cloud จริงได้ผ่าน TLS
ข้อมูลอยู่ครบหลัง Restart/Recreate Container
กู้คืน Backup แล้วข้อความและไฟล์กลับมาใช้ได้
ไม่เปิด Database Port ให้ Client และไม่มี Key จริงอยู่ใน Image/Source

**หลักฐาน:** คำสั่ง Deploy, Host/Port ที่ใช้ทดสอบ, ผล Restart/Restore
และผลเชื่อมต่อจาก Clients คนละเครือข่าย
ไฟล์ Deploy หรือ Container ที่รันได้เฉพาะ Local ยังไม่ถือว่าผ่าน Cloud

### CP11 เดโมครบระบบ

**งาน:** ทำ Scenario ใช้ 3 Clients บนคอมพิวเตอร์จริงอย่างน้อย 2 เครื่อง
A/B สนทนาและ C เป็นคนนอกห้อง จากนั้นทดสอบผ่าน Cloud คนละเครือข่าย

**ผ่านเมื่อ:** R1–R11 และฟีเจอร์พิเศษทั้ง 4 มีผลสาธิตจริง
ครอบคลุม Private/Group, Online updates, Restart, Search, File Hash,
AI API จริง, Cloud persistence และการปฏิเสธสิทธิ์คนนอก/ประวัติก่อน Join
ตรวจกรณี Disconnect และ AI ไม่พร้อมโดยแชตส่วนอื่นยังใช้ได้

**หลักฐาน:** `docs/demo-checklist.md` ระบุขั้นตอน ผลจริง เครื่อง/เครือข่าย
และภาพหรือวิดีโอที่อ้างอิงได้ หากมีข้อไม่ผ่านให้แก้และทดสอบส่วนนั้นก่อนปิด checkpoint

### CP12 เอกสารและชุดส่งงาน

**งาน:** ปรับ README, Setup, Architecture, Protocol และ Demo checklist ให้ตรงโค้ดจริง
จัดทำสไลด์ Implementation Explanation และคำสั่งติดตั้ง/รันสำหรับผู้ตรวจ

**ผ่านเมื่อ:** ผู้ทดสอบทำตามคู่มือจาก Environment ใหม่แล้วเปิด Client/Server ได้
มีคำอธิบาย Protocol, Threading, Authentication, Authorization และข้อมูลถาวร
แยก Prototype/Mock กับผลที่ทำงานจริง และบอกข้อจำกัดที่ยังมี
ชุดส่งงานไม่รวม Password/API Key/private keys หรือข้อมูลผู้ใช้จริง

**หลักฐาน:** ผลทดลองตามคู่มือ, ผลชุดทดสอบที่มีทั้งหมด และตำแหน่งไฟล์ส่งงานจริง
อัปเดตสถานะใน DEVELOPMENT และข้อความสถานะใน README/HANDOFF ให้สอดคล้องกัน

## คำสั่งสำหรับแต่ละ session

เริ่มจาก root ของโปรเจกต์ ใช้ environment ตาม [คู่มือ setup](docs/setup.md):

```bash
uv sync --locked
uv run --locked python --version
```

เมื่อสร้าง Tests แล้ว ตัวอย่างคำสั่งตรวจแต่ละส่วนคือ:

```bash
uv run --locked pytest tests/test_protocol.py
uv run --locked pytest tests/test_auth.py tests/test_permissions.py
uv run --locked pytest tests/test_chat_integration.py
uv run --locked pytest
```

ใช้ชื่อไฟล์จริงที่มีใน session นั้น บันทึกจำนวนผ่าน/ไม่ผ่าน/ข้ามและสาเหตุ
อย่ารายงานว่าชุดทดสอบผ่านเมื่อยังไม่มี Tests หรือมีแต่ผลข้าม
เมื่อมี entry points แล้วจึงใช้คำสั่งเปิดแอป:

```bash
uv run --locked --env-file .env python -m server.main
uv run --locked --env-file .env python -m client.main
```

อย่าส่ง `.env` ฝั่ง Server ที่มี AI Key/private key ให้ Client
เมื่อ Deploy จริงให้แยก Config ของแต่ละฝั่งตาม HANDOFF

## บันทึก session

เพิ่มบันทึกใหม่ต่อท้ายโดยคงประวัติก่อนหน้าไว้ ผลที่บันทึกเป็นผลของวันและสภาพแวดล้อมนั้น
หากโค้ดหรือ Dependency เปลี่ยนจนกระทบ checkpoint เดิม ให้บันทึกผลตรวจใหม่
และปรับสถานะ checkpoint ที่ได้รับผลกระทบ

### บันทึกเริ่มต้นจากการเตรียม Environment

- วันที่ทำ setup: 2 พฤศจิกายน 2026; นำสถานะมาเริ่มแผนนี้วันที่ 4 พฤศจิกายน 2026
- Checkpoint: CP00 ผ่าน
- สิ่งที่ทำ: uv project, `.venv`, Python pin, dependencies/lock,
  `.env.example`/Local `.env`, โฟลเดอร์ข้อมูล, Local CA/Server certificate และคู่มือ setup
- ไฟล์สำคัญ: `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`,
  `scripts/generate-dev-certs.sh`, `docs/setup.md`, README และ HANDOFF
- ผลตรวจรอบ setup: `uv sync --locked`, lock check และ dependency compatibility ผ่าน;
  สร้างหน้าต่าง Tkinter ได้, Argon2id Hash/Verify และ SQLite ทำงาน;
  TLS ยอมรับ `localhost` ที่เชื่อถือ CA และปฏิเสธ Hostname ผิด;
  `.env` และ private keys มีสิทธิ์ไฟล์ 0600
- Application Tests: ยังไม่มี จึงยังไม่มีผล `pytest` สำหรับแอป
- งานค้าง: CP01–CP12; ยังไม่มี Client/Server/Database จริง
- งานแรกของ session ถัดไป: สร้าง Packages และ Config พร้อมตรวจค่าตั้งต้น/ค่าผิดตาม CP01

### Session วันที่ 4 พฤศจิกายน 2026

- เป้าหมาย: สร้างแผนพัฒนาและ checkpoint กลางสำหรับใช้ต่อข้าม session
- สิ่งที่ทำ: เพิ่ม DEVELOPMENT พร้อมลำดับงาน เกณฑ์ผ่าน dependency และแบบบันทึก;
  เชื่อมจาก README/HANDOFF
- การตรวจ: เทียบแผนกับ HANDOFF และตรวจลิงก์ไฟล์ในเอกสาร
- สถานะ checkpoint: ไม่เปลี่ยนจากผล setup; CP01 ยังเป็น `TODO`
- งานถัดไป: เริ่ม CP01 ตามส่วนสถานะสำหรับเริ่ม session ถัดไป

### Session วันที่ 4 พฤศจิกายน 2026 — CP01 Packages และ Config

- เป้าหมาย: สร้าง Packages และ Config ที่ตรวจค่าได้ตามเกณฑ์ CP01
- สถานะ: CP01 `TODO` → `IN_PROGRESS` → `DONE`; CP02–CP12 ยังเป็น `TODO`
- สิ่งที่ทำสำเร็จ:
  - เพิ่ม Packages `client/`, `server/`, `shared/` โดย import ไม่อ่าน Config
    ไม่เปิด Network และไม่สร้าง Runtime data
  - เพิ่ม `ClientConfig.from_env()` และ `ServerConfig.from_env()` พร้อมค่าเริ่มต้น
    รองรับ Environment ปัจจุบันหรือ Mapping ที่ระบุเอง และรายงาน `ConfigError`
    พร้อมชื่อตัวแปรเมื่อ Host/Port/Path ไม่ถูกต้อง
  - Resolve Relative paths จาก Root โปรเจกต์ รองรับ Absolute paths/`~`
    ตรวจ TLS paths ว่าเป็นไฟล์ที่อ่านได้ และ Data directory/Parent ต้องเขียนและเข้าถึงได้
    โดยไม่สร้าง Directory หรือ Database ระหว่างอ่าน Config
  - Client อ่านเฉพาะ Host/Port/CA; ไม่ต้องใช้ AI Key, Server certificate,
    Server private key หรือ Data directory; ค่า AI ฝั่ง Server เว้นว่างได้
    และไม่แสดง AI Key ใน `repr(ServerConfig)`
  - กำหนด CA ว่างอย่างชัดเจนได้เพื่อเลือก System trust store;
    ถ้าไม่ตั้งตัวแปรจะใช้ `certs/ca.crt` ตามเดิม การตรวจ Certificate/Hostname
    เมื่อเชื่อมต่อจริงยังเป็นงาน CP04 และต้องเปิดไว้
- ไฟล์สำคัญ: `client/__init__.py`, `client/config.py`, `server/__init__.py`,
  `server/config.py`, `shared/__init__.py`, `shared/config.py`, `tests/test_config.py`,
  `pyproject.toml`, `.env.example`, `docs/setup.md`, README, HANDOFF และ DEVELOPMENT
- Dependencies: ไม่เพิ่ม Dependency; `uv.lock` ไม่ต้องเปลี่ยน เพิ่มเฉพาะ pytest
  configuration เพื่อให้ค้น Tests และ import Packages จาก Root ได้
- คำสั่งตรวจและผลจริง (ใช้ `UV_CACHE_DIR=/private/tmp/studygroup-uv-cache`
  นำหน้าคำสั่ง uv เพื่อใช้ Cache ในพื้นที่เขียนได้ของ Session):
  - `uv sync --locked`: ผ่าน; Checked 9 packages
  - `uv lock --check`: ผ่าน; Resolved 11 packages
  - `uv run --locked pytest`: **69 passed, 0 failed, 0 skipped**
    ครอบคลุม Defaults, Overrides, Environment ที่เปลี่ยนภายหลัง import,
    Mapping ว่าง, Port ขอบเขต/ค่าผิด, Host, TLS paths, Permissions,
    Data path ที่เป็นไฟล์/Parent เป็นไฟล์, Unicode paths, Path resolution,
    Client ที่ไม่มี Server secrets และ Import ที่ไม่มีผลข้างเคียง
  - ตรวจ import `client`, `server`, `shared` และอ่าน `from_env({})` ของทั้งสองฝั่ง:
    ผ่านด้วย Local TLS ที่มีอยู่ โดยไม่ใช้ Environment variables
  - `uv run --locked --env-file .env python -c "..."` เพื่อ import และเรียก
    `ClientConfig.from_env()`/`ServerConfig.from_env()`: ผ่าน; Port ทั้งสองฝั่งเป็น
    `5000`, TLS paths อ่านได้ และ Data directory ถูกต้อง โดยไม่แสดง Secrets
- ข้อจำกัดของผลตรวจ: TLS fixtures ใน Unit Tests เป็นไฟล์ Placeholder สำหรับตรวจ Path;
  Session นี้ไม่ได้ทดสอบ PEM/คู่ Key/Certificate, TLS handshake, GUI หรือหลายเครื่อง
  และไม่ได้สร้าง Entry points/Chat Server เพื่อแทนการตรวจฟีเจอร์จริง
- สภาพ Workspace: ไม่มี Git repository จึงตรวจ `git status`/diff ไม่ได้;
  ไม่แก้ Local `.env`, Certificates/private keys หรือข้อมูลใน `data/`
- งานที่ยังค้าง: CP02–CP12; Provider/Model/Key ของ AI และ Cloud ยังไม่เลือก
- งานแรกของ Session ถัดไป: เปลี่ยน CP02 เป็น `IN_PROGRESS` แล้วทำ
  `shared/protocol.py`, `shared/message_types.py`, Validation,
  `tests/test_protocol.py` และ `docs/protocol.md` ตาม Framing/EOF/Limit/Concurrency
  ที่ระบุในเกณฑ์ CP02

### Session วันที่ 6 พฤศจิกายน 2026 — CP02 Socket Protocol

- เป้าหมาย: สร้าง Protocol ที่ส่งต่อให้ Client/Server ใช้ร่วมกันและตรวจรับด้วย Socket จริง
- สถานะ: CP02 `TODO` → `IN_PROGRESS` → `DONE`; CP03–CP12 ยังเป็น `TODO`
- สิ่งที่ทำสำเร็จ:
  - เพิ่ม Header unsigned big-endian 4 bytes ตามด้วย JSON UTF-8 จำกัด Body
    1 MiB; ปฏิเสธ Header ขนาด 0/เกิน Limit ก่อนอ่านหรือ Allocate Body ตามค่านั้น
  - เพิ่ม `recv_exact()`, `recv_packet()`, `encode_packet()` และ
    `PacketConnection.send_packet()` ที่ใช้ `sendall()` ภายใต้ Lock ต่อ Connection
    เมื่อ Send ล้มเหลวป้องกันการเขียนซ้ำบน Stream เดิม
  - แยก EOF ปกติด้วย `None` เมื่อยังไม่ได้รับ Header กับ `IncompleteFrameError`
    เมื่อ EOF กลาง Header/Body; ส่งต่อ Timeout/OSError ตามจริง
  - เพิ่ม Request/Event/Error enums และ Builders สำหรับ Request/Response/Error/Event
    สร้าง Request ID ด้วย UUID4 เมื่อไม่ระบุเอง และตรวจรูปแบบ ID/Version/Type
  - ตรวจ Envelope และ Response/Error shape อย่างเคร่งครัด พร้อมปฏิเสธ Duplicate keys,
    UTF-8/JSON ผิดรูป, ค่าตัวเลขไม่สิ้นสุด, Unicode surrogate ผิดรูป,
    ความลึกเกิน 64, Python-only values และ Circular reference ฝั่งส่ง
  - บันทึก Wire contract, ตัวอย่าง, Error/EOF policy, API และขอบเขต Validation
    ใน `docs/protocol.md`; เชื่อมเอกสารจาก README/HANDOFF
- ไฟล์สำคัญ: `shared/protocol.py`, `shared/message_types.py`,
  `shared/validation.py`, `tests/test_protocol.py`, `docs/protocol.md`,
  README, HANDOFF และ DEVELOPMENT
- Dependencies: ไม่เพิ่ม Dependency และไม่เปลี่ยน `pyproject.toml`/`uv.lock`
- คำสั่งตรวจและผลจริง (ใช้ `UV_CACHE_DIR=/private/tmp/studygroup-uv-cache`
  นำหน้าคำสั่ง uv):
  - ก่อนแก้โค้ด: `uv run --locked pytest` — **69 passed**
  - `uv sync --locked` — ผ่าน; Resolved 11 packages, Checked 9 packages
  - `uv lock --check` — ผ่าน; Resolved 11 packages
  - `uv run --locked pytest tests/test_protocol.py` — **83 passed, 0 failed, 0 skipped**
  - `uv run --locked pytest` — **152 passed, 0 failed, 0 skipped**
  - Protocol Tests เปิด TCP `127.0.0.1` บนพอร์ตชั่วคราวจริง รับส่งไทย/Unicode
    ทั้งสองทิศทาง, อ่านทีละ 1–7 Bytes, แยก Writes, รวมหลาย Frame,
    EOF ทุกส่วน, Frame ขนาดพอดี 1 MiB/เกิน Limit และ JSON/Envelope ผิดรูป
  - ทดสอบ Writer 6 Threads รวม 120 Frames โดยบังคับแยกแต่ละ `sendall()`
    เป็นหลาย TCP writes และ Yield ให้ Threads อื่นทำงาน; Payload/ID ครบไม่แทรกกัน
    และมี `sendall()` ทำงานพร้อมกันสูงสุด 1 ครั้ง
- ข้อสังเกตระหว่างตรวจ:
  - Sandbox ปกติไม่อนุญาต `bind()` แม้เป็น Loopback; รอบแรกจึงได้
    6 passed/77 setup errors แล้วรันด้วยสิทธิ์ที่อนุญาต Local TCP จนผ่านครบ
    ไม่มีการ Skip หรือเปลี่ยนเป็น Mock เพื่อหลบข้อจำกัด
  - รอบ TCP แรกพบ Test expectations 2 จุดไม่ตรง Python 3.14 JSON decoder
    (JSON ลึกอาจ Decode ได้ก่อนถูก Validator ปฏิเสธ และ `Infinity` เป็น JSON
    ผิดรูป) แก้ Fixtures/Assertions และเพิ่มกรณี Number overflow `1e999`
    แล้วตรวจซ้ำผ่านตามผลข้างต้น
- ขอบเขตและการตัดสินใจ:
  - CP02 ตรวจ Envelope/JSON และ Response/Error; Schema ภายใน Request/Event
    `data` และผลสำเร็จ `result` เป็นงาน Handler รายฟีเจอร์ใน CP04–CP09
    ยังไม่มี Authentication, Authorization, Pending request registry หรือ Retry
  - Caller ต้องใช้ `PacketConnection` เดียวต่อ Socket และ Reader เดียว;
    ตั้ง Timeout และปิด/ทิ้ง Connection เมื่อรับ Error หรือ `sendall()` ล้มเหลว
    Lifecycle/การใช้งาน TLS หลาย Thread ต้องตรวจต่อใน CP04
  - Tests เป็น TCP Local บนเครื่องเดียว ไม่ใช่ผลตรวจ TLS, GUI หรือหลายเครื่อง
- สภาพ Workspace: ไม่มี Git repository จึงตรวจ `git status`/diff ไม่ได้;
  ไม่แก้ `.env`, Certificates/private keys หรือข้อมูลใน `data/`
- งานที่ยังค้าง: CP03–CP12; Provider/Model/Key ของ AI และ Cloud ยังไม่เลือก
- งานแรกของ Session ถัดไป: เปลี่ยน CP03 เป็น `IN_PROGRESS` แล้วทำ
  `server/schema.sql`, `server/database.py`, `server/permissions.py` และ Tests
  ด้วย Temporary database ตรวจ Constraints, Normalize username, คู่ห้องส่วนตัว,
  Join boundary ใน Transaction, สิทธิ์คนนอก/สมาชิกใหม่, Rollback และ Reopen

### Session วันที่ 6 พฤศจิกายน 2026 — CP03 SQLite และสิทธิ์เข้าถึงข้อมูล

- เป้าหมาย: สร้างฐานข้อมูลและสิทธิ์ร่วมสำหรับต่อ Authentication/Handlers
  โดยตรวจสมาชิกใหม่กับข้อความและ Metadata ไฟล์ด้วยเงื่อนไขเดียวกัน
- สถานะ: CP03 `TODO` → `IN_PROGRESS` → `DONE`; CP04–CP12 ยังเป็น `TODO`
- สิ่งที่ทำสำเร็จ:
  - เพิ่ม Schema v1 แบบ STRICT สำหรับ `users`, `rooms`, `room_members`,
    `messages`, `attachments` พร้อม Foreign keys, Composite membership foreign key,
    Check/Unique constraints, Triggers จำกัดสมาชิก Private/Attachment kind และ Index
    ตามผู้ใช้ ห้อง Message ID และเวลา
  - Username ใช้ ASCII อังกฤษ/ตัวเลข/`_` ยาว 3–24 ตัว เก็บ Display case เดิม
    และค่า Lowercase ที่ UNIQUE; บังคับทั้ง API และ Schema รวมกรณี NUL
    และทดสอบสมัครชื่อซ้ำต่างตัวพิมพ์พร้อมกันด้วย Connection จริง
  - `Database.initialize()` เรียกซ้ำ/เปิดไฟล์เดิมใหม่ได้โดยข้อมูลทั้ง 5 ตารางไม่หาย
    ใช้ `user_version = 1` และปฏิเสธ Version ที่ไม่รองรับ; Schema error Rollback
    ทั้งการ Initialize โดยไม่เหลือตารางที่สร้างค้างไว้
  - Connection แยกตาม Worker/Thread เปิด Foreign keys, Busy timeout 5 วินาที
    และ WAL; Context manager ปิด Connection และ Rollback งานที่ยังไม่ Commit
    ไม่มี Filesystem/Config/Connection side effect ระหว่าง import หรือ Constructor
  - เพิ่ม Transaction helper แบบ `BEGIN IMMEDIATE` รองรับ Nested savepoints;
    สร้างห้อง/Join/ส่งข้อความแบบอะตอมและใช้ Parameterized queries
    เวลา Create/Join มาจาก SQLite เป็น UTC ลงท้าย `Z`
  - ห้อง Private ใช้คู่ ID เรียงลำดับที่ UNIQUE พร้อมสมาชิกสองคนขอบเขต 0;
    เปิดพร้อมกันจาก 6 Workers หรือสลับผู้เรียก/คู่สนทนาก็ได้ห้องเดิม
    กลุ่มใหม่มีเพียงผู้สร้างและ Join ซ้ำไม่เปลี่ยนขอบเขตประวัติ
  - Join อ่าน Message ID ล่าสุดเฉพาะห้องแล้วเพิ่มสมาชิกใน Write transaction
    ทดสอบ Send ก่อน Join และ Join ก่อน Send โดยถือ Write lock แล้วให้ Connection
    อีกตัวรอจริง ยืนยันว่าข้อความก่อน Join ถูกซ่อนและข้อความหลัง Join อ่านได้
  - เพิ่ม Permission helpers สำหรับสมาชิก ข้อความ และไฟล์ พร้อม SQL เงื่อนไขร่วม
    `message_id > visible_after_message_id`; คนนอก/ID ที่ไม่มีอยู่ให้ `FORBIDDEN`
    รายชื่อกลุ่ม/สมาชิกกลุ่มเปิดให้บัญชีที่มีอยู่ตาม R9 โดยไม่คืนเนื้อหาหรือ Hash
  - เพิ่ม Query ข้อความที่เห็นแบบ Pagination เรียงเก่าไปใหม่เพื่อให้ Handler ใช้ต่อ;
    File message/Attachment ที่ยังไม่ `ready` ถูกซ่อน และ Publish ไฟล์เก่า
    หลัง Join ไม่ทำให้สมาชิกใหม่ข้ามขอบเขตได้
- ไฟล์สำคัญ: `server/schema.sql`, `server/database.py`, `server/permissions.py`,
  `tests/conftest.py`, `tests/test_database.py`, `tests/test_permissions.py`,
  `docs/database.md`, README, HANDOFF และ DEVELOPMENT
- Dependencies: ไม่เพิ่ม Dependency และไม่เปลี่ยน `pyproject.toml`/`uv.lock`
- คำสั่งตรวจและผลจริง (ใช้ `UV_CACHE_DIR=/private/tmp/studygroup-uv-cache`
  นำหน้าคำสั่ง uv):
  - `uv sync --locked`: ผ่าน; Resolved 11 packages, Checked 9 packages
  - `uv lock --check`: ผ่าน; Resolved 11 packages
  - รอบสุดท้าย `uv run --locked pytest`: **234 passed, 0 failed, 0 skipped**
    แยกเป็น Config 69, Protocol 83, Database 51 และ Permissions 31
  - Database/Permissions ใช้ฐานข้อมูลบน Disk ใน Temporary directory เท่านั้น
    ครอบคลุม Persistence/Reopen/Integrity, UTC, Constraints, SQL ที่เป็นข้อมูล,
    Atomic rollback, Nested savepoints, Thread ownership, Concurrent uniqueness,
    Join/Send contention และสิทธิ์ Private/Group/สมาชิกใหม่/ไฟล์ก่อน Join
  - Protocol ใช้ TCP Loopback จริง; รันภายใต้สิทธิ์ที่อนุญาต Local TCP แล้วผ่านครบ
    รอบเริ่มต้นภายใต้ Sandbox ปกติได้ 75 passed/77 setup errors จาก `bind()`
    ถูกปฏิเสธตามข้อจำกัดเดิมของ CP02 ไม่ได้ Skip หรือแทนด้วย Mock
- ขอบเขตและการตัดสินใจ:
  - `user_id` ของ API ต้องมาจาก Connection ที่ยืนยันตัวตนแล้ว; CP04 ต้องใช้
    Argon2id ก่อนเรียก `create_user()` และไม่ส่ง Hash จาก Internal login lookup
    กลับ Client; Session นี้ยังไม่ใช่ผลตรวจ Authentication/TLS
  - CP07 ต้องเพิ่ม Search โดยคงเงื่อนไขสิทธิ์ร่วม; CP09 ต้องจำกัด AI เฉพาะกลุ่ม
    และไม่เกิน 50 ข้อความ รวมทั้งตรวจสิทธิ์ซ้ำก่อนคืนผล
  - Attachment Tests ตรวจ Metadata/สถานะ/สิทธิ์เท่านั้น ไม่ได้ส่งไฟล์จริง
    CP08 ต้องรับ Chunk ตรวจ Bytes/Hash สร้างชื่อจัดเก็บเอง และ Publish หลังรับครบ
  - ยังไม่มี Handlers, Live Events, GUI หรือการทดสอบสองเครื่อง;
    CP05 ต้องส่ง Event เฉพาะผู้มีสิทธิ์และหลัง Transaction Commit
  - Migration หลัง Schema v1 และการลบสมาชิก/ห้อง/บัญชียังไม่ได้ออกแบบเป็นฟีเจอร์
    เมื่อประกอบหลาย Write operations ให้ใช้ `transaction()` เป็นชั้นนอกด้วย
    เพื่อไม่เริ่มอ่านภายใต้ Deferred transaction
- สภาพ Workspace: มี Git repository และเริ่มจาก Working tree สะอาด;
  ไม่แก้ `.env`, Certificates/private keys หรือข้อมูลจริงใน `data/`
- งานที่ยังค้าง: CP04–CP12; Provider/Model/Key ของ AI และ Cloud ยังไม่เลือก
- งานแรกของ Session ถัดไป: เปลี่ยน CP04 เป็น `IN_PROGRESS` แล้วทำ
  `server/passwords.py`, TLS listener/Connection lifecycle, Router, Auth handlers
  และ Session registry ที่ Login/Logout/Cleanup เป็นอะตอม พร้อม Tests ตามเกณฑ์ CP04
  โดยใช้ `Database` และ Permission API ใน `docs/database.md`

### Session วันที่ 6 พฤศจิกายน 2026 — CP04 TLS และ Authentication

- เป้าหมาย: ประกอบ TLS listener หลาย Clients, Auth handlers และ Session registry
  บน Protocol/Database เดิม พร้อมตรวจรับผ่านเครือข่ายจริงและไม่แตะข้อมูล Local จริง
- สถานะ: CP04 `TODO` → `IN_PROGRESS` → `DONE`; CP05–CP12 ยังเป็น `TODO`
- สิ่งที่ทำสำเร็จ:
  - เพิ่ม `server.main` สำหรับเปิด TLS listener ด้วย Config เดิม Initialize/Reopen SQLite
    และหยุดด้วย Ctrl+C โดยปิด Listener และรอ Workers Cleanup ครบ
  - แต่ละ Connection ใช้ Worker เจ้าของ TLS Handshake/Read/Write เพียงรายเดียว
    พร้อม Outbound queue แบบจำกัดขนาดและ Socket pair สำหรับปลุก Worker;
    Workers อื่นไม่เขียน TLS Socket ข้าม Thread และเปิด SQLite แยกตาม Worker
  - เพิ่ม `client.network.connect()` ตรวจ Certificate chain และ Hostname ก่อนคืน Transport
    ใช้ Local CA หรือ System trust store ตาม Config, TLS 1.2 ขึ้นไป ไม่มีโหมดปิด Verification
  - เพิ่ม Register/Login/Logout/Users list, Argon2id พร้อม Random salt และ Upgrade hash
    เมื่อ Parameters เก่า สมัครแล้วต้อง Login แยก ไม่คืน Hash/Exception/Secrets ให้ Client
  - Username ใช้ Normalize เดียวกับ CP03 และ Database UNIQUE ป้องกันสมัครชื่อซ้ำพร้อมกัน
    Password 8–128 Unicode characters, สูงสุด 512 UTF-8 bytes, ไม่มี NUL;
    ไม่ Trim/Normalize และตรวจ Confirm Password ฝั่ง Server
  - Router รับเฉพาะ Client requests; ก่อน Login ให้ผ่านเฉพาะ Register/Login
    ทุกคำขออื่นให้ AUTH_REQUIRED; ปฏิเสธ Fields ปลอมตัวตนใน Auth/Users list
    คำขอ CP05–CP09 หลัง Login ยังให้ UNKNOWN_TYPE จนกว่าจะมี Handler จริง
  - Registry ล็อกการ Login/Logout/เรียง Snapshot และเข้าคิว Event แบบอะตอม
    Login พร้อมกันได้เพียงผู้ชนะ ไม่ตัด Session เดิมหรือให้ Cleanup ผู้แพ้ล้างผู้ชนะ
    ตรวจ Connection identity ก่อนลบเพื่อป้องกัน Cleanup เก่าล้าง Session ใหม่
  - Online events มี User ID/ชื่อที่ Login รวมตัวเองและ Revision เพิ่มตาม Registry
    Login response มาก่อน Event แรก; Logout response มาก่อน Snapshot สุดท้ายของตน
    หลังจากนั้นไม่ Broadcast ให้ Connection ที่ Logout/ยังไม่ Login
  - EOF, Invalid/truncated Frame, TLS/Socket error, Deadline, Idle timeout, Queue เต็ม
    และ Server stop ผ่าน Cleanup เดียวกัน มี Total frame deadline กัน Byte drip
  - จำกัด Auth ต่อ Source IP และชื่อ Normalize ร่วมทั้ง Server ข้าม Reconnect/Logout
    ใช้ Monotonic window/Bounded buckets และจำกัดงาน Argon2 พร้อมกัน 2 งาน
    Unknown account Verify ด้วย Dummy hash ที่ Cost เดียวกัน Login ผิดใช้ข้อความรวม
    Log ใช้ข้อความคงที่ ไม่บันทึก Credentials/Keys หรือ Exception ที่อาจมี Secrets
- ไฟล์สำคัญ: `server/main.py`, `server/connection.py`, `server/router.py`,
  `server/handlers/auth.py`, `server/passwords.py`, `server/sessions.py`,
  `server/rate_limit.py`, `client/network.py`, `tests/test_auth.py`,
  `tests/test_tls_integration.py`, `docs/authentication.md`, docs/protocol/setup,
  README, HANDOFF และ DEVELOPMENT
- Dependencies: ไม่เพิ่ม Dependency และไม่เปลี่ยน `pyproject.toml`/`uv.lock`;
  Tests ใช้ OpenSSL CLI ที่มีอยู่เพื่อสร้างใบรับรองชั่วคราว
- คำสั่งตรวจและผลจริง (ใช้ `UV_CACHE_DIR=/private/tmp/studygroup-uv-cache`
  นำหน้าคำสั่ง uv):
  - ก่อนพัฒนา: `uv run --locked pytest -q` ภายใต้สิทธิ์ Local TCP — **234 passed**
  - `uv sync --locked` — ผ่าน; Resolved 11 packages, Checked 9 packages
  - `uv lock --check` — ผ่าน; Resolved 11 packages
  - รอบสุดท้าย `uv run --locked pytest -q --tb=short` — **313 passed, 0 failed, 0 skipped**
    ใช้เวลา 19.34 วินาที; Config 69, Protocol 83, Database 51, Permissions 31,
    Auth 19 และ TLS integration 60
  - TLS Tests ใช้ TCP จริงบน `127.0.0.1` และตรวจชื่อ DNS `localhost` ด้วย
    พอร์ตชั่วคราว พร้อม CA/Certificate/Keys และ SQLite ที่สร้างใน Temporary directories
    ครอบคลุมสมัคร/Login พร้อมกัน, Generic failures, Hash/Upgrade, Actor spoofing,
    CA ผิด/Hostname ผิด/หมดอายุ, Plaintext ถูกปฏิเสธ, Online events รวมตัวเอง,
    Logout/EOF/Frame error/Timeout, Stale cleanup, Reconnect limits, Capacity/Queue,
    งาน Hash เต็มแล้วฟื้นตัว, Byte drip และ Shutdown ระหว่าง Handshake/Partial frame
  - ตรวจ 3 TLS Clients ส่ง Requests รวม 60 ครั้งพร้อม Presence events และตรวจ Thread ID
    ของ Handshake/recv/sendall ฝั่ง Server พบ I/O owner เพียง Thread เดียวต่อ Connection
  - ทดสอบ Restart ใช้ Database เดิม บัญชียังอยู่แต่ต้อง Login ใหม่
    และเปิด `python -m server.main` ใน Process จริง รับ Register/Login ผ่าน TLS
    แล้วส่ง SIGINT แทน Ctrl+C ได้ Exit code 0
  - `git diff --check` — ผ่าน
- ข้อสังเกตระหว่างตรวจ:
  - Sandbox ปกติยังไม่อนุญาต TCP bind ตาม CP02–CP03 จึงรันชุดเครือข่ายด้วยสิทธิ์
    Local TCP ที่อนุมัติ ไม่ Skip หรือใช้ Mock แทน Integration tests
  - รอบใหม่แรก Auth unit 18 passed แต่ TLS fixtures 50 errors เพราะ OpenSSL ของเครื่องนี้
    ไม่รองรับ `x509 -days -1`; เปลี่ยน Fixture เป็น `openssl ca` กำหนดวันหมดอายุ
    ในอดีตอย่างชัดเจน จากนั้นผ่านครบ และเพิ่มกรณีตรวจรับจนได้ผลรอบสุดท้ายข้างต้น
- ขอบเขตและการตัดสินใจ:
  - Limits และ Wire fields ที่ใช้จริงอยู่ใน docs/authentication.md; ยังไม่มี Environment
    variables ใหม่ สามารถปรับ ServerLimits/AuthRateLimiter ผ่าน Constructor
    Limiter อยู่ใน Memory และเริ่มใหม่เมื่อ Restart; ผู้ใช้หลัง NAT ใช้งบ Source IP ร่วมกัน
  - Client transport ยังเป็น Blocking API ให้ผู้เรียกเดียวทำ I/O ไม่มี GUI worker,
    Pending request registry, Remember password หรือ Auto retry; CP06 ต้องทำต่อ
    โดยรักษา TLS I/O ownership และส่งผลไป Tkinter ผ่าน Queue/after()
  - Tests เป็น Local เครื่องเดียว ยังไม่ตรวจ GUI, สองเครื่องจริง หรือ Cloud
    CP04 จบตามเกณฑ์ Auth/TLS แต่ยังไม่ใช่การตรวจรับ R1–R11 ของ CP06
  - CP05 ต้องใช้ `connection.user` เป็น Actor ตรวจสิทธิ์ร่วมจาก CP03
    บันทึกข้อความก่อนตอบรับ และส่ง Live events เฉพาะสมาชิก/ผู้มีสิทธิ์หลัง Commit
- สภาพ Workspace: เริ่มจาก Git working tree สะอาด; ไม่แก้ `.env`, ใบรับรอง/Keys
  ใน `certs/` หรือข้อมูลจริงใน `data/`; ยังไม่ได้ Commit
- งานที่ยังค้าง: CP05–CP12; AI Provider/Model/Key และ Cloud ยังไม่เลือก
- งานแรกของ Session ถัดไป: เปลี่ยน CP05 เป็น `IN_PROGRESS` แล้วเพิ่ม Chat/Group handlers
  และ Routing สำหรับ PRIVATE_ROOM_OPEN, GROUP_CREATE/LIST/JOIN, MESSAGE_SEND
  ด้วย Database/Permissions เดิม พร้อม Registry API ส่ง Event ถึงผู้มีสิทธิ์เท่านั้น
  ทดสอบ Clients A/B/C ผ่าน TLS จริงเพื่อยืนยันว่าคนนอกห้องไม่เห็นข้อมูลหรือ Events

### Session วันที่ 6 พฤศจิกายน 2026 — CP05 Server สำหรับแชตส่วนตัวและกลุ่ม

- เป้าหมาย: เพิ่ม Chat/Group handlers บน TLS/Authentication เดิม และตรวจสิทธิ์
  ของผลตอบกลับกับ Live Events ผ่านหลาย Connections จริงตามเกณฑ์ CP05
- สถานะ: CP05 `TODO` → `IN_PROGRESS` → `DONE`; CP06–CP12 ยังเป็น `TODO`
- สิ่งที่ทำสำเร็จ:
  - เพิ่ม Routing/Handlers สำหรับ `PRIVATE_ROOM_OPEN`, `GROUP_CREATE`, `GROUP_LIST`,
    `GROUP_JOIN`, `MESSAGE_SEND`; `USERS_LIST` และ Presence ใช้ CP04 เดิม
    ทุกคำขอยึด Actor จาก `connection.user` และไม่รับ Fields อ้าง Sender/Actor/สมาชิกเพิ่ม
  - ห้อง Private ใช้ห้องเดิมทั้งสองทิศทางและเมื่อเปิดพร้อมกัน มีเพียงคู่สนทนา
    สร้างกลุ่มได้หลายกลุ่ม มีเพียงผู้สร้างเป็นสมาชิกคนแรก คนอื่น Join ด้วยตนเอง
    ทุกผู้ Login เห็นรายชื่อกลุ่ม/สมาชิก แต่ไม่เห็น Private rooms หรือเนื้อหาผ่าน Listing
  - รายชื่อกลุ่มมี Pagination ด้วย `after_id`/`limit` พร้อม `next_after_id`
    คัดเลือก Fields ตอบกลับอย่างชัดเจน ไม่ส่ง Password hash หรือข้อมูลสิทธิ์ภายใน
    จำกัด ID เป็น Integer 64-bit จริง ชื่อกลุ่ม 100 characters ข้อความ 4,000 characters/
    16,000 UTF-8 bytes ไม่รับ NUL/ข้อความว่าง โดยคงช่องว่างและ Unicode ของแชต
  - Registry ส่ง Public group invalidation หรือส่ง Message event ถึงเฉพาะ IDs ที่มีสิทธิ์
    และยัง Login อยู่ ไม่เขียน TLS จาก Thread อื่น ไม่ส่งให้ผู้ Logout/ยังไม่ Login
    `GROUPS_UPDATED` มีเพียง Room ID ให้ Client โหลด Listing ใหม่
  - เพิ่ม `message_recipient_ids()` โดยใช้ Join/Predicate เดียวกับการอ่านข้อความ/ไฟล์
    ใน SQL Query เดียว รวม Private pair guard และ `visible_after_message_id`
    ป้องกันคนนอกห้องและสมาชิกใหม่ได้รับข้อความก่อนเข้าร่วม
  - ใช้ Chat lock ร่วมตั้งแต่ Transaction จนถึงเข้าคิว Response/Event ให้ลำดับ
    Commit/Message ID/Join boundary สอดคล้องกัน โดยไม่มี Socket I/O ภายใต้ Lock
    Commit ก่อนตอบสำเร็จหรือส่ง Event เสมอ Transaction ผิดพลาด Rollback ไม่ประกาศ Event
    Join ซ้ำไม่เปลี่ยนขอบเขตหรือส่ง Group event ซ้ำ
  - ตรวจขนาด Room responses ก่อนเข้าคิว หากเกิน Frame limit คืน `FRAME_TOO_LARGE`
    และ Connection ยังใช้ต่อได้ การ Join ที่ Response เกินขนาด Rollback สมาชิกด้วย
  - ย้าย Fixtures ของ Temporary TLS certificates/Server ไป `tests/conftest.py`
    ใช้ร่วมระหว่าง CP04/CP05 และปรับ Auth spoof test ให้ตรงกับ Handler ที่พร้อมแล้ว
- ไฟล์สำคัญ: `server/handlers/chat.py`, `server/permissions.py`, `server/sessions.py`,
  `server/router.py`, `server/main.py`, `tests/test_chat_integration.py`,
  `tests/conftest.py`, `tests/test_tls_integration.py`, `docs/chat.md`,
  docs/protocol/authentication/database, README, HANDOFF และ DEVELOPMENT
- Dependencies: ไม่เพิ่ม Dependency ไม่เปลี่ยน Schema, Environment variables,
  `pyproject.toml` หรือ `uv.lock`
- คำสั่งตรวจและผลจริง (ใช้ `UV_CACHE_DIR=/private/tmp/studygroup-uv-cache`
  นำหน้าคำสั่ง uv):
  - ชุดเดิมหลังเชื่อม Routing: `uv run --locked pytest -q --tb=short` — **313 passed**
  - Chat รอบแรก: `uv run --locked pytest tests/test_chat_integration.py -q --tb=short`
    — **36 passed** ก่อนเพิ่มกรณีขนาด Frame/ข้อความสูงสุดและ Restart
  - `uv run --locked pytest tests/test_chat_integration.py tests/test_permissions.py tests/test_database.py -q --tb=short`
    — **121 passed** (Chat 39 + Permissions 31 + Database 51)
  - รอบสุดท้าย `uv run --locked pytest -q --tb=short` — **352 passed, 0 failed, 0 skipped**
    ใช้เวลา 31.77 วินาที รวมชุดเดิม 313 และ Chat integration 39
  - `uv lock --check` และ `uv sync --locked` — ผ่าน; Resolved 11 packages, Checked 9 packages
  - `git diff --check` — ผ่าน
  - Network tests ใช้สิทธิ์ Local TCP เพราะ Sandbox ปกติปฏิเสธ `bind()` เช่น CP02–CP04
    ไม่ Skip หรือใช้ Mock แทน Network ใช้ `127.0.0.1` กับพอร์ตชั่วคราว,
    CA/Keys และ SQLite ใน Temporary directories เท่านั้น
  - A/B/C ตรวจ Room ID probing, Sender/Actor spoofing, หลายกลุ่มและ Self-join,
    Group pagination, Unicode/Emoji สูงสุด 16,000 bytes, Response ก่อน Sender echo,
    Logout/Offline/Re-login และ Private metadata/ข้อความไม่รั่วไป C
  - ส่งพร้อมกันจากสอง Connections รวม 24 ข้อความ ผู้มีสิทธิ์ได้ลำดับเดียวกันตาม ID
    คนนอกไม่ได้รับ Event; Join/Send ทั้งสองลำดับใช้ Gates ให้ Worker อีกตัวมาถึง
    Handler ขณะ Transaction แรกยังไม่จบ แล้วตรวจทั้ง Live Events และขอบเขตใน SQLite
  - จำลอง Failure หลัง INSERT ภายใน Transaction จริง ยืนยัน Rollback/ไม่มี Event;
    ตรวจ Publication ด้วย SQLite Connection อีกตัวว่าข้อมูล Commit แล้ว
    ตรวจ Restart เปิด Database เดิม ห้อง/สมาชิก/ข้อความ/Join boundary อยู่ครบ
    และ Connection ใหม่ต้อง Login อีกครั้ง
- ขอบเขตและการตัดสินใจ:
  - Wire contract และ Limits อยู่ใน `docs/chat.md`; Group events เป็น Invalidation
    ไม่ใช่ Snapshot Client ต้องโหลด `GROUP_LIST` หลัง Login และเมื่อได้รับ Event
  - ไม่มี Replay/Retry อัตโนมัติ ส่งตอนคู่สนทนา Offline ยังคงบันทึกข้อความ
    หากหลุดหลัง Commit อาจไม่ได้รับ Response ห้ามถือว่า Request ID ทำให้ Exactly-once
    CP06 ต้องรวม Response กับ Sender echo ด้วย Message ID เพื่อไม่แสดงซ้ำ
  - แต่ละ Room ส่งรายชื่อสมาชิกใน Frame เดียว รายการกลุ่มใหญ่ลด Page size ได้
    หากสมาชิกกลุ่มเดียวเกิน 1 MiB ต้องเพิ่ม Member pagination ก่อนรองรับขนาดนั้น
    มี Test ลด Frame cap เพื่อทดสอบ Error/Recover/Join rollback ผ่าน TLS จริง
  - `HISTORY_GET`/`HISTORY_SEARCH`, Files และ AI หลัง Login ยังให้ `UNKNOWN_TYPE`
    ประวัติใน Session นี้ตรวจข้อมูลถาวรผ่าน Database; Network history/search เป็น CP07
  - ผลเป็น Server tests บนเครื่องเดียว ยังไม่มี GUI และยังไม่ตรวจสองเครื่องจริง/Cloud
    CP06 ต้องตรวจ R1–R11 พร้อม GUI ตามเงื่อนไขเดิม
- สภาพ Workspace: เริ่มจาก Git working tree สะอาด; ไม่แก้ `.env`, `certs/`
  หรือข้อมูลจริงใน `data/`; ยังไม่ได้ Commit
- งานที่ยังค้าง: CP06–CP12; AI Provider/Model/Key และ Cloud ยังไม่เลือก
- งานแรกของ Session ถัดไป: เปลี่ยน CP06 เป็น `IN_PROGRESS` อ่าน Prototype Focus,
  `docs/authentication.md` และ `docs/chat.md` แล้วเริ่ม Tkinter entry point,
  Login/Register/Server settings และ Network worker เจ้าของ TLS I/O เพียง Thread เดียว
  จับคู่ Pending requests และส่งผล/Event เข้า Main thread ผ่าน `queue.Queue`/`after()`
  จากนั้นต่อ Sidebar ออนไลน์/กลุ่มและหน้าห้องแชต พร้อมเริ่ม docs/architecture/demo-checklist

### Session CP06 — Desktop Client Tkinter / Local verification

- วันที่: 6 พฤศจิกายน 2026 (Asia/Bangkok)
- Branch: `codex/cp06-tkinter-client` แยกจาก `main` ที่ Working tree สะอาด
- เป้าหมาย: ต่อ Desktop Client กับ Server CP05 จริง เพื่อเตรียมตรวจ R1–R11
- สถานะ: CP06 `TODO` → `IN_PROGRESS`; ยังไม่ DONE เพราะยังไม่มีคอมพิวเตอร์จริงสองเครื่อง
- สิ่งที่ทำสำเร็จ:
  - เพิ่ม `client.main`, Application และหน้าจอ Native Tkinter แบบ Focus สีม่วง
    Register/Login/Server settings, Online users รวมตนเอง, Private conversations,
    รายชื่อทุกกลุ่มและสมาชิก, สร้างกลุ่ม/Join เอง, Dialog สมาชิก และสถานะข้อผิดพลาด
  - GUI รองรับภาษาไทย/Emoji, Enter ส่ง, Shift+Enter ขึ้นบรรทัดใหม่, Scroll,
    หน้าต่าง 850×700 / 1120×800 และหน้าสมัครแบบเลื่อนเมื่อพื้นที่ไม่พอ
  - เพิ่ม Single-owner NetworkWorker พร้อม Request/Event queues ที่จำกัดขนาด
    Nonblocking TLS, Incremental framing ที่ใช้ Decoder ร่วม, Total frame deadline,
    Request timeout, Response dispatch ด้วย Request ID และการปิดแบบไม่บล็อก Tk
  - ตรวจพบและแก้ TLS 1.3 session tickets ทำให้ select อ่านได้แต่ไม่มี Application data
    จึงใช้ Nonblocking TLS แทนการเข้า Blocking recv จนขวางคำขอขาออก
  - รวม Sender response/Event echo ด้วย Message ID; Draft แยกห้อง ไม่ลบร่างใหม่เมื่อ
    Ack ข้อความเก่ามาถึง; เก็บ Unread และค้น Private metadata เมื่อมีข้อความเข้าห้องใหม่
  - ลด Page size เมื่อ Group listing เกิน Frame และโหลดทุกหน้าพร้อม Coalesce invalidations
    ผลเปิดห้องเก่าไม่แย่งห้องที่ผู้ใช้เลือกภายหลัง ระหว่างรอ Response
  - Disconnect เก็บร่างและแจ้งผลส่งที่ยังยืนยันไม่ได้ ไม่ Replay/Retry เอง
    Login บัญชี/Server เดิมรักษา In-memory state; เปลี่ยนบัญชี/Server หรือ Logout ล้างข้อมูลเก่า
    แก้ Callback cycle เพื่อไม่ให้ Tk Variables ถูก Finalize ใน Network thread หลังปิดแอป
  - เพิ่มเอกสาร architecture.md และ demo-checklist.md พร้อมวิธีทดสอบ LAN
    สคริปต์ generate-lan-cert.sh ใช้ CA เดิม สร้าง SAN ตาม IP/DNS จริงใน certs/lan
    ไม่แทน Localhost certificate/keys เดิม และปฏิเสธการเขียนทับ
- หลักฐานและผลจริง (คำสั่ง uv ใช้ `UV_CACHE_DIR=/private/tmp/studygroup-uv-cache`):
  - `uv run --locked pytest -q --tb=short -W error` — **378 passed, 0 failed, 0 skipped**
    ใช้เวลา 41.62 วินาที รวมชุดเดิม 352 + Client 21 + LAN certificate 5
  - `uv run --locked pytest tests/gui_checks.py -q --tb=short -W error`
    — **3 passed** ใน 4.00 วินาที ไม่มี Callback error หรือ Warning
    เรียกแยกเพราะต้องมี Desktop/Display ไม่ถูก Collect ในชุด Headless ปกติ
  - GUI checks ใช้ Widgets จริงและ TCP/TLS จริง ครอบคลุมสมัคร/Login, เลือก Private,
    Thai/Emoji/Enter/Shift+Enter, Draft/สลับห้อง, สร้าง/Join กลุ่ม, รายชื่อสมาชิก,
    Disconnect/Re-login/Logout และปุ่มสำคัญไม่หลุดขอบหน้าต่างเล็ก
  - Client integration ใช้ A/B/C กับ TLS/SQLite ชั่วคราว ตรวจ Privacy, Sender echo,
    Pagination, Commit แล้วตัดก่อน Ack, ไม่มี Retry, Session isolation, I/O owner thread,
    Frame แตก/รวม/UTF-8, Partial-frame deadline และ UI queue เต็ม
  - Certificate tests ตรวจ SAN IP/DNS ถูกต้อง, ชื่อผิดถูกปฏิเสธ, ไม่เขียนทับ Key
    และ SAN ผิด/แทรก Config ไม่ Publish ใบรับรอง
  - เปิดหน้าต่างจริงผ่าน Desktop automation ตรวจ Login/ออนไลน์/Private/กลุ่มและข้อความไทย
    ภาพ Local อยู่ที่ docs/evidence/cp06/private-chat.png; Accounts/Database ใช้ Temporary data
  - `uv lock --check`, `bash -n scripts/generate-lan-cert.sh` และ `git diff --check` — ผ่าน
  - Network tests ต้องใช้สิทธิ์ Local TCP; Environment ปกติปฏิเสธ bind() เช่น checkpoint เดิม
    การเปิด Tk ต้องใช้สิทธิ์ Desktop ตรวจซ้ำด้วยสิทธิ์ที่พร้อมแล้ว ไม่ใช้ Mock หรือ Skip แทน
- Dependencies/ข้อมูลจริง: ไม่เพิ่ม Dependency ไม่เปลี่ยน Schema/uv.lock/.python-version
  ไม่แก้ `.env`, certs เดิม หรือข้อมูลจริงใน data/ ไม่ติดตั้ง/เปลี่ยน System trust
- ขอบเขต: ยังไม่มี Network history/search, Files, AI และ Cloud (CP07–CP10)
  UI แสดงเฉพาะข้อความที่รับระหว่างเปิดแอป ไม่มีการโหลดประวัติหลังเปิดใหม่ใน CP06
  ฟีเจอร์อนาคตใน Prototype ยังไม่เปิดเป็นปุ่มทำงานจำลองใน Desktop
- งานที่ยังค้างก่อน DONE: R1–R11 บนคอมพิวเตอร์จริงสองเครื่อง, LAN/Firewall/TLS จริง,
  Thai IME และ OS Copy/Paste บนเครื่องเดโม พร้อมรายละเอียดเครื่อง/เครือข่ายและภาพ A/B/C
- งานแรก Session ถัดไป: เปิด docs/demo-checklist.md เตรียม LAN SAN ให้ตรง Server จริง
  รัน Client A/B คนละเครื่องและ C เป็นคนนอกห้อง เติมหลักฐานแล้วจึงปิด CP06/เริ่ม CP07

### แบบบันทึกสำหรับ session ถัดไป

คัดลอกแบบนี้เป็นหัวข้อใหม่ แล้วกรอกข้อมูลจริง:

```text
Session วันที่และเวลา Asia/Bangkok:
Checkpoint และเป้าหมายของ session:
สถานะเริ่มต้นและสถานะเมื่อจบ:
สิ่งที่ทำสำเร็จ:
ไฟล์สำคัญที่เปลี่ยน:
คำสั่งตรวจและผลจริง รวมจำนวนผ่าน ไม่ผ่าน ข้าม:
ผลตรวจด้วย GUI หรือหลายเครื่อง พร้อมสภาพแวดล้อม:
การตัดสินใจและเหตุผล หากมี:
ปัญหาที่ยังค้างหรือข้อมูลภายนอกที่ต้องการ:
งานแรกของ session ถัดไป พร้อมไฟล์หรือคำสั่งที่จะเริ่ม:
```
