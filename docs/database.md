# SQLite และสิทธิ์เข้าถึงข้อมูล

CP03 ใช้ `server/schema.sql`, `server/database.py` และ `server/permissions.py`
เป็นส่วนจัดเก็บข้อมูลฝั่ง Server ปัจจุบัน Auth และ Chat handlers ใช้ API เหล่านี้แล้ว
ยังไม่มีการรับส่งไฟล์หรือ AI ที่เรียกใช้งานจริง ผลตรวจล่าสุดอยู่ใน
[DEVELOPMENT.md](../DEVELOPMENT.md)

## Connection และ Transaction

- สร้าง `Database(config.database_path)` จาก `ServerConfig` เมื่อเริ่ม Server
  แล้วเรียก `initialize()` ก่อนเริ่ม Workers; Constructor และ Module import
  ไม่สร้าง Directory, Database หรือ Connection
- `initialize()` สร้าง Parent directory และ Schema v1 ใน Transaction
  เรียกซ้ำได้โดยไม่ล้างข้อมูล ไม่ Seed บัญชี/ห้องตัวอย่าง;
  `PRAGMA user_version` ที่ไม่ใช่ 0 หรือ 1 ถูกปฏิเสธ ต้องเพิ่ม Migration
  อย่างชัดเจนเมื่อเปลี่ยน Schema ในอนาคต
- ใช้ `with database.connect() as conn:` ภายใน Worker แต่ละตัว
  ไม่แชร์ Connection ข้าม Thread; SQLite เปิด Thread ownership check ตามปกติ
  ทุก Connection ตั้ง Foreign keys และ Busy timeout 5 วินาที ใช้ WAL บน Disk Local
- ออกจาก `connect()` จะปิด Connection และ Rollback Transaction ที่ยังค้าง
  ไม่ Commit โดยปริยาย การเขียนผ่าน API ใช้ `transaction(conn)` ซึ่งเริ่มด้วย
  `BEGIN IMMEDIATE` และ Commit เมื่อสำเร็จ หรือ Rollback เมื่อมี Exception
- เรียก API หลายตัวให้เป็นงานเดียวได้ภายใน `with transaction(conn):`
  การเรียกซ้อนใช้ Savepoint; ใช้ Helper นี้เป็น Transaction ชั้นนอกด้วย
  เพื่อได้ Write lock ก่อนอ่าน ห้ามครอบด้วย `BEGIN` แบบ Deferred
- Query ใช้ Parameters สำหรับค่าข้อมูลทั้งหมด SQL ที่ประกอบภายในมีเฉพาะ
  เงื่อนไขคงที่และชื่อ Savepoint ที่ Server สร้างเอง

ตัวอย่างตรวจ Schema โดยไม่ใช้ข้อมูลจริง:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from server.database import Database

with TemporaryDirectory() as directory:
    database = Database(Path(directory) / "studygroup.db")
    database.initialize()
    with database.connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
```

## Schema และข้อมูลถาวร

| ตาราง | ข้อบังคับหลัก |
| --- | --- |
| `users` | Username 3–24 ตัว ใช้ ASCII อังกฤษ/ตัวเลข/`_`; เก็บชื่อเดิมและค่า Lowercase ที่ UNIQUE |
| `rooms` | `private` หรือ `group`; Private ใช้คู่ User ID เรียงน้อยไปมากและ UNIQUE; Group ต้องมีชื่อและไม่มี Private pair |
| `room_members` | Primary key `(room_id, user_id)`; ขอบเขตประวัติไม่ติดลบ; Trigger จำกัดสมาชิก Private ให้เป็นคู่สนทนาและมีขอบเขต 0 |
| `messages` | ID แบบ AUTOINCREMENT ไม่ใช้ ID ที่เคย Commit แล้วซ้ำ; ผู้ส่งต้องเป็นสมาชิกของห้องผ่าน Composite foreign key; แยก Text/File |
| `attachments` | หนึ่งรายการต่อ File message; ชื่อจัดเก็บไม่ซ้ำและไม่มี Path separator; ขนาด 0–5 MiB; SHA-256 แบบ Lowercase hex 64 ตัว; สถานะ `pending`/`ready`/`failed` |

ตารางใช้ STRICT และ Foreign keys; Index รองรับสมาชิกตามผู้ใช้,
ข้อความตามห้อง/ID/เวลา และการแสดงกลุ่ม เวลาที่สร้างข้อมูลและเวลา Join
มาจาก SQLite เป็น UTC รูปแบบ `YYYY-MM-DDTHH:MM:SS.sssZ`
ไม่รับเวลาจาก Client มาแทนเวลา Server
ยังไม่มี API ลบผู้ใช้/ห้อง/สมาชิก การลบข้อมูลที่ยังถูกอ้างอิงจะถูก Foreign key ปฏิเสธ

`create_user()` รับ Hash จากฝั่ง Server และไม่สร้าง Hash เอง;
CP04 ต้องส่ง Argon2id Hash ที่สร้างด้วย Library เท่านั้น
`find_user_for_login()` เป็น Internal lookup ที่มี `password_hash`
ห้ามส่ง Row นี้กลับ Client ส่วน `create_user()` คืนเฉพาะ ID, ชื่อ และเวลา
ชื่อผิดรูปให้ `ValueError` และชื่อซ้ำให้ `sqlite3.IntegrityError`
Handler ใน CP04 ต้องแปลงเป็น Error ตาม Protocol โดยไม่ส่ง Exception ดิบ

## กติกาสิทธิ์ร่วม

ทุกฟังก์ชันที่รับ `user_id` หมายถึงตัวตนที่ Server ยืนยันแล้วจาก Connection
Library นี้ไม่ใช่ Authentication; Handler ต้องไม่รับ Actor/Sender จาก Packet

- `create_group()` เพิ่มเพียงผู้สร้างที่มีขอบเขตประวัติ 0
  `open_private_room()` ใช้คู่เรียงลำดับและคืนห้องเดิมทั้งสองทิศทาง
  พร้อมสมาชิกสองคน ขอบเขต 0 แม้เปิดห้องพร้อมกันจากคนละ Worker
- `join_group()` ใช้ Write transaction อ่าน Message ID ล่าสุดของห้องนั้น
  แล้วบันทึก `visible_after_message_id` การส่งข้อความใช้ Write transaction เช่นกัน
  จึงไม่มีข้อความแทรกระหว่างอ่านขอบเขตกับเพิ่มสมาชิก;
  Join ซ้ำคงขอบเขตและเวลาเดิม ไม่เปลี่ยนเป็น 0 หรือเลื่อนขอบเขตใหม่
- `list_groups()` และ `list_group_members()` เปิดให้บัญชีที่มีอยู่ดูข้อมูลกลุ่ม
  ตาม R9 แต่ไม่คืนข้อความ, Hash หรือรายละเอียดสมาชิกของห้อง Private
- `require_member()` ตรวจสมาชิกและคู่สนทนา Private;
  `add_text_message()` ตรวจสิทธิ์และบันทึกใน Transaction ก่อนคืนผล
- `get_messages()`, `require_message()` และ `require_attachment()`
  ใช้ SQL เงื่อนไขร่วม `VISIBLE_MESSAGES_FROM` ต้องเป็นสมาชิก,
  Private ต้องเป็นหนึ่งในคู่ และ `message_id > visible_after_message_id`
  ข้อมูลที่ไม่มีอยู่หรือไม่มีสิทธิ์ให้ `AccessDenied` (`FORBIDDEN`) เหมือนกัน
- `get_messages()` คืนหน้าล่าสุดเรียงเก่าไปใหม่ ใช้ `before_id` สำหรับหน้าก่อนหน้า
  จำกัด 1–100 รายการ; Search ใน CP07 ต้องใช้เงื่อนไขสิทธิ์เดียวกัน
  AI ใน CP09 ต้องเพิ่มเงื่อนไขเฉพาะกลุ่มและจำกัดไม่เกิน 50 ข้อความ
  รวมทั้งตรวจสิทธิ์ซ้ำก่อนคืนผล
- File message และ Attachment ยังไม่เปิดให้อ่านจนสถานะเป็น `ready`
  การเปลี่ยนสถานะของ File message เก่าหลัง Join ไม่ทำให้สมาชิกใหม่อ่านไฟล์นั้นได้
  Schema/Tests เก็บเพียง Metadata ไม่ตรวจ Bytes หรือ Hash ของไฟล์จริง;
  CP08 ต้องตรวจขนาด/Hash, สร้างชื่อจัดเก็บเอง และ Publish แบบ Transaction
  หลังรับครบเท่านั้น ห้ามคืน `stored_name` หรือใช้ `original_name` เป็น Path ของ Client

CP05 ใช้ `message_recipient_ids()` เลือกผู้รับ Live Events ด้วย Join/Predicate เดียวกับ
`VISIBLE_MESSAGES_FROM` ใน Query เดียว แล้วเข้าคิว Event หลัง Commit
ดูสัญญาและการตรวจสิทธิ์ผ่าน Network ใน [chat.md](chat.md)

## การตรวจรับ

```bash
uv run --locked pytest tests/test_database.py tests/test_permissions.py
uv run --locked pytest
```

Tests ใช้ฐานข้อมูลใน Temporary directory และ Connection จริงแยกตาม Thread
ครอบคลุม Constraints, Initialization/Reopen, UTC, Rollback/Savepoints,
การแย่งสร้าง Username/Private room/Join, Join พร้อม Send ทั้งสองลำดับ
และสิทธิ์สมาชิก/คนนอก/สมาชิกใหม่ต่อข้อความและ Metadata ไฟล์
ไม่ใช้ `.env`, ใบรับรอง หรือข้อมูลจริงใน `data/` เป็น Fixture
