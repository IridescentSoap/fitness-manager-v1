<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiError } from '@/api/client'
import { listExercises } from '@/api/exercises'
import { getSchedule, type ScheduleItem } from '@/api/plans'
import {
  appendExercises,
  createDraft,
  deleteRecord,
  listRecords,
  patchAction,
  reopenRecord,
  submitRecord,
  type RecordExercise,
  type WorkoutRecord,
} from '@/api/records'
import type { ExerciseItem } from '@/types/auth'
import { addDays, businessToday } from '@/utils/date'
import {
  cloneSet,
  defaultSetsForCategory,
  emptySet,
  type SetDraft,
} from '@/utils/sets'

interface AdhocRow {
  key: number
  exercise_id: number
  sets: SetDraft[]
}

interface WorkoutSetView extends SetDraft {
  set_index: number
  completed?: boolean
}

const route = useRoute()

function initialDate() {
  const query = route.query.date
  if (query === 'today' || query == null || query === '') return businessToday()
  return typeof query === 'string' ? query : businessToday()
}

const date = ref(initialDate())
const tasks = ref<ScheduleItem[]>([])
const history = ref<WorkoutRecord[]>([])
const current = ref<WorkoutRecord | null>(null)
const composingAdhoc = ref(false)
const exercises = ref<ExerciseItem[]>([])
const saveState = ref('尚未修改')
const loading = ref(false)
const error = ref('')
const adhocTitle = ref('自由训练')
let adhocKeySeq = 1
const adhocRows = ref<AdhocRow[]>([])
const showAddAction = ref(false)
const addExerciseId = ref(0)
const expandedActions = ref<number[]>([])

const progress = computed(() => {
  if (!current.value || current.value.total_count === 0) return 0
  return Math.round((current.value.completed_count / current.value.total_count) * 100)
})

const selectedExerciseName = (id: number) =>
  exercises.value.find((item) => item.id === id)?.name ?? '—'

const selectedExerciseCategory = (id: number) =>
  exercises.value.find((item) => item.id === id)?.category ?? 'STRENGTH'

function defaultSets(exerciseId: number) {
  return defaultSetsForCategory(selectedExerciseCategory(exerciseId))
}

function resetAdhocRows() {
  const firstId = exercises.value[0]?.id ?? 0
  adhocRows.value = [{ key: adhocKeySeq++, exercise_id: firstId, sets: defaultSets(firstId) }]
}

function ensureAdhocDefaults() {
  const firstId = exercises.value[0]?.id ?? 0
  if (!adhocRows.value.length) {
    adhocRows.value = [{ key: adhocKeySeq++, exercise_id: firstId, sets: defaultSets(firstId) }]
    return
  }
  for (const row of adhocRows.value) {
    if (!row.exercise_id && firstId) {
      row.exercise_id = firstId
      row.sets = defaultSets(firstId)
    }
    if (!row.sets?.length) row.sets = defaultSets(row.exercise_id)
  }
  if (!addExerciseId.value && firstId) addExerciseId.value = firstId
}

function openAddActionForm() {
  showAddAction.value = true
  if (!addExerciseId.value) addExerciseId.value = exercises.value[0]?.id ?? 0
}

function cancelAddActionForm() {
  showAddAction.value = false
}

function actionSets(action: RecordExercise): WorkoutSetView[] {
  const raw = action.target?.sets
  if (Array.isArray(raw) && raw.length) {
    return raw.map((item, index) => {
      const row = item as WorkoutSetView
      return {
        set_index: Number(row.set_index ?? index + 1),
        reps: (row.reps as number | null) ?? null,
        weight_kg: (row.weight_kg as number | null) ?? null,
        duration_min: (row.duration_min as number | null) ?? null,
        distance_km: (row.distance_km as number | null) ?? null,
        completed: Boolean(row.completed),
      }
    })
  }
  return [{ set_index: 1, ...emptySet(), completed: action.completed }]
}

function isExpanded(actionId: number) {
  return expandedActions.value.includes(actionId)
}

function toggleExpanded(actionId: number) {
  if (isExpanded(actionId)) {
    expandedActions.value = expandedActions.value.filter((id) => id !== actionId)
  } else {
    expandedActions.value = [...expandedActions.value, actionId]
  }
}

function isStrengthAction(action: RecordExercise) {
  return action.category === 'STRENGTH'
}

async function confirmAddAction() {
  if (!current.value || current.value.status !== 'DRAFT') return
  if (!addExerciseId.value) {
    ElMessage.warning('请选择动作')
    return
  }
  addingAction.value = true
  try {
    current.value = await appendExercises(current.value.id, current.value.version, [
      {
        exercise_id: addExerciseId.value,
        sort_order: current.value.exercises.length + 1,
        sets: defaultSets(addExerciseId.value),
      },
    ])
    const newest = current.value.exercises[current.value.exercises.length - 1]
    if (newest) expandedActions.value = [...expandedActions.value, newest.id]
    saveState.value = '已添加动作'
    showAddAction.value = false
    ElMessage.success('已添加动作')
    await load()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '添加失败')
  } finally {
    addingAction.value = false
  }
}

const addingAction = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const schedule = await getSchedule(date.value, date.value)
    tasks.value = schedule.items
    const records = await listRecords(addDays(date.value, -14), date.value, 1, 50)
    history.value = records.items
    const exerciseData = await listExercises()
    exercises.value = exerciseData.items
    ensureAdhocDefaults()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '加载记录失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})

watch(date, () => {
  current.value = null
  composingAdhoc.value = false
  void load()
})

function startAdhocCompose() {
  current.value = null
  composingAdhoc.value = true
  adhocTitle.value = '自由训练'
  resetAdhocRows()
  saveState.value = '编辑自主训练'
}

function cancelAdhocCompose() {
  composingAdhoc.value = false
  resetAdhocRows()
}

async function openTask(task: ScheduleItem) {
  composingAdhoc.value = false
  showAddAction.value = false
  try {
    current.value = await createDraft({ occurrence_id: task.occurrence_id })
    expandedActions.value = current.value.exercises.map((item) => item.id)
    saveState.value = current.value.status === 'DRAFT' ? '草稿已打开' : '已提交'
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '无法打开任务')
  }
}

function openHistory(record: WorkoutRecord) {
  composingAdhoc.value = false
  showAddAction.value = false
  current.value = record
  expandedActions.value = record.exercises.map((item) => item.id)
  saveState.value = record.status === 'DRAFT' ? '草稿' : '已提交'
}

async function onToggle(actionId: number, completed: boolean) {
  if (!current.value) return
  saveState.value = '正在保存...'
  try {
    const saved = await patchAction(current.value.id, actionId, current.value.version, { completed })
    current.value = saved.record
    saveState.value = '已保存'
  } catch (err) {
    saveState.value = err instanceof ApiError && err.code === 'VERSION_CONFLICT' ? '该记录已在其他设备更新' : '保存失败'
    ElMessage.error(saveState.value)
  }
}

async function onToggleSet(actionId: number, setIndex: number, completed: boolean) {
  if (!current.value || current.value.status !== 'DRAFT') return
  saveState.value = '正在保存...'
  try {
    const saved = await patchAction(current.value.id, actionId, current.value.version, {
      set_index: setIndex,
      set_completed: completed,
    })
    current.value = saved.record
    saveState.value = '已保存'
  } catch (err) {
    saveState.value = err instanceof ApiError && err.code === 'VERSION_CONFLICT' ? '该记录已在其他设备更新' : '保存失败'
    ElMessage.error(saveState.value)
  }
}

async function onEditExercise(actionId: number, exerciseId: number) {
  if (!current.value || current.value.status !== 'DRAFT') return
  const action = current.value.exercises.find((item) => item.id === actionId)
  if (!action || action.exercise_id === exerciseId) return
  saveState.value = '正在保存...'
  try {
    const saved = await patchAction(current.value.id, actionId, current.value.version, {
      exercise_id: exerciseId,
      sets: defaultSets(exerciseId),
    })
    current.value = saved.record
    saveState.value = '已保存'
  } catch (err) {
    saveState.value = err instanceof ApiError && err.code === 'VERSION_CONFLICT' ? '该记录已在其他设备更新' : '保存失败'
    ElMessage.error(saveState.value)
  }
}

async function onEditSetField(
  actionId: number,
  setIndex: number,
  patch: { reps?: number | null; weight_kg?: number | null; duration_min?: number | null; distance_km?: number | null },
) {
  if (!current.value || current.value.status !== 'DRAFT') return
  saveState.value = '正在保存...'
  try {
    const saved = await patchAction(current.value.id, actionId, current.value.version, {
      set_index: setIndex,
      ...patch,
    })
    current.value = saved.record
    saveState.value = '已保存'
  } catch (err) {
    saveState.value = err instanceof ApiError && err.code === 'VERSION_CONFLICT' ? '该记录已在其他设备更新' : '保存失败'
    ElMessage.error(saveState.value)
  }
}

async function onReplaceSets(actionId: number, sets: SetDraft[]) {
  if (!current.value || current.value.status !== 'DRAFT') return
  saveState.value = '正在保存...'
  try {
    const saved = await patchAction(current.value.id, actionId, current.value.version, {
      sets: sets.map((set) => ({
        reps: set.reps,
        weight_kg: set.weight_kg,
        duration_min: set.duration_min,
        distance_km: set.distance_km,
      })),
    })
    current.value = saved.record
    saveState.value = '已保存'
  } catch (err) {
    saveState.value = err instanceof ApiError && err.code === 'VERSION_CONFLICT' ? '该记录已在其他设备更新' : '保存失败'
    ElMessage.error(saveState.value)
  }
}

function addSet(action: RecordExercise) {
  const sets = actionSets(action)
  const last = sets[sets.length - 1]
  const next = [...sets.map((set) => cloneSet(set)), last ? cloneSet(last) : emptySet()]
  void onReplaceSets(action.id, next)
}

function removeSet(action: RecordExercise, setIndex: number) {
  const sets = actionSets(action)
  if (sets.length <= 1) return
  const next = sets.filter((set) => set.set_index !== setIndex).map((set) => cloneSet(set))
  void onReplaceSets(action.id, next)
}

async function onSubmit() {
  if (!current.value) return
  if (current.value.completed_count === 0) {
    try {
      await ElMessageBox.confirm('确认提交未完成记录？', '提交记录', { type: 'warning' })
    } catch {
      return
    }
  }
  try {
    const result = await submitRecord(current.value.id, current.value.version)
    ElMessage.success(`已提交：${result.completion_result}`)
    current.value = {
      ...current.value,
      status: result.status,
      version: result.version,
      completion_result: result.completion_result,
      submitted_at: result.submitted_at,
      completed_count: result.completed_count,
      total_count: result.total_count,
    }
    saveState.value = '已提交'
    await load()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '提交失败')
  }
}

async function onReopen() {
  if (!current.value) return
  try {
    await ElMessageBox.confirm('撤回为草稿后，统计会暂时排除这条记录，直到重新提交。', '编辑历史')
  } catch {
    return
  }
  try {
    current.value = await reopenRecord(current.value.id, current.value.version)
    saveState.value = '重新编辑中'
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '无法重新编辑')
  }
}

async function onDelete() {
  if (!current.value) return
  try {
    await ElMessageBox.confirm('软删除后该记录不再计入统计，计划任务仍视为未完成。', '删除记录', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteRecord(current.value.id)
    current.value = null
    ElMessage.success('已删除')
    await load()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '删除失败')
  }
}

function addAdhocRow() {
  const firstId = exercises.value[0]?.id ?? 0
  adhocRows.value.push({ key: adhocKeySeq++, exercise_id: firstId, sets: defaultSets(firstId) })
}

function removeAdhocRow(key: number) {
  if (adhocRows.value.length <= 1) return
  adhocRows.value = adhocRows.value.filter((row) => row.key !== key)
}

function onAdhocExerciseChange(row: AdhocRow) {
  row.sets = defaultSets(row.exercise_id)
}

function addAdhocSet(row: AdhocRow) {
  const last = row.sets[row.sets.length - 1]
  row.sets.push(last ? cloneSet(last) : emptySet())
}

function removeAdhocSet(row: AdhocRow, index: number) {
  if (row.sets.length <= 1) return
  row.sets.splice(index, 1)
}

async function onAdhoc() {
  const rows = adhocRows.value.filter((row) => row.exercise_id)
  if (!rows.length) {
    ElMessage.warning('请至少选择一个动作')
    return
  }
  try {
    current.value = await createDraft({
      workout_date: date.value,
      title: adhocTitle.value || '自由训练',
      exercises: rows.map((row, index) => ({
        exercise_id: row.exercise_id,
        sort_order: index + 1,
        sets: row.sets,
      })),
    })
    composingAdhoc.value = false
    expandedActions.value = current.value.exercises.map((item) => item.id)
    saveState.value = '自主训练草稿已创建'
    resetAdhocRows()
    await load()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '创建失败')
  }
}

function parseNum(value: string): number | null {
  if (value.trim() === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}
</script>

<template>
  <div class="records">
    <aside class="panel">
      <label>训练日期 <input v-model="date" type="date" /></label>
      <p v-if="loading">正在加载…</p>
      <p v-if="error" class="error-text">{{ error }} <button type="button" @click="load">重试</button></p>
      <h2>当天任务</h2>
      <button v-for="task in tasks" :key="task.occurrence_id" type="button" class="block" @click="openTask(task)">
        {{ task.slot }} · {{ task.title }} · {{ task.record_status || '未开始' }}
      </button>
      <p v-if="!tasks.length" class="muted">这一天没有计划任务，可以添加自主训练。</p>
      <h2>近 14 天</h2>
      <button v-for="item in history" :key="item.id" type="button" class="block ghost" @click="openHistory(item)">
        {{ item.workout_date }} {{ item.title }} · {{ item.status === 'DRAFT' ? '草稿' : item.completion_result }}
      </button>
      <h2>自主训练</h2>
      <button type="button" class="block" @click="startAdhocCompose">新建自主训练</button>
    </aside>

    <section v-if="composingAdhoc" class="panel">
      <h2>新建自主训练</h2>
      <p class="muted">{{ date }} · 自主训练 · 为每个动作配置多组后再创建草稿</p>
      <label>标题 <input v-model="adhocTitle" placeholder="标题" /></label>
      <div v-for="row in adhocRows" :key="row.key" class="exercise-block">
        <div class="row">
          <select v-model.number="row.exercise_id" @change="onAdhocExerciseChange(row)">
            <option v-for="item in exercises" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
          <span class="muted">{{ selectedExerciseCategory(row.exercise_id) }}</span>
          <button type="button" class="ghost" :disabled="adhocRows.length <= 1" @click="removeAdhocRow(row.key)">
            删除动作
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>组</th>
              <th v-if="selectedExerciseCategory(row.exercise_id) === 'STRENGTH'">次数</th>
              <th v-if="selectedExerciseCategory(row.exercise_id) === 'STRENGTH'">重量(kg)</th>
              <th v-if="selectedExerciseCategory(row.exercise_id) !== 'STRENGTH'">时长(分)</th>
              <th v-if="selectedExerciseCategory(row.exercise_id) !== 'STRENGTH'">距离(km)</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(set, index) in row.sets" :key="`${row.key}-${index}`">
              <td>{{ index + 1 }}</td>
              <td v-if="selectedExerciseCategory(row.exercise_id) === 'STRENGTH'">
                <input v-model.number="set.reps" type="number" min="0" step="1" />
              </td>
              <td v-if="selectedExerciseCategory(row.exercise_id) === 'STRENGTH'">
                <input v-model.number="set.weight_kg" type="number" min="0" step="0.5" />
              </td>
              <td v-if="selectedExerciseCategory(row.exercise_id) !== 'STRENGTH'">
                <input v-model.number="set.duration_min" type="number" min="0" step="1" />
              </td>
              <td v-if="selectedExerciseCategory(row.exercise_id) !== 'STRENGTH'">
                <input v-model.number="set.distance_km" type="number" min="0" step="0.1" />
              </td>
              <td>
                <button type="button" class="ghost" :disabled="row.sets.length <= 1" @click="removeAdhocSet(row, index)">
                  删组
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <button type="button" class="ghost" @click="addAdhocSet(row)">添加组</button>
      </div>
      <div class="submit-bar">
        <button type="button" class="ghost" @click="addAdhocRow">添加动作</button>
        <button type="button" @click="onAdhoc">创建草稿</button>
        <button type="button" class="ghost" @click="cancelAdhocCompose">取消</button>
      </div>
      <p class="muted preview-hint">预览：{{ adhocRows.map((row) => selectedExerciseName(row.exercise_id)).join('、') }}</p>
    </section>

    <section class="panel" v-else-if="current">
      <div class="panel-header">
        <div>
          <h2>{{ current.title }}</h2>
          <p class="muted">
            {{ current.workout_date }} · {{ current.origin === 'AD_HOC' ? '自主训练' : '计划任务' }} · {{ saveState }}
          </p>
          <p v-if="current.status === 'DRAFT'" class="muted">勾选组或改数值会自动保存草稿；动作勾选=该动作全部组。</p>
        </div>
        <button
          v-if="current.status === 'DRAFT' && !showAddAction"
          type="button"
          class="ghost header-add"
          @click="openAddActionForm"
        >
          添加动作
        </button>
      </div>
      <div v-if="current.status === 'DRAFT' && showAddAction" class="add-action-form">
        <select v-model.number="addExerciseId">
          <option v-for="item in exercises" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <button type="button" :disabled="addingAction" @click="confirmAddAction">确认添加</button>
        <button type="button" class="ghost" @click="cancelAddActionForm">取消</button>
      </div>

      <div v-for="action in current.exercises" :key="action.id" class="exercise-block">
        <div class="row action-head">
          <label class="done-label">
            <input
              class="done-check"
              type="checkbox"
              :checked="action.completed"
              :disabled="current.status !== 'DRAFT'"
              @change="onToggle(action.id, ($event.target as HTMLInputElement).checked)"
            />
            <span>{{ action.completed ? '全部完成' : '未完成' }}</span>
          </label>
          <select
            v-if="current.status === 'DRAFT'"
            :value="action.exercise_id ?? 0"
            @change="onEditExercise(action.id, Number(($event.target as HTMLSelectElement).value))"
          >
            <option v-for="item in exercises" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
          <strong v-else>{{ action.name }}</strong>
          <span class="muted">{{ action.category }}</span>
          <button type="button" class="ghost" @click="toggleExpanded(action.id)">
            {{ isExpanded(action.id) ? '收起组' : `展开组(${actionSets(action).length})` }}
          </button>
        </div>

        <table v-if="isExpanded(action.id)">
          <thead>
            <tr>
              <th>完成</th>
              <th>组</th>
              <th v-if="isStrengthAction(action)">次数</th>
              <th v-if="isStrengthAction(action)">重量(kg)</th>
              <th v-if="!isStrengthAction(action)">时长(分)</th>
              <th v-if="!isStrengthAction(action)">距离(km)</th>
              <th v-if="current.status === 'DRAFT'"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="set in actionSets(action)" :key="`${action.id}-${set.set_index}`">
              <td>
                <input
                  class="done-check"
                  type="checkbox"
                  :checked="Boolean(set.completed)"
                  :disabled="current.status !== 'DRAFT'"
                  @change="onToggleSet(action.id, set.set_index, ($event.target as HTMLInputElement).checked)"
                />
              </td>
              <td>{{ set.set_index }}</td>
              <td v-if="isStrengthAction(action)">
                <input
                  v-if="current.status === 'DRAFT'"
                  type="number"
                  min="0"
                  step="1"
                  :value="set.reps ?? ''"
                  @change="onEditSetField(action.id, set.set_index, { reps: parseNum(($event.target as HTMLInputElement).value) })"
                />
                <span v-else>{{ set.reps ?? '—' }}</span>
              </td>
              <td v-if="isStrengthAction(action)">
                <input
                  v-if="current.status === 'DRAFT'"
                  type="number"
                  min="0"
                  step="0.5"
                  :value="set.weight_kg ?? ''"
                  @change="onEditSetField(action.id, set.set_index, { weight_kg: parseNum(($event.target as HTMLInputElement).value) })"
                />
                <span v-else>{{ set.weight_kg ?? '—' }}</span>
              </td>
              <td v-if="!isStrengthAction(action)">
                <input
                  v-if="current.status === 'DRAFT'"
                  type="number"
                  min="0"
                  step="1"
                  :value="set.duration_min ?? ''"
                  @change="onEditSetField(action.id, set.set_index, { duration_min: parseNum(($event.target as HTMLInputElement).value) })"
                />
                <span v-else>{{ set.duration_min ?? '—' }}</span>
              </td>
              <td v-if="!isStrengthAction(action)">
                <input
                  v-if="current.status === 'DRAFT'"
                  type="number"
                  min="0"
                  step="0.1"
                  :value="set.distance_km ?? ''"
                  @change="onEditSetField(action.id, set.set_index, { distance_km: parseNum(($event.target as HTMLInputElement).value) })"
                />
                <span v-else>{{ set.distance_km ?? '—' }}</span>
              </td>
              <td v-if="current.status === 'DRAFT'">
                <button
                  type="button"
                  class="ghost"
                  :disabled="actionSets(action).length <= 1"
                  @click="removeSet(action, set.set_index)"
                >
                  删组
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <button
          v-if="current.status === 'DRAFT' && isExpanded(action.id)"
          type="button"
          class="ghost"
          @click="addSet(action)"
        >
          添加组
        </button>
      </div>

      <div class="submit-bar">
        <span>完成组 {{ current.completed_count }}/{{ current.total_count }}</span>
        <progress :value="progress" max="100" />
        <button v-if="current.status === 'DRAFT'" type="button" @click="onSubmit">提交记录</button>
        <button v-else type="button" @click="onReopen">编辑历史</button>
        <button type="button" class="ghost" @click="onDelete">删除</button>
      </div>
    </section>
    <section v-else class="panel">
      <h2>选择一条任务</h2>
      <p class="muted">从左侧打开计划任务，或点「新建自主训练」在此添加多项动作。</p>
    </section>
  </div>
</template>

<style scoped>
.records {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: var(--row-gap);
}
.block {
  display: block;
  width: 100%;
  text-align: left;
  margin-bottom: 8px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.panel-header h2 {
  margin: 0 0 4px;
}
.header-add {
  flex-shrink: 0;
}
.submit-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.preview-hint {
  margin: 0;
}
.add-action-form {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) auto auto;
  gap: 10px;
  align-items: center;
}
.exercise-block {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  display: grid;
  gap: 10px;
  background: var(--surface-alt);
}
.action-head {
  justify-content: flex-start;
}
.records table th,
.records table td {
  vertical-align: middle;
  padding: 12px 8px;
  line-height: 1.45;
}
.done-label {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  margin: 0;
  white-space: nowrap;
  line-height: 1.45;
  color: var(--text);
}
.done-check {
  width: 16px;
  height: 16px;
  margin: 0;
  padding: 0;
  flex-shrink: 0;
  accent-color: var(--accent);
}
table select,
table input:not([type='checkbox']) {
  width: 100%;
  min-width: 0;
  height: var(--control-height);
  padding: 8px 10px;
  line-height: 1.45;
  box-sizing: border-box;
}
@media (max-width: 900px) {
  .add-action-form { grid-template-columns: 1fr; }
  .panel-header { flex-direction: column; align-items: stretch; }
}
@media (max-width: 800px) {
  .records { grid-template-columns: 1fr; }
}
</style>
