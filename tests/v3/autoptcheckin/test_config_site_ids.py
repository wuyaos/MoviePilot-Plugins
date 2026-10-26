"""Execute Config.vue setup with Vue reactivity; no host or network required."""
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins.v3/autoptcheckin"


def test_config_numeric_custom_site_ids():
    source = (ROOT / "frontend.v3/autoptcheckin/src/Config.vue").read_text(encoding="utf-8")
    setup = source.split("<script setup>", 1)[1].split("</script>", 1)[0]
    setup = re.sub(r"^import .*\n", "", setup, flags=re.MULTILINE)
    defaults = json.loads((PLUGIN / "config_defaults.json").read_text(encoding="utf-8"))
    harness = """
import assert from 'node:assert/strict';
import {reactive, ref, computed, watch, nextTick} from 'vue';
const onMounted = () => {}, onBeforeUnmount = () => {};
const inject = () => null;
const ids = [60005,60006,60012,60013,60018,60022,60023,60024];
const rows = ids.map(id => ({id, name:`Site ${id}`, url:`https://site-${id}.invalid/`, source:'自定义站点'}));
rows.push({id:'native', name:'Native'});
const config = () => ({enabled_sites:[...ids,'native'], sign_sites:[60005], login_sites:[60006],
  site_proxy:{60006:true}, site_emulate:{60005:true}, site_cloudsign:[60005], site_browserless:[60005],
  custom_sites_data:rows.slice(0,8)});
const input = reactive({initialConfig:config(), api:{get:async () => ({data:{sites:rows}})}});
const emitted = [];
const defineProps = () => input;
const defineEmits = () => (event, payload) => { if (event === 'save') emitted.push(payload) };
"""
    checks = """
await loadSites();
const expected = [...ids.map(String), 'native'];
assert.deepEqual(selected.value.map(s=>s.id), expected);
assert.deepEqual(pickerSelected.value.map(s=>s.id), expected);
assert.ok(model.sign_sites.includes(selected.value[0].id));
assert.ok(model.login_sites.includes(selected.value[1].id));
// 覆盖表缺键继承 /sites 有效字段；显式 false 终结继承，绝不能 OR 回声明值。
assert.ok(siteEmulated(selected.value[0]));
assert.ok(siteProxied(selected.value[1]));
assert.equal(siteEmulated(selected.value[2]), false);
setSiteOverride('site_emulate', selected.value[0], false);
assert.equal(siteEmulated(selected.value[0]), false, 'explicit false must win over declared true');
setSiteOverride('site_proxy', selected.value[2], true);
assert.ok(siteProxied(selected.value[2]));
// 未触碰的站点不得被物化成覆盖键。
assert.deepEqual(Object.keys(model.site_emulate), ['60005']);
assert.deepEqual(Object.keys(model.site_proxy), ['60006', '60012']);
// 云签按草稿选择；开启/关闭不自动启用站点或勾选动作。
const capable = {id:'audiences', name:'Audiences', cloudsign_capable:true};
toggleCloudsign(capable, true);
assert.ok(model.site_cloudsign.includes('audiences'));
assert.ok(!model.enabled_sites.includes('audiences'));
assert.ok(!model.sign_sites.includes('audiences'));
toggleCloudsign(capable, false);
assert.ok(!model.site_cloudsign.includes('audiences'));
assert.equal(typeof input.initialConfig.custom_sites_data[0].id, 'number');
// Editing an existing numeric-ID custom row must replace it, not duplicate it.
saveCustomSite({...model.custom_sites_data[0], name:'Renamed'});
assert.equal(selected.value.length, 9);
assert.equal(selected.value[0].name, 'Renamed');
assert.equal(model.custom_sites_data.length, 8);
// 保存 custom 条目同步 site_emulate 覆盖表，避免双真相。
assert.equal(model.site_emulate['60005'], false);
saveCustomSite({...model.custom_sites_data[0], name:'Renamed', emulate:true});
assert.equal(model.site_emulate['60005'], true);
assert.ok(siteEmulated(selected.value[0]));
// Custom dialog action switch updates flat action and enabled collections immediately.
toggleCustomSignin(model.custom_sites_data[1], true);
assert.ok(model.sign_sites.includes('60006') && model.enabled_sites.includes('60006'));
toggleCustomSignin(model.custom_sites_data[1], false);
assert.ok(!model.sign_sites.includes('60006') && model.enabled_sites.includes('60006'));
deleteCustomSite('60005');
assert.ok(!sites.value.some(s=>s.id==='60005'));
assert.ok(!model.enabled_sites.includes('60005'));
assert.ok(!model.sign_sites.includes('60005'));
assert.ok(!model.login_sites.includes('60005'));
// 删除 custom 条目同步清理覆盖表与云签选择。
assert.ok(!('60005' in model.site_proxy));
assert.ok(!('60005' in model.site_emulate));
assert.ok(!model.site_cloudsign.includes('60005'));
// Host config replacement must normalize again and discard the old overlay.
input.initialConfig = config();
await nextTick();
await loadSites();
assert.deepEqual(selected.value.map(s=>s.id), expected);
assert.equal(selected.value[0].name, 'Site 60005');
assert.ok(model.custom_sites_data.every(s=>typeof s.id==='string'));
// Also accept the host API's unwrapped response shape and string IDs.
input.api.get = async () => ({sites:rows.map(s=>({...s,id:String(s.id)}))});
await loadSites();
assert.deepEqual(selected.value.map(s=>s.id), expected);
// 保存 payload：旧键 site_browserless 不再出现；覆盖表键为字符串。
save();
assert.ok(emitted.length === 1);
const payload = emitted[0];
assert.ok(!('site_browserless' in payload), 'legacy site_browserless must not be saved');
assert.deepEqual(Object.keys(payload.site_emulate).sort(), ['60005'].sort());
assert.ok(payload.site_emulate['60005'] === true);
assert.ok(payload.site_cloudsign.every(v => typeof v === 'string'));
console.log('Config site ID regression: passed');
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", harness + "\nconst defaults = " + json.dumps(defaults) + ";\n" + setup + checks],
        cwd=Path(__file__).parents[3] / "frontend.v3" / "autoptcheckin", capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
