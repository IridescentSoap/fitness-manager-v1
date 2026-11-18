import { defineStore } from 'pinia'
import { ref } from 'vue'

import { fetchHealth } from '@/api/health'
import type { HealthData } from '@/types/api'

export type ThemeMode = 'light' | 'dark'

const THEME_KEY = 'fm_theme'

function readStoredTheme(): ThemeMode {
  const saved = localStorage.getItem(THEME_KEY)
  if (saved === 'light' || saved === 'dark') {
    return saved
  }
  // 默认明亮模式，便于日常查看；仍可一键切回深色运动主题
  return 'light'
}

function applyTheme(theme: ThemeMode) {
  document.documentElement.setAttribute('data-theme', theme)
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.setItem(THEME_KEY, theme)
}

export const useAppStore = defineStore('app', () => {
  const health = ref<HealthData | null>(null)
  const healthError = ref<string | null>(null)
  const navOpen = ref(false)
  const theme = ref<ThemeMode>(readStoredTheme())

  applyTheme(theme.value)

  async function loadHealth() {
    healthError.value = null
    try {
      health.value = await fetchHealth()
    } catch (error) {
      health.value = null
      healthError.value = error instanceof Error ? error.message : '健康检查失败'
    }
  }

  function toggleNav(force?: boolean) {
    navOpen.value = typeof force === 'boolean' ? force : !navOpen.value
  }

  function setTheme(next: ThemeMode) {
    theme.value = next
    applyTheme(next)
  }

  function toggleTheme() {
    setTheme(theme.value === 'light' ? 'dark' : 'light')
  }

  return {
    health,
    healthError,
    navOpen,
    theme,
    loadHealth,
    toggleNav,
    setTheme,
    toggleTheme,
  }
})
