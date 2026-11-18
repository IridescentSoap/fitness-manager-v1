import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EmptyState from './EmptyState.vue'

describe('EmptyState', () => {
  it('renders title and description without fabricated metrics', () => {
    const wrapper = mount(EmptyState, {
      props: {
        title: '数据概览尚未接入数据',
        description: '不会使用硬编码演示数值',
      },
    })

    expect(wrapper.text()).toContain('数据概览尚未接入数据')
    expect(wrapper.text()).toContain('不会使用硬编码演示数值')
    expect(wrapper.text()).not.toMatch(/\d+%/u)
  })
})
