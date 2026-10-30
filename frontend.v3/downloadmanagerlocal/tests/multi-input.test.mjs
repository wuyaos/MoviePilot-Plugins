import assert from 'node:assert/strict'
import test from 'node:test'
import { defineComponent, h, nextTick } from 'vue'
import { loadSfc, mount } from './helpers/load-sfc.mjs'

const Lines = await loadSfc('MultiLineInput.vue')
const Multi = await loadSfc('MultiValueInput.vue')

for (const [name, raw, initial, edited] of [
  ['array', ['  /keep path ', 'https://example.invalid/a,b', '/same', '/same'], '  /keep path \nhttps://example.invalid/a,b\n/same\n/same', ['/new path', 'https://example.invalid/a,b']],
  ['string', '  /keep path \nhttps://example.invalid/a,b\n', '  /keep path \nhttps://example.invalid/a,b\n', ' /new path \nhttps://example.invalid/a,b\n'],
]) {
  test(`MultiLineInput ${name}: no mount normalization, newlines stay editable and representation stays stable`, async () => {
    const changes = []
    const Area = defineComponent({ props: ['modelValue'], emits: ['update:modelValue'], setup(props, { emit }) {
      return () => h('div', [h('span', props.modelValue), h('button', { onClick: () => emit('update:modelValue', ' /new path \nhttps://example.invalid/a,b\n') }, 'edit')])
    } })
    const app = mount(Lines, { modelValue: raw, 'onUpdate:modelValue': v => changes.push(v) }, {}, { components: { VTextarea: Area } })
    try {
      assert.deepEqual(changes, [])
      assert.equal(app.findAll(n => n.type === 'span')[0].text, initial)
      app.findAll(n => n.type === 'button')[0].props.onClick(); await nextTick()
      assert.deepEqual(changes, [edited])
    } finally { app.unmount() }
  })
}

test('MultiValueInput does not commit Enter during IME composition', () => {
  const changes = []
  const Combo = defineComponent({ setup: () => () => h('input') })
  const app = mount(Multi, { label: '标签', modelValue: ['原始项'], 'onUpdate:modelValue': v => changes.push(v) }, {}, { components: { VCombobox: Combo } })
  try {
    const input = app.findAll(n => n.type === 'input')[0]
    assert.equal(typeof input.props.onKeydownCapture, 'function')
    let stopped = 0
    for (const properties of [{ isComposing: true }, { keyCode: 229 }]) {
      input.props.onKeydownCapture({ key: 'Enter', ...properties, stopImmediatePropagation() { stopped++ } })
    }
    input.props.onKeydownCapture({ key: 'Enter', isComposing: false, stopImmediatePropagation() { stopped++ } })
    assert.equal(stopped, 2)
    assert.deepEqual(changes, [])
  } finally { app.unmount() }
})
