import { test, expect, chromium, type BrowserContext, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const key = 'studygroup.session.v1'
const password = 'browser test password🔑'
const navigation = (page: Page) => page.getByRole('navigation', { name: 'รายชื่อคนและห้องแชต' })
let contexts: BrowserContext[] = []
test.afterEach(async () => { await Promise.all(contexts.map(context => context.close())); contexts = [] })

async function register(page: Page) {
  const username = `Remember_${randomUUID().slice(0, 7)}`
  await page.goto('/')
  await page.getByRole('button', { name: 'ยังไม่มีบัญชี? สมัครสมาชิก' }).click()
  await page.getByLabel('ชื่อผู้ใช้', { exact: true }).fill(username)
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByLabel('ยืนยันรหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'สมัครสมาชิก', exact: true }).click()
  await expect(page.getByText('สมัครสมาชิกแล้ว กรุณาเข้าสู่ระบบด้วยบัญชีที่สร้าง')).toBeVisible()
  await page.getByLabel('รหัสผ่าน', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click()
  await expect(navigation(page)).toBeVisible()
}

async function session(page: Page) {
  return page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key) as Promise<{ resume_token: string; expires_at: number }>
}

test('reload and reopening a tab restore the account and history without replaying drafts', async ({ browser }) => {
  const context = await browser.newContext(); contexts.push(context)
  const page = await context.newPage()
  const authRequests: string[] = []
  page.on('websocket', socket => socket.on('framesent', frame => {
    const packet = JSON.parse(String(frame.payload))
    if (['LOGIN', 'RESUME_SESSION'].includes(packet.type)) authRequests.push(packet.type)
  }))
  await register(page)
  const stored = await session(page)
  expect(Object.keys(stored).sort()).toEqual(['expires_at', 'resume_token'])
  expect(stored.resume_token).toMatch(/^[A-Za-z0-9_-]{43}$/)
  expect(stored.expires_at - Date.now() / 1000).toBeGreaterThan(7 * 86400 - 60)
  await navigation(page).getByRole('button', { name: 'สร้างกลุ่มใหม่', exact: true }).click()
  await page.getByRole('dialog').getByLabel('ชื่อกลุ่ม').fill('Remembered history')
  await page.getByRole('dialog').getByRole('button', { name: 'สร้างกลุ่ม', exact: true }).click()
  const editor = page.getByRole('textbox', { name: 'ข้อความแชต' })
  await editor.fill('บันทึกไว้แล้ว')
  await page.getByRole('button', { name: 'ส่งข้อความ', exact: true }).click()
  await expect(page.locator('.ss-bubble')).toHaveCount(1)
  await editor.fill('ร่างนี้ห้ามส่งเอง')
  await page.reload()
  await expect(navigation(page)).toBeVisible()
  await navigation(page).getByRole('button', { name: 'เปิดห้อง Remembered history', exact: true }).click()
  await expect(page.locator('.ss-bubble')).toHaveCount(1)
  await expect(page.locator('.ss-bubble')).toHaveText('บันทึกไว้แล้ว')
  await expect(editor).toHaveValue('')
  expect(await session(page)).toEqual(stored)
  expect(authRequests).toEqual(['LOGIN', 'RESUME_SESSION'])
  await page.close()
  const reopened = await context.newPage()
  await reopened.goto('/')
  await expect(navigation(reopened)).toBeVisible()
  expect(await session(reopened)).toEqual(stored)
})

test('closing and restarting the browser preserves login in its profile', async () => {
  const profile = await mkdtemp(join(tmpdir(), 'studygroup-resume-'))
  let context: BrowserContext | undefined
  try {
    const options = { channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome', headless: true, baseURL: 'http://127.0.0.1:8765' }
    context = await chromium.launchPersistentContext(profile, options)
    const page = await context.newPage()
    await register(page)
    const stored = await session(page)
    await context.close()
    context = await chromium.launchPersistentContext(profile, options)
    const reopened = await context.newPage()
    await reopened.goto('/')
    await expect(navigation(reopened)).toBeVisible()
    expect(await session(reopened)).toEqual(stored)
  } finally {
    await context?.close()
    await rm(profile, { recursive: true, force: true })
  }
})

test('newest tab takes over and logout clears other tabs and revokes the copied token', async ({ browser }) => {
  const context = await browser.newContext(); contexts.push(context)
  const first = await context.newPage()
  await register(first)
  const stored = await session(first)
  const latest = await context.newPage()
  await latest.goto('/')
  await expect(navigation(latest)).toBeVisible()
  await expect(first.getByRole('button', { name: 'เข้าสู่ระบบใหม่', exact: true })).toBeVisible()
  await expect(navigation(latest).getByText('1 คน', { exact: true })).toBeVisible()
  await latest.getByRole('button', { name: 'เมนูบัญชี', exact: true }).click()
  await latest.getByRole('button', { name: 'ออกจากระบบ', exact: true }).click()
  for (const page of [first, latest]) {
    await expect(page.getByRole('heading', { name: 'ยินดีต้อนรับกลับมา', exact: true })).toBeVisible()
    expect(await page.evaluate(key => localStorage.getItem(key), key)).toBeNull()
  }
  await latest.reload()
  await expect(navigation(latest)).toHaveCount(0)
  const other = await browser.newContext(); contexts.push(other)
  await other.addInitScript(({ key, stored }) => localStorage.setItem(key, JSON.stringify(stored)), { key, stored })
  const stale = await other.newPage()
  await stale.goto('/')
  await expect(stale.getByText('การเข้าสู่ระบบหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง')).toBeVisible()
  expect(await stale.evaluate(key => localStorage.getItem(key), key)).toBeNull()
})

test('server rejects an unknown token and the browser returns to login', async ({ browser }) => {
  const context = await browser.newContext(); contexts.push(context)
  await context.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({ resume_token: 'x'.repeat(43), expires_at: Math.floor(Date.now() / 1000) + 86400 })), { key })
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByText('การเข้าสู่ระบบหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง')).toBeVisible()
  expect(await page.evaluate(key => localStorage.getItem(key), key)).toBeNull()
  await expect(page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true })).toBeEnabled()
})

for (const [label, value] of [
  ['malformed JSON', '{broken'],
  ['malformed token', JSON.stringify({ resume_token: 'bad', expires_at: 9999999999 })],
  ['expired token', JSON.stringify({ resume_token: 'x'.repeat(43), expires_at: 1 })],
]) {
  test(`${label} in storage leaves login usable`, async ({ browser }) => {
    const context = await browser.newContext(); contexts.push(context)
    await context.addInitScript(({ key, value }) => localStorage.setItem(key, value), { key, value })
    const page = await context.newPage()
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'ยินดีต้อนรับกลับมา', exact: true })).toBeVisible()
    expect(await page.evaluate(key => localStorage.getItem(key), key)).toBeNull()
    await expect(page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true })).toBeEnabled()
  })
}

test('blocked storage does not prevent ordinary login', async ({ browser }) => {
  const context = await browser.newContext(); contexts.push(context)
  await context.addInitScript(() => { Storage.prototype.setItem = () => { throw new DOMException('Storage blocked', 'SecurityError') } })
  const page = await context.newPage()
  await register(page)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'ยินดีต้อนรับกลับมา', exact: true })).toBeVisible()
})

test('temporary socket failure retains the token for the next visit', async ({ browser }) => {
  const context = await browser.newContext(); contexts.push(context)
  const page = await context.newPage()
  await register(page)
  const stored = await session(page)
  await page.routeWebSocket('**/ws', socket => socket.close())
  await page.reload()
  await expect(page.getByRole('alert')).toBeVisible()
  expect(await session(page)).toEqual(stored)
  await page.close()
  const next = await context.newPage()
  await next.goto('/')
  await expect(navigation(next)).toBeVisible()
})
