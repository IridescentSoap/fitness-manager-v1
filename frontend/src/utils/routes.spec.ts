import { describe, expect, it } from 'vitest'

import { CORE_ROUTES } from './routes'

describe('CORE_ROUTES', () => {
  it('covers the six primary pages required by T0', () => {
    expect(CORE_ROUTES).toEqual([
      '/dashboard',
      '/plans',
      '/records',
      '/statistics',
      '/compare',
      '/settings',
    ])
  })
})
