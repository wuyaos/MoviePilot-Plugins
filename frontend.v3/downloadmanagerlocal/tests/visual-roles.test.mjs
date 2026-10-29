import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import postcss from 'postcss'
import { computed, nextTick, reactive, ref, watch } from 'vue'

const root = new URL('../src/', import.meta.url)
const sources = Object.fromEntries(['Config', 'Page', 'DownloaderBadge'].map(name => [name, fs.readFileSync(new URL(`components/${name}.vue`, root), 'utf8')]))
const css = fs.readFileSync(new URL('styles/dm-tokens.css', root), 'utf8')
const templates = {}
function elements(node, found = []) {
  if (node.type === 1) found.push(node)
  for (const child of node.children || []) elements(child, found)
  return found
}
const attribute = (node, name) => node.props.find(prop => prop.type === 6 && prop.name === name)?.value?.content
const binding = (node, name) => node.props.find(prop => prop.type === 7 && prop.name === 'bind' && prop.arg?.content === name)?.exp?.content
const model = node => node.props.find(prop => prop.type === 7 && prop.name === 'model')?.exp?.content
const controls = new Set(['VSwitch', 'VSelect', 'VTextField', 'VTextarea', 'VCombobox', 'VCheckbox', 'VCronField'])

for (const [name, source] of Object.entries(sources)) {
  test(`${name} 的真实 SFC/template/scoped CSS 可编译`, () => {
    const { descriptor, errors } = parse(source, { filename: name + '.vue' })
    assert.deepEqual(errors, [])
    const compiled = compileTemplate({ source: descriptor.template.content, filename: name + '.vue', id: 'dml-visual' })
    assert.deepEqual(compiled.errors, [])
    templates[name] = elements(descriptor.template.ast)
    for (const style of descriptor.styles) assert.deepEqual(compileStyle({ source: style.content, filename: name + '.vue', id: 'dml-visual', scoped: true }).errors, [])
  })
}

test('全页业务按钮 small、输入/开关 compact，导航不纳入按钮门禁', () => {
  for (const name of ['Config', 'Page']) {
    const nodes = templates[name]
    const buttons = nodes.filter(node => node.tag === 'VBtn')
    assert.equal(buttons.length, name === 'Config' ? 28 : 46)
    for (const node of buttons) assert.equal(attribute(node, 'size'), 'small', `${name}:${node.loc.start.line}`)
    for (const node of nodes.filter(node => controls.has(node.tag))) assert.equal(attribute(node, 'density'), 'compact', `${name}:${node.loc.start.line}`)
  }
})

test('普通帮助无 caption/medium-emphasis 或蓝色信息框；所有观察帮助有图标与条件', () => {
  for (const name of ['Config', 'Page']) {
    assert.doesNotMatch(sources[name], /text-caption|text-medium-emphasis|type="info"/)
  }
  const nodes = templates.Config
  const switches = nodes.filter(node => node.tag === 'VSwitch' && /_observe_only$/.test(model(node) || ''))
  assert.equal(switches.length, 7)
  for (const node of switches) {
    assert.equal(attribute(node, 'color'), 'warning')
    const condition = model(node)
    const help = nodes.find(candidate => candidate.props.some(prop => prop.type === 7 && prop.name === 'if' && prop.exp?.content === condition) && attribute(candidate, 'class')?.includes('dm-risk'))
    assert.ok(help, condition)
    assert.ok(attribute(help, 'class').includes('dm-hint'))
    assert.ok(elements(help).some(child => child.tag === 'VIcon' && attribute(child, 'icon') === 'mdi-alert-outline'))
  }
})

test('开关去 success/info；真实删除选项为 error，风险不替代字段错误', () => {
  for (const node of templates.Config.filter(node => node.tag === 'VSwitch')) {
    assert.ok(!['success', 'info'].includes(attribute(node, 'color')), node.loc.source)
    if (['transferForm.delete_source', 'transferForm.delete_duplicate', 'form.tag_enable_del_tags'].includes(model(node))) assert.equal(attribute(node, 'color'), 'error')
  }
  for (const key of ['hrNewSiteName', 'form.hr_site_config_str', 'form.upload_limit_downloaders', 'transferForm.from_downloader', 'transferForm.to_downloader', 'transferForm.from_path', 'transferForm.to_path']) {
    const node = templates.Config.find(candidate => model(candidate) === key)
    assert.ok(binding(node, 'error-messages'), key)
    assert.equal(attribute(node, 'hide-details'), undefined)
    assert.ok(!node.props.some(prop => prop.type === 6 && prop.name === 'hide-details'), key)
  }
})

test('危险操作有对象；图标按钮有可访问名称；弹窗仍在插件 token 作用域内', () => {
  for (const name of ['Config', 'Page']) {
    for (const node of templates[name].filter(node => node.tag === 'VBtn')) {
      if (attribute(node, 'icon')) assert.ok(attribute(node, 'aria-label') || binding(node, 'aria-label'), node.loc.source)
      const content = node.children.filter(child => child.type === 2).map(child => child.content.trim()).join('')
      assert.ok(!['删除', '清除', '清理', '确认清理', '确认清除'].includes(content), content)
    }
    for (const node of templates[name].filter(node => node.tag === 'VDialog')) assert.equal(attribute(node, 'content-class'), name === 'Config' ? 'dm-config' : 'dm-page')
  }
})

test('同角色使用唯一 token；浮动 label 缩放与导航/容器尺寸不被共享样式覆盖', () => {
  const ast = postcss.parse(css)
  ast.walkRules(rule => {
    assert.ok(rule.selector.startsWith(':where(.dm-'))
    assert.ok(!rule.selector.includes('*'))
    assert.ok(!/dm-(?:subtab|nav|side)|v-tab/.test(rule.selector))
  })
  const rule = selector => ast.nodes.find(node => node.type === 'rule' && node.selector === selector)
  assert.ok(rule(':where(.dm-config, .dm-page) .v-label:not(.v-field-label--floating)'))
  assert.ok(rule(':where(.dm-config, .dm-page) .v-input--error .v-messages__message').nodes.some(decl => decl.prop === 'color' && decl.value === 'var(--dm-color-error)'))
  ast.walkDecls(decl => assert.ok(!['transform', '--v-field-label-scale'].includes(decl.prop), decl.toString()))
  for (const name of ['Config', 'Page']) {
    const styles = parse(sources[name]).descriptor.styles[0].content
    // Navigation is intentionally unchanged; business typography must reference the shared tokens.
    postcss.parse(styles).walkDecls(decl => {
      if (/dm-subtab/.test(decl.parent.selector || '')) return
      if (['font-size', 'font-weight', 'line-height'].includes(decl.prop)) assert.match(decl.value, /var\(--dm-text-/, `${name}: ${decl.parent.selector} ${decl.prop}`)
    })
  }
})

test('自动删种执行按钮保留动作对象，观察/真实删除/暂停颜色分离，构建展示零请求', () => {
  const script = parse(sources.Page).descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const setup = new Function('reactive', 'ref', 'computed', 'watch', 'nextTick', 'onMounted', 'onBeforeUnmount',
    'defineProps', 'defineEmits', 'getPluginApi', 'postPluginApi', 'postPluginJsonApi',
    `${script}\nreturn { autoremoveStatus, moduleCards };`)
  const noRequest = () => { throw new Error('构建按钮展示不得请求 API') }
  const page = setup(reactive, ref, computed, watch, nextTick, () => {}, () => {},
    () => ({ api: null, pluginId: 'DownloadManagerLocal' }), () => () => {}, noRequest, noRequest, noRequest)
  for (const [action, label, realColor] of [
    ['pause', '暂停任务', 'primary'], ['delete', '删除任务', 'error'], ['deletefile', '删除任务及文件', 'error'],
  ]) {
    for (const observing of [true, false]) {
      page.autoremoveStatus.value = { action, observe_only: observing }
      const button = page.moduleCards.value.find(card => card.key === 'autoremove').actions.find(item => item.key === 'autoremove-run')
      assert.equal(button.label, label)
      assert.equal(button.color, observing ? 'warning' : realColor)
    }
  }
})
