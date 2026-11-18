<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { ApiError } from '@/api/client'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const appStore = useAppStore()
const router = useRouter()
const route = useRoute()

const themeLabel = computed(() => (appStore.theme === 'light' ? '深色' : '明亮'))

const mode = ref<'login' | 'setup'>('login')
const submitting = ref(false)
const form = reactive({
  username: '',
  display_name: '',
  password: '',
})

const title = computed(() => (mode.value === 'setup' ? '首次初始化管理员' : '登录 FitManager'))
const subtitle = computed(() =>
  mode.value === 'setup'
    ? '仅本机 127.0.0.1 可执行首次初始化。密码非空即可。'
    : '训练后记录 · 局域网访问',
)

onMounted(async () => {
  if (!auth.bootstrapped) {
    await auth.bootstrap()
  }
  mode.value = auth.initialized === false ? 'setup' : 'login'
  if (auth.isAuthenticated) {
    await router.replace((route.query.redirect as string) || '/dashboard')
  }
})

async function submit() {
  submitting.value = true
  try {
    if (mode.value === 'setup') {
      await auth.initialize({
        username: form.username,
        display_name: form.display_name || form.username,
        password: form.password,
      })
      ElMessage.success('管理员已创建')
    } else {
      await auth.login({ username: form.username, password: form.password })
      ElMessage.success('登录成功')
    }
    await router.replace((route.query.redirect as string) || '/dashboard')
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '操作失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <button
      type="button"
      class="theme-toggle login-theme"
      :aria-label="`切换到${themeLabel}模式`"
      @click="appStore.toggleTheme()"
    >
      {{ themeLabel }}模式
    </button>
    <form class="login-card" @submit.prevent="submit">
      <div class="brand-row">
        <div class="app-brand-mark" aria-hidden="true" />
        <div>
          <p class="brand-kicker">FitManager</p>
          <h1>{{ title }}</h1>
          <p>{{ subtitle }}</p>
        </div>
      </div>

      <label>
        用户名
        <input v-model="form.username" name="username" autocomplete="username" required />
      </label>

      <label v-if="mode === 'setup'">
        显示名
        <input v-model="form.display_name" name="display_name" autocomplete="nickname" />
      </label>

      <label>
        密码
        <input
          v-model="form.password"
          type="password"
          name="password"
          autocomplete="current-password"
          required
          maxlength="128"
        />
      </label>

      <button type="submit" :disabled="submitting">
        {{ submitting ? '提交中…' : mode === 'setup' ? '创建管理员' : '登录' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 28px;
  background:
    linear-gradient(180deg, var(--bg-deep), var(--bg) 50%, var(--bg-end));
}

.login-theme {
  position: absolute;
  top: 20px;
  right: 20px;
}

.login-card {
  width: min(100%, 420px);
  display: grid;
  gap: 16px;
  padding: 32px 28px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  box-shadow: var(--shadow);
}

.brand-row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 4px;
}

.brand-kicker {
  margin: 0 0 4px;
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.brand-row h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.4rem;
  letter-spacing: 0.01em;
}

.brand-row p:last-child {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

label {
  display: grid;
  gap: 6px;
  color: var(--text-muted);
  font-size: 0.88rem;
}

input {
  width: 100%;
  min-height: var(--control-height);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}

button[type='submit'] {
  margin-top: 4px;
  min-height: 44px;
  padding: 0 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: var(--btn-on-accent);
  font-weight: 700;
  cursor: pointer;
}

button[type='submit']:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

button[type='submit']:hover:not(:disabled) {
  background: var(--accent-hover);
}
</style>
