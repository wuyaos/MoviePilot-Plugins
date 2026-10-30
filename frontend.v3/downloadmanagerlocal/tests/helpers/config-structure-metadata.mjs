// Read-only evidence for the P2-1d contract fixture update. Run from the frontend directory.
import { MODULE_ICONS } from '../../src/components/module-icons.js'
import fs from 'node:fs'
import { createHash } from 'node:crypto'
import { parse } from '@vue/compiler-sfc'
import { execFileSync } from 'node:child_process'
import { reactive, ref, computed, watch, effectScope } from 'vue'

const source = fs.readFileSync('src/components/Config.vue', 'utf8')
const priorSource = execFileSync('git', ['show', '74dabf82:frontend.v3/downloadmanagerlocal/src/components/Config.vue'], { encoding: 'utf8' })
const scriptOf = value => value.replace(/\r\n/g, '\n').match(/<script setup>([\s\S]*?)<\/script>/)[1]
const directivesOf = value => [...parse(value).descriptor.template.content.matchAll(/(?:v-[\w.-]+|[:@][\w:-]+)="[^"]*"/g)].map(match => match[0]).sort()
const hash = value => createHash('sha256').update(scriptOf(value)).digest('hex')
const count = values => { const out = {}; for (const value of values) out[value] = (out[value] || 0) + 1; return out }
const before = count(directivesOf(priorSource)), after = count(directivesOf(source))
const delta = [...new Set([...Object.keys(before), ...Object.keys(after)])].filter(key => before[key] !== after[key]).map(directive => ({
  directive, old: before[directive] || 0, new: after[directive] || 0,
  oldLines: priorSource.split(/\r?\n/).flatMap((line, index) => line.includes(directive) ? [index + 1] : []),
  lines: source.split(/\r?\n/).flatMap((line, index) => line.includes(directive) ? [index + 1] : []),
}))
async function inspect(value) {
  const calls = [], scope = effectScope()
  const setup = new Function('reactive', 'ref', 'computed', 'watch', 'onMounted', 'defineProps', 'defineEmits', scriptOf(value).replace(/^import .*$/gm, '').replace(/^/, `const MODULE_ICONS = ${JSON.stringify(MODULE_ICONS)};\n`) + '\nreturn { defaults, PANE_RESET_KEYS, saveConfig };')
  try {
    const state = scope.run(() => setup(reactive, ref, computed, watch, () => {}, () => ({ initialConfig: { enabled: true }, pluginId: 'DownloadManagerLocal', api: { put: async (_path, payload) => { calls.push(payload); return { success: true } } } }), () => () => {}))
    await state.saveConfig()
    return { defaults: state.defaults, reset: state.PANE_RESET_KEYS, keys: Object.keys(calls[0]).sort() }
  } finally { scope.stop() }
}
const current = await inspect(source), prior = await inspect(priorSource)
console.log(JSON.stringify({
  fixture: { scriptSha256: hash(source), directives: directivesOf(source) }, oldSha: hash(priorSource), delta,
  reset: current.reset, defaults: current.defaults,
  payloadKeyDelta: { removed: prior.keys.filter(key => !current.keys.includes(key)), added: current.keys.filter(key => !prior.keys.includes(key)) },
  pureCRLF: !source.replace(/\r\n/g, '').includes('\n'),
}, null, 2))
