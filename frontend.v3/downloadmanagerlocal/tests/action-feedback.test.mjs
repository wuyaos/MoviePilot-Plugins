import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { unwrapResponse } from '../src/components/api.js'

const pageSource = fs.readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')

test('unwrapResponse: standard envelope unwraps data; failure throws Error carrying business code', () => {
  assert.deepEqual(unwrapResponse({ success: true, message: '', data: { code: 0, msg: 'ok' } }), { code: 0, msg: 'ok' })

  for (const code of [2, 1]) {
    assert.throws(
      () => unwrapResponse({ success: false, message: `partial-${code}`, data: { code, msg: `m-${code}` } }),
      error => {
        assert.equal(error.code, code)
        assert.equal(error.message, `partial-${code}`)
        return true
      },
    )
  }
})

test('unwrapResponse: non-envelope responses pass through untouched', () => {
  const raw = { foo: 'bar' }
  assert.equal(unwrapResponse(raw), raw)
})

test('Page.vue: module action feedback is unified through applyActionResp/applyActionError', () => {
  assert.match(pageSource, /function applyActionResp\(resp, fallback\)/)
  assert.match(pageSource, /function applyActionError\(e, fallback\)/)
  // 统一口径：code=0 成功 / code=2 部分完成 / 其余失败；错误携带业务 code=2 时按部分完成收尾
  assert.match(pageSource, /code === 2 \? 'partial' : 'error'/)
  assert.match(pageSource, /if \(e\?\.code === 2\) return applyActionResp\(\{ code: 2, msg: e\?\.message \}, fallback\)/)
  // 展示层三分支：partial 映射 warning
  assert.match(pageSource, /actionLevel === 'partial' \? 'warning' : 'error'/)
  // 旧二值状态不再残留
  assert.doesNotMatch(pageSource, /actionOk/)
})

test('Page.vue: every legacy inline feedback site now routes through the shared helpers', () => {
  const uses = pageSource.match(/applyAction(?:Resp|Error)\(/g) || []
  // 9 个动作点 × 2（成功/失败路径）+ applyActionError 内部转发 = 19
  assert.ok(uses.length >= 19, `expected >=19 helper call sites, got ${uses.length}`)
  assert.doesNotMatch(pageSource, /actionOk\.value = resp\?\.code === 0/)
  assert.doesNotMatch(pageSource, /actionOk\.value = !!resp && resp\.code !== 1/)
})
