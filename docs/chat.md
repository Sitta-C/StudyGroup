# Chat Server (CP05)

เปิด Server ตาม [authentication.md](authentication.md) และใช้ TLS transport เดิม
ทุกคำขอด้านล่างต้อง Login แล้ว ผู้ส่ง/ผู้เข้ากลุ่มมาจาก `connection.user`
ห้ามส่ง `sender_id`, `user_id`, `username`, รายชื่อสมาชิก หรือ Fields เพิ่มเพื่ออ้างตัวตน

## คำขอและผลตอบกลับ

ใช้ Envelope, Request ID และ Error ตาม [protocol.md](protocol.md)

| Request | `data` | สำเร็จ: `result` |
| --- | --- | --- |
| `USERS_LIST` | `{}` | `{"users":[{"id":1,"username":"Alice"}]}` ตาม CP04 |
| `PRIVATE_ROOM_OPEN` | `{"peer_id":2}` | `{"room": Room}` |
| `GROUP_CREATE` | `{"name":"กลุ่มอ่านหนังสือ"}` | `{"room": Room}` |
| `GROUP_LIST` | `{}` หรือ `{"after_id":0,"limit":50}` | `{"groups":[Room],"next_after_id":null}` |
| `GROUP_JOIN` | `{"room_id":12}` | `{"room": Room}` |
| `MESSAGE_SEND` | `{"room_id":12,"text":"สวัสดี 👋"}` | `{"message": Message}` |

`Room` มีเพียง `id`, `kind` (`private`/`group`), `name` (Private เป็น `null`),
`created_by`, `created_at`, `members` โดยสมาชิกแต่ละคนมี `id`, `username`, `joined_at`
เรียงตาม User ID ไม่ส่ง Password hash, คู่ Private ภายใน Schema หรือขอบเขตประวัติของสมาชิก
ทุกเวลาเป็น UTC ลงท้าย `Z`

`Message` มี `message_id`, `room_id`, `sender_id`, `text`, `created_at`
เป็นข้อมูลเดียวกันทั้ง Response และ `MESSAGE_NEW` ผู้ส่งต้องใช้ `message_id`
รวมผลตอบกลับกับ Event echo เป็นข้อความเดียวใน GUI

- IDs ต้องเป็น Integer จริงระหว่าง 1 ถึง `2**63 - 1` ไม่รับ Bool/Float/String
- ชื่อกลุ่ม 1–100 Unicode characters ตรวจขนาดก่อน Trim ช่องว่างหัวท้าย
  ข้อความแชต 1–4,000 characters และไม่เกิน 16,000 UTF-8 bytes
  ทั้งสองอย่างต้องไม่เป็นช่องว่างล้วนและไม่มี NUL
  ข้อความแชตเก็บช่องว่าง/บรรทัดใหม่/Unicode ตามที่ส่ง ไม่ Normalize หรือ Trim
- Private room ใช้ห้องเดิมเสมอเมื่อสลับคู่หรือเปิดพร้อมกัน มีสมาชิกเพียงสองบัญชี
  ห้ามเปิดหาตนเอง บัญชีคู่สนทนาต้องมีอยู่แต่ไม่จำเป็นต้องออนไลน์ในขณะส่ง
- สร้างกลุ่มได้หลายกลุ่มและชื่อซ้ำได้ แต่ละกลุ่มมี ID ของตัวเอง
  ตอนสร้างมีเพียงผู้สร้างเป็นสมาชิก คนอื่นต้อง Join ด้วย Connection ของตนเอง
  Join ซ้ำคืนสมาชิกเดิม ไม่เลื่อนขอบเขตประวัติหรือประกาศ Event ซ้ำ
- ทุกบัญชีที่ Login เห็นกลุ่มและสมาชิกทั้งหมดผ่าน `GROUP_LIST` แม้ไม่ได้เข้าร่วม
  ไม่มี Private rooms หรือข้อความในผลตอบกลับ รายชื่อกลุ่มเรียงตาม ID
  ใช้ `next_after_id` เป็น `after_id` ของหน้าถัดไปจนเป็น `null`
  `after_id` เริ่มที่ 0 และ `limit` เป็น Integer 1–100 ค่าเริ่มต้น 50
- สมาชิกต้องมีสิทธิ์ก่อนส่งข้อความ ID ห้องที่ไม่มีอยู่หรือเข้าไม่ถึง และการ Join
  Private room ให้ `FORBIDDEN` แบบเดียวกัน ไม่คืนเนื้อหาหรือข้อมูล Private room
  Fields ขาด/เกิน, ID ผิดชนิด, เปิด Private หาตนเอง หรือข้อความผิดขอบเขตให้ `INVALID_INPUT`

## Live Events และลำดับการบันทึก

```json
{"v":1,"type":"GROUPS_UPDATED","data":{"room_id":12}}
```

ส่งเมื่อสร้างกลุ่มหรือมีสมาชิกใหม่ ให้ทุก Connection ที่ Login อยู่รวมผู้ทำรายการ
เป็นสัญญาณให้เรียก `GROUP_LIST` ใหม่ ไม่มีข้อความหรือ Private room metadata
Client ต้องโหลดรายชื่อเริ่มต้นหลัง Login; ไม่มีการ Replay Events ย้อนหลัง

```json
{"v":1,"type":"MESSAGE_NEW","data":{"message_id":205,"room_id":12,"sender_id":3,"text":"สวัสดี 👋","created_at":"2026-11-06T13:00:00.000Z"}}
```

ส่งเฉพาะผู้ Login ที่มีสิทธิ์อ่านข้อความนั้น รวมผู้ส่ง ไม่ Broadcast เนื้อหาให้ทุกคน
รายชื่อผู้รับใช้ Predicate เดียวกับประวัติ/ไฟล์ใน `server/permissions.py`:
ต้องเป็นสมาชิก คู่ Private ต้องตรง และ Message ID มากกว่า `visible_after_message_id`
สมาชิกใหม่จึงไม่ได้รับข้อความก่อน Join ทั้งจาก Live Event และ Database query

Chat handlers ใช้ Lock ร่วมต่อ Server ตั้งแต่ Transaction จนถึงเข้าคิวผลตอบกลับ/Event
จึงรักษาลำดับ Message ID และขอบเขต Join เมื่อหลาย Workers ส่งพร้อมกัน
แต่ละ Worker เปิด SQLite ของตนเอง ใช้ `BEGIN IMMEDIATE` และ Commit ก่อนเข้าคิวสำเร็จ
หรือ Event เสมอ หาก Transaction ล้มเหลวจะ Rollback และไม่ประกาศ Event
Lock ไม่ครอบ Socket I/O: Registry เข้าคิวแบบไม่รอ และเจ้าของ Connection ส่ง TLS เอง
Queue เต็มปิด Connection ที่ช้าโดยไม่กีดกันผู้รับคนอื่นตาม CP04

ผลตอบกลับของผู้ส่ง/ผู้สร้าง/ผู้ Join เข้าคิวก่อน Event ของรายการเดียวกัน
แต่ Events อื่นอาจแทรกระหว่าง Requests ได้ ต้องจับคู่ Response ด้วย Request ID
Logout/EOF/Error ลบ Session ตาม Registry เดิม ไม่ส่ง Events แชตให้ Connection ที่ยังไม่ Login
หรือ Logout แล้ว ไม่มีการ Push ข้อความที่ส่งตอน Offline ย้อนหลังเมื่อ Login ใหม่
ข้อความยังเก็บใน SQLite และการโหลดประวัติผ่าน Network เป็นงาน CP07

## ขอบเขตและการตรวจรับ

- ไม่มี Retry หรือ Exactly-once delivery: หากหลุดหลัง Commit แต่อ่าน Response ไม่ทัน
  ข้อความอาจถูกบันทึกแล้ว ห้ามส่งซ้ำอัตโนมัติ Request ID ใช้จับคู่ผลเท่านั้น
- Frame cap ยังเป็น 1 MiB รายชื่อสมาชิกภายในแต่ละ Room อยู่ใน Frame เดียว
  ถ้ารายชื่อกลุ่มเกินขนาดให้ `FRAME_TOO_LARGE` แล้วขอ `limit` เล็กลงได้
  ถ้ารายชื่อสมาชิกของกลุ่มเดียวเกิน 1 MiB ต้องเพิ่ม Member pagination ก่อนรองรับขนาดนั้น
  การ Join ที่ทำให้ Response เกินขนาดจะ Rollback และ Connection ยังใช้ต่อได้
- `HISTORY_GET`, `HISTORY_SEARCH`, Files และ AI ยังให้ `UNKNOWN_TYPE` หลัง Login
  CP05 ตรวจ Live chat กับข้อมูลถาวรฝั่ง Server; CP06 เพิ่ม Tkinter และ Network worker แล้ว
  การตรวจสองเครื่องจริงยังต้องทำ ดู [demo-checklist.md](demo-checklist.md)

```bash
uv run --locked pytest tests/test_chat_integration.py -q
uv run --locked pytest -q
```

Tests ใช้ A/B/C ผ่าน TCP/TLS จริงบน Loopback พร้อม CA/Keys และ SQLite ชั่วคราว
ตรวจการเปิด Private พร้อมกัน, หลายกลุ่ม/สมาชิก, ส่งพร้อมกัน, Join/Send ทั้งสองลำดับ,
เดา Room ID/ปลอม Sender, ข้อความไทย/Emoji, Rollback/Commit ก่อน Event,
Logout/Offline, Frame limit และข้อมูลหลัง Restart ผลล่าสุดอยู่ใน
[DEVELOPMENT.md](../DEVELOPMENT.md)
