<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiError } from '@/api/client'
import { listExercises } from '@/api/exercises'
import {
  activatePlan,
  createPlan,
  deactivatePlan,
  deleteOverride,
  duplicatePlan,
  getSchedule,
  listPlans,
  putOverride,
  updatePlan,
  type PlanDay,
  type PlanExercise,
  type PlanItem,
  type ScheduleItem,
} from '@/api/plans'
import type { ExerciseItem } from '@/types/auth'
import { addDays, businessToday, monthBounds, weekdayOf } from '@/utils/date'
import {
  cloneSet,
  defaultSetsForCategory,
  emptySet,
  formatSetsSummary,
  setsFromPlanExercise,
  type SetDraft,
} from '@/utils/sets'

interface EditorRow {
  key: number
  exercise_id: number
  sets: SetDraft[]
}

const loading = ref(false)
const error = ref('')
const plans = ref<PlanItem[]>([])
const exercises = ref<ExerciseItem[]>([])
const schedule = ref<ScheduleItem[]>([])
const month = ref(businessToday().slice(0, 7))
const view = ref<'week' | 'calendar'>('week')
const selectedDate = ref(businessToday())
const overrideMode = ref<'REST' | 'REPLACE' | 'ADD'>('REST')
const overrideTitle = ref('临时训练')
const overrideExerciseId = ref<number | null>(null)
const form = reactive({
  name: '',
  start_date: businessToday(),
  title: '训练日',
  exercise_id: 0,
})
const selectedWeekdays = ref<number[]>([1, 3, 5])
const editingPlanId = ref<number | null>(null)

const drawerOpen = ref(false)
const drawerSaving = ref(false)
const drawerWeekday = ref(1)
const drawerTitle = ref('训练日')
const drawerIsRest = ref(false)
let editorKeySeq = 1
const drawerRows = ref<EditorRow[]>([])
const expandedWeekdays = ref<number[]>([])

const activePlan = computed(() => plans.value.find((item) => item.status === 'ACTIVE') ?? null)
const editingPlan = computed(() => {
  if (editingPlanId.value != null) {
    return plans.value.find((item) => item.id === editingPlanId.value) ?? activePlan.value
  }
  return activePlan.value
})
const weekLabels = ['一', '二', '三', '四', '五', '六', '日']

const monthDays = computed(() => {
  const { from, to } = monthBounds(`${month.value}-01`)
  const days: string[] = []
  let cursor = from
  while (cursor <= to) {
    days.push(cursor)
    cursor = addDays(cursor, 1)
  }
  return days
})

function exerciseTargetSets(exerciseId: number): SetDraft[] {
  const item = exercises.value.find((entry) => entry.id === exerciseId)
  return defaultSetsForCategory(item?.category || 'STRENGTH')
}

function tasksOn(date: string) {
  return schedule.value.filter((item) => item.workout_date === date)
}

function exerciseName(id: number) {
  return exercises.value.find((item) => item.id === id)?.name ?? `#${id}`
}

function exerciseCategory(id: number) {
  return exercises.value.find((item) => item.id === id)?.category ?? '—'
}

function capacityText(item: PlanExercise) {
  const category = exerciseCategory(item.exercise_id)
  if (item.sets?.length) return formatSetsSummary(item.sets as SetDraft[], category)
  if (item.capacity?.trim()) return item.capacity.trim()
  if (item.target_sets != null) return `${item.target_sets} 组`
  if (item.target_duration_min != null) return `${item.target_duration_min} 分钟`
  return '—'
}

function isStrength(exerciseId: number) {
  return exerciseCategory(exerciseId) === 'STRENGTH'
}

function isDayExpanded(weekday: number) {
  return expandedWeekdays.value.includes(weekday)
}

function toggleDayDetails(weekday: number) {
  if (isDayExpanded(weekday)) {
    expandedWeekdays.value = expandedWeekdays.value.filter((item) => item !== weekday)
  } else {
    expandedWeekdays.value = [...expandedWeekdays.value, weekday]
  }
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [planData, exerciseData] = await Promise.all([listPlans(), listExercises()])
    plans.value = planData.items
    exercises.value = exerciseData.items
    if (!form.exercise_id && exercises.value[0]) {
      form.exercise_id = exercises.value[0].id
      overrideExerciseId.value = exercises.value[0].id
    }
    if (editingPlanId.value != null && !plans.value.some((item) => item.id === editingPlanId.value)) {
      editingPlanId.value = activePlan.value?.id ?? null
    }
    if (editingPlanId.value == null && activePlan.value) {
      editingPlanId.value = activePlan.value.id
    }
    const bounds = monthBounds(`${month.value}-01`)
    const end = bounds.to > addDays(businessToday(), 30) ? addDays(businessToday(), 30) : bounds.to
    const start = bounds.from
    if (start <= end) {
      const data = await getSchedule(start, end)
      schedule.value = data.items
    }
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '加载计划失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void reload()
})

function openDayEditor(day: PlanDay) {
  if (!editingPlan.value) return
  drawerWeekday.value = day.weekday
  drawerTitle.value = day.title
  drawerIsRest.value = day.is_rest
  drawerRows.value = day.is_rest
    ? []
    : day.exercises.map((item) => ({
        key: editorKeySeq++,
        exercise_id: item.exercise_id,
        sets: setsFromPlanExercise(item),
      }))
  if (!drawerIsRest.value && !drawerRows.value.length) {
    const exerciseId = exercises.value[0]?.id ?? 0
    drawerRows.value = [
      {
        key: editorKeySeq++,
        exercise_id: exerciseId,
        sets: exerciseTargetSets(exerciseId),
      },
    ]
  }
  drawerOpen.value = true
}

function closeDrawer() {
  drawerOpen.value = false
}

function addDrawerRow() {
  const exerciseId = exercises.value[0]?.id ?? 0
  drawerRows.value.push({
    key: editorKeySeq++,
    exercise_id: exerciseId,
    sets: exerciseTargetSets(exerciseId),
  })
}

function removeDrawerRow(key: number) {
  if (drawerRows.value.length <= 1) return
  drawerRows.value = drawerRows.value.filter((row) => row.key !== key)
}

function onDrawerExerciseChange(row: EditorRow) {
  row.sets = exerciseTargetSets(row.exercise_id)
}

function addDrawerSet(row: EditorRow) {
  const last = row.sets[row.sets.length - 1]
  row.sets.push(last ? cloneSet(last) : emptySet())
}

function removeDrawerSet(row: EditorRow, index: number) {
  if (row.sets.length <= 1) return
  row.sets.splice(index, 1)
}

function moveDrawerRow(key: number, delta: number) {
  const index = drawerRows.value.findIndex((row) => row.key === key)
  if (index < 0) return
  const next = index + delta
  if (next < 0 || next >= drawerRows.value.length) return
  const copy = [...drawerRows.value]
  const [row] = copy.splice(index, 1)
  copy.splice(next, 0, row)
  drawerRows.value = copy
}

function onToggleRest(checked: boolean) {
  drawerIsRest.value = checked
  if (checked) {
    drawerRows.value = []
  } else if (!drawerRows.value.length) {
    addDrawerRow()
  }
}

function buildExercisePayload(rows: EditorRow[]): PlanExercise[] {
  return rows
    .filter((row) => row.exercise_id)
    .map((row, index) => ({
      exercise_id: row.exercise_id,
      sort_order: index + 1,
      sets: (row.sets.length ? row.sets : [emptySet()]).map((set) => ({
        reps: set.reps,
        weight_kg: set.weight_kg,
        duration_min: set.duration_min,
        distance_km: set.distance_km,
      })),
    }))
}

async function saveDayEditor() {
  const plan = editingPlan.value
  if (!plan) return
  if (!drawerTitle.value.trim()) {
    ElMessage.warning('请填写训练日标题')
    return
  }
  if (!drawerIsRest.value) {
    const rows = drawerRows.value.filter((row) => row.exercise_id)
    if (!rows.length) {
      ElMessage.warning('训练日至少包含一个动作')
      return
    }
    for (const row of rows) {
      if (!row.sets.length) {
        ElMessage.warning('每个动作至少 1 组')
        return
      }
    }
  }

  const nextDays: PlanDay[] = plan.days.map((day) => {
    if (day.weekday !== drawerWeekday.value) return day
    return {
      weekday: day.weekday,
      title: drawerTitle.value.trim(),
      is_rest: drawerIsRest.value,
      exercises: drawerIsRest.value ? [] : buildExercisePayload(drawerRows.value),
    }
  })

  drawerSaving.value = true
  try {
    await updatePlan(plan.id, { days: nextDays })
    ElMessage.success('训练日已保存')
    drawerOpen.value = false
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '保存失败')
  } finally {
    drawerSaving.value = false
  }
}

async function onCreate() {
  if (!form.name.trim() || !form.exercise_id || selectedWeekdays.value.length === 0) {
    ElMessage.warning('请填写计划名称、训练日和动作')
    return
  }
  try {
    const exercise: PlanExercise = {
      exercise_id: form.exercise_id,
      sort_order: 1,
      sets: exerciseTargetSets(form.exercise_id),
    }
    const created = await createPlan({
      name: form.name.trim(),
      start_date: form.start_date,
      days: selectedWeekdays.value.map((weekday) => ({
        weekday: Number(weekday),
        title: form.title,
        is_rest: false,
        exercises: [exercise],
      })),
    })
    form.name = ''
    editingPlanId.value = created.id
    view.value = 'week'
    ElMessage.success('计划已创建，可在周循环中编辑各训练日与组')
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '创建失败')
  }
}

async function onActivate(plan: PlanItem) {
  try {
    await activatePlan(plan.id)
    editingPlanId.value = plan.id
    ElMessage.success('计划已启用')
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '启用失败')
  }
}

async function onDeactivate(plan: PlanItem) {
  try {
    await deactivatePlan(plan.id)
    ElMessage.success('计划已停用，历史任务保留')
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '停用失败')
  }
}

async function onDuplicate(plan: PlanItem) {
  try {
    const copied = await duplicatePlan(plan.id)
    editingPlanId.value = copied.id
    view.value = 'week'
    ElMessage.success('已复制为草稿，可编辑周模板')
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '复制失败')
  }
}

function openPlanTemplate(plan: PlanItem) {
  editingPlanId.value = plan.id
  view.value = 'week'
}

async function onSaveOverride() {
  try {
    const payload =
      overrideMode.value === 'REST' || overrideExerciseId.value == null
        ? []
        : [
            {
              exercise_id: overrideExerciseId.value,
              sort_order: 1,
              sets: exerciseTargetSets(overrideExerciseId.value),
            },
          ]
    await putOverride(selectedDate.value, {
      mode: overrideMode.value,
      title: overrideTitle.value,
      exercises: payload,
    })
    ElMessage.success('日期覆盖已保存，仅影响这一天')
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '保存覆盖失败')
  }
}

async function onClearOverride() {
  try {
    await deleteOverride(selectedDate.value)
    ElMessage.success('已撤销该日期覆盖')
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '撤销失败')
  }
}
</script>

<template>
  <div class="page-stack plans-page">
    <p v-if="loading">正在加载计划…</p>
    <p v-if="error" class="error-text">{{ error }} <button type="button" @click="reload">重试</button></p>

    <section class="panel">
      <h2>{{ editingPlan ? editingPlan.name : '还没有可编辑的计划' }}</h2>
      <p class="muted">
        <template v-if="editingPlan">
          生效 {{ editingPlan.start_date }} · {{ editingPlan.status }}
          <span v-if="activePlan && editingPlan.id !== activePlan.id">（当前启用：{{ activePlan.name }}）</span>
        </template>
        <template v-else>创建你的第一份每周计划。</template>
      </p>
      <div class="row">
        <button type="button" :class="{ active: view === 'week' }" @click="view = 'week'">周循环</button>
        <button type="button" :class="{ active: view === 'calendar' }" @click="view = 'calendar'">月历</button>
      </div>
    </section>

    <section v-if="view === 'week'" class="panel">
      <h2>每周模板</h2>
      <table v-if="editingPlan" class="week-table">
        <thead>
          <tr><th>星期</th><th>主题</th><th>动作数</th><th>休息</th><th></th></tr>
        </thead>
        <tbody>
          <template v-for="day in editingPlan.days" :key="day.weekday">
            <tr>
              <td>周{{ weekLabels[day.weekday - 1] }}</td>
              <td>{{ day.title }}</td>
              <td>{{ day.is_rest ? 0 : day.exercises.length }}</td>
              <td>{{ day.is_rest ? '是' : '否' }}</td>
              <td class="row week-actions">
                <button type="button" class="ghost" @click="toggleDayDetails(day.weekday)">
                  {{ isDayExpanded(day.weekday) ? '收起详情' : '展开详情' }}
                </button>
                <button type="button" class="ghost" @click="openDayEditor(day)">编辑</button>
              </td>
            </tr>
            <tr v-if="isDayExpanded(day.weekday)" class="detail-row">
              <td colspan="5">
                <div v-if="day.is_rest" class="muted">休息日，无动作。</div>
                <table v-else-if="day.exercises.length" class="detail-table">
                  <thead>
                    <tr><th>动作</th><th>类型</th><th>分组目标</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in day.exercises" :key="`${day.weekday}-${item.sort_order}-${item.exercise_id}`">
                      <td>{{ exerciseName(item.exercise_id) }}</td>
                      <td>{{ exerciseCategory(item.exercise_id) }}</td>
                      <td>{{ capacityText(item) }}</td>
                    </tr>
                  </tbody>
                </table>
                <div v-else class="muted">暂无动作，可点编辑添加。</div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <p v-else class="muted">创建或从下方计划列表选择「编辑模板」。</p>
    </section>

    <section v-else class="panel">
      <div class="row">
        <label>月份 <input v-model="month" type="month" @change="reload" /></label>
      </div>
      <div class="calendar">
        <button
          v-for="day in monthDays"
          :key="day"
          type="button"
          class="day"
          :class="{ selected: day === selectedDate }"
          @click="selectedDate = day"
        >
          <strong>{{ day.slice(8) }}</strong>
          <span>{{ tasksOn(day).length ? `${tasksOn(day).length} 项` : '休息' }}</span>
        </button>
      </div>
      <div class="override">
        <h3>{{ selectedDate }} · 周{{ weekLabels[weekdayOf(selectedDate) - 1] }}</h3>
        <p class="muted">覆盖仅此日期，不改变每周模板。</p>
        <ul>
          <li v-for="task in tasksOn(selectedDate)" :key="task.occurrence_id">
            {{ task.slot }} · {{ task.title }} · {{ task.actions_count }} 个动作 · {{ task.record_status || '未记录' }}
          </li>
        </ul>
        <div class="row">
          <select v-model="overrideMode">
            <option value="REST">设为休息</option>
            <option value="REPLACE">替换</option>
            <option value="ADD">追加</option>
          </select>
          <input v-model="overrideTitle" placeholder="临时标题" />
          <select v-if="overrideMode !== 'REST'" v-model.number="overrideExerciseId">
            <option v-for="item in exercises" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
          <button type="button" @click="onSaveOverride">保存覆盖</button>
          <button type="button" class="ghost" @click="onClearOverride">撤销覆盖</button>
        </div>
      </div>
    </section>

    <section class="panel">
      <h2>新建计划</h2>
      <div class="row">
        <input v-model="form.name" placeholder="计划名称" />
        <input v-model="form.start_date" type="date" />
        <label v-for="(label, index) in weekLabels" :key="label" class="check">
          <input v-model="selectedWeekdays" type="checkbox" :value="index + 1" />周{{ label }}
        </label>
        <input v-model="form.title" placeholder="训练主题" />
        <select v-model.number="form.exercise_id">
          <option v-for="item in exercises" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <button type="button" @click="onCreate">创建</button>
      </div>
      <p class="muted">创建后可在周循环里逐日编辑多动作与每组次数/重量。</p>
    </section>

    <section class="panel">
      <h2>全部计划</h2>
      <table v-if="plans.length">
        <thead>
          <tr><th>名称</th><th>状态</th><th>开始</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="plan in plans" :key="plan.id">
            <td>{{ plan.name }}</td>
            <td>{{ plan.status }}</td>
            <td>{{ plan.start_date }}</td>
            <td class="row">
              <button type="button" class="ghost" @click="openPlanTemplate(plan)">编辑模板</button>
              <button v-if="plan.status !== 'ACTIVE'" type="button" @click="onActivate(plan)">启用</button>
              <button v-else type="button" class="ghost" @click="onDeactivate(plan)">停用</button>
              <button type="button" class="ghost" @click="onDuplicate(plan)">复制</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">创建你的第一份每周计划。</p>
    </section>

    <div v-if="drawerOpen" class="drawer-mask" @click.self="closeDrawer">
      <aside class="plan-drawer" role="dialog" aria-label="编辑训练日">
        <div class="drawer-header">
          <h2>编辑 · 周{{ weekLabels[drawerWeekday - 1] }}</h2>
          <button type="button" class="ghost" @click="closeDrawer">关闭</button>
        </div>
        <label>
          训练日标题
          <input v-model="drawerTitle" maxlength="100" />
        </label>
        <label class="check">
          <input
            type="checkbox"
            :checked="drawerIsRest"
            @change="onToggleRest(($event.target as HTMLInputElement).checked)"
          />
          设为休息日
        </label>

        <template v-if="!drawerIsRest">
          <h3>动作与分组</h3>
          <div v-for="row in drawerRows" :key="row.key" class="drawer-exercise">
            <div class="row">
              <select v-model.number="row.exercise_id" @change="onDrawerExerciseChange(row)">
                <option v-for="item in exercises" :key="item.id" :value="item.id">{{ item.name }}</option>
              </select>
              <button type="button" class="ghost" @click="moveDrawerRow(row.key, -1)">上移</button>
              <button type="button" class="ghost" @click="moveDrawerRow(row.key, 1)">下移</button>
              <button
                type="button"
                class="ghost"
                :disabled="drawerRows.length <= 1"
                @click="removeDrawerRow(row.key)"
              >
                删除动作
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>组</th>
                  <th v-if="isStrength(row.exercise_id)">次数</th>
                  <th v-if="isStrength(row.exercise_id)">重量(kg)</th>
                  <th v-if="!isStrength(row.exercise_id)">时长(分)</th>
                  <th v-if="!isStrength(row.exercise_id)">距离(km)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(set, setIndex) in row.sets" :key="`${row.key}-${setIndex}`">
                  <td>{{ setIndex + 1 }}</td>
                  <td v-if="isStrength(row.exercise_id)">
                    <input v-model.number="set.reps" type="number" min="0" step="1" />
                  </td>
                  <td v-if="isStrength(row.exercise_id)">
                    <input v-model.number="set.weight_kg" type="number" min="0" step="0.5" />
                  </td>
                  <td v-if="!isStrength(row.exercise_id)">
                    <input v-model.number="set.duration_min" type="number" min="0" step="1" />
                  </td>
                  <td v-if="!isStrength(row.exercise_id)">
                    <input v-model.number="set.distance_km" type="number" min="0" step="0.1" />
                  </td>
                  <td>
                    <button
                      type="button"
                      class="ghost"
                      :disabled="row.sets.length <= 1"
                      @click="removeDrawerSet(row, setIndex)"
                    >
                      删组
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <button type="button" class="ghost" @click="addDrawerSet(row)">添加组</button>
          </div>
          <button type="button" class="ghost" @click="addDrawerRow">添加动作</button>
        </template>
        <p v-else class="muted">休息日不生成训练任务。</p>

        <div class="drawer-actions">
          <button type="button" :disabled="drawerSaving" @click="saveDayEditor">保存</button>
          <button type="button" class="ghost" @click="closeDrawer">取消</button>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.calendar {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}
.day {
  text-align: left;
  background: var(--surface-alt);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.day:hover {
  border-color: var(--border-strong);
}
.day.selected {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.day span { display: block; color: var(--text-muted); font-size: 0.8rem; }
.check { display: inline-flex; gap: 4px; align-items: center; }
.week-actions { justify-content: flex-end; }
.week-table th,
.week-table td {
  vertical-align: middle;
  padding: 12px 8px;
}
.detail-row td {
  background: var(--surface-alt);
  border-bottom: 1px solid var(--border);
}
.detail-table {
  width: 100%;
  margin: 0;
}
.detail-table th,
.detail-table td {
  padding: 10px 8px;
}

.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: var(--el-mask-color);
  display: flex;
  justify-content: flex-end;
}
.plan-drawer {
  width: min(560px, 100%);
  height: 100%;
  overflow: auto;
  background: var(--surface);
  color: var(--text);
  border-left: 1px solid var(--border);
  box-shadow: var(--shadow);
  padding: 24px;
  display: grid;
  gap: 16px;
  align-content: start;
}
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.drawer-header h2 { margin: 0; }
.plan-drawer label {
  display: grid;
  gap: 6px;
  color: var(--text-muted);
  font-size: 0.9rem;
}
.plan-drawer table th,
.plan-drawer table td {
  vertical-align: middle;
  padding: 12px 8px;
}
.plan-drawer select,
.plan-drawer input:not([type='checkbox']) {
  width: 100%;
  min-width: 0;
  height: var(--control-height);
  box-sizing: border-box;
}
.drawer-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.drawer-exercise {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  display: grid;
  gap: 10px;
  background: var(--surface-alt);
}
</style>
