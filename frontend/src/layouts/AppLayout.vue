<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const auth = useAuthStore()

const pageTitle = computed(() => {
  return typeof route.meta.title === 'string' ? route.meta.title : 'FitManager'
})

const themeLabel = computed(() => (appStore.theme === 'light' ? '深色' : '明亮'))

const navItems = [
  { to: '/dashboard', label: '数据概览' },
  { to: '/plans', label: '健身计划' },
  { to: '/records', label: '训练记录' },
  { to: '/statistics', label: '统计分析' },
  { to: '/compare', label: '多用户比较' },
  { to: '/settings', label: '系统设置' },
]

async function onLogout() {
  await auth.logout()
  ElMessage.success('已退出')
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell" :class="{ 'nav-open': appStore.navOpen }">
    <aside class="app-sidebar" aria-label="主导航">
      <div class="app-brand">
        <div class="app-brand-mark" aria-hidden="true" />
        <div>
          <div class="app-brand-title">FitManager</div>
          <div class="app-brand-sub">训练记录</div>
        </div>
      </div>
      <nav class="app-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          @click="appStore.toggleNav(false)"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <div class="app-topbar-left">
          <button
            class="mobile-nav-toggle"
            type="button"
            aria-label="打开导航"
            @click="appStore.toggleNav()"
          >
            菜单
          </button>
          <h1>{{ pageTitle }}</h1>
        </div>
        <div class="app-topbar-meta">
          <button
            type="button"
            class="theme-toggle"
            :aria-label="`切换到${themeLabel}模式`"
            @click="appStore.toggleTheme()"
          >
            {{ themeLabel }}模式
          </button>
          <span>{{ auth.user?.display_name }}（{{ auth.user?.username }}）</span>
          <button type="button" class="logout-btn" @click="onLogout">退出</button>
        </div>
      </header>

      <main class="app-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>
