import assert from 'node:assert/strict'
import test from 'node:test'
import { h } from 'vue'
import { readFileSync } from 'node:fs'
import { loadSfc, render } from './helpers/load-sfc.mjs'
const Badges = await loadSfc('UploadSettingsBadges.vue')
const options = { components: { VChip: { setup: (_, { attrs, slots }) => () => h('span', { ...attrs, class: 'test-chip' }, slots.default?.()) } } }
const visible = html => html.replace(/<[^>]*>/g, '')
test('global before/after settings show two compact badges instead of visible JSON', async () => {
  for (const [value, expected] of [
    [{ upload_limit_bps: 81788928, upload_enabled: true, alternate_upload_limit_bps: 81788928, alternate_upload_enabled: true }, ['普通 78 MB/s', '备用 78 MB/s']],
    [{ upload_limit_bps: 92160000, upload_enabled: true, alternate_upload_limit_bps: 10240, alternate_upload_enabled: true }, ['普通 87.89 MB/s', '备用 0.01 MB/s']],
  ]) {
    const html = await render(Badges, { value }, {}, options)
    const text = visible(html)
    for (const label of expected) assert.ok(text.includes(label), text)
    assert.doesNotMatch(text, /upload_limit_bps|upload_enabled|[{]/)
    assert.equal((html.match(/class="test-chip"/g) || []).length, 2)
    assert.match(html, /title=".*upload_limit_bps/)
    assert.match(html, /tabindex="0"/)
  }
})
test('single settings distinguish disabled/unlimited/missing, retain real zero and false', async () => {
  for (const [value, expected] of [[{ limit_bps: 1048576, enabled: true }, '单种 1 MB/s'], [{ limit_bps: 0, enabled: true }, '单种 不限速'], [{ limit_bps: 1048576, enabled: false }, '单种 未启用'], [null, '—'], [0, '0'], [false, 'false'], [{ limit_bps: null }, '额度未知']]) {
    assert.ok(visible(await render(Badges, { value }, {}, options)).includes(expected))
  }
})
test('badge container prevents line wrapping and Page uses it for both actual cells', () => {
  const css = readFileSync(new URL('../src/components/UploadSettingsBadges.vue', import.meta.url), 'utf8')
  assert.match(css, /inline-flex/)
  assert.match(css, /white-space: nowrap/)
  const page = readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')
  for (const cell of ['before', 'after']) assert.ok(page.includes('#cell-' + cell + '="{ value }"><UploadSettingsBadges :value="value"'))
})
