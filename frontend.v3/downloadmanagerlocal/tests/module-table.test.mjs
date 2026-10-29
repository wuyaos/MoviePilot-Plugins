import assert from 'node:assert/strict'
import test from 'node:test'
import { h, nextTick, reactive } from 'vue'
import { loadSfc, mount, render } from './helpers/load-sfc.mjs'

const component = await loadSfc('ModuleTable.vue')
const base = { title: '执行记录', columns: [{ key: 'name', label: '名称' }, { key: 'count', label: '数量' }], rows: [{ id: 'a', name: '保留旧记录', count: 7 }], total: 101 }

test('ModuleTable 数值表头和正文右对齐，格式化字符串可显式对齐，单一表格', async () => {
  const html = await render(component, base)
  assert.match(html, /<th[^>]*text-align:right[^>]*>数量/)
  assert.match(html.replace(/<!--[\s\S]*?-->/g, ''), /<td[^>]*text-align:right[^>]*>7/)
  assert.equal((html.match(/<table\b/g) || []).length, 1)
  assert.match(html, /class="dm-table-scroll"[^>]*tabindex="0"/)
  const custom = await render(component, { ...base, columns: [{ key: 'name', label: '占用 (GiB)', align: 'right', width: 144 }] })
  assert.match(custom, /text-align:right;width:144px/)
})

test('ModuleTable 每页仅 20/50/100；默认20，页码按 total；不二次切片', async () => {
  const defaults = await render(component, base)
  assert.match(defaults, /第 1 \/ 6 页/)
  assert.match(defaults, /共 101 条/)
  assert.deepEqual([...defaults.matchAll(/<option value="(\d+)"/g)].map(match => Number(match[1])), [20, 50, 100])
  for (const [pageSize, pages] of [[20, 6], [50, 3], [100, 2]]) {
    const html = await render(component, { ...base, pageSize, page: 2 })
    assert.ok(html.includes('第 2 / ' + pages + ' 页'))
    assert.ok(html.includes('保留旧记录'), 'rows 已由后端分页，前端不能再切片')
  }
})

test('ModuleTable 五种空态保留标题表头，零条无空分页器且清理禁用', async () => {
  for (const [empty, text] of Object.entries({ none: '暂无记录', filtered: '筛选无结果', 'not-scanned': '尚未扫描', 'no-candidates': '扫描无候选', disabled: '模块已关闭' })) {
    const html = await render(component, { ...base, rows: [], total: 0, state: { empty }, cleanupLabel: '清理记录' })
    assert.ok(html.includes(text))
    assert.match(html, /<h3[^>]*>执行记录/)
    assert.match(html, /<thead>/)
    assert.match(html, /dm-table-cleanup" disabled/)
    assert.doesNotMatch(html, /每页条数|下一页/)
  }
})

test('ModuleTable loading/error/refreshFailed 与关闭历史的真实渲染分支', async () => {
  const loading = await render(component, { ...base, rows: [], total: 0, state: { loading: true } })
  assert.match(loading, /dm-table-skeleton/)
  const error = await render(component, { ...base, rows: [], total: 0, state: { error: '离线' } })
  assert.match(error, /记录加载失败/)
  assert.match(error, /重试/)
  for (const state of [{ loading: true }, { refreshFailed: '刷新超时' }, { error: '读取失败' }, { empty: 'disabled' }]) {
    const html = await render(component, { ...base, state })
    assert.match(html, /保留旧记录/)
    assert.doesNotMatch(html, /dm-table-skeleton|模块已关闭|记录加载失败/)
    if (state.refreshFailed || state.error) assert.match(html, /刷新失败，保留上次结果/)
  }
})

test('ModuleTable toolbar/cell/rowActions 插槽真实渲染且无默认无效操作列', async () => {
  let disabled
  const html = await render(component, base, {
    toolbar: ({ cleanupDisabled }) => { disabled = cleanupDisabled; return h('span', '筛选控件') },
    'cell-name': ({ row, value }) => h('strong', row.id + ':' + value),
    rowActions: ({ row }) => h('button', '查看 ' + row.id),
  })
  assert.equal(disabled, false)
  assert.match(html, /筛选控件/)
  assert.match(html, /<strong>a:保留旧记录/)
  assert.match(html, /查看 a/)
  assert.match(html, />操作<\/th>/)
  assert.doesNotMatch(await render(component, base), />操作<\/th>|dm-table-cleanup/)
})

test('ModuleTable 分页/页大小/重试/筛选重置/清理只 emit，无 API', () => {
  const events = []
  const handlers = {
    'onUpdate:page': value => events.push(['page', value]),
    'onUpdate:pageSize': value => events.push(['pageSize', value]),
    onRetry: () => events.push(['retry']),
    onResetFilters: () => events.push(['reset']),
    onCleanup: () => events.push(['cleanup']),
  }
  const view = mount(component, { ...base, ...handlers, cleanupLabel: '清理记录' })
  const select = view.findAll(el => el.type === 'select')[0]
  for (const value of ['20', '50', '100']) select.props.onChange({ target: { value } })
  select.props.onChange({ target: { value: '200' } })
  view.findAll(el => el.props['aria-label'] === '下一页')[0].props.onClick()
  view.findAll(el => el.props.class?.includes('dm-table-cleanup'))[0].props.onClick()
  assert.deepEqual(events, [['pageSize', 20], ['page', 1], ['pageSize', 50], ['page', 1], ['pageSize', 100], ['page', 1], ['page', 2], ['cleanup']])
  view.unmount()
  const filtered = mount(component, { ...base, ...handlers, rows: [], total: 0, state: { empty: 'filtered' } })
  filtered.findAll(el => el.type === 'button')[0].props.onClick()
  assert.deepEqual(events.slice(-2), [['page', 1], ['reset']])
  filtered.unmount()
  const failed = mount(component, { ...base, ...handlers, state: { refreshFailed: true } })
  failed.findAll(el => el.text === '重试')[0].props.onClick()
  assert.deepEqual(events.at(-1), ['retry'])
  failed.unmount()
})

test('ModuleTable 行展开使用稳定 rowKey；按钮可收起且数据替换移除旧展开状态', async () => {
  const props = reactive({ ...base, rowKey: row => row.id })
  const view = mount(component, props, { expand: ({ row }) => h('div', { class: 'actual-detail' }, '真实详情 ' + row.id) })
  const toggle = () => view.findAll(el => el.type === 'button' && el.props['aria-expanded'] !== undefined)[0]
  assert.equal(toggle().props['aria-expanded'], false)
  toggle().props.onClick()
  await nextTick()
  assert.equal(toggle().props['aria-expanded'], true)
  assert.equal(view.findAll(el => el.props.class === 'actual-detail')[0].text, '真实详情 a')
  toggle().props.onClick()
  await nextTick()
  assert.equal(view.findAll(el => el.props.class === 'actual-detail').length, 0)
  toggle().props.onClick()
  await nextTick()
  props.rows = [{ id: 'b', name: '新记录', count: 1 }]
  await nextTick()
  assert.equal(toggle().props['aria-expanded'], false)
  view.unmount()
})
