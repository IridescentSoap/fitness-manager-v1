import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  changePassword as changePasswordApi,
  fetchMe,
  fetchSetupStatus,
  initializeAdmin,
  login as loginApi,
  logout as logoutApi,
} from '@/api/auth'
import { setCsrfToken } from '@/api/client'
import type { AuthUser } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const initialized = ref<boolean | null>(null)
  const bootstrapped = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => user.value != null)
  const isAdmin = computed(() => user.value?.role === 'ADMIN')

  async function bootstrap() {
    loading.value = true
    error.value = null
    try {
      const status = await fetchSetupStatus()
      initialized.value = status.initialized
      if (status.initialized) {
        try {
          const me = await fetchMe()
          user.value = me.user
        } catch {
          user.value = null
          setCsrfToken('')
        }
      } else {
        user.value = null
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '无法连接后端'
      initialized.value = null
      user.value = null
    } finally {
      bootstrapped.value = true
      loading.value = false
    }
  }

  async function initialize(payload: {
    username: string
    display_name: string
    password: string
  }) {
    const data = await initializeAdmin(payload)
    user.value = data.user
    initialized.value = true
  }

  async function login(payload: { username: string; password: string }) {
    const data = await loginApi(payload)
    user.value = data.user
    initialized.value = true
  }

  async function logout() {
    try {
      await logoutApi()
    } finally {
      user.value = null
      setCsrfToken('')
    }
  }

  async function changePassword(payload: { old_password: string; new_password: string }) {
    const data = await changePasswordApi(payload)
    user.value = data.user
  }

  return {
    user,
    initialized,
    bootstrapped,
    loading,
    error,
    isAuthenticated,
    isAdmin,
    bootstrap,
    initialize,
    login,
    logout,
    changePassword,
  }
})
