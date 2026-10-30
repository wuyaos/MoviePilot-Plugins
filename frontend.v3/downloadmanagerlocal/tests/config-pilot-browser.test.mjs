import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'
import test from 'node:test'
import { build } from 'vite'
import vue from '@vitejs/plugin-vue'

const project = fileURLToPath(new URL('../', import.meta.url))
const chrome = process.env.CHROME_BIN || ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe', '/usr/bin/chromium', '/usr/bin/google-chrome'].find(p => fs.existsSync(p))

test('real Config consumer: title dividers, 36px fields, native compact switches, wrapped multi-inputs and narrow layout', async () => {
  assert.ok(chrome, 'Set CHROME_BIN')
  const entry = fs.mkdtempSync(path.join(project, 'node_modules', '.dml-config-pilot-'))
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'dml-config-pilot-'))
  try {
    const configPath = JSON.stringify(path.join(project, 'src/components/Config.vue').replaceAll('\\', '/'))
    fs.writeFileSync(path.join(entry, 'index.html'), '<!doctype html><meta charset="utf-8"><div id="app"></div><pre id="result"></pre><script type="module" src="./entry.js"></script>')
    fs.writeFileSync(path.join(entry, 'entry.js'), `
import { createApp, h, nextTick } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import 'vuetify/styles'
import Config from ${configPath}
const writes=[]
const api={ get:async(path)=>path==='media/category'?{success:true,message:'',data:{电影:['电影','新分类'],电视剧:['剧集']}}:[], put:async()=>{writes.push('put');throw Error('Unexpected save')}, post:async()=>{writes.push('post');throw Error('Unexpected action')} }
const vuetify=createVuetify({components:{...components,VCronField:components.VTextField}})
createApp({render:()=>h(components.VApp,()=>h('div',{class:'fixture',style:'width:1100px;max-width:100%'},[h(Config,{pluginId:'DownloadManagerLocal',api,initialConfig:{enabled:true,tag_all_cat:['电影'],tag_all_cat_rename:['Movies'],failcleanup_enabled:true,failcleanup_observe_only:false,transfer_fallback_enabled:false,hr_enable_site_config:true,hr_site_config_str:"- site_name: 'Fixture'\\n  hr_duration: 72\\n",hr_notify:'none',hr_protection_enabled:false,hr_sites:['SiteName'.repeat(25),'SiteB'],hr_exclude_tags:['VeryLongTagName'.repeat(25),'TagB']}})]))}).use(vuetify).mount('#app')
const sleep=ms=>new Promise(r=>setTimeout(r,ms))
const button=text=>[...document.querySelectorAll('button')].find(n=>n.textContent.trim()===text)
async function inspect(width,theme){
  document.querySelector('.fixture').style.width=width+'px'
  vuetify.theme.global.name.value=theme
  await nextTick();await sleep(80)
  const pane=document.querySelector('.dm-pane.dm-transfer-form')
  const fields=[...pane.querySelectorAll('.v-text-field .v-field')]
  const switches=[...pane.querySelectorAll('.v-switch__track')]
  const sections=[...pane.querySelectorAll('.dm-form-section')]
  const post=pane.querySelector('[aria-label=转移后操作] .dm-switch-group')
  const postTops=[...post.querySelectorAll('.v-switch')].map(n=>Math.round(n.getBoundingClientRect().top))
  return {width,theme,postTops,outerOverflow:document.querySelector('.fixture').scrollWidth-document.querySelector('.fixture').clientWidth,overflow:pane.scrollWidth-pane.clientWidth,fields:fields.map(n=>n.getBoundingClientRect().height),tracks:switches.map(n=>n.getBoundingClientRect().height),sections:sections.length,icons:sections.filter(n=>n.querySelector('.dm-form-section-icon')).length,divider:sections.map(n=>getComputedStyle(n.querySelector('.dm-form-section-line')).display),fieldX:fields.slice(0,2).map(n=>Math.round(n.getBoundingClientRect().left))}
}
try {
  await sleep(100)
  const layouts=[]
  for(const width of [1100,360])for(const theme of ['light','dark'])layouts.push(await inspect(width,theme))
  const pane=document.querySelector('.dm-pane.dm-transfer-form')
  const fallback=[...pane.querySelectorAll('.v-switch')].find(n=>n.textContent.trim()==='兜底扫描')
  const fallbackInput=[...pane.querySelectorAll('.v-text-field')].find(n=>n.textContent.includes('兜底间隔')).querySelector('input[type=number]')
  const initiallyDisabled=fallbackInput.disabled
  fallback.querySelector('input[type=checkbox]').click();await nextTick()
  const enabledAfterClick=!fallbackInput.disabled
  const hrNav=[...document.querySelectorAll('.dm-nav-item')].find(n=>n.textContent.includes('H&R 管理'))
  hrNav.click();await nextTick();await sleep(80)
  const hrLayouts=[]
  for(const width of [1100,360])for(const theme of ['light','dark']){
    document.querySelector('.fixture').style.width=width+'px';vuetify.theme.global.name.value=theme;await nextTick();await sleep(80)
    const pane=document.querySelector('.dm-pane.dm-hr-form')
    const sections=[...pane.querySelectorAll('.dm-form-section')]
    const singles=[...pane.querySelectorAll('.v-text-field:not(.v-combobox):not(.v-select) .v-field')]
    const controls=[...sections[0].querySelectorAll('.dm-switch-group .v-switch')]
    const chips=[...pane.querySelectorAll('.v-chip')]
    const notify=pane.querySelector('[aria-label=基础设置] .v-select').getBoundingClientRect()
    const cron=[...pane.querySelectorAll('.v-text-field')].find(n=>n.textContent.includes('汇总计划'))
    const textFields=[...pane.querySelectorAll('.v-text-field')]
    const period=textFields.find(n=>n.textContent.includes('检查间隔')).getBoundingClientRect()
    const scopes=sections[1].querySelector('.dm-field-row').getBoundingClientRect()
    hrLayouts.push({width,theme,fieldRowWidths:[...pane.querySelectorAll('.dm-field-row')].map(n=>Math.round(n.getBoundingClientRect().width)),basicInputWidths:[...pane.querySelectorAll('.dm-field-row .dm-field > .v-input')].map(n=>Math.round(n.getBoundingClientRect().width)),basicRows:[...sections[0].querySelectorAll('.dm-field-row')].map(n=>n.querySelectorAll('.dm-field').length),trackingRows:[...sections[1].querySelectorAll('.dm-field-row')].map(n=>n.querySelectorAll('.dm-field').length),titles:sections.map(n=>n.getAttribute('aria-label')),fields:singles.map(n=>n.getBoundingClientRect().height),tracks:[...pane.querySelectorAll('.v-switch__track')].map(n=>n.getBoundingClientRect().height),switchTops:controls.map(n=>Math.round(n.getBoundingClientRect().top)),overflow:pane.scrollWidth-pane.clientWidth,outerOverflow:document.querySelector('.fixture').scrollWidth-document.querySelector('.fixture').clientWidth,chipOverflow:chips.some(n=>n.getBoundingClientRect().right>n.closest('.v-input').getBoundingClientRect().right+1),summaryDisabled:cron.querySelector('input').disabled,periodBeforeScopes:period.top<scopes.top,notificationX:Math.round(notify.left),summaryX:Math.round(cron.getBoundingClientRect().left),riskVisible:pane.textContent.includes('未达标 H&R 任务可能被删除')})
  }
  const hrPane=document.querySelector('.dm-pane.dm-hr-form')
  const notifyPane=document.querySelector('.dm-hr-basic-form')
  const notifySwitch=[...notifyPane.querySelectorAll('.v-switch')].find(n=>n.textContent.trim()==='发送通知').querySelector('input')
  const notifySelect=[...notifyPane.querySelectorAll('.v-select')].find(n=>n.textContent.includes('通知模式'))
  const notifyOffInitially=!notifySwitch.checked&&notifySelect.querySelector('input').disabled
  notifySwitch.click();await nextTick()
  notifySelect.querySelector('input').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));await nextTick();await sleep(200)
  const errorOption=[...document.querySelectorAll('.v-overlay--active .v-list-item')].find(n=>n.textContent.trim()==='仅异常')
  if(!errorOption)throw Error('Notification options: '+[...document.querySelectorAll('.v-overlay--active .v-list-item')].map(n=>n.textContent.trim()).join(','))
  errorOption.click();await nextTick();await sleep(100)
  const choseError=notifySelect.textContent.includes('仅异常')
  notifySwitch.click();await nextTick()
  const notifyDisabledAgain=notifySelect.querySelector('input').disabled
  notifySwitch.click();await nextTick()
  const restoredError=notifySelect.textContent.includes('仅异常')
  notifySwitch.click();await nextTick()
  const protection=[...hrPane.querySelectorAll('.v-switch')].find(n=>n.textContent.trim()==='删除保护')
  protection.querySelector('input[type=checkbox]').click();await nextTick()
  const riskCleared=!hrPane.textContent.includes('未达标 H&R 任务可能被删除')
  button('站点规则').click();await nextTick();await sleep(100)
  const sitePane=document.querySelector('.dm-hr-sites-form')
  sitePane.querySelector('button[aria-label="更多操作：Fixture"]').click();await sleep(150)
  ;[...document.querySelectorAll('.v-overlay--active .v-list-item')].find(n=>n.textContent.trim()==='编辑').click();await nextTick();await sleep(150)
  ;[...sitePane.querySelectorAll('.v-switch')].find(n=>n.textContent.includes('显示继承字段')).querySelector('input').click();await nextTick()
  const siteLayouts=[]
  for(const width of [1100,360])for(const theme of ['light','dark']){
    document.querySelector('.fixture').style.width=width+'px';vuetify.theme.global.name.value=theme;await nextTick();await sleep(80)
    const scroll=sitePane.querySelector('.v-table__wrapper')
    const fitBadges=[...sitePane.querySelectorAll('.dm-hr-values .dm-hr-rule-badge')].map(n=>({width:n.getBoundingClientRect().width,slot:n.closest('.dm-hr-chip').getBoundingClientRect().width,content:n.querySelector('.v-chip__content').getBoundingClientRect().width,clipped:n.querySelector('.v-chip__content > span').scrollWidth>n.querySelector('.v-chip__content > span').clientWidth}))
    sitePane.querySelector('.dm-hr-rules-more').click();await nextTick();await sleep(100)
    const allBadges=[...sitePane.querySelectorAll('.dm-hr-values .dm-hr-rule-badge'),...document.querySelectorAll('.v-overlay--active .dm-hr-rule-badge')]
    const ruleColors=Object.fromEntries(allBadges.map(n=>[n.dataset.ruleKey,getComputedStyle(n).color]))
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await nextTick();await sleep(100)
    const inherited=sitePane.querySelector('.dm-hr-chip--inherit')
    const inheritedBadge=inherited.querySelector('.dm-hr-rule-badge')
    const explicitBadge=sitePane.querySelector('.dm-hr-chip:not(.dm-hr-chip--inherit):not(.dm-hr-chip--more) .dm-hr-rule-badge')
    const styles={headWeight:getComputedStyle(sitePane.querySelector('th')).fontWeight,cellSize:getComputedStyle(sitePane.querySelector('td')).fontSize,badgeRadius:getComputedStyle(inheritedBadge).borderRadius,badgeHeight:getComputedStyle(inheritedBadge).height,distinct:getComputedStyle(inheritedBadge).color!==getComputedStyle(explicitBadge).color,mark:inheritedBadge.textContent.trim()}
    siteLayouts.push({width,theme,styles,fitBadges,ruleColors,fieldRowWidths:[...sitePane.querySelectorAll('.dm-field-row')].map(n=>Math.round(n.getBoundingClientRect().width)),editorGridWidths:[...sitePane.querySelectorAll('.dm-hr-editor-grid')].map(n=>Math.round(n.getBoundingClientRect().width)),editorInputWidths:[...sitePane.querySelectorAll('.dm-hr-editor-grid .v-input')].map(n=>Math.round(n.getBoundingClientRect().width)),ruleGridRows:getComputedStyle(sitePane.querySelector('.dm-hr-values')).gridTemplateRows.split(' ').length,ruleGridHeight:Math.round(sitePane.querySelector('.dm-hr-values').getBoundingClientRect().height),summaryBadgeCount:sitePane.querySelectorAll('.dm-hr-values > .dm-hr-chip .dm-hr-rule-badge').length,overflowCount:sitePane.querySelector('.dm-hr-rules-more')?.textContent.trim()||'',titles:[...sitePane.querySelectorAll('.dm-form-section')].map(n=>n.getAttribute('aria-label')),overflow:sitePane.scrollWidth-sitePane.clientWidth,outerOverflow:document.querySelector('.fixture').scrollWidth-document.querySelector('.fixture').clientWidth,scrollable:scroll.scrollWidth>scroll.clientWidth,fields:[...sitePane.querySelectorAll('.v-text-field:not(.v-combobox):not(.v-select):not(.v-textarea) .v-field')].map(n=>n.getBoundingClientRect().height),trackerCount:sitePane.querySelectorAll('.dm-hr-trackers .dm-multi-line-input').length,menuCount:sitePane.querySelectorAll('button[aria-label^="更多操作："]').length,editorCount:sitePane.querySelectorAll('.dm-hr-editor').length})
  }
  sitePane.querySelector('.dm-hr-rules-more').click();await nextTick();await sleep(100)
  const overflowMenuCount=document.querySelectorAll('.v-overlay--active .dm-hr-rule-badge').length
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await nextTick()
  const ruleToggle=sitePane.querySelector('input[aria-label="Fixture规则启用"]')
  ruleToggle.click();await nextTick()
  const fallsBack=sitePane.textContent.includes('已停用，回退全局')
  ruleToggle.click();await nextTick()
  const reEnabled=!sitePane.textContent.includes('已停用，回退全局')
  const moduleLayouts=[]
  for(const name of ['自动删种','失败清理','种子重命名','分类与标签','上传限速']) {
    [...document.querySelectorAll('.dm-nav-item')].find(n=>n.textContent.includes(name)).click();await nextTick()
    for(const sub of [...document.querySelectorAll('.dm-subtab')]) {
      sub.click();await nextTick()
      for(const width of [1100,360])for(const theme of ['light','dark']) {
        document.querySelector('.fixture').style.width=width+'px';vuetify.theme.global.name.value=theme;await nextTick();await sleep(20)
        const pane=[...document.querySelectorAll('.dm-pane')].find(n=>getComputedStyle(n).display!=='none')
        const footer=document.querySelector('.dm-actions')
        const risk=[...pane.querySelectorAll('.dm-risk')].find(n=>getComputedStyle(n).display!=='none')
        const nextFields=risk?.nextElementSibling
        moduleLayouts.push({name,sub:sub.textContent.trim(),width,theme,overflow:pane.scrollWidth-pane.clientWidth,outer:document.querySelector('.fixture').scrollWidth-document.querySelector('.fixture').clientWidth,footerOverflow:footer.scrollWidth-footer.clientWidth,headerTrack:document.querySelector('.dm-header .v-switch__track').getBoundingClientRect().height,footerHeights:[...footer.querySelectorAll('.v-btn')].map(n=>n.getBoundingClientRect().height),footerTonal:[...footer.querySelectorAll('.v-btn')].every(n=>n.classList.contains('v-btn--variant-tonal')),riskGap:risk&&nextFields?nextFields.getBoundingClientRect().top-risk.getBoundingClientRect().bottom:null,heights:[...pane.querySelectorAll('.v-input:not(.v-select--multiple):not(.v-combobox):not(.v-textarea) .v-field')].map(n=>n.getBoundingClientRect().height)})
      }
    }
  }
  button('限速规则').click();await nextTick()
  const uploadPane=document.querySelector('[class*=dm-pane][style*="display"]')
  const combo=document.querySelector('.dm-upload-add-site input')
  combo.value='CustomFixture';combo.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
  button('添加站点').click();await nextTick()
  const customSiteAdded=[...document.querySelectorAll('.dm-upload-site-row')].some(n=>n.textContent.includes('CustomFixture'))
  ;[...document.querySelectorAll('.dm-nav-item')].find(n=>n.textContent.includes('分类与标签')).click();await nextTick()
  button('映射规则').click();await nextTick()
  const catRow=document.querySelector('.dm-cat-row:not(.dm-cat-row--head)')
  const catSingleInput=catRow.querySelectorAll('.v-text-field').length===1&&catRow.querySelector('.dm-cat-source').textContent.includes('电影')
  const targetInput=catRow.querySelector('.v-text-field input')
  targetInput.value='Films';targetInput.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
  const catSourceEdited=catRow.querySelector('.dm-cat-source').textContent.trim()==='电影'&&!catRow.querySelector('.dm-cat-source input')&&catRow.querySelector('.v-text-field input').value==='Films'&&[...document.querySelectorAll('.dm-cat-source')].some(n=>n.textContent.trim()==='新分类')
  ;[...document.querySelectorAll('.dm-nav-item')].find(n=>n.textContent.includes('转移做种')).click();await nextTick()
  button('任务列表').click();await nextTick()
  button('添加任务').click();await sleep(200)
  document.querySelector('.v-overlay--active .v-overlay__content').style.maxWidth='312px'
  const dialog=document.querySelector('.v-overlay--active .dm-transfer-form')
  const multi=dialog.querySelectorAll('.dm-multi-value-input')
  const input=multi[0].querySelector('input')
  input.focus();input.value='VeryLongCategoryName'.repeat(8);input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
  input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));await nextTick();await sleep(80)
  input.value='CategoryB';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
  input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));await nextTick()
  const chips=multi[0].querySelectorAll('.v-chip')
  const dialogOverflow=dialog.scrollWidth-dialog.clientWidth
  const chipOverflow=[...chips].some(n=>n.getBoundingClientRect().right>multi[0].getBoundingClientRect().right+1)
  const wrapped=chips[0].getBoundingClientRect().top!==chips[1].getBoundingClientRect().top
  chips[0].querySelector('.v-chip__close').click();await nextTick()
  const chipsAfterRemoval=multi[0].querySelectorAll('.v-chip').length
  const tagInput=multi[0].querySelector('input');tagInput.focus();tagInput.value='普通标签Fixture';tagInput.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
  tagInput.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:229,isComposing:true,bubbles:true}));await nextTick()
  const imeChipCount=multi[0].querySelectorAll('.v-chip').length
  tagInput.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,bubbles:true}));await nextTick()
  const enteredChip=[...multi[0].querySelectorAll('.v-chip')].some(n=>n.textContent.includes('普通标签Fixture'))
  document.getElementById('result').textContent=JSON.stringify({customSiteAdded,catSingleInput,catSourceEdited,imeChipCount,enteredChip,moduleLayouts,notifyOffInitially,choseError,notifyDisabledAgain,restoredError,siteLayouts,overflowMenuCount,fallsBack,reEnabled,hrLayouts,riskCleared,layouts,initiallyDisabled,enabledAfterClick,multi:multi.length,chips:chips.length,dialogOverflow,chipOverflow,wrapped,chipsAfterRemoval,writes})
}catch(error){document.getElementById('result').textContent=JSON.stringify({error:error.message,stack:error.stack})}
`)
    await build({ configFile: false, root: entry, base: './', plugins: [vue()], logLevel: 'error', build: { target: 'esnext', outDir: path.join(output, 'site'), emptyOutDir: true } })
    const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--allow-file-access-from-files', '--window-size=1280,1000', '--virtual-time-budget=8000', `--user-data-dir=${path.join(output, 'profile')}`, '--dump-dom', pathToFileURL(path.join(output, 'site/index.html')).href], { encoding: 'utf8', timeout: 45000, maxBuffer: 3 * 1024 * 1024 })
    assert.equal(result.error, undefined, result.error?.message)
    assert.equal(result.status, 0, result.stderr)
    const match = result.stdout.match(/<pre id="result">([^<]+)<\/pre>/)
    assert.ok(match, result.stdout.slice(-1500))
    const report = JSON.parse(match[1].replaceAll('&quot;', '"').replaceAll('&amp;', '&'))
    assert.equal(report.error, undefined, JSON.stringify(report))
    assert.equal(report.imeChipCount, report.chipsAfterRemoval)
    assert.equal(report.enteredChip, true)
    assert.equal(report.customSiteAdded,true)
    assert.equal(report.catSingleInput,true)
    assert.equal(report.catSourceEdited,true)
    for(const row of report.moduleLayouts){assert.equal(row.headerTrack,24);assert.ok(row.footerHeights.every(h=>h===28),JSON.stringify(row));assert.equal(row.footerTonal,true);if(row.name==='失败清理')assert.ok(row.riskGap>=16,JSON.stringify(row));}
    assert.equal(report.moduleLayouts.length,32)
    for(const row of report.moduleLayouts){ assert.ok(row.overflow<=1 && row.outer<=1 && row.footerOverflow<=1,JSON.stringify(row)); assert.ok(row.heights.every(h=>h===36),JSON.stringify(row)) }
    for (const row of report.layouts) {
      assert.ok(row.overflow <= 1, JSON.stringify(report))
      assert.ok(row.outerOverflow <= 1, JSON.stringify(report))
      assert.equal(row.sections, 3)
      assert.equal(row.icons, 3)
      assert.ok(row.fields.every(height => height === 36), JSON.stringify(report))
      assert.ok(row.tracks.every(height => height === 24), JSON.stringify(report))
      if (row.width === 360) assert.equal(row.fieldX[0], row.fieldX[1], JSON.stringify(report))
      else assert.notEqual(row.fieldX[0], row.fieldX[1], JSON.stringify(report))
      if (row.width === 1100) assert.equal(new Set(row.postTops).size, 1, JSON.stringify(report))
    }
    for (const row of report.hrLayouts) {
      assert.deepEqual(row.titles, ['基础设置','跟踪策略','保护与记录'])
      assert.ok(row.overflow <= 1 && row.outerOverflow <= 1, JSON.stringify(row))
      assert.ok(row.fields.every(h => h === 36), JSON.stringify(row))
      assert.ok(row.tracks.every(h => h === 24), JSON.stringify(row))
      assert.equal(row.chipOverflow, false, JSON.stringify(row))
      assert.equal(row.summaryDisabled, true)
      assert.equal(row.periodBeforeScopes, true)
      assert.equal(row.riskVisible, true)
      assert.ok(row.fieldRowWidths.every(w => w <= 832 && w >= 257), JSON.stringify(row))
      assert.ok(row.basicInputWidths.every(w => w <= 220 && w >= 176), JSON.stringify(row))
      assert.deepEqual(row.basicRows, [3])
      assert.deepEqual(row.trackingRows, [3, 2])
      if (row.width === 1100) { assert.equal(new Set(row.switchTops).size, 1); assert.notEqual(row.notificationX, row.summaryX) }
      else assert.equal(row.notificationX, row.summaryX)
    }
    assert.equal(report.siteLayouts.length, 4)
    assert.equal(report.fallsBack, true)
    assert.equal(report.reEnabled, true)
    for (const row of report.siteLayouts) {
      assert.deepEqual(row.titles, ['全局规则', '站点规则'])
      assert.ok(row.overflow <= 1 && row.outerOverflow <= 1, JSON.stringify(row))
      assert.ok(row.fieldRowWidths.every(w => w <= 832 && w >= 257), JSON.stringify(row))
      assert.ok(row.editorGridWidths.every(w => w <= 832 && w >= 257), JSON.stringify(row))
      assert.ok(row.editorInputWidths.every(w => w <= 220 && w >= 176), JSON.stringify(row))
      if (row.width === 1100) assert.equal(row.editorInputWidths[0], row.editorInputWidths[1], JSON.stringify(row))
      else assert.ok(row.editorInputWidths.every(w => w <= row.editorGridWidths[0] && w >= 176), JSON.stringify(row))
      assert.ok(row.fields.every(h => h === 36), JSON.stringify(row))
      assert.equal(row.trackerCount, 1)
      assert.equal(row.menuCount, 1)
      assert.equal(row.editorCount, 1)
      assert.ok(Number(row.styles.headWeight)>=500)
      assert.equal(row.styles.cellSize,'13px')
      assert.equal(Object.keys(row.ruleColors).length,8,JSON.stringify(row))
      assert.equal(new Set(Object.values(row.ruleColors)).size,8,JSON.stringify(row.ruleColors))
      assert.ok(row.fitBadges.every(b=>b.width<=b.content+14),JSON.stringify(row.fitBadges))
      assert.ok(row.fitBadges.every(b=>!b.clipped),JSON.stringify(row.fitBadges))
      assert.ok(row.ruleGridRows <= 2, JSON.stringify(row))
      assert.ok(row.ruleGridHeight <= 48, JSON.stringify(row))
      assert.ok(row.summaryBadgeCount <= 3, JSON.stringify(row))
      if (row.overflowCount) assert.match(row.overflowCount,/^\+\d+项$/)
      assert.equal(row.styles.badgeRadius,'9999px')
      assert.ok(parseFloat(row.styles.badgeHeight)>=22)
      assert.equal(row.styles.distinct,true)
      assert.match(row.styles.mark,/继承/)
      assert.equal(report.overflowMenuCount, Number(report.siteLayouts.at(-1).overflowCount.match(/\d+/)[0]))
      if (row.width === 360) assert.equal(row.scrollable, true)
    }
    assert.equal(report.hrLayouts.length, 4)
    assert.equal(report.notifyOffInitially,true)
    assert.equal(report.choseError,true)
    assert.equal(report.notifyDisabledAgain,true)
    assert.equal(report.restoredError,true)
    assert.equal(report.riskCleared, true)
    assert.equal(report.initiallyDisabled, true)
    assert.equal(report.enabledAfterClick, true)
    assert.equal(report.multi, 3)
    assert.equal(report.chips, 2)
    assert.ok(report.dialogOverflow <= 1, JSON.stringify(report))
    assert.equal(report.chipOverflow, false)
    assert.equal(report.wrapped, true)
    assert.equal(report.chipsAfterRemoval, 1)
    assert.deepEqual(report.writes, [])
    console.log('Config pilot browser evidence:', JSON.stringify(report))
  } finally { fs.rmSync(entry, { recursive: true, force: true }); fs.rmSync(output, { recursive: true, force: true }) }
})
