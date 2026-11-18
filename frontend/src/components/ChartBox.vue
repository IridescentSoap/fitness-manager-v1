<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

import { useAppStore } from '@/stores/app'

const props = defineProps<{ option: EChartsOption | Record<string, unknown> }>()
const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
const { theme } = storeToRefs(useAppStore())

function render() {
  if (!el.value) return
  if (!chart) {
    chart = echarts.init(el.value)
  }
  chart.setOption(props.option as EChartsOption, true)
  chart.resize()
}

function remount() {
  chart?.dispose()
  chart = null
  render()
}

onMounted(render)
watch(() => props.option, render, { deep: true })
watch(theme, remount)
onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" class="chart-box" />
</template>
