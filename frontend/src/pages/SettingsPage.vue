<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createUser, listUsers, resetUserPassword, updateUser } from '@/api/admin'
import { createBackup, listBackups, restoreBackup, type BackupItem } from '@/api/backups'
import { ApiError } from '@/api/client'
import { createExercise, deactivateExercise, listExercises } from '@/api/exercises'
import { getSharing, updateProfile, updateSharing } from '@/api/settings'
import { useAuthStore } from '@/stores/auth'
import type { AdminUserItem, ExerciseItem, SharingSettings } from '@/types/auth'

const auth = useAuthStore()

const profileForm = reactive({
  display_name: auth.user?.display_name ?? '',
  target_weight_kg: '' as string,
  old_password: '',
  new_password: '',
})

const sharing = reactive<SharingSettings>({
  share_training_stats: false,
  share_weight_change: false,
  share_weight_values: false,
})

const exercises = ref<ExerciseItem[]>([])
const exerciseForm = reactive({
  name: '',
  category: 'STRENGTH',
  description: '',
})

const users = ref<AdminUserItem[]>([])
const backups = ref<BackupItem[]>([])
const userForm = reactive({
  username: '',
  display_name: '',
  password: '',
})

async function loadAll() {
  try {
    const [share, exerciseData] = await Promise.all([getSharing(), listExercises()])
    Object.assign(sharing, share)
    exercises.value = exerciseData.items
    if (auth.isAdmin) {
      const userData = await listUsers()
      users.value = userData.items
      const backupData = await listBackups()
      backups.value = backupData.items
    }
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '加载设置失败')
  }
}

onMounted(() => {
  profileForm.display_name = auth.user?.display_name ?? ''
  void loadAll()
})

async function saveProfile() {
  try {
    const profilePayload: { display_name: string; target_weight_kg?: number | null } = {
      display_name: profileForm.display_name,
    }
    if (profileForm.target_weight_kg.trim() !== '') {
      profilePayload.target_weight_kg = Number(profileForm.target_weight_kg)
    }
    await updateProfile(profilePayload)
    if (profileForm.old_password && profileForm.new_password) {
      await auth.changePassword({
        old_password: profileForm.old_password,
        new_password: profileForm.new_password,
      })
      profileForm.old_password = ''
      profileForm.new_password = ''
    }
    ElMessage.success('资料已保存')
    await auth.bootstrap()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '保存失败')
  }
}

async function saveSharing() {
  try {
    if (sharing.share_weight_values) {
      await ElMessageBox.confirm(
        '开启体重数值共享后，他人可查看你的体重曲线并推导变化。确认继续？',
        '确认授权',
        { type: 'warning' },
      )
    }
    const data = await updateSharing({ ...sharing })
    Object.assign(sharing, data)
    ElMessage.success('共享设置已更新')
  } catch (err) {
    if (err === 'cancel') return
    ElMessage.error(err instanceof ApiError ? err.message : '更新失败')
  }
}

async function addExercise() {
  try {
    await createExercise({ ...exerciseForm })
    exerciseForm.name = ''
    exerciseForm.description = ''
    ElMessage.success('已添加自定义动作')
    const data = await listExercises()
    exercises.value = data.items
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '添加失败')
  }
}

async function removeExercise(item: ExerciseItem) {
  if (item.is_system) return
  try {
    await deactivateExercise(item.id)
    ElMessage.success('已停用')
    const data = await listExercises()
    exercises.value = data.items
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '停用失败')
  }
}

async function addUser() {
  try {
    await createUser({ ...userForm })
    userForm.username = ''
    userForm.display_name = ''
    userForm.password = ''
    ElMessage.success('用户已创建')
    const data = await listUsers()
    users.value = data.items
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '创建失败')
  }
}

async function toggleUserStatus(item: AdminUserItem) {
  if (item.role === 'ADMIN') return
  const status = item.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
  try {
    await updateUser(item.id, { status })
    ElMessage.success(status === 'DISABLED' ? '已停用' : '已启用')
    const data = await listUsers()
    users.value = data.items
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '操作失败')
  }
}

async function onBackup() {
  try {
    const created = await createBackup()
    ElMessage.success(`已备份 ${created.filename}`)
    backups.value = (await listBackups()).items
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '备份失败')
  }
}

async function onRestore(item: BackupItem) {
  try {
    const { value } = await ElMessageBox.prompt(
      `将用 ${item.filename} 覆盖当前数据库。请输入确认短语 RESTORE。`,
      '恢复备份',
      {
        type: 'warning',
        inputPattern: /^RESTORE$/,
        inputErrorMessage: '必须输入 RESTORE',
      },
    )
    if (value !== 'RESTORE') return
    await restoreBackup(item.id)
    ElMessage.success('已恢复，请刷新页面')
  } catch (err) {
    if (err === 'cancel') return
    ElMessage.error(err instanceof ApiError ? err.message : '恢复失败')
  }
}

async function resetPassword(item: AdminUserItem) {
  try {
    const { value } = await ElMessageBox.prompt(`为 ${item.username} 设置新密码`, '重置密码', {
      inputType: 'password',
      inputPattern: /^[\s\S]{1,128}$/,
      inputErrorMessage: '密码不能为空，最长 128',
    })
    await resetUserPassword(item.id, value)
    ElMessage.success('密码已重置，旧会话已失效')
  } catch (err) {
    if (err === 'cancel') return
    ElMessage.error(err instanceof ApiError ? err.message : '重置失败')
  }
}
</script>

<template>
  <div class="settings-grid">
    <section class="panel">
      <h2>账户资料</h2>
      <label>显示名<input v-model="profileForm.display_name" /></label>
      <label>目标体重 (kg)<input v-model="profileForm.target_weight_kg" type="number" step="0.1" min="20" max="400" placeholder="可选" /></label>
      <label>原密码<input v-model="profileForm.old_password" type="password" autocomplete="current-password" /></label>
      <label>新密码<input v-model="profileForm.new_password" type="password" autocomplete="new-password" maxlength="128" /></label>
      <button type="button" @click="saveProfile">保存资料/密码</button>
    </section>

    <section class="panel">
      <h2>共享授权（默认关闭）</h2>
      <label class="check"><input v-model="sharing.share_training_stats" type="checkbox" /> 共享训练汇总</label>
      <label class="check"><input v-model="sharing.share_weight_change" type="checkbox" /> 共享体重变化</label>
      <label class="check"><input v-model="sharing.share_weight_values" type="checkbox" /> 共享体重原始数值</label>
      <button type="button" @click="saveSharing">保存共享设置</button>
    </section>

    <section class="panel wide">
      <h2>动作库</h2>
      <div class="inline-form">
        <input v-model="exerciseForm.name" placeholder="自定义动作名" />
        <select v-model="exerciseForm.category">
          <option value="STRENGTH">力量</option>
          <option value="CARDIO">有氧</option>
          <option value="STRETCH">拉伸</option>
        </select>
        <input v-model="exerciseForm.description" placeholder="备注（可选）" />
        <button type="button" @click="addExercise">添加</button>
      </div>
      <table>
        <thead>
          <tr><th>名称</th><th>类型</th><th>来源</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="item in exercises" :key="item.id">
            <td>{{ item.name }}</td>
            <td>{{ item.category }}</td>
            <td>{{ item.is_system ? '系统' : '自定义' }}</td>
            <td>
              <button
                v-if="!item.is_system"
                type="button"
                class="ghost"
                @click="removeExercise(item)"
              >
                停用
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="auth.isAdmin" class="panel wide">
      <h2>备份与恢复</h2>
      <p>恢复会覆盖当前数据。系统会先自动做一份恢复前备份。</p>
      <button type="button" @click="onBackup">立即备份</button>
      <table>
        <thead><tr><th>文件</th><th>时间</th><th></th></tr></thead>
        <tbody>
          <tr v-for="item in backups" :key="item.id">
            <td>{{ item.filename }}</td>
            <td>{{ item.created_at || '—' }}</td>
            <td><button type="button" class="ghost" @click="onRestore(item)">恢复</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="auth.isAdmin" class="panel wide">
      <h2>用户管理（管理员）</h2>
      <div class="inline-form">
        <input v-model="userForm.username" placeholder="用户名" />
        <input v-model="userForm.display_name" placeholder="显示名" />
        <input v-model="userForm.password" type="password" placeholder="初始密码" />
        <button type="button" @click="addUser">创建用户</button>
      </div>
      <table>
        <thead>
          <tr><th>用户名</th><th>显示名</th><th>角色</th><th>状态</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="item in users" :key="item.id">
            <td>{{ item.username }}</td>
            <td>{{ item.display_name }}</td>
            <td>{{ item.role }}</td>
            <td>{{ item.status }}</td>
            <td class="actions">
              <button
                v-if="item.role !== 'ADMIN'"
                type="button"
                class="ghost"
                @click="toggleUserStatus(item)"
              >
                {{ item.status === 'ACTIVE' ? '停用' : '启用' }}
              </button>
              <button type="button" class="ghost" @click="resetPassword(item)">重置密码</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  padding: var(--panel-pad);
  display: grid;
  gap: 14px;
  box-shadow: var(--shadow-soft);
}

.panel.wide {
  grid-column: 1 / -1;
}

.panel h2 {
  margin: 0 0 4px;
  font-size: 1.05rem;
}

label {
  display: grid;
  gap: 6px;
  color: var(--text-muted);
  font-size: 0.9rem;
}

label.check {
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 8px;
}

input,
select,
button {
  font: inherit;
}

input,
select {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
}

button {
  justify-self: start;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: var(--btn-on-accent);
  font-weight: 650;
  cursor: pointer;
}

button.ghost {
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--border);
}

.inline-form {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 1.2fr auto;
  gap: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

th,
td {
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid var(--border);
}

.actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .inline-form {
    grid-template-columns: 1fr;
  }
}
</style>
