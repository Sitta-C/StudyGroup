import { test, expect, type Page, type BrowserContext } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

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
async function login(page: Page, username: string) {
  await page.getByLabel('ชื่อผู้ใช้', { exact: true }).fill(username)
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click()
}
async function createGroup(page: Page, title: string) {
  await page.getByRole('navigation').getByRole('button', { name: 'สร้างกลุ่มใหม่', exact: true }).click()
  await page.getByRole('dialog').getByLabel('ชื่อกลุ่ม').fill(title)
  await page.getByRole('dialog').getByRole('button', { name: 'สร้างกลุ่ม', exact: true }).click()
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
}
async function privateRoom(page: Page, username: string) {
  await page.getByRole('navigation').getByRole('button', { name: `แชตส่วนตัวกับ ${username}`, exact: true }).click()
  await expect(page.getByRole('heading', { name: username, exact: true })).toBeVisible()
}
async function send(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'ข้อความแชต' }).fill(text)
  await page.getByRole('button', { name: 'ส่งข้อความ', exact: true }).click()
  await expect(page.locator('.ss-bubble').getByText(text, { exact: true })).toHaveCount(1)
  await expect(page.getByRole('textbox', { name: 'ข้อความแชต' })).toHaveValue('')
}
async function logout(page: Page) {
  await page.getByRole('button', { name: 'เมนูบัญชี', exact: true }).click()
  await page.getByRole('button', { name: 'ออกจากระบบ', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'ยินดีต้อนรับกลับมา' })).toBeVisible()
}

let contexts: BrowserContext[] = []
test.afterEach(async () => { await Promise.all(contexts.map(context => context.close())); contexts = [] })

test('register/login, private isolation, sender echo dedup, drafts, duplicate login and online cleanup', async ({ browser }) => {
  const pages: Page[] = []
  for (let index = 0; index < 3; index++) { const context = await browser.newContext(); contexts.push(context); pages.push(await context.newPage()) }
  const [a, b, c] = pages, [an, bn, cn] = [name('Alice'), name('Bob'), name('Carol')]
  await register(a, an); await register(b, bn); await register(c, cn)
  await expect(a.getByRole('navigation').getByText('3 คน', { exact: true })).toBeVisible()
  await privateRoom(a, bn)
  const editor = a.getByRole('textbox', { name: 'ข้อความแชต' })
  await editor.fill('ข้อความไทย 👋'); await editor.press('Shift+Enter'); await editor.pressSequentially('second line'); await editor.press('Enter')
  const message = 'ข้อความไทย 👋\nsecond line'
  await expect(a.locator('.ss-bubble').filter({ hasText: message })).toHaveCount(1)
  await privateRoom(b, an)
  await expect(b.locator('.ss-bubble').filter({ hasText: message })).toHaveCount(1)
  await expect(c.getByRole('main')).not.toContainText('ข้อความไทย 👋')
  await editor.fill('ร่างสำหรับ Bob')
  await privateRoom(a, cn)
  await a.getByRole('textbox', { name: 'ข้อความแชต' }).fill('ร่างสำหรับ Carol')
  await privateRoom(a, bn)
  await expect(editor).toHaveValue('ร่างสำหรับ Bob')
  const duplicate = await browser.newContext(); contexts.push(duplicate)
  const d = await duplicate.newPage(); await d.goto('/'); await login(d, an)
  await expect(d.getByRole('alert')).toContainText('บัญชีนี้เข้าสู่ระบบอยู่แล้ว')
  await logout(b)
  await expect(a.getByRole('navigation').getByRole('button', { name: `แชตส่วนตัวกับ ${bn}`, exact: true })).toHaveCount(0)
  await expect(a.getByRole('heading', { name: bn, exact: true })).toBeVisible()
})

test('public group rosters, self join, join boundary, member-only live delivery and literal HTML', async ({ browser }) => {
  const pages: Page[] = []
  for (let index = 0; index < 3; index++) { const context = await browser.newContext(); contexts.push(context); pages.push(await context.newPage()) }
  const [a, b, c] = pages, an = name('Owner'), bn = name('Member'), cn = name('Outside')
  await register(a, an); await register(b, bn); await register(c, cn)
  const group = `กลุ่มทดสอบ ${randomUUID().slice(0, 4)}`
  await createGroup(a, group)
  await a.getByRole('button', { name: 'ดูสมาชิก', exact: true }).click()
  await expect(a.getByRole('dialog')).toContainText('1 คน')
  await expect(a.getByRole('dialog')).toContainText(an)
  await a.getByRole('button', { name: 'ปิดหน้าต่าง' }).click()
  await send(a, 'ข้อความก่อนเข้าร่วม')
  await b.getByRole('navigation').getByRole('button', { name: `เปิดห้อง ${group}`, exact: true }).click()
  await expect(b.getByRole('button', { name: 'เข้าร่วมด้วยตัวเอง' })).toBeVisible()
  await expect(b.getByRole('textbox', { name: 'ข้อความแชต' })).toHaveCount(0)
  await b.getByRole('button', { name: 'เข้าร่วมด้วยตัวเอง' }).click()
  await expect(b.getByRole('textbox', { name: 'ข้อความแชต' })).toBeVisible()
  await expect(b.getByRole('main')).not.toContainText('ข้อความก่อนเข้าร่วม')
  const html = '<img src=x onerror="window.hacked=1">'
  await send(a, html)
  await expect(b.locator('.ss-bubble').getByText(html, { exact: true })).toBeVisible()
  expect(await b.evaluate(() => (window as unknown as Record<string, unknown>).hacked)).toBeUndefined()
  await expect(c.getByRole('main')).not.toContainText(html)
  await c.getByRole('button', { name: 'สำรวจกลุ่มทั้งหมด' }).click()
  await expect(c.getByRole('dialog')).toContainText(group)
  await expect(c.getByRole('dialog')).toContainText(bn)
  await c.getByRole('button', { name: 'ปิดหน้าต่าง' }).click()
  // CP07/CP08 enabled search and files; AI stays disabled until CP09.
  await expect(a.getByRole('button', { name: 'สรุปด้วย AI', exact: true })).toBeDisabled()
  await expect(a.getByRole('button', { name: 'ค้นหาข้อความ', exact: true })).toBeEnabled()
  await expect(a.getByRole('tab', { name: 'ไฟล์', exact: true })).toBeEnabled()
})

test('real socket interruption preserves drafts, explicit re-login, no replay, account isolation', async ({ browser, request }) => {
  const context = await browser.newContext(); contexts.push(context)
  const page = await context.newPage(), first = name('Reconnect'), second = name('Next')
  await register(page, first)
  await createGroup(page, `ร่างไม่หาย ${first}`)
  const editor = page.getByRole('textbox', { name: 'ข้อความแชต' })
  await editor.fill('เก็บร่างนี้ไว้ ไม่ส่งเอง')
  const response = await request.get('/__test__/disconnect', { headers: { 'X-Test-Control': process.env.STUDYGROUP_TEST_CONTROL! } })
  expect(response.ok()).toBeTruthy()
  await expect(page.getByRole('button', { name: 'เข้าสู่ระบบใหม่', exact: true })).toBeVisible()
  await expect(editor).toHaveValue('เก็บร่างนี้ไว้ ไม่ส่งเอง')
  await expect(page.getByRole('button', { name: 'ส่งข้อความ', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'เข้าสู่ระบบใหม่', exact: true }).click()
  await login(page, first)
  await expect(editor).toHaveValue('เก็บร่างนี้ไว้ ไม่ส่งเอง')
  await expect(page.locator('.ss-bubble')).toHaveCount(0)
  await logout(page)
  await page.getByRole('button', { name: 'ยังไม่มีบัญชี? สมัครสมาชิก' }).click()
  await page.getByLabel('ชื่อผู้ใช้', { exact: true }).fill(second)
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByLabel('ยืนยันรหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'สมัครสมาชิก', exact: true }).click()
  await expect(page.getByText('สมัครสมาชิกแล้ว กรุณาเข้าสู่ระบบด้วยบัญชีที่สร้าง')).toBeVisible()
  await login(page, second)
  await expect(page.getByRole('main')).not.toContainText('เก็บร่างนี้ไว้ ไม่ส่งเอง')
  await expect(page.getByRole('heading', { name: 'เริ่มบทสนทนา' })).toBeVisible()
})

test('mobile navigation, long names/messages and IME composition stay usable', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }); contexts.push(context)
  const page = await context.newPage()
  await register(page, name('Mobile'))
  await page.getByRole('button', { name: 'เปิดรายชื่อห้อง', exact: true }).click()
  await createGroup(page, 'ก'.repeat(100))
  await expect(page.getByRole('button', { name: 'ปิดรายชื่อห้อง', exact: true })).toHaveCount(0)
  const editor = page.getByRole('textbox', { name: 'ข้อความแชต' })
  await editor.fill('ภาษาไทยที่กำลังประกอบ')
  await editor.dispatchEvent('compositionstart')
  await editor.press('Enter')
  await expect(page.locator('.ss-bubble')).toHaveCount(0)
  await editor.dispatchEvent('compositionend')
  await editor.press('Enter')
  await expect(page.locator('.ss-bubble')).toHaveCount(1)
  await send(page, '🙂'.repeat(4000))
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.getByRole('button', { name: 'ดูสมาชิก', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('1 คน')
})


test('commit without acknowledgement keeps the draft and never replays on re-login', async ({ browser, request }) => {
  const context = await browser.newContext(); contexts.push(context)
  const page = await context.newPage(), user = name('Uncertain')
  const headers = { 'X-Test-Control': process.env.STUDYGROUP_TEST_CONTROL! }
  const count = async () => Number(await (await request.get('/__test__/message-count', { headers })).text())
  await register(page, user)
  await createGroup(page, `Ack ${user}`)
  const before = await count()
  expect((await request.get('/__test__/drop-next-send', { headers })).ok()).toBeTruthy()
  const text = 'บันทึกแล้วแต่ยังไม่ได้รับคำยืนยัน'
  await page.getByRole('textbox', { name: 'ข้อความแชต' }).fill(text)
  await page.getByRole('button', { name: 'ส่งข้อความ', exact: true }).click()
  await expect(page.getByRole('button', { name: 'เข้าสู่ระบบใหม่', exact: true })).toBeVisible()
  await expect(page.locator('.ss-composer-foot')).toContainText('ยังยืนยันการส่งไม่ได้')
  await expect(page.getByRole('textbox', { name: 'ข้อความแชต' })).toHaveValue(text)
  expect(await count()).toBe(before + 1)
  await page.getByRole('button', { name: 'เข้าสู่ระบบใหม่', exact: true }).click()
  await login(page, user)
  await expect(page.getByRole('textbox', { name: 'ข้อความแชต' })).toHaveValue(text)
  // CP07 loads the one committed row from Server history; the client never resent it.
  await expect(page.locator('.ss-bubble').filter({ hasText: text })).toHaveCount(1)
  expect(await count()).toBe(before + 1)
})

test('Focus reference layout with real chat on desktop and mobile', async ({ browser }, testInfo) => {
  const pages: Page[] = []
  for (let index = 0; index < 3; index++) { const context = await browser.newContext({ viewport: { width: 1048, height: 810 } }); contexts.push(context); pages.push(await context.newPage()) }
  const [a, b, c] = pages
  await register(a, 'Anan'); await register(b, 'Ploy'); await register(c, 'Mek')
  await createGroup(c, 'Study Café')
  await createGroup(a, 'Network Project')
  await b.getByRole('navigation').getByRole('button', { name: 'เปิดห้อง Network Project', exact: true }).click()
  await b.getByRole('button', { name: 'เข้าร่วมด้วยตัวเอง' }).click()
  await send(b, 'มาแบ่งงาน Network Project กันนะ เราต้องมีแชตส่วนตัวกับห้องกลุ่มให้ครบก่อน')
  await send(a, 'ได้เลย เราดูส่วน Server กับ Cloud ให้ แล้วเพิ่ม AI สรุปบทสนทนาด้วย')
  await send(b, 'งั้นเราทำ GUI กับส่งไฟล์นะ เดี๋ยวส่งโครงร่างโปรเจกต์ให้')
  await send(a, 'โอเค แล้วมาทดสอบ Socket บนคอมคนละเครื่องกัน 👍')
  await expect(a.locator('.ss-bubble')).toHaveCount(4)
  await a.evaluate(() => document.fonts.ready)
  const evidence = process.env.STUDYGROUP_CAPTURE_EVIDENCE ? fileURLToPath(new URL('../../docs/evidence/cp06-web/', import.meta.url)) : testInfo.outputDir
  await mkdir(evidence, { recursive: true })
  await a.screenshot({ path: `${evidence}/focus-desktop.png`, fullPage: true, animations: 'disabled' })
  await a.setViewportSize({ width: 390, height: 844 })
  await expect(a.getByRole('navigation')).not.toBeInViewport()
  await a.screenshot({ path: `${evidence}/focus-mobile.png`, fullPage: true, animations: 'disabled' })
  expect(await a.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})
