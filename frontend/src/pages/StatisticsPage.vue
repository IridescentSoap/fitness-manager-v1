<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { EChartsOption } from 'echarts'

import { ApiError } from '@/api/client'
import {
  createWeight,
  deleteWeight,
  getOverview,
  getTraining,
  getWeightSummary,
  listWeights,
  type Overview,
  type TrainingSeries,
  type WeightItem,
  type WeightSummary,
} from '@/api/stats'
import ChartBox from '@/components/ChartBox.vue'
import { useAppStore } from '@/stores/app'
import { categoryAxis, chartBase, readChartTheme, valueAxis } from '@/utils/chartTheme'
import { addDays, businessToday, formatRate, monthBounds } from '@/utils/date'

const { theme } = storeToRefs(useAppStore())

const today = businessToday()
const preset = ref<'week' | 'month' | 'd90' | 'custom'>('month')
const customFrom = ref(addDays(today, -30))
const customTo = ref(today)
const tab = ref<'training' | 'weight'>('training')
const overview = ref<Overview | null>(null)
const training = ref<TrainingSeries | null>(null)
const weight = ref<WeightSummary | null>(null)
const weights = ref<WeightItem[]>([])
const error = ref('')
const form = ref({ record_date: today, time: '08:00', weight_kg: '', note: '' })

const range = computed(() => {
  if (preset.value === 'week') return { from: addDays(today, -6), to: today }
  if (preset.value === 'd90') return { from: addDays(today, -89), to: today }
  if (preset.value === 'custom') return { from: customFrom.value, to: customTo.value }
  const bounds = monthBounds(today)
  return { from: bounds.from, to: today < bounds.to ? today : bounds.to }
})

const sessionOption = computed<EChartsOption>(() => {
  const t = readChartTheme()
  return {
    ...chartBase(theme.value),
    tooltip: { trigger: 'axis' },
    xAxis: categoryAxis((training.value?.series ?? []).map((item) => item.period), theme.value),
    yAxis: valueAxis({}, theme.value),
    series: [{ type: 'bar', name: '训练次数', data: (training.value?.series ?? []).map((item) => item.sessions), itemStyle: { color: t.accent } }],
  }
})

const weightOption = computed<EChartsOption>(() => {
  const t = readChartTheme()
  return {
    ...chartBase(theme.value),
    tooltip: { trigger: 'axis' },
    xAxis: categoryAxis((weight.value?.points ?? []).map((item) => item.date), theme.value),
    yAxis: valueAxis({ scale: true }, theme.value),
    series: [{
      type: 'line',
      name: '日体重',
      connectNulls: false,
      data: (weight.value?.points ?? []).map((item) => item.weight_kg),
      itemStyle: { color: t.success },
    }],
  }
})

async function reload() {
  error.value = ''
  try {
    const { from, to } = range.value
    const [overviewData, trainingData, weightData, weightList] = await Promise.all([
      getOverview(from, to),
      getTraining(from, to, 'week'),
      getWeightSummary(from, to),
      listWeights(from, to),
    ])
    overview.value = overviewData
    training.value = trainingData
    weight.value = weightData
    weights.value = weightList.items
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '统计加载失败'
  }
}

onMounted(() => {
  void reload()
})

async function onAddWeight() {
  const kg = Number(form.value.weight_kg)
  if (!kg) {
    ElMessage.warning('请输入体重')
    return
  }
  try {
    await createWeight({
      record_date: form.value.record_date,
      recorded_at: `${form.value.record_date}T${form.value.time}:00+08:00`,
      weight_kg: kg,
      note: form.value.note,
    })
    ElMessage.success('体重已记录')
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '保存失败')
  }
}

async function onDeleteWeight(item: WeightItem) {
  try {
    await ElMessageBox.confirm('删除后不再参与趋势计算。', '删除体重')
  } catch {
    return
  }
  try {
    await deleteWeight(item.id)
    await reload()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '删除失败')
  }
}
</script>

<template>
  <div class="page-stack">
    <section class="panel row">
      <button type="button" :class="{ active: preset === 'week' }" @click="preset = 'week'; reload()">本周</button>
      <button type="button" :class="{ active: preset === 'month' }" @click="preset = 'month'; reload()">本月</button>
      <button type="button" :class="{ active: preset === 'd90' }" @click="preset = 'd90'; reload()">最近90天</button>
      <button type="button" :class="{ active: preset === 'custom' }" @click="preset = 'custom'">自定义</button>
      <template v-if="preset === 'custom'">
        <input v-model="customFrom" type="date" />
        <input v-model="customTo" type="date" />
        <button type="button" @click="reload">应用</button>
      </template>
      <button type="button" :class="{ active: tab === 'training' }" @click="tab = 'training'">训练统计</button>
      <button type="button" :class="{ active: tab === 'weight' }" @click="tab = 'weight'">体重管理</button>
    </section>
    <p v-if="error" class="error-text">{{ error }} <button type="button" @click="reload">重试</button></p>
    <section v-if="overview" class="kpi-grid">
      <article class="kpi"><span>训练次数</span><strong>{{ overview.completed_sessions }}</strong></article>
      <article class="kpi"><span>训练天数</span><strong>{{ overview.training_days }}</strong></article>
      <article class="kpi"><span>计划完成率</span><strong>{{ formatRate(overview.plan_completion_rate) }}</strong></article>
      <article class="kpi"><span>动作完成率</span><strong>{{ formatRate(overview.action_completion_rate) }}</strong></article>
    </section>
    <section v-if="tab === 'training'" class="panel">
      <h2>训练次数</h2>
      <ChartBox :option="sessionOption" />
      <h2>动作频次</h2>
      <table v-if="training?.exercise_frequency.length">
        <thead><tr><th>动作</th><th>完成次数</th></tr></thead>
        <tbody>
          <tr v-for="item in training.exercise_frequency" :key="item.exercise_id">
            <td>{{ item.name }}</td><td>{{ item.count }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">这个区间还没有已提交的完成动作。</p>
    </section>
    <section v-else class="panel">
      <div class="kpi-grid">
        <article class="kpi"><span>最新体重</span><strong>{{ weight?.latest ? `${weight.latest.weight_kg} kg` : '尚未录入体重' }}</strong></article>
        <article class="kpi"><span>区间变化</span><strong>{{ weight?.delta_kg == null ? '—' : `${weight.delta_kg} kg` }}</strong></article>
        <article class="kpi"><span>变化率</span><strong>{{ weight?.delta_percent == null ? '—' : `${weight.delta_percent}%` }}</strong></article>
        <article class="kpi"><span>目标</span><strong>{{ weight?.target_weight_kg ?? '未设置目标' }}</strong></article>
      </div>
      <ChartBox :option="weightOption" />
      <div class="row">
        <input v-model="form.record_date" type="date" />
        <input v-model="form.time" type="time" />
        <input v-model="form.weight_kg" type="number" min="20" max="400" step="0.1" placeholder="kg" />
        <input v-model="form.note" placeholder="备注" />
        <button type="button" @click="onAddWeight">新增体重</button>
      </div>
      <table>
        <thead><tr><th>日期</th><th>时间</th><th>kg</th><th>备注</th><th></th></tr></thead>
        <tbody>
          <tr v-for="item in weights" :key="item.id">
            <td>{{ item.record_date }}</td>
            <td>{{ item.recorded_at }}</td>
            <td>{{ item.weight_kg }}</td>
            <td>{{ item.note }}</td>
            <td><button type="button" class="ghost" @click="onDeleteWeight(item)">删除</button></td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
