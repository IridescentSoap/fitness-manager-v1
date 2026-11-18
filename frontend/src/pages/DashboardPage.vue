<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink } from 'vue-router'
import type { EChartsOption } from 'echarts'

import { ApiError } from '@/api/client'
import { listRecords, type WorkoutRecord } from '@/api/records'
import { getOverview, getTraining, getWeightSummary, type Overview, type TrainingSeries, type WeightSummary } from '@/api/stats'
import ChartBox from '@/components/ChartBox.vue'
import { useAppStore } from '@/stores/app'
import { categoryAxis, chartBase, readChartTheme, valueAxis } from '@/utils/chartTheme'
import { addDays, businessToday, formatRate, monthBounds } from '@/utils/date'

const { theme } = storeToRefs(useAppStore())
const today = businessToday()
const from = monthBounds(today).from
const overview = ref<Overview | null>(null)
const training = ref<TrainingSeries | null>(null)
const weight = ref<WeightSummary | null>(null)
const records = ref<WorkoutRecord[]>([])
const error = ref('')

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
    series: [{ type: 'line', name: '体重', connectNulls: false, data: (weight.value?.points ?? []).map((item) => item.weight_kg), itemStyle: { color: t.success } }],
  }
})

async function reload() {
  error.value = ''
  try {
    const to = today
    const [overviewData, trainingData, weightData, recordData] = await Promise.all([
      getOverview(from, to),
      getTraining(from, to, 'week'),
      getWeightSummary(from, to),
      listRecords(addDays(today, -30), to, 1, 10),
    ])
    overview.value = overviewData
    training.value = trainingData
    weight.value = weightData
    records.value = recordData.items
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '概览加载失败'
  }
}

onMounted(() => {
  void reload()
})
</script>

<template>
  <div class="page-stack">
    <div class="dashboard-toolbar">
      <p class="muted">本月 {{ from }} 至 {{ today }}</p>
      <RouterLink class="link-btn" to="/records?date=today">补录训练</RouterLink>
    </div>
    <p v-if="error" class="error-text">{{ error }} <button type="button" @click="reload">重试</button></p>
    <section v-if="overview" class="kpi-grid">
      <RouterLink class="kpi" to="/statistics">
        <span>完成训练次数</span><strong>{{ overview.completed_sessions }}</strong>
      </RouterLink>
      <RouterLink class="kpi" to="/statistics">
        <span>计划完成率</span><strong>{{ formatRate(overview.plan_completion_rate) }}</strong>
      </RouterLink>
      <RouterLink class="kpi" to="/statistics">
        <span>训练天数</span><strong>{{ overview.training_days }}</strong>
      </RouterLink>
      <RouterLink class="kpi" to="/statistics">
        <span>最新体重</span><strong>{{ overview.latest_weight ? `${overview.latest_weight.weight_kg} kg` : '尚未录入体重' }}</strong>
      </RouterLink>
    </section>
    <div class="split">
      <section class="panel"><h2>每周训练次数</h2><ChartBox :option="sessionOption" /></section>
      <section class="panel"><h2>近期体重</h2><ChartBox :option="weightOption" /></section>
    </div>
    <section class="panel">
      <h2>最近记录</h2>
      <table v-if="records.length">
        <thead><tr><th>日期</th><th>主题</th><th>完成情况</th></tr></thead>
        <tbody>
          <tr v-for="item in records" :key="item.id">
            <td>{{ item.workout_date }}</td>
            <td>{{ item.title }}</td>
            <td>{{ item.status === 'DRAFT' ? '草稿' : item.completion_result }} {{ item.completed_count }}/{{ item.total_count }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">还没有训练记录。</p>
    </section>
  </div>
</template>

<style scoped>
.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--row-gap);
}
.dashboard-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.link-btn {
  display: inline-flex;
  align-items: center;
  min-height: var(--control-height);
  padding: 0 16px;
  border-radius: var(--radius-sm);
  color: var(--btn-on-accent);
  background: var(--accent);
  font-weight: 650;
}
.link-btn:hover {
  background: var(--accent-hover);
}
.kpi {
  text-decoration: none;
  color: inherit;
}
@media (max-width: 900px) {
  .split { grid-template-columns: 1fr; }
}
</style>
