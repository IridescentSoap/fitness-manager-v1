/** Read live CSS theme tokens for ECharts so light/dark stay in sync. */
export function readChartTheme() {
  const styles = getComputedStyle(document.documentElement)
  const read = (name: string, fallback: string) =>
    styles.getPropertyValue(name).trim() || fallback

  return {
    text: read('--text', '#1c2430'),
    muted: read('--text-muted', '#667585'),
    border: read('--border', '#e4e8ee'),
    accent: read('--accent', '#e25b2a'),
    success: read('--success', '#1f9a6a'),
  }
}

export function chartBase(themeDep?: string) {
  void themeDep
  const t = readChartTheme()
  return {
    backgroundColor: 'transparent' as const,
    textStyle: { color: t.text },
    legend: { textStyle: { color: t.text } },
  }
}

export function categoryAxis(data: string[], themeDep?: string) {
  void themeDep
  const t = readChartTheme()
  return {
    type: 'category' as const,
    data,
    axisLabel: { color: t.muted },
    axisLine: { lineStyle: { color: t.border } },
  }
}

export function valueAxis(extra: Record<string, unknown> = {}, themeDep?: string) {
  void themeDep
  const t = readChartTheme()
  return {
    type: 'value' as const,
    axisLabel: { color: t.muted },
    splitLine: { lineStyle: { color: t.border } },
    axisLine: { lineStyle: { color: t.border } },
    ...extra,
  }
}
