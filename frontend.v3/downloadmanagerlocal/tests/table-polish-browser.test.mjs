import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import test from 'node:test'
import { build } from 'vite'
import vue from '@vitejs/plugin-vue'

const project = fileURLToPath(new URL('../', import.meta.url))
const chrome = process.env.CHROME_BIN || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome',
].find(file => fs.existsSync(file))

test('real Vuetify consumer: compact rows, shared selects, menu actions, full details and narrow scrolling', async () => {
  assert.ok(chrome, 'Set CHROME_BIN to Chrome/Chromium')
  const entry = fs.mkdtempSync(path.join(project, 'node_modules', '.dml-polish-'))
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'dml-polish-browser-'))
  const source = name => JSON.stringify(path.join(project, 'src/components', name + '.vue').replaceAll('\\', '/'))
  try {
    fs.writeFileSync(path.join(entry, 'index.html'), '<!doctype html><meta charset="utf-8"><div id="app"></div><pre id="result"></pre><script type="module" src="./entry.js"></script>')
    fs.writeFileSync(path.join(entry, 'entry.js'), `
import { createApp, nextTick, ref } from 'vue'
import { createVuetify } from 'vuetify'
import { VApp, VAvatar, VTable, VSelect, VBtn, VMenu, VList, VListItem, VListItemTitle, VIcon, VChip } from 'vuetify/components'
import 'vuetify/styles'
import Harness from './Harness.vue'
import { name, reason, events } from './state.js'
createApp(Harness).use(createVuetify({components:{VApp,VAvatar,VTable,VSelect,VBtn,VMenu,VList,VListItem,VListItemTitle,VIcon,VChip}})).mount('#app')
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
async function waitFor(fn, label) { for(let i=0;i<80;i++){const value=fn(); if(value)return value; await sleep(20)} throw Error(label) }
const menuItem = text => [...document.querySelectorAll('.v-overlay--active .v-list-item')].find(node => node.textContent.trim() === text)
const font = node => { const s=getComputedStyle(node); return [s.fontFamily,s.fontSize,s.fontWeight,s.letterSpacing] }
const controls = () => [...document.querySelectorAll('.dm-compact-select')].map(node => Math.round(node.getBoundingClientRect().height))
async function inspect(width) {
  document.querySelector('.dm-page').style.width=width+'px'
  await nextTick(); await sleep(30)
  const row = document.querySelector('.dm-table tbody tr')
  const cells = [...row.querySelectorAll('.dm-table-cell-text')]
  const scroll=document.querySelector('.dm-table-scroll')
  return {width, rowHeight:row.getBoundingClientRect().height, textHeights:cells.map(n=>n.getBoundingClientRect().height), controls:controls(),
    fullText:cells.every(n=>n.textContent.length>300), tableOverflow:scroll.scrollWidth>scroll.clientWidth,
    outerOverflow:document.querySelector('.dm-page').scrollWidth-document.querySelector('.dm-page').clientWidth,
    actionButtons:row.querySelectorAll('td:last-child button').length}
}
try {
  const desktop=await inspect(1100)
  const button=document.querySelector('.fixture-action'), badge=document.querySelector('.fixture-badge')
  const roles={buttonRadius:getComputedStyle(button).borderRadius,badgeRadius:getComputedStyle(badge).borderRadius,avatar:document.querySelector('.v-avatar').getBoundingClientRect().width,nativeTable:document.querySelectorAll('.v-table table').length}
  const selectedFont=font(document.querySelector('.dm-compact-select .v-select__selection-text'))
  const narrow=await inspect(360)
  const trigger=document.querySelector('[aria-label="更多操作：测试归档"]')
  trigger.click()
  ;(await waitFor(()=>menuItem('不可用'),'disabled item')).click()
  await nextTick()
  const blocked=events.length===0
  if (!menuItem('重试')) { trigger.click(); await nextTick() }
  ;(await waitFor(()=>menuItem('重试'),'retry item')).click()
  await sleep(150)
  const menuClosed=!document.querySelector('.v-overlay--active .v-list-item')
  const input=document.querySelector('[aria-label="每页条数"]')
  input.focus()
  input.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true, cancelable:true}))
  const option=await waitFor(()=>menuItem('50'),'page size item')
  const optionFont=font(option.querySelector('.v-list-item-title'))
  option.click()
  await sleep(150)
  const toggle=document.querySelector('[aria-label="展开记录详情"]')
  toggle.click(); await nextTick()
  const detail=document.querySelector('.dm-record-details')
  const fullDetails=detail.textContent.includes(name)&&detail.textContent.includes(reason)
  toggle.click(); await nextTick()
  document.getElementById('result').textContent=JSON.stringify({desktop,narrow,roles,selectedFont,optionFont,blocked,menuClosed,events,fullDetails,collapsed:!document.querySelector('.dm-record-details')})
} catch(error) {document.getElementById('result').textContent=JSON.stringify({error:error.message})}
`)
    fs.writeFileSync(path.join(entry, 'state.js'), "export const name='Long.Movie.Title.'.repeat(35); export const reason='A full failure reason with details. '.repeat(30); export const events=[]")
    fs.writeFileSync(path.join(entry, 'Harness.vue'), `<script setup>
import { ref } from 'vue'
import Table from ${source('ModuleTable')}
import Select from ${source('CompactSelect')}
import Menu from ${source('RowActionMenu')}
import Details from ${source('RecordDetails')}
import Header from ${source('ModuleHeader')}
import { name, reason, events } from './state.js'
const size=ref(20), filter=ref('all')
const rows=[{id:'a',name,reason}]
const columns=[{key:'name',label:'名称',lines:2},{key:'reason',label:'原因',lines:2}]
const actions=[{key:'retry',label:'重试',icon:'mdi-refresh'},{key:'delete',label:'删除记录',icon:'mdi-delete',color:'error'},{key:'blocked',label:'不可用',disabled:true}]
</script>
<template><VApp><div class="dm-page"><Header title="测试模块" icon="mdi-transfer" enabled /><VBtn class="fixture-action" size="small" variant="tonal" color="primary">刷新</VBtn><VChip class="fixture-badge" size="small" variant="tonal">已启用</VChip><Table title="失败归档" :rows="rows" :columns="columns" :total="120" :page-size="size" @update:page-size="size=$event; events.push(['size',$event])" @update:page="events.push(['page',$event])">
<template #filters><Select v-model="filter" label="结果" :items="[{title:'全部结果',value:'all'},{title:'失败',value:'failed'}]" /></template>
<template #toolbar><VBtn size="small" variant="tonal" color="primary">清归档</VBtn></template>
<template #rowActions><Menu label="测试归档" :actions="actions" @select="events.push(['action',$event])" /></template>
<template #expand="{row}"><Details :record="row" /></template>
</Table></div></VApp></template>`)
    await build({ configFile: false, root: entry, base: './', plugins: [vue()], logLevel: 'error',
      build: { target: 'esnext', outDir: path.join(output, 'site'), emptyOutDir: true },
    })
    const built = path.join(output, 'site/index.html')
    // Only fixture framing; the controls/table/menu all consume the real SFC CSS.
    fs.appendFileSync(built, '<style>.dm-page{--v-border-color:0,0,0;--v-border-opacity:.12;max-width:100%;padding:4px}.dm-module-table-filters .dm-compact-select{width:150px}#result{white-space:pre-wrap}</style>')
    const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--allow-file-access-from-files',
      '--virtual-time-budget=6000', `--user-data-dir=${path.join(output, 'profile')}`, '--dump-dom', pathToFileURL(built).href],
    { encoding: 'utf8', timeout: 30000, maxBuffer: 2 * 1024 * 1024 })
    assert.equal(result.error, undefined, result.error?.message)
    assert.equal(result.status, 0, result.stderr)
    const match = result.stdout.match(/<pre id="result">([^<]+)<\/pre>/)
    assert.ok(match, result.stderr + result.stdout.slice(-1000))
    const measured = JSON.parse(match[1].replaceAll('&quot;', '"').replaceAll('&amp;', '&'))
    assert.equal(measured.error, undefined, JSON.stringify(measured))
    for (const layout of [measured.desktop, measured.narrow]) {
      assert.ok(layout.rowHeight <= 64, JSON.stringify(layout))
      assert.ok(layout.textHeights.every(height => height <= 40), JSON.stringify(layout))
      assert.deepEqual(layout.controls, [28, 28])
      assert.equal(layout.fullText, true)
      assert.equal(layout.actionButtons, 1)
      assert.ok(layout.outerOverflow <= 1, JSON.stringify(layout))
    }
    assert.equal(measured.narrow.tableOverflow, true)
    assert.deepEqual(measured.selectedFont, measured.optionFont, 'selected value and teleported menu must share typography')
    assert.notEqual(measured.roles.buttonRadius, measured.roles.badgeRadius, 'status chips must not look like action buttons')
    assert.equal(measured.roles.avatar, 30)
    assert.equal(measured.roles.nativeTable, 1)
    assert.equal(measured.blocked, true)
    assert.equal(measured.menuClosed, true)
    assert.deepEqual(measured.events, [['action', 'retry'], ['size', 50], ['page', 1]])
    assert.equal(measured.fullDetails, true)
    assert.equal(measured.collapsed, true)
    console.log('Table polish browser measurements:', JSON.stringify(measured))
  } finally {
    fs.rmSync(entry, {recursive:true,force:true,maxRetries:5,retryDelay:100})
    fs.rmSync(output, {recursive:true,force:true,maxRetries:5,retryDelay:100})
  }
})
