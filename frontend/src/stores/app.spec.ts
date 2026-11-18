import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAppStore } from './app'

describe('theme mode', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.classList.remove('dark')
    setActivePinia(createPinia())
  })

  it('defaults to light mode for readable browsing', () => {
    const store = useAppStore()
    expect(store.theme).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('toggles between light and dark and persists', () => {
    const store = useAppStore()
    store.toggleTheme()
    expect(store.theme).toBe('dark')
    expect(localStorage.getItem('fm_theme')).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    store.toggleTheme()
    expect(store.theme).toBe('light')
    expect(localStorage.getItem('fm_theme')).toBe('light')
  })
})
