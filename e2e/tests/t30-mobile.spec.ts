import { expect, test } from '@playwright/test'

import { ensureInitialized } from './helpers'

test('T30 mobile 375px: login and core nav usable', async ({ page }) => {
  await ensureInitialized(page)
  await expect(page.locator('.app-shell')).toBeVisible()

  const overflow = await page.evaluate(() => {
    const el = document.scrollingElement
    return el ? el.scrollWidth - el.clientWidth : 0
  })
  expect(overflow).toBeLessThanOrEqual(16)

  await page.getByRole('button', { name: '菜单' }).click()
  await expect(page.locator('.app-sidebar')).toBeVisible()
  await page.locator('.app-nav a', { hasText: '训练记录' }).click()
  await expect(page.getByRole('heading', { name: '训练记录' })).toBeVisible()
  await page.getByRole('button', { name: '菜单' }).click()
  await page.locator('.app-nav a', { hasText: '系统设置' }).click()
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
})
