# CP06 — React Web demo checklist

CP06 เป็น `DONE` ตามผู้ใช้ยืนยันตรวจรับเมื่อ 6 พ.ย. 2026 หลังเปิดเว็บผ่าน HTTPS บน LAN
ผลตรวจอัตโนมัติเป็น localhost บน macOS เครื่องเดียว; หลักฐานรายอุปกรณ์/ภาพ R1–R11
ยังต้องเก็บสำหรับเดโม CP11 ตารางที่ระบุรอตรวจหมายถึงยังไม่มีผลรายข้อบันทึกไว้
หลาย Browser contexts ไม่แทนคอมพิวเตอร์จริงสองเครื่องตาม R1
เปลี่ยน UI เป็น React ตามคำสั่งผู้ใช้ 6 พ.ย. 2026 ใช้ Python/SQLite และสิทธิ์เดิม

## เริ่มรัน

เตรียม [setup.md](setup.md) แล้ว:

```bash
npm --prefix web run build
uv run --locked --env-file .env python -m server.web
```

เปิด http://127.0.0.1:8000 ด้วย Browser profiles/Incognito แยก A/B/C คนละบัญชี
สมัครแล้ว Login ไม่กรอก Server ในหน้า Login หนึ่งบัญชีมี Session ออนไลน์ได้ตัวเดียว

## R1–R11

| ข้อ | วิธีตรวจใน Browser | หลักฐาน Local | สองเครื่องจริง |
| --- | --- | --- | --- |
| R1 | A/B อยู่คนละคอมพิวเตอร์ อธิบาย React → WS → Python → SQLite | architecture.md และ Browser tests บนเครื่องเดียว | รอตรวจ |
| R2 | Network `/ws` เป็น 101 แล้วแชตส่งผ่าน Socket | WebSocket/WSS integration + Browser จริง | รอตรวจ |
| R3 | สมัครชื่อซ้ำ/ต่าง case และ Login ซ้อน | Auth tests เดิม, Browser ตรวจ duplicate login | รอตรวจ |
| R4 | A/B/C เห็นตนเอง/กันและกัน B Logout/ปิดแท็บแล้วหาย | Browser presence/cleanup และ WS integration | รอตรวจ |
| R5 | A–B, A–C และหลายกลุ่ม สลับแล้วข้อความ/ร่างไม่ปน | Browser drafts/private rooms + Server tests | รอตรวจ |
| R6 | ทุกห้องมีช่องพิมพ์และข้อความ ไทย/Emoji/หลายบรรทัด | Browser Enter/Shift+Enter, 4,000 emoji, ภาพ Focus | รอตรวจ |
| R7 | A ส่งหา B; C ไม่เห็นเนื้อหา/Private metadata | A/B/C Browser contexts และ WS permission tests | รอตรวจ |
| R8 | สร้างหลายกลุ่ม ผู้สร้างเป็นสมาชิกคนแรกเพียงคนเดียว | Browser create/member dialog + Server tests | รอตรวจ |
| R9 | C เห็นทุกกลุ่ม/สมาชิกก่อน Join | Browser directory + Server pagination tests | รอตรวจ |
| R10 | C เลือกกลุ่ม ช่องพิมพ์ไม่แสดง จนกด Join เอง | Browser join flow และ WS integration | รอตรวจ |
| R11 | A/B สมาชิกคุยได้ C ไม่ได้เนื้อหา สมาชิกใหม่ไม่เห็นก่อน Join | Browser/WS join boundary + permission tests | รอตรวจ |

## หลักฐานหน้าเว็บ

- [Focus desktop](evidence/cp06-web/focus-desktop.png) และ [Focus mobile](evidence/cp06-web/focus-mobile.png)
  จับจาก React build ที่ใช้ Python WebSocket Server/SQLite จริง
- บัญชี Anan/Ploy/Mek และข้อความในภาพเป็นข้อมูลทดสอบแยกใน Temporary directory
  ไม่ seed ข้อมูลตัวอย่างเข้า runtime จริง วันเวลาเป็นเวลาที่ Server สร้าง
- เทียบกับ Focus prototype โดยเอา title bar จำลองออก สี/spacing/typography ใช้ CSS ตามแบบ
  ภาพนี้ถ่ายตอน CP06 ซึ่งปุ่ม Files/Search/AI/Attachment ยัง disabled; CP07–CP08 เปิด Search/Files/Attachment แล้ว AI ยังปิด
- ภาพเดิมใน `evidence/cp06/` เป็นหลักฐาน Tkinter ก่อน migration ไม่ใช่เว็บปัจจุบัน

## Connection / UI checks

- [x] Login/Register จริง, รายชื่อออนไลน์และสมาชิก
- [x] Sender response/event echo แสดงเพียงครั้งเดียวด้วย message ID
- [x] Draft แยกห้อง และเก็บไว้เมื่อ socket หลุด ไม่ reconnect/replay เอง
- [x] หลัง Commit แล้วตัดก่อน Ack: SQLite เพิ่มหนึ่งข้อความ UI เก็บร่าง/แจ้งยังยืนยันไม่ได้
  Login ใหม่ไม่ส่งข้อความนั้นซ้ำ
- [x] เปลี่ยนบัญชี/Logout ล้าง state บัญชีเก่า; re-login บัญชีเดิมในแท็บเดิมรักษาร่าง
- [x] React แสดง HTML เป็นข้อความ ไม่ execute; CSP สำหรับ production assets
- [x] มือถือ 390×844, ชื่อกลุ่ม 100 ตัว, ข้อความ 4,000 emoji ไม่ล้นแนวนอน
- [x] Synthetic IME composition ไม่ส่งเมื่อกด Enter ขณะประกอบอักษร
- [ ] Thai IME จริงและ OS copy/paste บนเครื่องเดโมทั้งสองเครื่อง
- [ ] สลับ App/Browser, mobile soft keyboard และ zoom บนอุปกรณ์จริง
- [ ] หยุด Server/ตัด Wi-Fi บน LAN จริง แล้วตรวจ online cleanup/draft/ข้อความไม่ replay
- [ ] HTTPS/WSS, certificate/trust และ Firewall บนสองเครื่องจริง

## เตรียมสองเครื่อง

1. เลือก Server และ DNS/IP ที่ Client ทั้งสองเข้าถึงได้ ตั้ง HTTPS/WSS ตาม [setup.md](setup.md)
2. ตั้ง Origin allowlist ให้ตรง URL ที่เปิดจริง ไม่ใช้ wildcard และไม่ข้าม TLS warning
3. เปิดเฉพาะพอร์ต Web/HTTPS ที่ใช้ ไม่เปิด SQLite หรือส่ง keys/.env ให้ Client
4. ให้ A/B เปิดคนละคอมพิวเตอร์ C เป็น Browser profile แยกสำหรับตรวจคนนอก
5. ไล่ R1–R11 บันทึกผลและภาพจากทั้งสองเครื่อง ตรวจ `/ws` Upgrade/ข้อความใน Network
6. ข้อมูล/บัญชียังอยู่หลัง restart และ UI โหลดข้อความเก่าหลังเปิดใหม่ (CP07)
7. ลงวันที่/OS/Browser/เครื่อง/เครือข่าย/URL/ผล TLS และภาพไว้ใน DEVELOPMENT สำหรับ CP11

| ข้อมูลตรวจจริง | ผล |
| --- | --- |
| วันที่ / ผู้ตรวจ | 6 พ.ย. 2026 / ผู้ใช้ยืนยันรับงานในแชต |
| Server OS / URL / TLS issuer | รอ |
| เครื่อง A: OS / Browser / เครือข่าย | รอ |
| เครื่อง B: OS / Browser / เครือข่าย | รอ |
| Client C / บัญชีคนนอก | รอ |
| R1–R11 / IME / disconnect / ภาพ | รอ |

### CP07–CP08 บนเครื่องจริง (เก็บผลสำหรับ CP11)

1. A ส่งข้อความหลายข้อความ ปิด Browser และหยุด/เริ่ม Server ใหม่ แล้ว Login ใหม่ ข้อความเดิมยังอยู่
2. กด “โหลดข้อความก่อนหน้า” ในห้องที่มีมากกว่า 50 ข้อความ ไม่มีข้อความซ้ำหรือหาย
3. ค้นหาด้วยคำและช่วงวันที่ กดผลลัพธ์แล้วเลื่อนไปข้อความนั้น; C (คนนอก) ค้นห้อง A/B ไม่ได้
4. B เข้ากลุ่มหลัง A ส่งข้อความ/ไฟล์ B ไม่เห็นของก่อน Join ทั้งแชต ค้นหา และแท็บไฟล์
5. A ส่งไฟล์ ≤ 5 MB B ดาวน์โหลดจากอีกเครื่องแล้ว `shasum -a 256` ตรงกับต้นฉบับ
6. ไฟล์เกิน 5 MB ถูกปฏิเสธ และตัดเน็ตระหว่างส่งไฟล์แล้วแชตยังใช้ได้หลัง Login ใหม่

ผล CP07–CP08 ล่าสุดเป็นผล Local (Python + Browser E2E) ดู DEVELOPMENT; AI จริง (CP09), Cloud (CP10) ยังไม่ตรวจรับ
