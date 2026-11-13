// Read-only contract metadata for the authorized transfer controls and wording update.
import fs from 'node:fs'
import { createHash } from 'node:crypto'
import { parse } from '@vue/compiler-sfc'
const source = fs.readFileSync('src/components/Config.vue', 'utf8')
const hash = text => createHash('sha256').update(text).digest('hex')
const descriptor = parse(source).descriptor
const normalized = source.replace(/\r\n/g, '\n')
const script = descriptor.scriptSetup.content.replace(/\r\n/g, '\n')
  .replace("import RowActionMenu from './RowActionMenu.vue'\n", '')
  .replace("import MultiLineInput from './MultiLineInput.vue'\n", '')
const start = script.indexOf('// 通知开关仅映射已有三态')
const end = script.indexOf('const removerActionItems', start)
console.log(JSON.stringify({
  fixture: {
    scriptSha256: hash(normalized.match(/<script setup>([\s\S]*?)<\/script>/)[1]),
    directives: [...descriptor.template.content.matchAll(/(?:v-[\w.-]+|[:@][\w:-]+)="[^"]*"/g)].map(m => m[0].replace(/\r\n/g, '\n')).sort(),
  },
  businessSha: hash((script.slice(0, start) + script.slice(end)).split('\n')
    .filter(line => !line.startsWith('        color: `var(--dm-hr-rule-')).join('\n')),
}, null, 2))
