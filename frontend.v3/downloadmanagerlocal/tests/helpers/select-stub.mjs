import { defineComponent, h } from 'vue'

// Bridge Vuetify's public value event in the memory/SSR renderer. Real overlay,
// keyboard and layout behaviour is covered by the browser consumer test.
export const VSelectStub = defineComponent({
  props: ['modelValue', 'items', 'disabled'],
  emits: ['update:modelValue'],
  setup(props, { attrs, emit }) {
    return () => h('select', { ...attrs, value: props.modelValue, disabled: props.disabled,
      onChange: event => emit('update:modelValue', event.target.value) },
    props.items.map(item => h('option', { value: typeof item === 'object' ? item.value : item }, typeof item === 'object' ? item.title : item)))
  },
})
