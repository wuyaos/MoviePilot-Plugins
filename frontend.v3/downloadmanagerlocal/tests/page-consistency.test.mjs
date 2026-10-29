import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

// 数据页「各模块表现风格统一」（用户 m18958 ①）的结构约束：
// 只断言可复现的结构事实（重复块的外围类名、空态兜底、共享明细组件），
// 不断言具体文案（方案 §9 禁止机械文案断言）。
const source = readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')

const RECORD_BLOCKS = [
  'rename-history',
  'rename-archive',
  'autoremove-preview',
  'hr-tasks',
  'transfer-tasks',
  'tag-cleanup',
  'module-data-cleanup',
]

function sliceBlocks() {
  const marks = [...source.matchAll(/data-record-block="([^"]+)"/g)].map((match) => ({ name: match[1], at: match.index }))
  const tail = source.indexOf('<style')
  marks.push({ name: '__END__', at: tail === -1 ? source.length : tail })
  const blocks = new Map()
  for (let index = 0; index < marks.length - 1; index += 1) {
    blocks.set(marks[index].name, source.slice(marks[index].at, marks[index + 1].at))
  }
  return blocks
}

const blocks = sliceBlocks()
// 每个 <ModuleDetailPanel 的完整起始标签：同行收尾（...>）或多行绑定（单独一行 />）。
function panelTags() {
  const tags = []
  for (const match of source.matchAll(/<ModuleDetailPanel/g)) {
    const collected = []
    for (const line of source.slice(match.index).split('\n')) {
      collected.push(line)
      if (/\n\s*\/>\s*$/.test(collected.join('\n')) || /[^<]>$/.test(line)) break
      if (collected.length > 20) break
    }
    tags.push(collected.join('\n'))
  }
  return tags
}

const detailPanels = panelTags()

test('数据页记录块清单稳定（新增/删除模块必须同步本测试与外围类名）', () => {
  assert.deepEqual([...blocks.keys()].sort(), [...RECORD_BLOCKS].sort())
})

test('每个记录块都使用共享标题外围（dm-record-block-head + dm-record-block-title）', () => {
  const offenders = []
  for (const name of RECORD_BLOCKS) {
    const block = blocks.get(name)
    if (!/class="dm-record-block-head"/.test(block) || !/class="dm-record-block-title"/.test(block)) {
      offenders.push(name)
    }
  }
  assert.deepEqual(offenders, [], `未使用共享标题外围的记录块：${offenders.join(', ')}`)
})

test('每个记录块都有空态兜底或数据面（表格/移动卡片）', () => {
  const offenders = []
  for (const name of RECORD_BLOCKS) {
    const block = blocks.get(name)
    const hasEmpty = /class="dm-state|class="dm-monitor-empty/.test(block)
    const hasData = /<VTable|dm-record-card/.test(block)
    if (!hasEmpty && !hasData) offenders.push(name)
  }
  assert.deepEqual(offenders, [], `既无空态也无数据面的记录块：${offenders.join(', ')}`)
})

test('模块运行明细统一走共享展示组件，且总览卡透传条数口径', () => {
  assert.match(source, /import ModuleDetailPanel from '\.\/ModuleDetailPanel\.vue'/)
  assert.ok(detailPanels.length >= 2, `共享明细组件使用点应覆盖总览卡与上传限速专项页，实际 ${detailPanels.length} 处`)
  for (const tag of detailPanels) {
    assert.match(tag, /:rows="/, '共享明细组件必须绑定 rows')
  }
  const overview = detailPanels.filter((tag) => tag.includes(':items="'))
  assert.equal(overview.length, 1, '总览卡应有且只有一处透传 items')
  for (const binding of [':items="', ':total="', ':limit="', ':truncated="', ':error="']) {
    assert.ok(overview[0].includes(binding), `总览卡共享明细组件缺少 ${binding} 绑定`)
  }
})

test('上传限速专项页的专属网格走 appendix 槽，不重复透传 items', () => {
  const index = source.indexOf(":rows=\"moduleDetail('upload_limit').rows\"")
  assert.notEqual(index, -1, '缺少上传限速专项页的共享明细组件用法')
  const tag = source.slice(index, index + 400)
  assert.ok(!tag.includes(':items="'), '上传限速的站点聚合已由专属网格展示，不应再透传 items')
  const end = source.indexOf('</ModuleDetailPanel>', index)
  assert.notEqual(end, -1, '上传限速专项页的共享明细组件未闭合')
  const section = source.slice(index, end)
  assert.match(section, /#appendix/, '专属网格应作为 appendix 槽内容嵌套在共享组件内')
  assert.match(section, /dm-upload-status-grid/, '缺少下载器状态网格')
  assert.match(section, /dm-upload-site-status-row/, '缺少受限站点网格')
})
