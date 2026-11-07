# StudyGroup บน Railway — CP10

ตรวจจริงเมื่อ 7 พฤศจิกายน 2026 (Asia/Bangkok) โดยใช้ Railway Trial, Docker service
หนึ่ง Replica และ Volume เดียว ผลตรวจอยู่ใน DEVELOPMENT.md และ
[รายงานที่ไม่มีข้อมูลลับ](evidence/cp10-railway/verification.json)

Public URL: https://studygroup-production-b33d.up.railway.app

## Config ที่ตรวจบน Container จริง

| ค่า | ค่าที่ใช้ |
| --- | --- |
| `PORT` / `STUDYGROUP_WEB_PORT` | `8000` |
| `STUDYGROUP_WEB_HOST` | `0.0.0.0` |
| `STUDYGROUP_WEB_ORIGINS` | `https://studygroup-production-b33d.up.railway.app` |
| `STUDYGROUP_DATA_DIR` | `/app/data` |
| Volume mount | `/app/data` ตรวจ `os.path.ismount()` ได้ `True` |
| Public TLS | Railway จัดการ HTTPS/WSS; แอปภายในใช้ HTTP |
| Replicas | `1` เพื่อให้ connection registry และ SQLite อยู่ใน process เดียว |

AI Key อยู่ใน Railway Variables เท่านั้น ตรวจพบว่าตั้งค่า Anthropic แล้ว แต่รอบ CP10 นี้
ไม่เรียก paid AI API; การตรวจ AI จริงบน Cloud เป็นส่วนหนึ่งของเดโม CP11
การ Refresh ใช้ resume token ได้ ส่วน Restart/Redeploy ทำให้ต้อง Login ใหม่ เพราะ
token registry อยู่ใน memory ตามขอบเขต Auth ที่ตกลงไว้ ข้อมูลบัญชี/ประวัติ/ไฟล์ยังอยู่ใน Volume

## สำรอง SQLite และไฟล์แนบโดยไม่ต้องอัปเกรดแผน

หน้า Backups ของ Trial ที่ตรวจแจ้งว่าต้องใช้ Pro เพื่อสร้าง platform backup ใหม่
รอบนี้จึงใช้ `scripts/data_backup.py` ซึ่งใช้เฉพาะ Python standard library
และไม่ต้องซื้อบริการเพิ่ม วิธีนี้ไม่ใช่ Railway platform snapshot

สคริปต์ใช้ SQLite online backup API อ่าน snapshot ที่รวม committed WAL แล้ว
จากนั้นคัดลอกเฉพาะไฟล์ `ready` ที่อ้างอยู่ใน snapshot และตรวจ size/SHA-256 ทุกไฟล์
published attachments ของระบบปัจจุบันไม่ถูกแก้ไขหรือลบระหว่างใช้งาน จึงสำรองขณะเปิดแอปได้
ถ้าไฟล์หาย/เปลี่ยน สคริปต์จะไม่เผยแพร่ archive ที่ไม่สมบูรณ์
ไม่รวม `.env`, partial uploads, credentials ของเครื่องมือทดสอบ หรือไฟล์อื่นใน data directory

Dockerfile ใน source รอบนี้เพิ่มสคริปต์ที่ `/app/scripts/data_backup.py` สำหรับ Image รุ่นถัดไป
Image ที่ Deploy อยู่ตอนตรวจยังเป็น source เดิม จึงอัปโหลดสคริปต์ที่ผ่าน Tests ผ่าน
Service → Console → Files ไป `/app/data/data_backup.py` แล้วรันจาก Console:

```bash
umask 077
/app/.venv/bin/python /app/data/data_backup.py backup \
  --data-dir /app/data \
  --output /app/data/backups/studygroup-$(date -u +%Y%m%dT%H%M%SZ).zip
```

เมื่อ Deploy Image ที่มี helper แล้ว เปลี่ยนเฉพาะตำแหน่งสคริปต์เป็น
`/app/scripts/data_backup.py` ใช้ `/app/.venv/bin/python` ให้ตรง environment ของแอป
Console shell อาจเลือก system Python ซึ่งไม่มี Dependencies ของ Web Server

ผลลัพธ์เป็น JSON: archive path, SHA-256, จำนวนแถวในตาราง และจำนวนไฟล์
Archive ถูกสร้างด้วยสิทธิ์ `0600` และปฏิเสธการเขียนทับไฟล์เดิม
ใน Console → Files เปิด `data/backups`, คลิกขวาที่ ZIP → Download
เก็บสำเนานอก Railway ด้วย และเทียบ SHA-256 กับผลบน Server
Backup มีฐานข้อมูลบัญชี/ประวัติและไฟล์จริง จึงเก็บนอก Git; `work/` และ `backups/`
ถูกกันออกจาก Git/Docker context แล้ว

## กู้คืนใน directory ใหม่ก่อนเปิดใช้งาน

```bash
/app/.venv/bin/python /app/data/data_backup.py restore \
  --archive /app/data/backups/ชื่อชุดสำรอง.zip \
  --destination /app/data/recovered-demo
```

ต้องใช้ directory ใหม่เสมอ สคริปต์ไม่มี `--force` และไม่เขียนทับข้อมูลที่เปิดใช้งานอยู่
ตรวจ ZIP members/path/symlink, size/SHA-256, SQLite integrity/foreign keys
และ inventory ไฟล์ให้ตรงกับ Database ก่อนสร้างปลายทาง ขนาดที่รับกู้คืนรวมไม่เกิน 1 GiB

ตรวจข้อมูลที่กู้คืนด้วยแอปอีก instance บน loopback/port แยก โดยให้ `data_dir`
ชี้ directory ที่กู้คืนและปิด AI สำหรับการตรวจนี้ รอบ CP10 ตรวจ Login, ห้อง/สมาชิก,
Private/Group history, Search, การดาวน์โหลดไฟล์และสิทธิ์คนนอกจริงแล้ว ทั้งบน Railway
ใน `/tmp/cp10-restored-11071229454e` และจาก archive ที่ดาวน์โหลดลงเครื่องใน `work/cp10/`
instance ทดสอบหยุดแล้ว ฐานข้อมูล Production ไม่ถูกแทนที่หรือย้อนเวลา

หากตั้งใจนำ Backup มาใช้เป็นข้อมูล Production ภายหลัง ให้หยุดการใช้งานชั่วคราว
กู้คืนไป directory ใหม่ใต้ Volume เดิม ตรวจให้ผ่าน แล้วเปลี่ยน `STUDYGROUP_DATA_DIR`
เป็น directory นั้นและ Deploy changes เก็บ directory เดิมไว้เพื่อย้อนกลับ
การทดสอบ CP10 รอบนี้ไม่ได้สลับ Production ไปใช้ Backup

## ตรวจ Restart/Redeploy ซ้ำด้วยข้อมูลเดโม

จาก root โปรเจกต์บนเครื่องพัฒนา:

```bash
.venv/bin/python scripts/cloud_demo_check.py \
  --url https://studygroup-production-b33d.up.railway.app \
  --state work/cp10/private-state.json --prepare
```

`--prepare` สร้างบัญชี `cp10a_…`/`cp10b_…`/`cp10c_…`, กลุ่มชื่อ CP10,
ห้องส่วนตัว ข้อความ และไฟล์ 64 KiB เพียงครั้งเดียว State มีรหัสผ่านบัญชีทดสอบและใช้สิทธิ์ `0600`
ไม่อ่านห้องของผู้ใช้จริงและไม่เรียก AI อย่าเริ่ม prepare ใหม่ด้วย state เดิม

หลัง Service → Deployments → Deployment actions → Restart หรือ Redeploy รอ Active แล้ว:

```bash
.venv/bin/python scripts/cloud_demo_check.py \
  --url https://studygroup-production-b33d.up.railway.app \
  --state work/cp10/private-state.json --verify
```

ต้อง Login ด้วยบัญชีเดิมได้ เห็นข้อความ/สมาชิกเดิม ค้นหาได้ ดาวน์โหลดไฟล์แล้ว bytes/SHA-256
ตรง และบัญชี C ได้ `FORBIDDEN` เมื่ออ่านห้อง/ไฟล์ที่ไม่ใช่สมาชิก
การ Redeploy ที่มี Volume จะมี downtime สั้น ๆ ให้ใช้ Replica เดียวและ Login ใหม่หลังเริ่ม Server

## หลักฐานและขอบเขต

- Restart จริง: 7 พ.ย. 2026 เวลา 19:36 น.; ข้อมูลเดโมผ่านทุก check หลังเริ่มใหม่
- Redeploy จริง: Deployment ใหม่ `b88cfd56-d888-4bb8-a281-680e9dc8baa9` เป็น Active;
  ข้อมูลเดโมเดิมผ่านทุก check โดยใช้ Volume เดิม
- Backup มี 8 users, 5 rooms, 12 memberships, 23 messages และ attachments 7 ไฟล์
  (เป็นจำนวน ณ เวลาสำรอง ไม่ใช่จำนวนคงที่ของระบบ)
- ผู้ใช้ยืนยัน iPhone / Chrome / Cellular ส่งข้อความได้ปกติ เป็นหลักฐานเครือข่ายจากผู้ใช้
- CP11 ยังต้องเก็บ R1–R11 บนคอมพิวเตอร์จริงอย่างน้อยสองเครื่อง และเดโม AI จริงบน Cloud

เอกสาร Provider: [Dockerfile](https://docs.railway.com/builds/dockerfiles),
[Volumes](https://docs.railway.com/volumes),
[Healthchecks และ downtime](https://docs.railway.com/deployments/healthchecks)
