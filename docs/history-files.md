# ประวัติ ค้นหา และไฟล์ (CP07–CP08)

สัญญาที่ใช้จริงใน `server/handlers/history.py`, `server/handlers/files.py`
และ React (`web/src/chat.ts`, `web/src/files.ts`) ใช้ Envelope/Request ID/Error ตาม
[protocol.md](protocol.md) ผ่าน WebSocket `/ws` เดียวกับแชต (Legacy TCP/TLS ใช้ handlers เดียวกัน)
ทุกคำขอต้อง Login แล้ว ตัวตนมาจาก Connection เสมอ ห้ามส่ง `user_id`/`sender_id`
Fields ขาด/เกินหรือชนิดผิดให้ `INVALID_INPUT`; ห้องที่ไม่มีอยู่และห้องที่เข้าไม่ถึงให้
`FORBIDDEN` แบบเดียวกัน (ไม่บอกว่ามี ID นั้นหรือไม่)

## Message

`Message` ของข้อความตัวอักษรคงรูปเดิมจาก CP05:
`message_id`, `room_id`, `sender_id`, `text`, `created_at` (UTC ลงท้าย `Z`)
ข้อความไฟล์มี `text: null` และเพิ่ม `attachment`:

```json
{"message_id":9,"room_id":3,"sender_id":1,"text":null,"created_at":"2026-11-06T14:31:02.120Z",
 "attachment":{"id":4,"name":"รายงาน Lab 3.pdf","size":1500000,"sha256":"c95b…"}}
```

ชื่อจัดเก็บบน Server (`stored_name`) ไม่ออกนอก Server ทั้ง Response, History และ `MESSAGE_NEW`

## ประวัติและค้นหา (CP07)

| Request | `data` | สำเร็จ: `result` |
| --- | --- | --- |
| `PRIVATE_ROOM_LIST` | `{}` หรือ `{"after_id":0,"limit":50}` | `{"rooms":[Room],"next_after_id":null}` เฉพาะห้องส่วนตัวของผู้ขอ |
| `HISTORY_GET` | `{"room_id":3}` + optional `before_id`, `limit` | `{"messages":[Message] (เก่า→ใหม่), "next_before_id": 12 \| null}` |
| `HISTORY_SEARCH` | `{"room_id":3}` + อย่างน้อยหนึ่งใน `query`, `from`, `to`, `kind` + optional `before_id`, `limit` | `{"messages":[Message] (ใหม่→เก่า), "next_before_id"}` |

- `PRIVATE_ROOM_LIST` ทำให้เห็นแชตส่วนตัวเดิมหลัง Login ใหม่ แม้คู่สนทนาออฟไลน์
  (`GROUP_LIST` ไม่เคยคืน Private room)
- **Pagination แบบ Keyset ด้วย Message ID:** หน้าแรกไม่ส่ง `before_id` ได้ข้อความล่าสุด
  หน้าถัดไปส่ง `before_id = next_before_id` จนเป็น `null`
  ข้อความใหม่ระหว่างโหลดมี ID มากกว่าทุกหน้าเดิมเสมอ จึงไม่ทำให้หน้าเก่าเลื่อน ข้าม หรือซ้ำ
  ข้อความใหม่เข้ามาทาง `MESSAGE_NEW` และ Client รวมด้วย `message_id`
- `limit` 1–100 ค่าเริ่มต้น 50 (UI ค้นหาใช้ 30) ถ้าหน้าเกิน 1 MiB ได้ `FRAME_TOO_LARGE`
  แล้ว Client ลด `limit` ครึ่งหนึ่งอัตโนมัติ
- `query` 1–200 ตัวอักษร ไม่เป็นช่องว่างล้วนและไม่มี NUL ตัดช่องว่างหัวท้ายก่อนค้น
  เป็น Substring แบบตรงตัว (`%`, `_`, `\` ไม่ใช่ Wildcard) ไม่แยกตัวพิมพ์ใหญ่/เล็กเฉพาะ ASCII
  ค้นทั้งข้อความและชื่อไฟล์แนบ
- `from`/`to` เป็น ISO 8601 ที่ **ต้องมี Offset** (`Z` หรือ `+07:00`) Server แปลงเป็น UTC
  รูปแบบเดียวกับ `created_at` ก่อน Query: `from` รวมขอบ, `to` ไม่รวมขอบ, ต้อง `from < to`
  ปีที่รับคือ 2000–9998 เศษต่ำกว่ามิลลิวินาทีปัดขึ้น
- Browser แปลงวันที่ปฏิทินของผู้ใช้เป็นช่วง UTC เอง: ช่อง “ตั้งแต่ 6 พ.ย.” และ “ถึง 6 พ.ย.”
  ที่ Asia/Bangkok กลายเป็น `from=2026-11-05T17:00:00.000Z`, `to=2026-11-06T17:00:00.000Z`
- `kind` เป็น `text` หรือ `file`; แท็บ “ไฟล์” ใช้ `HISTORY_SEARCH {"kind":"file"}`
- ทุกคำสั่งใช้ `search_messages()` ซึ่งใช้ Predicate ร่วมใน `server/permissions.py`:
  ต้องเป็นสมาชิก คู่ Private ต้องตรง ข้อความต้องมี ID มากกว่า `visible_after_message_id`
  และไฟล์ต้องมีสถานะ `ready` สมาชิกใหม่จึงอ่าน/ค้น/ดาวน์โหลดสิ่งที่อยู่ก่อนตน Join ไม่ได้

UI: หลัง Login (รวม Refresh/ปิดเปิด Browser) โหลดรายชื่อห้องและหน้าล่าสุดของห้องที่เปิด
มีปุ่ม “โหลดข้อความก่อนหน้า” ที่คงตำแหน่ง Scroll เดิม และแจ้งเมื่อถึงจุดเริ่มต้นที่มีสิทธิ์เห็น
Dialog ค้นหาทำงานแบบ async มีสถานะกำลังค้นหา/ไม่พบ/Error และทิ้งผลเก่าที่มาช้า
กดผลลัพธ์แล้วโหลดหน้าเก่าจนพบข้อความ จากนั้นเลื่อนไปและไฮไลต์ชั่วคราว
เมื่อ Login ใหม่จะล้างข้อความในหน่วยความจำแล้วโหลดจาก Server ใหม่ (ร่างข้อความยังอยู่)
จึงไม่มีช่องว่างจากข้อความที่ส่งมาระหว่างหลุด และไม่มีการส่งซ้ำอัตโนมัติ

## ส่งไฟล์ (CP08)

```text
FILE_BEGIN {room_id, name, size, sha256}        -> {transfer_id, chunk_size: 32768, chunks}
FILE_CHUNK {transfer_id, index, data(Base64)}   -> {received}         (ทำซ้ำ index = 0..chunks-1)
FILE_END   {transfer_id}                        -> {message}          + MESSAGE_NEW ถึงสมาชิกที่มีสิทธิ์
FILE_GET   {attachment_id, offset?}             -> {attachment_id, name, size, sha256, offset, data, done}
```

- ขนาด 0–5 MiB (5,242,880 bytes) นับจาก **Bytes จริงหลัง Decode**: ทุก Chunk ยกเว้นตัวสุดท้าย
  ต้องเป็น 32 KiB พอดี ตัวสุดท้ายต้องเท่าที่เหลือ ความยาว Base64 ต้องตรงขนาดนั้น
  และ Decode แบบ strict ส่งเกิน/ขาด/ผิดลำดับ/ซ้ำ/Base64 ผิด = `INVALID_INPUT` และยกเลิก Transfer ทันที
- `sha256` เป็น hex ตัวเล็ก 64 ตัว Server คำนวณ Hash ระหว่างรับและเทียบตอน `FILE_END`
  ไม่ครบหรือ Hash ไม่ตรง = `INVALID_INPUT` ไม่สร้าง Message/Attachment และลบไฟล์ชั่วคราว
- `name` เป็นเพียงชื่อแสดงผล 1–255 ตัวอักษร (≤1020 bytes) ปฏิเสธ `/ \ : * ? " < > |`,
  `.`/`..`, ช่องว่างหัวท้าย และอักขระควบคุม/ทิศทาง (เช่น U+202E) ไม่แปลงชื่อให้เงียบ ๆ
- ไฟล์ชั่วคราวอยู่ที่ `data/uploads/.partial/<transfer_id>.part` (สร้างด้วย `O_EXCL`, สิทธิ์ 0600)
  เมื่อผ่านทุกเงื่อนไข Server สุ่ม `stored_name` hex 32 ตัว แล้ว `os.replace` ไป `data/uploads/<stored_name>`
  จากนั้น Commit Message + Attachment (`status='ready'`) ใน Transaction เดียวและตรวจสมาชิกซ้ำ
  ประกาศ `MESSAGE_NEW` ใต้ Lock เดียวกับแชตเพื่อรักษาลำดับ ถ้า Commit ล้มเหลวจะลบไฟล์ที่ย้ายแล้ว
- `transfer_id` สร้างโดย Server ผูกกับ Connection และผู้ใช้ที่เริ่ม Connection อื่น/บัญชีอื่นใช้ไม่ได้
  ต่อ Connection มีได้ 3 Transfers และทั้ง Server 32 (`RATE_LIMITED` เมื่อเกิน)
  Transfer ที่ไม่มี Chunk ใหม่ 120 วินาที หรือเปิดนานเกิน 600 วินาที ถูกลบเมื่อมีคำขอ `FILE_*` ถัดไป
  `FILE_BEGIN` ปฏิเสธด้วย `RATE_LIMITED` เมื่อพื้นที่ว่างบน Disk เหลือน้อยกว่าขนาดไฟล์ + 64 MiB
  `LOGOUT` (แม้ Socket ยังเปิด) และ EOF/Error ลบ Transfers ของ Connection นั้น
  ตอนเริ่ม Server ลบ `.part` ที่ค้าง และไฟล์ชื่อ hex 32 ตัวใน `uploads/` ที่ไม่มีแถว Attachment
  (หยุดระหว่าง rename กับ commit) และ fsync โฟลเดอร์หลัง rename ก่อน commit
- `FILE_GET` ตรวจ `require_attachment()` ทุก Chunk (สมาชิก + ขอบเขต Join + `ready`)
  ส่งทีละ 128 KiB ตาม `offset` (0 ถึงก่อน `size`; ไฟล์ว่างใช้ 0) Attachment ID ที่เดาหรือของห้องอื่นได้ `FORBIDDEN`
  ไฟล์หายจาก Disk ได้ `NOT_FOUND` หลังผ่านสิทธิ์แล้วเท่านั้น
- Browser คำนวณ SHA-256 ด้วย `crypto.subtle` (มี Fallback แบบ JavaScript เมื่อเป็น HTTP ที่ไม่ใช่ secure context)
  ส่ง Chunk แบบ pipeline ครั้งละ 4 และดาวน์โหลดครั้งละ 2 คำขอ `FILE_*` รอได้ 60 วินาที
  (คำขออื่น 15 วินาที) เพื่อไม่ให้เน็ตช้าทำให้ Session หลุด แสดง Progress ทั้งสองทาง
  ตรวจ Hash ซ้ำหลังดาวน์โหลดก่อนบันทึก ถ้าไม่ตรงจะไม่บันทึกไฟล์ ไฟล์เกิน 5 MiB ถูกปฏิเสธก่อนส่ง
  การหลุดระหว่างส่ง/รับแสดง Error และให้ Login ใหม่ ไม่ส่งไฟล์ซ้ำเอง

Backup/Restore (CP10) ต้องเก็บ `studygroup.db` และ `uploads/` ไปพร้อมกัน

ข้อจำกัดที่ยังมี: ไม่มีโควตาพื้นที่ต่อผู้ใช้/ห้อง (มีเพียงตรวจพื้นที่ว่างรวม) และการกดผลค้นหาที่เก่ากว่า
ประมาณ 2,000 ข้อความจะแจ้งให้ค้นด้วยช่วงวันที่แคบลงแทนการโหลดประวัติทั้งหมด

## หลักฐานทดสอบ

```bash
uv run --locked pytest tests/test_history_integration.py tests/test_files_integration.py -q
npm --prefix web run build && npm --prefix web run test:e2e
```

Python tests ใช้ WebSocket จริงกับ SQLite/uploads ชั่วคราว ครอบคลุม Restart ของ Server,
Pagination ระหว่างมีข้อความใหม่, คนนอก/สมาชิกใหม่, Keyword แบบ literal/ไทย, ช่วงวันที่ UTC/Offset,
Frame limit, ไฟล์ 5 MiB ไป-กลับ Hash ตรง, ไฟล์เกินขนาด, Chunk ผิดลำดับ/ซ้ำ/Base64 ผิด, Hash ผิด,
ไฟล์ไม่ครบ, Path traversal/ชื่ออันตราย, หลุดกลางทาง, Transfer ของ Connection อื่น,
เดา Attachment ID/ไฟล์ก่อน Join, จำกัดจำนวน Transfer และ `.part` ที่ค้างตอนเริ่ม Server
Browser E2E ใช้ React build จริง: Reload แล้วประวัติยังอยู่, โหลดหน้าเก่าไม่ซ้ำ/ไม่ขาด,
ค้นคำ+วันที่แล้วกระโดดไปข้อความ, สมาชิกใหม่/คนนอก, อัปโหลด-ดาวน์โหลดเทียบ SHA-256,
แท็บไฟล์ และตัดการเชื่อมต่อระหว่างอัปโหลด ผลล่าสุดอยู่ใน [DEVELOPMENT.md](../DEVELOPMENT.md)
