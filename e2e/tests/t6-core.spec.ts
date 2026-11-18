import { expect, test } from '@playwright/test'

import {
  ADMIN,
  USER_A,
  USER_B,
  apiLogin,
  csrfHeaders,
  ensureInitialized,
  loginAs,
  logout,
  todayBusinessIso,
  weekdayIso,
} from './helpers'

test.describe.configure({ mode: 'serial' })

test('T01 initialize / login and desktop shell', async ({ page }) => {
  await ensureInitialized(page)
  await expect(page.locator('.app-shell')).toBeVisible()
  await expect(page.locator('.app-sidebar')).toBeVisible()
  const overflow = await page.evaluate(() => {
    const el = document.scrollingElement
    return el ? el.scrollWidth - el.clientWidth : 0
  })
  expect(overflow).toBeLessThanOrEqual(8)
})

test('T02 create users and isolate custom exercises', async ({ page, request }) => {
  await ensureInitialized(page)
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '用户管理（管理员）' })).toBeVisible()

  const usersSection = page.locator('section.panel.wide').filter({ hasText: '用户管理' })
  for (const user of [USER_A, USER_B]) {
    if (!(await usersSection.getByText(user.username).count())) {
      await page.locator('input[placeholder="用户名"]').fill(user.username)
      await page.locator('input[placeholder="显示名"]').fill(user.display_name)
      await page.locator('input[placeholder="初始密码"]').fill(user.password)
      await page.getByRole('button', { name: '创建用户' }).click()
      await expect(usersSection.getByText(user.username)).toBeVisible({ timeout: 15_000 })
    }
  }

  await logout(page)
  await loginAs(page, USER_A.username, USER_A.password)
  await page.goto('/settings')
  await page.locator('input[placeholder="自定义动作名"]').fill('Alice私有深蹲变式')
  await page.getByRole('button', { name: '添加' }).click()
  await expect(page.getByText('Alice私有深蹲变式')).toBeVisible({ timeout: 15_000 })

  await apiLogin(request, USER_A.username, USER_A.password)
  const listA = await request.get('/api/exercises')
  expect(listA.ok()).toBeTruthy()
  const aliceItems = (await listA.json()).data.items as Array<{ id: number; name: string }>
  const privateItem = aliceItems.find((item) => item.name === 'Alice私有深蹲变式')
  expect(privateItem).toBeTruthy()

  await logout(page)
  await loginAs(page, USER_B.username, USER_B.password)
  await apiLogin(request, USER_B.username, USER_B.password)
  const detail = await request.get(`/api/exercises/${privateItem!.id}`)
  expect(detail.status()).toBe(404)
})

test('T05 ADD override + T10/T11 draft checkbox submit', async ({ page, request }) => {
  await logout(page).catch(() => undefined)
  await loginAs(page, USER_A.username, USER_A.password)

  const session = await apiLogin(request, USER_A.username, USER_A.password)
  const exercises = await request.get('/api/exercises')
  const items = (await exercises.json()).data.items as Array<{
    id: number
    name: string
    category: string
  }>
  const strength = items.filter((item) => item.category === 'STRENGTH').slice(0, 4)
  expect(strength.length).toBeGreaterThanOrEqual(1)
  const swim =
    items.find((item) => item.name.includes('游泳')) ||
    items.find((item) => item.category === 'CARDIO')
  expect(swim).toBeTruthy()

  const todayIso = todayBusinessIso()
  const weekday = weekdayIso(todayIso)

  const planRes = await request.post('/api/plans', {
    headers: csrfHeaders(session.csrf_token),
    data: {
      name: `E2E计划-${Date.now()}`,
      start_date: todayIso,
      end_date: null,
      days: [
        {
          weekday,
          title: '今日力量',
          is_rest: false,
          exercises: strength.slice(0, 4).map((item, index) => ({
            exercise_id: item.id,
            sort_order: index + 1,
            target_sets: 3,
            target_reps: 10,
            target_weight_kg: 20,
          })),
        },
      ],
    },
  })
  expect(planRes.status(), await planRes.text()).toBe(201)
  const planId = (await planRes.json()).data.id

  let activate = await request.post(`/api/plans/${planId}/activate`, {
    headers: csrfHeaders(session.csrf_token),
  })
  if (activate.status() === 409) {
    const plans = await request.get('/api/plans')
    const list = (await plans.json()).data.items as Array<{ id: number; status: string }>
    for (const item of list.filter((p) => p.status === 'ACTIVE' && p.id !== planId)) {
      await request.post(`/api/plans/${item.id}/deactivate`, {
        headers: csrfHeaders(session.csrf_token),
      })
    }
    activate = await request.post(`/api/plans/${planId}/activate`, {
      headers: csrfHeaders(session.csrf_token),
    })
  }
  expect(activate.ok(), await activate.text()).toBeTruthy()

  const add = await request.put(`/api/schedule/overrides/${todayIso}`, {
    headers: csrfHeaders(session.csrf_token),
    data: {
      mode: 'ADD',
      title: '临时游泳',
      exercises: [{ exercise_id: swim!.id, sort_order: 1, target_duration_min: 40 }],
    },
  })
  expect(add.ok(), await add.text()).toBeTruthy()

  const schedule = await request.get(`/api/schedule?from=${todayIso}&to=${todayIso}`)
  const tasks = (await schedule.json()).data.items as Array<{ slot: string; title: string }>
  expect(tasks.some((t) => t.slot === 'BASE')).toBeTruthy()
  expect(tasks.some((t) => t.slot === 'EXTRA' && t.title.includes('游泳'))).toBeTruthy()

  await page.goto(`/records?date=${todayIso}`)
  await expect(page.getByText('当天任务')).toBeVisible()
  await page.getByRole('button', { name: /BASE · 今日力量/ }).click()
  await expect(page.getByText(/草稿已打开|已保存|尚未修改|已提交/)).toBeVisible()

  const boxes = page.locator('table input[type="checkbox"]')
  const count = await boxes.count()
  expect(count).toBeGreaterThanOrEqual(3)
  for (let i = 0; i < Math.min(3, count); i += 1) {
    await boxes.nth(i).check()
  }
  await expect(page.getByText('已保存')).toBeVisible({ timeout: 15_000 })
  await page.reload()
  await page.getByRole('button', { name: /BASE · 今日力量/ }).click()
  await expect(page.locator('table input[type="checkbox"]:checked')).toHaveCount(
    Math.min(3, count),
  )

  await page.getByRole('button', { name: '提交记录' }).click()
  await expect(page.getByText(/已提交/)).toBeVisible({ timeout: 15_000 })
})

test('T20 weight same-day records', async ({ page, request }) => {
  await logout(page).catch(() => undefined)
  await loginAs(page, USER_A.username, USER_A.password)
  const session = await apiLogin(request, USER_A.username, USER_A.password)
  const todayIso = todayBusinessIso()

  for (const [hour, kg] of [
    [8, 70.2],
    [20, 69.8],
  ] as const) {
    const res = await request.post('/api/weights', {
      headers: csrfHeaders(session.csrf_token),
      data: {
        record_date: todayIso,
        recorded_at: `${todayIso}T${String(hour).padStart(2, '0')}:00:00+08:00`,
        weight_kg: kg,
        note: `e2e-${hour}`,
      },
    })
    expect(res.status(), await res.text()).toBe(201)
  }

  await page.goto('/statistics')
  await expect(page.getByRole('heading', { name: '统计分析' })).toBeVisible()
  await page.getByRole('button', { name: '体重管理' }).click()
  await expect(page.getByText(/最新体重/)).toBeVisible()
  await expect(page.getByText(/70\.2|69\.8|e2e-8|e2e-20/)).toBeVisible()
})

test('T22/T23 sharing revoke', async ({ request }) => {
  let alice = await apiLogin(request, USER_A.username, USER_A.password)
  let patch = await request.patch('/api/settings/sharing', {
    headers: csrfHeaders(alice.csrf_token),
    data: {
      share_training_stats: true,
      share_weight_change: true,
      share_weight_values: false,
    },
  })
  expect(patch.ok(), await patch.text()).toBeTruthy()

  await apiLogin(request, USER_B.username, USER_B.password)
  const list = await request.get('/api/comparison/users?scope=weight_change')
  expect(list.ok(), await list.text()).toBeTruthy()
  const users = (await list.json()).data.items as Array<{ username: string }>
  expect(users.some((u) => u.username === USER_A.username)).toBeTruthy()

  const bobSession = await apiLogin(request, USER_B.username, USER_B.password)
  const forbidden = await request.get(
    `/api/comparison/weight-trends?user_ids=${alice.user.id},${bobSession.user.id}&from=2020-01-01&to=2030-01-01`,
  )
  expect(forbidden.status()).toBe(403)

  alice = await apiLogin(request, USER_A.username, USER_A.password)
  patch = await request.patch('/api/settings/sharing', {
    headers: csrfHeaders(alice.csrf_token),
    data: {
      share_training_stats: false,
      share_weight_change: false,
      share_weight_values: false,
    },
  })
  expect(patch.ok(), await patch.text()).toBeTruthy()

  await apiLogin(request, USER_B.username, USER_B.password)
  const after = await request.get('/api/comparison/users?scope=weight_change')
  const afterUsers = (await after.json()).data.items as Array<{ username: string }>
  expect(afterUsers.some((u) => u.username === USER_A.username)).toBeFalsy()
})

test('T28 backup and restore via settings UI', async ({ page, request }) => {
  await logout(page).catch(() => undefined)
  await ensureInitialized(page)
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '备份与恢复' })).toBeVisible()

  const todayIso = todayBusinessIso()
  const before = await apiLogin(request, ADMIN.username, ADMIN.password)
  await request.post('/api/weights', {
    headers: csrfHeaders(before.csrf_token),
    data: {
      record_date: todayIso,
      recorded_at: `${todayIso}T07:00:00+08:00`,
      weight_kg: 66.6,
      note: 'backup-marker',
    },
  })

  await page.getByRole('button', { name: '立即备份' }).click()
  await expect(page.getByText(/已备份/)).toBeVisible({ timeout: 30_000 })

  const afterLogin = await apiLogin(request, ADMIN.username, ADMIN.password)
  await request.post('/api/weights', {
    headers: csrfHeaders(afterLogin.csrf_token),
    data: {
      record_date: todayIso,
      recorded_at: `${todayIso}T21:00:00+08:00`,
      weight_kg: 88.8,
      note: 'after-backup',
    },
  })

  await page.getByRole('button', { name: '恢复' }).first().click()
  const dialog = page.locator('.el-message-box')
  await expect(dialog).toBeVisible({ timeout: 10_000 })
  await dialog.locator('input').fill('RESTORE')
  await dialog.getByRole('button', { name: /确定|确认|OK/i }).click()
  await expect(page.getByText(/已恢复/)).toBeVisible({ timeout: 60_000 })
})
