"""3.5.1 UI contracts and interaction state; rendered checks use the host browser."""
from pathlib import Path
import subprocess

SRC = Path(__file__).parents[3] / 'plugins.v3/autoptcheckin/frontend/src'


def test_config_expand_collapse_and_batch_confirmation():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    functions = source.split('const openSites = ref([])', 1)[1].split('const customDialog = ref', 1)[0]
    start = functions.index('const pickerAnchor')
    end = functions.index('function togglePicker')
    functions = functions[:start] + functions[end:]
    script = """
const assert = require('node:assert/strict');
const ref = value => ({value});
const selected = ref([{id:'alpha'}, {id:'hotel'}, {id:'tango'}]);
const groupKey = site => site.id[0];
const openGroups = ref([]), openSites = ref([]);
const model = {enabled_sites:['alpha']};
""" + functions + """
expandSites();
assert.deepEqual(openSites.value, ['alpha','hotel','tango']);

toggleSite('hotel');
assert.deepEqual(openSites.value, ['alpha','tango']);
collapseSites();
assert.deepEqual(openSites.value, []);

expandSites();
assert.equal(openSites.value.length, 3);
togglePicker();
pendingSites.value.push('hotel','tango');
assert.deepEqual(model.enabled_sites, ['alpha']);
confirmSites();
assert.deepEqual(model.enabled_sites, ['alpha','hotel','tango']);
assert.equal(pickerOpen.value, false);
togglePicker();
pendingSites.value = [];
pickerOpen.value = false;
togglePicker();
assert.deepEqual(pendingSites.value, model.enabled_sites);
"""
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
    assert ':open="openSites.includes(site.id)"' in source
    assert '<summary @click.prevent>' in source
    assert 'class="btn ghost mini expand-icon"' in source
    assert '@click.prevent="toggleSite(site.id)"' in source
    assert 'site-metadata' in source
    assert '@click="expandSites"' in source and '@click="collapseSites"' in source
    assert 'v-model="pendingSites"' in source
    assert '@click="confirmSites"' in source


def test_site_name_badges_and_equal_data_grid():
    css = (SRC / 'preview.css').read_text(encoding='utf8')
    assert 'min-width:120px; flex:0 0 120px;' in css
    assert '.enabled-site-list .badges {display:flex; align-items:center;' in css
    assert '.data-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-rows:1fr;' in css
    assert '.data-grid .site-card:last-child' not in css
    assert '.grid,.grid.three,.data-grid{grid-template-columns:1fr}' in css
    assert 'v-if="!stats.sites.length"' in (SRC / 'Page.vue').read_text(encoding='utf8')


def test_config_summary_actions_and_emulate_contract():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    summary = source.split(':open="openSites.includes(site.id)"><summary', 1)[1].split('</summary>', 1)[0]
    assert summary.count('type="checkbox"') == 2
    assert 'v-if="site.login_capable"' in summary
    assert 'cfBadge' in summary and 'credentialBadge' in summary
    assert summary.index('site.source') < summary.index('credentialBadge') < summary.index('cfBadge') < summary.index('siteConfigured') < summary.index('model.sign_sites') < summary.index('model.login_sites')
    assert summary.index('model.login_sites') < summary.index('expand-icon')
    detail = source.split('<div class="site-detail">', 1)[1]
    assert 'v-model="model.sign_sites"' not in detail and 'v-model="model.login_sites"' not in detail
    assert 'selectedGroups' not in source


def test_picker_chips_reflect_pending_or_enabled_sites():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert 'pickerOpen.value ? pendingSites.value : model.enabled_sites' in source
    assert 'v-for="site in pickerSelected"' in source
    assert '@click.stop.prevent="removePickerSite(site.id)"' in source
    assert 'if (pickerOpen.value) pendingSites.value = pendingSites.value.filter' in source
    assert 'else remove(id)' in source


def test_sites_use_registry_with_only_unsaved_custom_overlay():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert 'const sites = computed(() => {' in source
    expression = source.split('const sites = computed(() => {', 1)[1].split('\n})', 1)[0]
    script = "const assert=require('node:assert/strict');" + '''
const registrySites={value:[{id:'custom-1',name:'Saved'},{id:'hdsky',name:'Sky'}]};
const customOverlay={value:[]};
const model={custom_sites_data:[{id:'custom-1',name:'Saved'}]};
const getSites=()=>{''' + expression + '''};
assert.equal(getSites().length,2);
customOverlay.value=[{id:'custom-1',name:'Edited'},{id:'custom-2',name:'New'}];
assert.deepEqual(getSites().map(s=>s.name),['Edited','Sky','New']);
customOverlay.value=[{id:'custom-1',deleted:true}];
assert.deepEqual(getSites().map(s=>s.id),['hdsky']);
registrySites.value=[{id:'custom-2',name:'Persisted'}];
customOverlay.value=[];
assert.deepEqual(getSites(),registrySites.value);
'''
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)
    assert 'customOverlay.value = []\n  loadSites()' in source
    assert '[...registrySites.value, ...model.custom_sites_data]' not in source
    assert "response?.data?.sites || response?.sites" in source


def test_custom_site_dialog_contract():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert 'class="custom-entry"' not in source
    assert '<dialog ref="customDialog"' in source
    assert '@click="editCustomSites"' in source
    assert 'customEnabled' not in source
    assert '@click="deleteCustomSite(site.id)"' in source
    assert 'model.custom_sites_data.push(updated)' in source
    assert 'model.sign_sites = model.sign_sites.filter' in source
    assert 'customDialog.value.showModal()' in source


def test_page_history_five_columns_and_optional_evidence():
    source = (SRC / 'Page.vue').read_text(encoding='utf8')
    assert "['时间','站点','状态','最近消息','证据']" in source
    assert 'colspan="6"' not in source and 'colspan="5"' in source
    assert '未解析到' not in source
    assert "{{ item.evidence?.[key] || '' }}" in source
    assert 'resultMessage(item)' in source
    functions = source.split('function formatTime(value)', 1)[1].split('async function get(path)', 1)[0]
    script = "const assert=require('node:assert/strict'); function formatTime(value)" + functions + """
assert.equal(formatTime('2026-01-02T03:04:05'), '2026/01/02 03:04:05');
assert.equal(formatTime(null), '');
assert.equal(resultMessage({message:'签到成功',reward:'+87 爆米花'}), '签到成功 +87 爆米花');
assert.equal(resultMessage({message:'签到前页面已签标记',evidence:{button_text:'已签到'}}), '签到前页面已签标记');
"""
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)


def test_inline_removal_requires_confirmation():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert '@click="pendingRemove = site.id"' in source
    assert '@click="confirmRemove(site.id)"' in source
    assert 'class="remove-site"' not in source
    assert '@submit.prevent="saveCustomSite(site)"' in source


def test_filtered_select_all_preserves_nonmatching_draft():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    functions = source.split('function toggleFilteredSelection()',1)[1].split('function remove(id)',1)[0]
    script = "const assert=require('node:assert/strict');const filtered={value:[{id:'a'},{id:'b'}]},pendingSites={value:['x','a']},allFilteredSelected={value:false};function toggleFilteredSelection()" + functions + """
toggleFilteredSelection(); assert.deepEqual(pendingSites.value,['x','a','b']);
allFilteredSelected.value=true;
toggleFilteredSelection(); assert.deepEqual(pendingSites.value,['x']);
"""
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)
    assert "allFilteredSelected ? '全不选' : '全选'" in source


def test_badge_palette_has_light_and_dark_tokens():
    css = (SRC / 'preview.css').read_text(encoding='utf8')
    for name in ('mp','adapter','custom','cookie','api','password','clear','unknown'):
        assert css.count('--ptc-badge-'+name+'-bg:rgba(') == 2
        assert '.chip.badge-'+name in css


def test_picker_uses_viewport_constrained_top_layer():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert 'popover="manual"' in source and 'showPopover()' in source
    assert 'below < desired && above > below' in source
    assert 'window.innerWidth-width-8' in source
    assert "window.removeEventListener('scroll', positionPicker, true)" in source


def test_page_filters_collapse_and_day_groups():
    source = (SRC / 'Page.vue').read_text(encoding='utf8')
    functions = source.split('const showAllSites', 1)[1].split('async function get(path)', 1)[0]
    script = """
const assert = require('node:assert/strict');
const ref = value => ({value});
const computed = getter => ({get value() {return getter()}});
const stats=ref({sites:Array.from({length:12},(_,i)=>({id:i,status:i===10?'failed':i===11?'unconfirmed':'success'}))});
const history=ref({items:[{time:new Date().toISOString()},{time:'2020-01-02T03:04:05'},{time:'2020-01-02T04:04:05'}]});
const showAllSites""" + functions + """
assert.equal(visibleSites.value.length,8);
assert.deepEqual(visibleSites.value.slice(0,2).map(s=>s.id),[10,11]);
showAllSites.value=true; assert.equal(visibleSites.value.length,12);
toggleSiteFilter('failed'); assert.equal(showAllSites.value,false); assert.deepEqual(visibleSites.value.map(s=>s.id),[10]);
toggleSiteFilter('failed'); assert.equal(visibleSites.value.length,8);
toggleSiteFilter('signed'); assert.equal(visibleSites.value.length,0);
toggleSiteFilter('signed');
const today=historyDay(new Date()); assert.equal(dayIsOpen(today),true);
assert.equal(dayIsOpen('2020-01-02'),false);
toggleDay('2020-01-02'); assert.equal(dayIsOpen('2020-01-02'),true);
assert.equal(historyDays.value.find(g=>g.day==='2020-01-02').records.length,2);
assert.equal(historyDay('bad'),'日期未知');
"""
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)
    card = source.split('<article ',1)[1].split('</article>',1)[0]
    assert 'site.uid' not in card and 'credential_source' not in card and 'site.time' not in card
    assert 'signin_by_domain' in card and 'verify_site' in card
    assert 'site-icon' in card and '@error=' in card


def test_page_history_loads_all_pages():
    source = (SRC / 'Page.vue').read_text(encoding='utf8')
    function = 'async function loadHistory()' + source.split('async function loadHistory()',1)[1].split('async function load()',1)[0]
    script = """
const assert=require('node:assert/strict'); const calls=[];
async function get(path) {calls.push(path); const page=Number(new URLSearchParams(path.split('?')[1]).get('page')); return {total:205,items:Array.from({length:page<3?100:5},(_,i)=>({id:(page-1)*100+i}))};}
""" + function + """
loadHistory().then(result=>{assert.equal(result.items.length,205);assert.equal(calls.length,3);assert.equal(result.items[204].id,204)}).catch(e=>{console.error(e);process.exit(1)});
"""
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)
