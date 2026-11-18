import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', redirect: '/dashboard' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/pages/DashboardPage.vue'),
        meta: { title: '数据概览' },
      },
      {
        path: 'plans',
        name: 'plans',
        component: () => import('@/pages/PlansPage.vue'),
        meta: { title: '健身计划' },
      },
      {
        path: 'records',
        name: 'records',
        component: () => import('@/pages/RecordsPage.vue'),
        meta: { title: '训练记录' },
      },
      {
        path: 'statistics',
        name: 'statistics',
        component: () => import('@/pages/StatisticsPage.vue'),
        meta: { title: '统计分析' },
      },
      {
        path: 'compare',
        name: 'compare',
        component: () => import('@/pages/ComparePage.vue'),
        meta: { title: '多用户比较' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/pages/SettingsPage.vue'),
        meta: { title: '系统设置' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.bootstrapped) {
    await auth.bootstrap()
  }

  const isPublic = Boolean(to.meta.public)
  if (!auth.isAuthenticated && !isPublic) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (auth.isAuthenticated && to.name === 'login') {
    return { name: 'dashboard' }
  }
  return true
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : 'FitManager'
  document.title = `${title} · FitManager`
})

export default router
