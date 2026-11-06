import { test, expect, type Page, type BrowserContext } from '@playwright/test'
import { randomUUID } from 'node:crypto'

// CP09 UI with the labelled mock provider; the real API is checked by scripts/ai_live_check.py.
const password = 'browser test password🔑'
const name = (prefix: string) => `${prefix}_${randomUUID().slice(0, 7)}`
async function register(page: Page, username: string) {
  await page.goto('/')
  await page.getByRole('button', { name: 'ยังไม่มีบัญชี? สมัครสมาชิก' }).click()
  await page.getByLabel('ชื่อผู้ใช้', { exact: true }).fill(username)
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByLabel('ยืนยันรหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'สมัครสมาชิก', exact: true }).click()
  await expect(page.getByText('สมัครสมาชิกแล้ว กรุณาเข้าสู่ระบบด้วยบัญชีที่สร้าง')).toBeVisible()
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click()
  await expect(page.getByRole('navigation', { name: 'รายชื่อคนและห้องแชต' })).toBeVisible()
}
async function send(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'ข้อความแชต' }).fill(text)
  await page.getByRole('button', { name: 'ส่งข้อความ', exact: true }).click()
  await expect(page.locator('.ss-bubble').getByText(text, { exact: true })).toHaveCount(1)
}

let contexts: BrowserContext[] = []
test.afterEach(async () => { await Promise.all(contexts.map(context => context.close())); contexts = [] })

test('AI summary panel for group members only, labelled, private to the requester', async ({ browser }) => {
  const pages: Page[] = []
  for (let index = 0; index < 3; index++) { const context = await browser.newContext(); contexts.push(context); pages.push(await context.newPage()) }
  const [a, b, c] = pages, an = name('Lead'), bn = name('Mate'), group = `AI ${an}`
  await register(a, an); await register(b, bn); await register(c, name('Out'))
  await a.getByRole('navigation').getByRole('button', { name: 'สร้างกลุ่มใหม่', exact: true }).click()
  await a.getByRole('dialog').getByLabel('ชื่อกลุ่ม').fill(group)
  await a.getByRole('dialog').getByRole('button', { name: 'สร้างกลุ่ม', exact: true }).click()
  await b.getByRole('navigation').getByRole('button', { name: `เปิดห้อง ${group}`, exact: true }).click()
  await expect(b.getByRole('button', { name: 'สรุปด้วย AI', exact: true })).toHaveCount(0)  // Not a member yet.
  await b.getByRole('button', { name: 'เข้าร่วมด้วยตัวเอง' }).click()
  await send(a, 'แบ่งงาน: เราทำ Server')
  await send(b, 'เราทำ GUI ส่งศุกร์นี้')
  await a.getByRole('button', { name: 'สรุปด้วย AI', exact: true }).click()
  const panel = a.getByRole('complementary', { name: 'ผู้ช่วยสรุปบทสนทนา' })
  await expect(panel).toContainText('(Mock) สรุปจำลองจาก 2 ข้อความ')
  await expect(panel).toContainText('ผลจำลอง (Mock) สำหรับทดสอบ · ไม่ได้เรียก AI จริง')
  await expect(panel).toContainText('2 ข้อความล่าสุดที่คุณเห็นได้')
  await expect(panel.getByText('ไม่ระบุ')).toHaveCount(3)  // Empty sections say so instead of inventing.
  await expect(b.getByRole('complementary', { name: 'ผู้ช่วยสรุปบทสนทนา' })).toHaveCount(0)
  await expect(b.getByRole('main')).not.toContainText('สรุปจำลอง')
  // Repeating immediately is rate limited; chat keeps working.
  await panel.getByRole('button', { name: 'สรุปอีกครั้ง' }).click()
  await expect(panel.getByRole('alert')).toContainText('ลองบ่อยเกินไป')
  await send(a, 'แชตยังใช้ได้หลังกดสรุป')
  await a.getByRole('button', { name: 'ปิดสรุป AI' }).click()
  await expect(panel).toHaveCount(0)
  // An outsider never gets the button for a group they have not joined.
  await c.getByRole('navigation').getByRole('button', { name: `เปิดห้อง ${group}`, exact: true }).click()
  await expect(c.getByRole('button', { name: 'สรุปด้วย AI', exact: true })).toHaveCount(0)
})
