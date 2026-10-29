import assert from 'node:assert/strict'
import test from 'node:test'
import { loadSfc, mount, render } from './helpers/load-sfc.mjs'

const component = await loadSfc('TableState.vue')
const states = { none: '暂无记录', filtered: '筛选无结果', 'not-scanned': '尚未扫描', 'no-candidates': '扫描无候选', disabled: '模块已关闭' }
for (const [empty, title] of Object.entries(states)) {
  test('TableState 空态：' + empty, async () => {
    const html = await render(component, { empty })
    assert.match(html, new RegExp(title))
    for (const other of Object.values(states).filter(value => value !== title)) assert.ok(!html.includes(other))
    assert.equal(html.includes('重置筛选'), empty === 'filtered')
    assert.match(html, /role="status"/)
    assert.match(html, /aria-hidden="true"/)
  })
}

test('TableState 首次 loading 渲染三行骨架，优先于错误和空态', async () => {
  const html = await render(component, { loading: true, error: '连接失败', empty: 'none' })
  assert.equal((html.match(/class="dm-table-skeleton"/g) || []).length, 3)
  assert.match(html, /aria-busy="true"/)
  assert.doesNotMatch(html, /连接失败|暂无记录/)
})

test('TableState 首次 error 可见且转义错误正文；refreshFailed 使用保留结果提示', async () => {
  const first = await render(component, { error: '<断线>', empty: 'none' })
  assert.match(first, /role="alert"/)
  assert.match(first, /记录加载失败/)
  assert.match(first, /&lt;断线&gt;/)
  assert.match(first, /重试/)
  const refresh = await render(component, { refreshFailed: '超时' })
  assert.match(refresh, /刷新失败，保留上次结果：超时/)
  assert.doesNotMatch(refresh, /记录加载失败|dm-table-skeleton/)
  assert.equal((await render(component)).replace(/<!--[\s\S]*?-->/g, ''), '')
})

test('TableState 重试与重置按钮发出真实组件事件', () => {
  for (const [props, event] of [[{ error: true }, 'onRetry'], [{ refreshFailed: true }, 'onRetry'], [{ empty: 'filtered' }, 'onResetFilters']]) {
    let called = 0
    const view = mount(component, { ...props, [event]: () => called++ })
    view.findAll(el => el.type === 'button')[0].props.onClick()
    assert.equal(called, 1)
    view.unmount()
  }
})
