import { defineConfig, devices } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { fileURLToPath } from 'node:url'

const control = process.env.STUDYGROUP_TEST_CONTROL ||= randomUUID()
const repo = fileURLToPath(new URL('..', import.meta.url))
export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: { ...devices['Desktop Chrome'], channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome', baseURL: 'http://127.0.0.1:8765', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: {
    command: 'uv run --locked python web/e2e/server.py', cwd: repo,
    url: 'http://127.0.0.1:8765/health', reuseExistingServer: false, timeout: 30000,
    env: { UV_CACHE_DIR: '/private/tmp/studygroup-uv-cache', STUDYGROUP_TEST_CONTROL: control,
           STUDYGROUP_WEB_HOST: '127.0.0.1', STUDYGROUP_WEB_PORT: '8765', STUDYGROUP_WEB_ORIGINS: 'http://127.0.0.1:8765' },
  },
})
