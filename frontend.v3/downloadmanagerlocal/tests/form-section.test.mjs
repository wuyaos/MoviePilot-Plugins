import assert from 'node:assert/strict'
import test from 'node:test'
import { defineComponent, h, nextTick } from 'vue'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { loadSfc, render, mount } from './helpers/load-sfc.mjs'

const Section = await loadSfc('FormSection.vue')
const Multi = await loadSfc('MultiValueInput.vue')
const source = readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)

test('FormSection uses a shared heading, theme divider and independent content/actions slots', async () => {
  const components = { VIcon: { setup: (_, { attrs }) => () => h('i', attrs) }, VDivider: { setup: () => () => h('hr') } }
  const html = await render(Section, { title: '做种校验', icon: 'mdi-transfer' }, { default: () => h('input', { name: 'interval' }), actions: () => h('button', '启用') }, { components })
  assert.match(html, /aria-label="做种校验"/)
  assert.match(html, /<h3[^>]*>做种校验<\/h3>/)
  assert.match(html, /mdi-transfer/)
  assert.match(html, /dm-form-section-actions/)
  assert.match(html, /name="interval"/)
  assert.match(html, /<hr/)
})

test('MultiValueInput preserves the raw string on mount and emits only comma strings on user edits', async () => {
  const changes = []
  const Combo = defineComponent({ props: ['modelValue'], emits: ['update:modelValue'], setup(props, { emit }) {
    return () => h('div', [h('span', JSON.stringify(props.modelValue)), h('button', { id: 'edit', onClick: () => emit('update:modelValue', ['Movie', 'TV']) }), h('button', { id: 'clear', onClick: () => emit('update:modelValue', []) })])
  } })
  const app = mount(Multi, { modelValue: '  Movie ,TV,Movie ', label: '包含分类', 'onUpdate:modelValue': value => changes.push(value) }, {}, { components: { VCombobox: Combo, VChip: { setup: (_, { slots }) => () => h('span', slots.default?.()) } } })
  try {
    assert.deepEqual(changes, [], 'opening must not normalize stored configuration')
    assert.equal(app.findAll(n => n.type === 'span')[0].text, '["Movie","TV","Movie"]')
    app.findAll(n => n.props.id === 'edit')[0].props.onClick(); await nextTick()
    app.findAll(n => n.props.id === 'clear')[0].props.onClick(); await nextTick()
    assert.deepEqual(changes, ['Movie,TV', ''])
  } finally { app.unmount() }
})

test('transfer pilot separates switches from fields and keeps fallback disabling and all model keys', () => {
  const panes = []
  function visit(node) { if (node.type === 1 && node.props.some(p => p.type === 7 && p.name === 'show' && p.exp?.content === "activeSub === 'basic'")) panes.push(node); for (const child of node.children || []) visit(child) }
  visit(descriptor.template.ast)
  assert.equal(panes.length, 1)
  const pane = panes[0]
  assert.match(pane.loc.source, /dm-transfer-form/)
  const sections = pane.children.filter(n => n.type === 1 && n.tag === 'FormSection')
  assert.equal(sections.length, 3)
  assert.deepEqual(sections.map(n => n.props.find(p => p.type === 6 && p.name === 'title').value.content), ['基础设置', '转移策略', '转移后操作'])
  assert.doesNotMatch(pane.loc.source, /新任务默认值|v-model="form.transfer_delete_(?:source|duplicate)_default"/)
  const post = sections[2].children.find(n => n.type === 1 && n.props.some(p => p.type === 6 && p.value?.content === 'dm-switch-group'))
  assert.equal((post.loc.source.match(/<VSwitch/g) || []).length, 3)
  for (const key of ['transfer_rename_enabled', 'seed_autostart', 'seed_skipverify']) assert.ok(post.loc.source.includes('form.' + key))
  for (const section of sections) assert.ok(section.props.some(p => p.type === 7 && p.arg?.content === 'icon' && p.exp?.content === 'MODULE_ICONS.transfer'))
  function check(node) {
    if (node.type === 1 && node.props.some(p => p.type === 6 && p.name === 'class' && p.value?.content === 'dm-field-row')) assert.doesNotMatch(node.loc.source, /<V(?:Switch|Checkbox)/)
    for (const child of node.children || []) check(child)
  }
  check(pane)
  assert.match(pane.loc.source, /:disabled="!form.transfer_fallback_enabled"/)
  assert.equal((descriptor.template.content.match(/<MultiValueInput\b/g) || []).length, 10)
  assert.equal((descriptor.template.content.match(/v-model="transferForm\.(?:include_category|include_labels|exclude_labels)"/g) || []).length, 3)
})


test('MultiValueInput keeps array models as arrays without mount-time normalization', async () => {
  const changes = []
  const raw = ['  Original ', 'Movie', 'Movie']
  const Combo = defineComponent({ props: ['modelValue'], emits: ['update:modelValue'], setup(props, { emit }) {
    return () => h('div', [h('span', JSON.stringify(props.modelValue)), h('button', { id: 'edit', onClick: () => emit('update:modelValue', ['Movie', 'TV']) }), h('button', { id: 'clear', onClick: () => emit('update:modelValue', []) })])
  } })
  const app = mount(Multi, { modelValue: raw, label: '排除标签', 'onUpdate:modelValue': value => changes.push(value) }, {}, { components: { VCombobox: Combo, VChip: { setup: (_, { slots }) => () => h('span', slots.default?.()) } } })
  try {
    assert.deepEqual(changes, [])
    assert.equal(app.findAll(n => n.type === 'span')[0].text, JSON.stringify(raw))
    app.findAll(n => n.props.id === 'edit')[0].props.onClick(); await nextTick()
    app.findAll(n => n.props.id === 'clear')[0].props.onClick(); await nextTick()
    assert.deepEqual(changes, [['Movie', 'TV'], []])
    assert.deepEqual(raw, ['  Original ', 'Movie', 'Movie'])
  } finally { app.unmount() }
})

test('H&R basic page has exactly three shared sections with protected field ownership and no advanced fold', () => {
  const panes=[]
  function visit(n) { if(n.type===1 && n.props.some(p=>p.type===7 && p.name==='show' && p.exp?.content==="activeSub === 'hr_basic'")) panes.push(n); for(const child of n.children||[])visit(child) }
  visit(descriptor.template.ast)
  assert.equal(panes.length,1)
  const pane=panes[0]
  assert.match(pane.loc.source,/dm-compact-form/)
  const sections=pane.children.filter(n=>n.type===1 && n.tag==='FormSection')
  assert.deepEqual(sections.map(n=>n.props.find(p=>p.type===6 && p.name==='title').value.content),['基础设置','跟踪策略','保护与记录'])
  assert.doesNotMatch(pane.loc.source,/<details|更多设置|运行调度/)
  const keys=[['hr_enabled','hr_observe_only','hr_auto_discover','hr_notify','hr_notify_summary_cron','hr_check_period'],['hr_enable_site_config','hr_downloader','hr_sites','hr_exclude_tags','hr_exclude_categories','hr_brush_plugin'],['hr_protection_enabled','hr_hit_and_run_tag','hr_auto_cleanup_days']]
  for(let i=0;i<3;i++){
    assert.match(sections[i].loc.source,/:icon="MODULE_ICONS.hr"/)
    const actual=[...sections[i].loc.source.matchAll(/v-model(?:.number)?="form.([^"]+)"/g)].map(m=>m[1]).sort()
    assert.deepEqual(actual,[...keys[i]].sort())
  }
  assert.match(sections[0].loc.source,/:disabled="form.hr_notify === 'none'"/)
  assert.match(sections[2].loc.source,/v-if="!form.hr_protection_enabled"/)
  assert.match(sections[2].loc.source,/未达标 H&R 任务可能被删除/)
  assert.equal((sections[1].loc.source.match(/<MultiValueInput/g)||[]).length,2)
  function check(n){ if(n.type===1 && n.props.some(p=>p.type===6 && p.value?.content==='dm-field-row'))assert.doesNotMatch(n.loc.source,/<VSwitch/); for(const child of n.children||[])check(child) }
  check(pane)
})

test('H&R site rules use two shared sections, one native table and existing rule mutation handlers', () => {
  const panes=[]
  function visit(n){ if(n.type===1 && n.props.some(p=>p.type===7 && p.name==='show' && p.exp?.content==="activeSub === 'hr_sites'"))panes.push(n); for(const c of n.children||[])visit(c) }
  visit(descriptor.template.ast)
  assert.equal(panes.length,1)
  const source=panes[0].loc.source
  const sections=panes[0].children.filter(n=>n.type===1 && n.tag==='FormSection')
  assert.deepEqual(sections.map(n=>n.props.find(p=>p.type===6 && p.name==='title').value.content),['全局规则','站点规则'])
  assert.match(source,/dm-compact-form/)
  assert.equal((source.match(/<VTable\b/g)||[]).length,1)
  assert.equal((source.match(/<RowActionMenu\b/g)||[]).length,1)
  assert.equal((source.match(/<MultiLineInput\b/g)||[]).length,1)
  assert.doesNotMatch(source,/persistent-hint|dm-hr-row|影子条目|顶层为列表/)
  for(const name of ['hrSetSiteEnabled(row.name, $event)','hrToggleExpanded(row.name)','hrRemoveCustomSite(row.name)','hrCopyPresetToCustom(row.name)','hrSetRuleNumber(row.name, field.key, $event)','hrSetRuleFlag(row.name, field.key, $event)','hrSetRuleTrackers(row.name, $event)','hrRemoveTier(row.name, tierIndex)'])assert.ok(source.includes(name),name)
  assert.match(source,/:error-messages="hrRawError"/)
  assert.match(source,/停用后回退全局/)
  assert.match(source,/继承 \$\{hrGlobalText\(field.key\)\}/)
})

test('H&R layout retains the approved configuration business script byte-for-byte apart from authorized presentation adapters', async () => {
  const { createHash } = await import('node:crypto')
  const script=descriptor.scriptSetup.content.replace(/\r\n/g,'\n').replace("import RowActionMenu from './RowActionMenu.vue'\n",'').replace("import MultiLineInput from './MultiLineInput.vue'\n",'')
  const adapterStart = script.indexOf('// 通知开关仅映射已有三态')
  const adapterEnd = script.indexOf('const removerActionItems', adapterStart)
  const businessScript = (script.slice(0, adapterStart) + script.slice(adapterEnd))
    .split('\n').filter(line => !line.startsWith('        color: `var(--dm-hr-rule-')).join('\n')
  assert.equal(createHash('sha256').update(businessScript).digest('hex'),'57155b6c4ce00953c7cc371ff5d0921d330ee9865b7d0368c0bb4168b17a724c')
})
