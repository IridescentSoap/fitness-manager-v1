import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const ADMIN = {
  username: 'admin',
  display_name: '管理员',
  password: 'AdminPass123!',
}

export const USER_A = {
  username: 'alice',
  display_name: 'Alice',
  password: 'UserPass1234!',
}

export const USER_B = {
  username: 'bob',
  display_name: 'Bob',
  password: 'UserPass1234!',
}

export function todayBusinessIso(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

export function weekdayIso(dateIso: string): number {
  return ((new Date(`${dateIso}T12:00:00+08:00`).getDay() + 6) % 7) + 1
}

export async function ensureInitialized(page: Page) {
  await page.goto('/')
  await page.waitForLoadState('domcontentloaded')
  const heading = page.locator('h1')
  await expect(heading).toBeVisible({ timeout: 30_000 })
  const text = (await heading.textContent()) || ''

  if (text.includes('首次初始化')) {
    await page.fill('input[name="username"]', ADMIN.username)
    await page.fill('input[name="display_name"]', ADMIN.display_name)
    await page.fill('input[name="password"]', ADMIN.password)
    await page.click('button[type="submit"]')
  } else if (text.includes('登录')) {
    await page.fill('input[name="username"]', ADMIN.username)
    await page.fill('input[name="password"]', ADMIN.password)
    await page.click('button[type="submit"]')
  }

  await expect(page.getByRole('heading', { name: '数据概览' })).toBeVisible({ timeout: 30_000 })
}

export async function loginAs(page: Page, username: string, password: string) {
  await page.goto('/login')
  await page.fill('input[name="username"]', username)
  await page.fill('input[name="password"]', password)
  await page.click('button[type="submit"]')
  await expect(page.getByRole('heading', { name: '数据概览' })).toBeVisible({ timeout: 30_000 })
}

export async function logout(page: Page) {
  const logoutBtn = page.getByRole('button', { name: '退出' })
  if (await logoutBtn.isVisible().catch(() => false)) {
    await logoutBtn.click()
    await expect(page.locator('h1')).toContainText(/登录|首次初始化/)
  }
}

export async function apiLogin(request: APIRequestContext, username: string, password: string) {
  const response = await request.post('/api/auth/login', {
    data: { username, password },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()).data as {
    csrf_token: string
    user: { id: number; username: string }
  }
}

export function csrfHeaders(token: string) {
  return { 'X-CSRF-Token': token }
}
