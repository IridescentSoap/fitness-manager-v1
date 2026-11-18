<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink } from 'vue-router'
import type { EChartsOption } from 'echarts'

import { ApiError } from '@/api/client'
import { getMetrics, getRankings, getWeightTrends, listCandidates, type CandidateUser, type RankItem } from '@/api/comparison'
import ChartBox from '@/components/ChartBox.vue'
import { useAppStore } from '@/stores/app'
import { categoryAxis, chartBase, readChartTheme, valueAxis } from '@/utils/chartTheme'
import { businessToday, formatRate, monthBounds } from '@/utils/date'

const { theme } = storeToRefs(useAppStore())

const today = businessToday()
const from = ref(monthBounds(today).from)
const to = ref(today)
const metric = ref<'sessions' | 'days' | 'plan_rate' | 'action_rate'>('sessions')
const ranked = ref<RankItem[]>([])
const unranked = ref<RankItem[]>([])
const candidates = ref<CandidateUser[]>([])
const selected = ref<number[]>([])
const message = ref('')
const error = ref('')
const trendNote = ref('变化仅作数据对比，不代表训练效果优劣')
const compareValues = ref<{ name: string; value: number | null }[]>([])
const trendOption = ref<Record<string, unknown>>({ series: [] })

const metricKeys = ['sessions', 'days', 'plan_rate', 'action_rate'] as const
const labels: Record<(typeof metricKeys)[number], string> = {
  sessions: '训练次数',
  days: '训练天数',
  plan_rate: '计划完成率',
  action_rate: '动作完成率',
}

const rankOption = computed<EChartsOption>(() => {
  const t = readChartTheme()
  return {
    ...chartBase(theme.value),
    tooltip: { trigger: 'axis' },
    xAxis: categoryAxis(compareValues.value.map((item) => item.name), theme.value),
    yAxis: valueAxis({}, theme.value),
    series: [{ type: 'bar', name: labels[metric.value], data: compareValues.value.map((item) => item.value), itemStyle: { color: t.accent } }],
  }
})

function displayValue(item: RankItem) {
  if (item.label === '无数据' || item.value == null) return '无数据'
  if (metric.value.endsWith('rate')) return formatRate(item.value)
  return String(item.value)
}

async function reload() {
  error.value = ''
  message.value = ''
  try {
    const [rankData, people] = await Promise.all([
      getRankings(metric.value, from.value, to.value),
      listCandidates('training'),
    ])
    ranked.value = rankData.items
    unranked.value = rankData.unranked
    candidates.value = people.items
    if (!ranked.value.length && !unranked.value.length) {
      message.value = '还没有人开放训练汇总。可以在系统设置里打开共享。'
    }
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '排行加载失败'
  }
}

async function loadCompare() {
  compareValues.value = []
  if (selected.value.length < 2) return
  try {
    const data = await getMetrics(selected.value.slice(0, 5), metric.value, from.value, to.value)
    compareValues.value = data.items.map((item) => ({ name: item.display_name, value: item.value ?? null }))
  } catch (err) {
    Elike(err)
  }
}

function Elike(err: unknown) {
  error.value = err instanceof ApiError ? err.message : '对比失败'
  if (err instanceof ApiError && err.code === 'SHARING_NOT_ALLOWED') {
    selected.value = []
    compareValues.value = []
  }
}

async function loadTrends() {
  if (selected.value.length < 2) return
  try {
    const data = await getWeightTrends(selected.value.slice(0, 5), from.value, to.value)
    trendNote.value = data.note
    const dates = data.series[0]?.points.map((point) => point.date) ?? []
    const t = readChartTheme()
    trendOption.value = {
      ...chartBase(theme.value),
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: t.text } },
      xAxis: categoryAxis(dates, theme.value),
      yAxis: valueAxis({ scale: true }, theme.value),
      series: data.series.map((item) => ({
        type: 'line' as const,
        name: item.display_name,
        connectNulls: false,
        data: item.points.map((point) => point.weight_kg),
      })),
    }
  } catch (err) {
    Elike(err)
  }
}

onMounted(() => {
  void reload()
})

watch(theme, () => {
  if (selected.value.length >= 2) {
    void loadCompare()
    void loadTrends()
  }
})

function toggleUser(id: number, checked: boolean) {
  if (checked) {
    if (selected.value.length >= 5) return
    selected.value = [...selected.value, id]
  } else {
    selected.value = selected.value.filter((item) => item !== id)
  }
  void loadCompare()
}
</script>

<template>
  <div class="page-stack">
    <section class="panel row">
      <label>从 <input v-model="from" type="date" /></label>
      <label>到 <input v-model="to" type="date" /></label>
      <button type="button" @click="reload">刷新排行</button>
      <button v-for="key in metricKeys" :key="key" type="button" :class="{ active: metric === key }" @click="metric = key; reload()">
        {{ labels[key] }}
      </button>
    </section>
    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-if="message" class="muted">{{ message }} <RouterLink to="/settings">去设置共享</RouterLink></p>
    <section class="panel">
      <h2>{{ labels[metric] }}排行</h2>
      <table>
        <thead><tr><th>名次</th><th>用户</th><th>数值</th></tr></thead>
        <tbody>
          <tr v-for="item in ranked" :key="item.user_id">
            <td>{{ item.rank }}</td><td>{{ item.display_name }}</td><td>{{ displayValue(item) }}</td>
          </tr>
          <tr v-for="item in unranked" :key="`u-${item.user_id}`">
            <td>—</td><td>{{ item.display_name }}</td><td>无数据</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!ranked.length && !unranked.length" class="muted">当前没有可排名的数据。</p>
    </section>
    <section class="panel">
      <h2>横向对比（2 到 5 人）</h2>
      <label v-for="user in candidates" :key="user.id" class="check">
        <input
          type="checkbox"
          :checked="selected.includes(user.id)"
          @change="toggleUser(user.id, ($event.target as HTMLInputElement).checked)"
        />
        {{ user.display_name }}{{ user.is_self ? '（我）' : '' }}
      </label>
      <ChartBox v-if="compareValues.length" :option="rankOption" />
      <button type="button" class="ghost" @click="loadTrends">查看原始体重曲线（需数值授权）</button>
      <ChartBox :option="trendOption" />
      <p class="muted">{{ trendNote }}</p>
    </section>
  </div>
</template>

<style scoped>
.check { display: flex; gap: 8px; align-items: center; margin-right: 12px; }
</style>
