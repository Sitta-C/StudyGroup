# StudyGroup Socket Protocol v1

สัญญาระดับ Frame และ Packet ที่ใช้จริงใน `shared/protocol.py`,
`shared/message_types.py` และ `shared/validation.py` ตาม CP02
ใช้กับ Blocking TCP Socket และ Socket ที่หุ้ม TLS แล้วใน CP04
Server/Router และ Auth handlers ใช้สัญญารายฟีเจอร์ใน [authentication.md](authentication.md)
Chat/Groups/History/Files/AI handlers ยังเป็นงาน checkpoint ถัดไป

## Frame

```text
4 bytes: unsigned big-endian length N | N bytes: JSON encoded as UTF-8
```

- Header ใช้ `struct.Struct("!I")`; N นับ **bytes ของ Body** ไม่ใช่จำนวนตัวอักษร
  และไม่รวม Header ไม่มี Newline หรือ Null terminator ท้าย Frame
- `1 <= N <= 1,048,576` (1 MiB) ใช้ขอบเขตเดียวกันทั้งสองฝั่ง
  Header ที่เป็น 0 หรือเกิน Limit ถูกปฏิเสธก่อนอ่านหรือ Allocate Body ตาม N
- Body เป็น JSON Object หนึ่งรายการ รองรับไทย Emoji และ Unicode
  ฝั่งส่งใช้ `ensure_ascii=False`; ฝั่งรับรองรับ JSON Unicode escapes ด้วย
- ห้าม BOM, UTF-8 ผิดรูป, JSON ซ้ำหลายรายการใน Body, Duplicate keys ทุกระดับ,
  `NaN`, `Infinity`, ตัวเลขที่กลายเป็นค่าไม่สิ้นสุด และ Unpaired surrogates
  ไม่แปลงชนิดข้อมูลเงียบ ๆ และจำกัดความลึก JSON ที่ 64 จาก Root ระดับ 0
- TCP อาจแบ่งหนึ่ง Frame เป็นหลาย `recv()` หรือรวมหลาย Frame ใน Buffer เดียว
  `recv_exact()` วนรับเท่าที่เหลือ และ `recv_packet()` ใช้ข้อมูลเพียง Frame เดียว

## Envelope และประเภท Packet

| ชนิด | Fields ที่อนุญาตทั้งหมด | ทิศทาง |
| --- | --- | --- |
| Request | `v`, `id`, `type`, `data` | Client → Server |
| Response | `v`, `id`, `type: "RESPONSE"`, `data` | Server → Client |
| Event | `v`, `type`, `data` ไม่มี `id` | Server → Client |

`v` ต้องเป็น Integer `1` เท่านั้น ไม่รับ Boolean หรือ Float
`data` ต้องเป็น Object เสมอ ไม่รับ Array/Null และห้าม Fields เกินใน Envelope
`type` ต้องตรงชื่อใน `RequestType`, `EventType` หรือ `RESPONSE`

Request ID เป็น String ยาว 1–64 ตัว ใช้ ASCII `[A-Za-z0-9_.:-]`
Client ใช้ ID ไม่ซ้ำกันในคำขอที่ยังรอผลต่อ Connection; `make_request()` สร้าง
UUID4 hex ให้เมื่อไม่ระบุ `request_id` Server ตอบด้วย ID เดิม
Response และ Event อาจสลับลำดับกันได้ Client จึงจับคู่ด้วย ID ไม่ใช่ลำดับการรับ
ID ใช้จับคู่ผลเท่านั้น ไม่ใช่สิทธิ์เข้าถึงข้อมูลหรือกลไกป้องกันการทำคำขอซ้ำ
การติดตาม Pending requests เป็นหน้าที่ Network/Router ใน checkpoint ถัดไป

คำขอที่มีชื่อประกาศแล้ว:

| กลุ่ม | `RequestType` |
| --- | --- |
| Auth | `REGISTER`, `LOGIN`, `LOGOUT` |
| Users/Rooms | `USERS_LIST`, `PRIVATE_ROOM_OPEN`, `GROUP_CREATE`, `GROUP_LIST`, `GROUP_JOIN` |
| Chat/History | `MESSAGE_SEND`, `HISTORY_GET`, `HISTORY_SEARCH` |
| Files | `FILE_BEGIN`, `FILE_CHUNK`, `FILE_END`, `FILE_GET` |
| AI | `AI_SUMMARIZE` |

Events: `USERS_UPDATED`, `GROUPS_UPDATED`, `MESSAGE_NEW`

CP02 ตรวจโครงสร้าง Envelope, ชนิดข้อมูล JSON และรูปแบบ Response/Error
ส่วน Fields ภายใน `data` ของ Request/Event และภายใน `result` ยังเป็น Object
ที่ไม่ได้กำหนด Schema รายฟีเจอร์ การมีชื่อคำสั่งไม่ได้หมายความว่ามี Handler แล้ว
ให้เพิ่ม Field validation, ขอบเขตข้อความ/ไฟล์, Authentication และ Authorization
ใน checkpoint ของฟีเจอร์นั้นก่อนนำไปใช้งานจริง
ตัวอย่าง `sender_id` ใน Event มาจาก Server; Handler ต้องใช้ผู้ที่ Login บน Connection
เป็นผู้ส่งเสมอและต้องปฏิเสธการอ้างตัวตนเองในข้อมูลคำขอ
Transport ไม่ใช่ตัวตรวจสมาชิกห้องหรือผู้ส่ง

## ตัวอย่าง Request / Response / Event

ตัวอย่างด้านล่างแสดง Body; ส่งจริงต้องมี Header ตามจำนวน UTF-8 bytes ด้านหน้า

```json
{"v":1,"id":"req-42","type":"MESSAGE_SEND","data":{"room_id":12,"text":"ประชุมตอนสองทุ่มนะ 👋"}}
```

สำเร็จ: `data` มีเพียง `ok: true` และ `result` ซึ่งต้องเป็น Object

```json
{"v":1,"id":"req-42","type":"RESPONSE","data":{"ok":true,"result":{"message_id":205}}}
```

ผิดพลาด: `data` มีเพียง `ok: false` และ `error` ซึ่งมี `code`, `message` เท่านั้น
`message` ต้องเป็น String ไม่ว่าง/ไม่เป็นช่องว่างล้วน และยาวไม่เกิน 512 ตัวอักษร
ไม่ส่ง Exception, Credentials หรือข้อมูลลับกลับ Client

```json
{"v":1,"id":"req-42","type":"RESPONSE","data":{"ok":false,"error":{"code":"AUTH_REQUIRED","message":"กรุณาเข้าสู่ระบบ"}}}
```

Event ไม่ต้องรอ Request และไม่มี Request ID:

```json
{"v":1,"type":"MESSAGE_NEW","data":{"message_id":205,"room_id":12,"sender_id":3,"text":"ประชุมตอนสองทุ่มนะ 👋","created_at":"2026-11-06T13:00:00Z"}}
```

## Error และ EOF

| ผลจาก API / Code | ความหมายและการจัดการ |
| --- | --- |
| `recv_packet()` คืน `None` | EOF ปกติที่เริ่ม Header ใหม่ ยังไม่ได้รับ Header แม้แต่ Byte เดียว |
| `IncompleteFrameError(EOFError)` | EOF กลาง Header หรือ Body รวมถึง Header ครบแต่ Body ไม่มาเลย; มี `expected`/`received` ของส่วนที่กำลังอ่าน |
| `ProtocolError`, `INVALID_FRAME` | Header ระบุ Body ขนาด 0 |
| `ProtocolError`, `FRAME_TOO_LARGE` | Body เกิน 1 MiB ทั้งรับและส่ง |
| `ProtocolError`, `INVALID_JSON` | JSON/UTF-8 ผิดรูป, Duplicate keys, ค่าคงที่นอก JSON หรือ Decoder ไม่สามารถอ่านได้ |
| `PacketValidationError(ProtocolError)`, `INVALID_PACKET` | JSON อ่านได้แต่ Envelope/Response/ชนิดค่าหรือความลึกผิดสัญญา |
| `PacketValidationError`, `UNSUPPORTED_VERSION` | Version เป็น Integer แต่ไม่ใช่ 1 |
| `PacketValidationError`, `UNKNOWN_TYPE` | ชนิด Packet ไม่ตรงชื่อที่ประกาศ |
| `TimeoutError` / `OSError` | ส่งต่อข้อผิดพลาด Socket ตามจริง ไม่แปลงเป็น EOF ปกติ |

ความลึกสุดขั้วอาจเป็น `INVALID_JSON` จาก Decoder หรือ `INVALID_PACKET` จาก
Validator ตาม Python runtime ทั้งสองกรณีถูกปฏิเสธด้วย `ProtocolError`
ข้อความ Exception ที่ Library สร้างไม่คัดลอก Payload ที่รับมา

Error Codes ฝั่งฟีเจอร์ที่ประกาศไว้เพิ่มเติม (Auth เริ่มใช้แล้วใน CP04):
`INVALID_INPUT`, `AUTH_REQUIRED`, `AUTH_FAILED`, `USERNAME_TAKEN`,
`ALREADY_LOGGED_IN`, `FORBIDDEN`, `NOT_FOUND`, `RATE_LIMITED`,
`AI_UNAVAILABLE`, `INTERNAL_ERROR`

Library ไม่ส่ง Error Response อัตโนมัติ ไม่สร้าง ID ปลอมให้ Frame ที่อ่านไม่ได้
เมื่อ **รับ** เกิด Error ใด ๆ ผู้เรียกต้องปิดและทิ้ง Connection ไม่อ่านต่อเพื่อหา Frame ใหม่
เพราะ Timeout/EOF/Frame ผิดรูปอาจทำให้ตำแหน่ง Stream ไม่สมบูรณ์
Router ใน CP04 จึงต้องมี Cleanup ครอบคลุม Error เหล่านี้

เมื่อ **ส่ง** เกิด Validation/Size error ยังไม่มีการเขียน Bytes จึงแก้ข้อมูลแล้วส่งใหม่ได้
แต่เมื่อ `sendall()` ล้มเหลว อาจเขียนไปแล้วบางส่วน; `PacketConnection` จะจำสถานะ
และปฏิเสธการเขียนครั้งต่อไปด้วย `ConnectionError` ผู้เรียกต้องปิด Socket และ
เชื่อมต่อใหม่ ไม่ส่งคำขอซ้ำอัตโนมัติหรือถือว่าคำขอเดิมทำสำเร็จ

## API และงานพร้อมกัน

```python
from shared.message_types import RequestType
from shared.protocol import PacketConnection, make_request

# sock เป็น Blocking Socket ที่ตั้ง Timeout แล้ว
# ในแอปจริงต้องผ่าน TLS และตรวจ CA/Hostname ก่อนส่ง Credentials (CP04)
connection = PacketConnection(sock)
connection.send_packet(make_request(
    RequestType.MESSAGE_SEND,
    {"room_id": 12, "text": "สวัสดีครับ"},
))
packet = connection.recv_packet()  # dict หรือ None เมื่อ EOF ปกติ
```

- ใช้ **หนึ่ง `PacketConnection` ต่อ Socket** และส่งผ่าน `send_packet()` ของ Object
  เดียวกันทุก Thread ตัว Lock ครอบคลุม `sendall()` ของ Frame ทั้ง Header และ Body
  เพื่อไม่ให้ Response/Event/File chunk แทรกกัน ห้ามสร้าง Wrapper หลายตัวบน Socket เดียว
  หรือเขียนลง Socket โดยตรงระหว่างใช้งาน Wrapper
- มี Reader เพียงหนึ่ง Thread ต่อ Socket; `recv_packet(sock)` แบบ Function
  มีไว้ใช้ใน Receive worker/Tests ไม่เรียกอ่านพร้อมกันหลาย Thread
- `encode_packet(packet)` ใช้เตรียม Frame/Tests; `make_request`, `make_response`,
  `make_error`, `make_event` สร้างและตรวจ Envelope ตามสัญญา ไม่ทำ Network I/O
- อย่าแก้ไข Packet/`data` จากอีก Thread ระหว่าง Validate/Encode/Send
  Builders ไม่ Copy ข้อมูลภายใน
- Caller เป็นเจ้าของ Socket, Timeout และการปิด/Cleanup; Lock การเขียน
  ไม่ขวาง Reader แต่ TLS Server ใน CP04 ใช้เจ้าของ I/O เพียง Worker เดียวต่อ Socket
  และ Outbound queue สำหรับ Thread อื่น ตาม [authentication.md](authentication.md)
- Module import ไม่เปิด Network ไม่อ่าน Config และไม่สร้าง Runtime data

## หลักฐานและคำสั่งทดสอบ

```bash
uv run --locked pytest tests/test_protocol.py
uv run --locked pytest
```

`tests/test_protocol.py` เปิด TCP จริงบน `127.0.0.1` ด้วยพอร์ตที่ OS เลือก
ไม่ต้องมี Server แอปหรือ Certificate ใช้ Wrapper บังคับอ่านทีละ 1–7 Bytes
และแยกการเขียนเพื่อทดสอบ Fragmentation โดยไม่พึ่งการแบ่ง Packet ของ OS
ทดสอบ Frame ติดกัน, EOF, ขนาดขอบเขต 1 MiB, Header 0/เกิน Limit,
JSON/Envelope ผิดรูป, Request/Response/Event สองทิศทาง และ Writer 6 Threads
ส่งรวม 120 Frames โดยแยกหนึ่ง `sendall` เป็นหลาย TCP writes เพื่อทดสอบ Lock
ผลตรวจรอบล่าสุดและข้อจำกัดของ Environment บันทึกใน `DEVELOPMENT.md`

อ้างอิง API ที่ใช้: [Python 3.14 socket](https://docs.python.org/3.14/library/socket.html)
และ [Python 3.14 json](https://docs.python.org/3.14/library/json.html)
