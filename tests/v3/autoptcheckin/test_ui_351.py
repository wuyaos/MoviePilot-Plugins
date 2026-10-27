"""3.5.1 UI contracts and interaction state; rendered checks use the host browser."""
from pathlib import Path
import subprocess

SRC = Path(__file__).parents[3] / 'frontend.v3/autoptcheckin/src'


def test_config_expand_collapse_and_batch_confirmation():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    functions = source.split('const openSites = ref([])', 1)[1].split('const customDialog = ref', 1)[0]
    start = functions.index('const pickerAnchor')
    end = functions.index('function togglePicker')
    functions = functions[:start] + functions[end:]
    script = """
const assert = require('node:assert/strict');
const ref = value => ({value});
const computed = () => ({value: []});
const customDraft = {value: []};
const selected = ref([{id:'alpha'}, {id:'hotel'}, {id:'tango', fields:[{key:'rousi_username'}]}]);
const openSites = ref([]);
const model = {enabled_sites:['alpha'], site_proxy:{}, site_emulate:{}, site_cloudsign:[]};
const hasExtraSettings = site => (site.fields || []).length > 0;
""" + functions + """
expandSites();
assert.deepEqual(openSites.value, ['tango'], '只有含额外配置的站点可展开');

toggleSite('tango');
assert.deepEqual(openSites.value, []);
collapseSites();
assert.deepEqual(openSites.value, []);

expandSites();
assert.equal(openSites.value.length, 1);
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
    assert ':open="hasExtraSettings(site) && openSites.includes(site.id)"' in source
    assert '<summary @click.prevent>' in source
    assert 'class="btn ghost mini expand-icon"' in source
    assert 'hasExtraSettings(site)' in source
    assert '@click.prevent="toggleSite(site.id)"' in source
    assert 'site-metadata' not in source  # 3.37 用户裁决：展开态不再显示站点类型/凭证/URL 行
    assert '@click="expandSites"' in source and '@click="collapseSites"' in source
    assert 'v-model="pendingSites"' in source
    assert '@click="confirmSites"' in source


def test_site_name_badges_and_equal_data_grid():
    css = (SRC / 'preview.css').read_text(encoding='utf8')
    assert 'min-width:120px; flex:0 0 120px;' in css
    assert '.enabled-site-list .badges {display:flex; align-items:center;' in css
    assert '.data-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-rows:1fr;' in css
    assert '.data-grid .site-card:last-child' not in css
    assert '.grid,.data-grid{grid-template-columns:1fr}' in css
    assert 'v-if="!stats.sites.length"' in (SRC / 'Page.vue').read_text(encoding='utf8')


def test_config_summary_actions_and_emulate_contract():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    summary = source.split(':open="hasExtraSettings(site) && openSites.includes(site.id)"><summary', 1)[1].split('</summary>', 1)[0]
    assert summary.count('type="checkbox"') == 5
    assert 'role="switch"' in summary
    assert 'v-if="site.login_capable"' not in summary  # 3.37 用户裁决：登录开关所有站点可见
    assert 'credentialBadge' in summary
    assert 'v-if="site.cf === true"' in summary and 'CF 盾' in summary
    assert 'v-if="cloudsignSelected(site)"' in summary and '云签' in summary  # R4: 云签徽标按草稿 site_cloudsign 选择
    assert 'v-else-if="siteEmulated(site)"' in summary and '仿真' in summary  # R4: 云签关闭回退有效仿真徽标（显式 false 压声明值）
    assert summary.index('site.source') < summary.index('credentialBadge') < summary.index('CF 盾') < summary.index('仿真') < summary.index('model.sign_sites') < summary.index('model.login_sites')
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
    assert 'removeCustomDraft' in source and 'saveCustomDraft' in source
    assert 'class="custom-row custom-columns"' in source and 'class="btn confirm mini"' not in source
    assert '<dialog ref="customDialog"' in source
    assert '@click="editCustomSites"' in source
    assert 'customEnabled' not in source
    assert '@click="removeCustomDraft(site.id)"' in source
    assert 'model.custom_sites_data = kept.map' in source
    assert 'model.sign_sites = model.sign_sites.filter' in source
    assert 'customDialog.value?.showModal()' in source


def test_page_history_four_columns_without_evidence():
    """历史四列（时间/站点/状态/最近消息），证据字段只在存储契约保留、不在 UI 展开。"""
    source = (SRC / 'Page.vue').read_text(encoding='utf8')
    assert "['时间','站点','状态','最近消息']" in source
    assert 'colspan="5"' not in source and '证据' not in source and 'item.evidence' not in source
    assert 'colspan="4"' in source
    assert '未解析到' not in source
    assert 'resultMessage(item)' in source
    functions = source.split('function formatTime(value)', 1)[1].split('\nfunction historyDay', 1)[0]
    assert 'historyDays' in source and 'history-day' in source
    script = (
        "const assert=require('node:assert/strict'); function formatTime(value)"
        + functions
        + "function resultMessage(item) { return [item.message, item.reward].filter(Boolean).join(' ') }\n"
        + "assert.equal(formatTime('2026-01-02T03:04:05'), '2026/01/02 03:04:05');\n"
        + "assert.equal(formatTime(null), '');\n"
        + "assert.equal(resultMessage({message:'签到成功',reward:'+87 爆米花'}), '签到成功 +87 爆米花');\n"
        + "assert.equal(resultMessage({message:'签到前页面已签标记',evidence:{button_text:'已签到'}}), '签到前页面已签标记');\n"
    )
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)


def test_inline_removal_requires_confirmation():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert '@click="pendingRemove = site.id"' in source
    assert '@click="confirmRemove(site.id)"' in source
    assert 'class="remove-site"' not in source
    assert '@click="saveCustomDraft"' in source and 'custom-footer' in source


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
    for name in ('mp','adapter','custom','cookie','api_key','password','unknown'):
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
const stats=ref({sites:Array.from({length:12},(_,i)=>({id:i,
  sign_state:i===10||i===11?'failed':'success',
  sign_status:i===11?'unconfirmed':'success',
  login_state:'pending', login_status:'',
  name:'站点'+i}))});
const history=ref({items:[{time:new Date().toISOString()},{time:'2020-01-02T03:04:05'},{time:'2020-01-02T04:04:05'}]});
const showAllSites""" + functions + """
assert.equal(trackStates.length,8); assert.deepEqual(trackStates[0],{key:'sign_success',label:'签到成功',cls:'success'});
assert.equal(visibleSites.value.length,8);
assert.deepEqual(visibleSites.value.slice(0,2).map(s=>s.id),[10,11]);
showAllSites.value=true; assert.equal(visibleSites.value.length,12);
toggleSiteFilter('sign_failed'); assert.equal(showAllSites.value,false); assert.deepEqual(visibleSites.value.map(s=>s.id),[10]);
toggleSiteFilter('sign_failed'); assert.equal(visibleSites.value.length,8);
toggleSiteFilter('sign_unknown'); assert.deepEqual(visibleSites.value.map(s=>s.id),[11]);
toggleSiteFilter('sign_unknown');
toggleSiteFilter('sign_pending'); assert.equal(visibleSites.value.length,0);
toggleSiteFilter('sign_pending');
const today=historyDay(new Date());
assert.equal(historyDays.value.some(g=>g.day===today),false);
assert.equal(dayIsOpen('2020-01-02'),false);
toggleDay('2020-01-02'); assert.equal(dayIsOpen('2020-01-02'),true);
assert.equal(historyDays.value.find(g=>g.day==='2020-01-02').records.length,2);
assert.equal(historyDay('bad'),'日期未知');
"""
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)
    card = source.split('<article ',1)[1].split('</article>',1)[0]
    assert 'site.uid' not in card and 'credential_source' not in card and 'site.time' not in card
    assert 'signin_by_domain' in card and 'toggleSitePaused' in source and 'paused_sites: [...paused]' in source
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


def test_config_pause_control_keeps_enabled_sites_and_switch_order():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert 'async function togglePaused(site)' in source
    assert 'paused_sites: next' in source and 'model.paused_sites = next' in source
    assert "selected = computed(() => sites.value.filter(s => model.enabled_sites.includes(s.id)))" in source
    card = source.split('<span class="row-right">', 1)[1].split('</span></summary>', 1)[0]
    ordered = [' 代理', ' 仿真', ' 云签', ' 签到', ' 登录']
    positions = [card.index(label) for label in ordered]
    assert positions == sorted(positions)
    assert 'class="pwr"' in source and "'恢复执行' : '暂停执行'" in source


def test_page_filter_states_are_eight_single_select_and_blank_message():
    source = (SRC / 'Page.vue').read_text(encoding='utf8')
    assert source.count("{key:") >= 8
    assert "sign_pending: pending(s)" in source and "login_pending: pending(l)" in source
    assert "siteFilter.value === key ? '' : key" in source
    assert "cardMessage(site) || '—'" not in source
    card = source.split('<div class="site-caps"', 1)[1].split('</div>', 1)[0]
    assert 'CF盾' not in card


def test_custom_dialog_has_sticky_single_header():
    source = (SRC / 'Config.vue').read_text(encoding='utf8')
    assert source.count('class="custom-table-head"') == 1
    assert 'position:sticky' in (SRC / 'preview.css').read_text(encoding='utf8')
    row = source.split('class="custom-row custom-columns"', 1)[1].split('</div>', 1)[0]
    assert '<span>站点名称</span>' not in row and '<span>站点地址</span>' not in row
