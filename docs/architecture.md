# StudyGroup architecture

แอป Desktop ใช้ Tkinter และ TCP Socket หุ้ม TLS ข้อมูลถาวรอยู่ที่ Server เท่านั้น
Local ใช้ Server บนเครื่องพัฒนาได้ ส่วน Cloud deployment เป็น CP10

```text
Tk main thread                         Network worker (หนึ่งตัวต่อ Connection)
  Application / Views                  ตรวจ CA + hostname / TLS handshake
  ClientController                     nonblocking TLS read / write
  Session (ข้อมูลในหน่วยความจำ)        frame buffer / request deadlines
       │                                        │
       ├──── bounded request queue + wake ──────►│
       ◄──── bounded event queue ────────────────┤
       │                                        │
  after(40 ms) → pump()                    TCP + TLS
                                                │
                                       Server listener
                                                │
                                       Connection owner thread
                                       Router → Auth / Chat handlers
                                                │
                                       SQLite connection ต่อ worker
                                       SessionRegistry → event outboxes
```

## หน้าที่ของแต่ละส่วน

- `client/main.py` เปิดหน้าต่าง Native และ Tk event loop
- `client/app.py`, `client/ui/` ดูแล Login/Register, Server settings, Focus sidebar,
  แชต, สร้าง/เข้าร่วมกลุ่ม และ Dialog สมาชิก ทุก Widget ทำงานใน Main thread
- `client/controller.py` จับคู่ Response ด้วย Request ID และจัดการ Live Events
  callbacks ทำงานเฉพาะเมื่อ Main thread เรียก `pump()` ไม่มี Tk ใน Network worker
- `client/session.py` เก็บตัวตน รายชื่อ ห้อง ข้อความที่รับในรอบนี้ Draft และ Unread
  แยกแต่ละห้อง ไม่มีการเขียนรหัสผ่าน ข้อความ หรือ Draft ลงเครื่อง Client
- `client/network.py` ตรวจ TLS ก่อนส่ง Credentials และให้ Thread เดียวทำ TLS I/O
  รวม Connect/Handshake/Read/Write/Close; Main thread เพียงเข้าคิวและปลุกด้วย socketpair
- `shared/protocol.py` กำหนด Header unsigned big-endian 4 bytes + JSON UTF-8
  จำกัด Body 1 MiB Worker รอให้ Buffer มี Frame ครบก่อนเรียก Decoder ร่วม
- Server ยืนยันตัวตนกับ Connection ตรวจสมาชิกและขอบเขต Join ก่อนส่งข้อมูล
  SQLite และไฟล์อยู่ฝั่ง Server; Client ไม่เปิด Database โดยตรง

Worker ใช้ TLS แบบ nonblocking เพราะ Socket ที่อ่านได้อาจมีเพียง TLS control record
เช่น TLS 1.3 session ticket โดยยังไม่มีข้อความแอป จึงไม่รอ `recv()` จนขวางคำขอขาออก
รองรับ Frame ที่แตกหลาย Read และหลาย Frame ใน Read เดียว มี Total frame deadline
5 วินาที และ Request deadline 15 วินาที รวมเวลารอในคิว

คิว Request/Event จำกัด 256 รายการ และ Pending requests จำกัด 256 รายการ
เมื่อผู้รับช้าจน Event queue เต็ม Worker ปิด Connection และเก็บ Terminal notification
ไว้แทนการรอ Main thread ไม่สิ้นสุด คำขอที่ยังไม่ได้ยืนยันถือว่าผลลัพธ์ไม่แน่นอน
Main thread ประมวลผลครั้งละไม่เกิน 100 Events แล้วคืนการควบคุมให้ Tk

## Login และการโหลดข้อมูลเริ่มต้น

1. ผู้ใช้กรอก Host/Port/CA; CA ว่างหมายถึง System trust store โดยยังตรวจ Hostname
2. Network worker ตรวจ TLS สำเร็จ แล้วจึงส่ง Register หรือ Login
3. Register สำเร็จต้อง Login แยก และล้างช่อง Password/Confirm หลังเข้าคิว
4. Login สำเร็จโหลดรายชื่อผู้ใช้ และโหลด `GROUP_LIST` ทุกหน้าจน `next_after_id=null`
5. `USERS_UPDATED` ใช้ Revision ภายใน Connection ปัจจุบัน ป้องกัน Snapshot ย้อนลำดับ
6. `GROUPS_UPDATED` เป็นสัญญาณให้โหลดรายชื่อใหม่ ถ้ามีการเปลี่ยนระหว่างโหลดให้โหลดซ้ำ
   ลด Page size ได้เมื่อ Server แจ้ง `FRAME_TOO_LARGE`
7. ข้อความส่วนตัวอาจเข้ามาก่อนเปิดห้อง Client โหลดกลุ่มก่อน แล้วเปิด Private metadata
   ด้วย Sender ID เฉพาะห้องที่ยังไม่รู้จัก เพื่อแสดงใน Sidebar โดยไม่สลับห้องที่กำลังอ่าน

## ส่งข้อความและการเชื่อมต่อหลุด

ข้อความอยู่ใน Draft จน Server ตอบสำเร็จ Response กับ `MESSAGE_NEW` echo รวมกันด้วย
`message_id` จึงแสดงครั้งเดียว ถ้าผู้ใช้แก้ร่างระหว่างรอ คำยืนยันข้อความเดิมไม่ลบร่างใหม่
แต่ละห้องรอคำยืนยันการส่งได้ครั้งละหนึ่งข้อความ ส่วนห้องอื่นยังใช้งานได้

ไม่มี Retry/Replay อัตโนมัติ หาก Server Commit แล้ว Connection หลุดก่อนตอบ
ข้อความอาจอยู่ใน Database แล้ว หน้าจอแสดงว่ายังยืนยันไม่ได้ พร้อมเก็บ Draft
ให้ผู้ใช้ตรวจสอบก่อนตัดสินใจส่งใหม่ Request ID ไม่ใช่หลักประกัน Exactly-once

เมื่อหลุดยังอ่านข้อความที่รับแล้วและพิมพ์ร่างในห้องเดิมได้ แต่ปุ่มส่งถูกปิด
กดเชื่อมต่อใหม่และ Login เอง ร่าง/ข้อความในหน่วยความจำจะกลับมาเฉพาะ Host/Port/CA
และ User ID เดิม เมื่อเปลี่ยนบัญชีหรือ Server จะล้างข้อมูล Session เก่า
Logout และปิดแอปล้างข้อมูลในหน่วยความจำ ไม่มี Remember Password
การปิดหน้าต่างไม่ Join Network worker บน Main thread จึงไม่รอ Network ที่ค้าง

## ขอบเขตรอบ CP06

แชตส่วนตัว กลุ่ม และสถานะออนไลน์ใช้ Server จริง หน้าจออิง Focus โดยใช้ Native title bar
รองรับภาษาไทย/Unicode, Enter ส่ง, Shift+Enter ขึ้นบรรทัดใหม่ และ Draft แยกห้อง

ประวัติหลังเปิดแอปใหม่/ค้นหา (CP07), ไฟล์ (CP08), AI (CP09), Cloud (CP10)
ยังไม่เปิดเป็นปุ่มใช้งานในรอบนี้ แม้ Prototype HTML จะมีตัวอย่าง ฟีเจอร์เหล่านี้ไม่ได้ส่ง
คำขอปลอมเพื่อแสดงผลสำเร็จ เวลาแสดงใน UI แปลงจาก UTC เป็น Timezone ของเครื่อง

หลักฐานตรวจ Local และงานค้างสองเครื่องอยู่ใน [demo-checklist.md](demo-checklist.md)
สถานะและผลทดสอบล่าสุดอยู่ใน [DEVELOPMENT.md](../DEVELOPMENT.md)

อ้างอิง: [Tkinter threading model](https://docs.python.org/3.14/library/tkinter.html#threading-model),
[SSL nonblocking I/O](https://docs.python.org/3.14/library/ssl.html#notes-on-non-blocking-sockets)
