import { test, expect, type Page, type BrowserContext } from '@playwright/test'
import { createHash, randomBytes, randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'

// CP07 history/search and CP08 files through the real React build, WebSocket and SQLite.
const password = 'browser test password🔑'
const name = (prefix: string) => `${prefix}_${randomUUID().slice(0, 7)}`
const sha = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex')

async function register(page: Page, username: string) {
  await page.goto('/')
  await page.getByRole('button', { name: 'ยังไม่มีบัญชี? สมัครสมาชิก' }).click()
  await page.getByLabel('ชื่อผู้ใช้', { exact: true }).fill(username)
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByLabel('ยืนยันรหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'สมัครสมาชิก', exact: true }).click()
  await expect(page.getByText('สมัครสมาชิกแล้ว กรุณาเข้าสู่ระบบด้วยบัญชีที่สร้าง')).toBeVisible()
  await login(page, username)
}
async function login(page: Page, username: string) {
  await page.getByLabel('ชื่อผู้ใช้', { exact: true }).fill(username)
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click()
  await expect(page.getByRole('navigation', { name: 'รายชื่อคนและห้องแชต' })).toBeVisible()
}
async function createGroup(page: Page, title: string) {
  await page.getByRole('navigation').getByRole('button', { name: 'สร้างกลุ่มใหม่', exact: true }).click()
  await page.getByRole('dialog').getByLabel('ชื่อกลุ่ม').fill(title)
  await page.getByRole('dialog').getByRole('button', { name: 'สร้างกลุ่ม', exact: true }).click()
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
}
async function openGroup(page: Page, title: string) {
  await page.getByRole('navigation').getByRole('button', { name: `เปิดห้อง ${title}`, exact: true }).click()
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
}
async function send(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'ข้อความแชต' }).fill(text)
  await page.getByRole('button', { name: 'ส่งข้อความ', exact: true }).click()
  await expect(page.locator('.ss-bubble').getByText(text, { exact: true })).toHaveCount(1)
}

type Step = { type: string; data: Record<string, unknown> }
/** A second, raw WebSocket client inside a browser page: same /ws protocol as the app. */
async function rawClient(page: Page, username: string, group: string | null, steps: Step[], join = true) {
  return page.evaluate(async ({ username, password, group, steps, join }) => {
    const ws = new WebSocket(`ws://${location.host}/ws`)
    await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
    let counter = 0
    const call = (type: string, data: Record<string, unknown>) => new Promise<{ ok: boolean; result?: any; error?: { code: string } }>(resolve => {
      const id = `raw-${++counter}`
      const listener = (event: MessageEvent) => { const packet = JSON.parse(event.data); if (packet.id === id) { ws.removeEventListener('message', listener); resolve(packet.data) } }
      ws.addEventListener('message', listener)
      ws.send(JSON.stringify({ v: 1, id, type, data }))
    })
    await call('REGISTER', { username, password, confirm_password: password })
    await call('LOGIN', { username, password })
    let room = 0
    if (group) {
      const groups = (await call('GROUP_LIST', { limit: 100 })).result.groups as { id: number; name: string }[]
      room = groups.find(item => item.name === group)!.id
      if (join) await call('GROUP_JOIN', { room_id: room })
    }
    const results = []
    for (const step of steps) results.push(await call(step.type, JSON.parse(JSON.stringify(step.data).replaceAll('"$ROOM"', String(room)))))
    ws.close()
    return results
  }, { username, password, group, steps, join })
}

let contexts: BrowserContext[] = []
test.afterEach(async () => { await Promise.all(contexts.map(context => context.close())); contexts = [] })

test('history survives reload, pages older messages without gaps, and search jumps to a result', async ({ browser }) => {
  const context = await browser.newContext(); contexts.push(context)
  const page = await context.newPage(), owner = name('Hist'), helper = name('Helper'), group = `ประวัติ ${owner}`
  await register(page, owner)
  await createGroup(page, group)
  await send(page, 'เริ่มต้น กำหนดส่ง Lab วันศุกร์')
  // Another member writes 70 messages so the room needs more than one page.
  const steps = Array.from({ length: 70 }, (_, i) => ({ type: 'MESSAGE_SEND', data: { room_id: '$ROOM', text: `ข้อความหมายเลข ${String(i + 1).padStart(3, '0')}` } }))
  const sent = await rawClient(page, helper, group, steps)
  expect(sent.every(result => result.ok)).toBeTruthy()
  await expect(page.locator('.ss-bubble')).toHaveCount(71)

  // Reload drops app memory; the stored token restores authentication.
  await page.reload()
  await expect(page.getByRole('navigation')).toBeVisible()
  await openGroup(page, group)
  await expect(page.locator('.ss-bubble')).toHaveCount(50)
  await expect(page.locator('.ss-bubble').last()).toHaveText('ข้อความหมายเลข 070')
  await page.getByRole('button', { name: 'โหลดข้อความก่อนหน้า', exact: true }).click()
  await expect(page.locator('.ss-bubble')).toHaveCount(71)
  await expect(page.getByText('จุดเริ่มต้นประวัติที่คุณเห็นได้ในห้องนี้')).toBeVisible()
  const ids = await page.locator('article[data-message-id]').evaluateAll(nodes => nodes.map(node => Number((node as HTMLElement).dataset.messageId)))
  expect(new Set(ids).size).toBe(71)
  expect([...ids].sort((a, b) => a - b)).toEqual(ids)

  // Keyword search with a local-date range, then jump to an old result after a fresh reload.
  await page.reload()
  await expect(page.getByRole('navigation')).toBeVisible()
  await openGroup(page, group)
  await expect(page.locator('.ss-bubble')).toHaveCount(50)
  await page.getByRole('button', { name: 'ค้นหาข้อความ', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('คำค้น').fill('กำหนดส่ง')
  const today = await page.evaluate(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` })
  await dialog.getByRole('button', { name: 'กรองตามวันที่', exact: true }).click()
  await dialog.getByLabel('ตั้งแต่วันที่').fill(today)
  await dialog.getByLabel('ถึงวันที่').fill(today)
  await dialog.getByRole('button', { name: 'ค้นหา', exact: true }).click()
  await expect(dialog.locator('.ss-result')).toHaveCount(1)
  await expect(dialog.locator('mark')).toHaveText('กำหนดส่ง')
  await dialog.locator('.ss-result').click()
  await expect(page.locator('article.is-highlighted .ss-bubble')).toHaveText('เริ่มต้น กำหนดส่ง Lab วันศุกร์')
  await expect(page.locator('article.is-highlighted')).toBeInViewport()

  // A range that ended before today finds nothing; a keyword alone pages newest first.
  await page.getByRole('button', { name: 'ค้นหาข้อความ', exact: true }).click()
  await dialog.getByLabel('คำค้น').fill('กำหนดส่ง')
  await dialog.getByRole('button', { name: 'กรองตามวันที่', exact: true }).click()
  await dialog.getByLabel('ถึงวันที่').fill('2020-01-01')
  await dialog.getByRole('button', { name: 'ค้นหา', exact: true }).click()
  await expect(dialog.getByText('ไม่พบข้อความที่ตรงกับเงื่อนไข')).toBeVisible()
  await dialog.getByRole('button', { name: 'ล้าง', exact: true }).click()
  await dialog.getByLabel('คำค้น').fill('หมายเลข')
  await dialog.getByRole('button', { name: 'ค้นหา', exact: true }).click()
  await expect(dialog.locator('.ss-result')).toHaveCount(30)
  await expect(dialog.locator('.ss-result').first()).toContainText('ข้อความหมายเลข 070')
  await dialog.getByRole('button', { name: 'โหลดผลเพิ่ม', exact: true }).click()
  await expect(dialog.locator('.ss-result')).toHaveCount(60)
  await dialog.getByRole('button', { name: 'โหลดผลเพิ่ม', exact: true }).click()
  await expect(dialog.locator('.ss-result')).toHaveCount(70)
  await expect(dialog.getByRole('button', { name: 'โหลดผลเพิ่ม', exact: true })).toHaveCount(0)
})

test('new members see history only from their join point and outsiders cannot read it', async ({ browser }) => {
  const pages: Page[] = []
  for (let index = 0; index < 2; index++) { const context = await browser.newContext(); contexts.push(context); pages.push(await context.newPage()) }
  const [a, b] = pages, an = name('Early'), bn = name('Late'), group = `ขอบเขต ${an}`
  await register(a, an); await register(b, bn)
  await createGroup(a, group)
  await send(a, 'ก่อน Late เข้าร่วม')
  await openGroup(b, group)
  await b.getByRole('button', { name: 'เข้าร่วมด้วยตัวเอง' }).click()
  await expect(b.getByText('คุณจะเห็นข้อความตั้งแต่ตอนที่เข้าร่วมกลุ่มเป็นต้นไป')).toBeVisible()
  await send(a, 'หลัง Late เข้าร่วม')
  await b.reload(); await expect(b.getByRole('navigation')).toBeVisible(); await openGroup(b, group)
  await expect(b.locator('.ss-bubble')).toHaveText(['หลัง Late เข้าร่วม'])
  // An outsider guessing room IDs gets FORBIDDEN for history and search.
  const outsider = await rawClient(a, name('Out'), group, [
    { type: 'HISTORY_GET', data: { room_id: '$ROOM' } }, { type: 'HISTORY_SEARCH', data: { room_id: '$ROOM', query: 'Late' } },
  ], false)
  expect(outsider.map(result => result.error?.code)).toEqual(['FORBIDDEN', 'FORBIDDEN'])
})

test('files upload with progress, download with matching SHA-256, list in Files tab and stay private', async ({ browser }) => {
  const pages: Page[] = []
  for (let index = 0; index < 2; index++) { const context = await browser.newContext({ acceptDownloads: true }); contexts.push(context); pages.push(await context.newPage()) }
  const [a, b] = pages, an = name('Sender'), bn = name('Receiver'), group = `ไฟล์ ${an}`
  await register(a, an); await register(b, bn)
  await createGroup(a, group)
  await openGroup(b, group)
  await b.getByRole('button', { name: 'เข้าร่วมด้วยตัวเอง' }).click()
  const content = randomBytes(1_500_000), fileName = 'รายงาน Lab 3.pdf'
  await a.locator('input[type=file]').setInputFiles({ name: fileName, mimeType: 'application/pdf', buffer: content })
  await expect(a.locator('.ss-file-card').getByText(fileName, { exact: true })).toBeVisible()
  await expect(a.locator('.ss-upload')).toHaveCount(0)
  const card = b.locator('.ss-file-card').filter({ hasText: fileName })
  await expect(card).toContainText('1.43 MB')
  const [download] = await Promise.all([b.waitForEvent('download'), card.getByRole('button', { name: `ดาวน์โหลด ${fileName}` }).click()])
  expect(download.suggestedFilename()).toBe(fileName)
  const saved = await readFile((await download.path())!)
  expect(sha(saved)).toBe(sha(content))

  // Over the 5 MiB limit is refused in the browser before any bytes are sent.
  await a.locator('input[type=file]').setInputFiles({ name: 'big.bin', mimeType: 'application/octet-stream', buffer: Buffer.alloc(5 * 1024 * 1024 + 1) })
  await expect(a.locator('.ss-upload.is-error')).toContainText('ไฟล์ต้องมีขนาดไม่เกิน 5 MB')
  await a.getByRole('button', { name: 'ปิดข้อความแจ้งไฟล์' }).click()

  // Files tab lists permitted files; history keeps them after a reload.
  await b.reload(); await expect(b.getByRole('navigation')).toBeVisible(); await openGroup(b, group)
  await b.getByRole('tab', { name: 'ไฟล์', exact: true }).click()
  await expect(b.locator('.ss-file-row')).toHaveCount(1)
  await expect(b.locator('.ss-file-row code')).toBeHidden()
  await b.locator('.ss-file-row').getByText('รายละเอียดไฟล์', { exact: true }).click()
  await expect(b.locator('.ss-file-row code')).toHaveText(sha(content))
  await b.getByRole('tab', { name: 'แชต', exact: true }).click()
  await expect(b.locator('.ss-file-card').filter({ hasText: fileName })).toHaveCount(1)

  // An outsider guessing attachment IDs is refused, and never received the event.
  const guesses = Array.from({ length: 20 }, (_, i) => ({ type: 'FILE_GET', data: { attachment_id: i + 1 } }))
  const outsider = await rawClient(a, name('Peek'), null, guesses)
  expect(outsider.every(result => result.error?.code === 'FORBIDDEN')).toBeTruthy()
})

test('a dropped connection mid-upload reports failure, keeps chat usable after re-login and publishes nothing', async ({ browser, request }) => {
  const context = await browser.newContext(); contexts.push(context)
  const page = await context.newPage(), user = name('Drop'), group = `หลุด ${user}`
  const headers = { 'X-Test-Control': process.env.STUDYGROUP_TEST_CONTROL! }
  await register(page, user)
  await createGroup(page, group)
  expect((await request.get('/__test__/stall-file-chunks', { headers })).ok()).toBeTruthy()
  await page.locator('input[type=file]').setInputFiles({ name: 'large.bin', mimeType: 'application/octet-stream', buffer: randomBytes(5 * 1024 * 1024) })
  await expect(page.getByRole('progressbar', { name: 'กำลังส่งไฟล์ large.bin' })).toBeVisible()
  await expect.poll(async () => Number(await (await request.get('/__test__/partial-count', { headers })).text())).toBe(1)
  expect((await request.get('/__test__/disconnect', { headers })).ok()).toBeTruthy()
  await expect(page.locator('.ss-upload.is-error')).toContainText('การเชื่อมต่อขาดหาย')
  await page.getByRole('button', { name: 'เข้าสู่ระบบใหม่', exact: true }).click()
  await login(page, user)
  await send(page, 'แชตยังใช้งานได้หลังไฟล์ขาด')
  await page.getByRole('tab', { name: 'ไฟล์', exact: true }).click()
  await expect(page.getByText('ยังไม่มีไฟล์ในห้องนี้')).toBeVisible()
  await expect.poll(async () => Number(await (await request.get('/__test__/partial-count', { headers })).text())).toBe(0)
})
