"""Execute Config.vue setup with Vue reactivity; no host or network required."""
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins.v3/autoptcheckin"


def test_config_numeric_custom_site_ids():
    source = (PLUGIN / "frontend/src/Config.vue").read_text(encoding="utf-8")
    setup = source.split("<script setup>", 1)[1].split("</script>", 1)[0]
    setup = re.sub(r"^import .*\n", "", setup, flags=re.MULTILINE)
    defaults = json.loads((PLUGIN / "config_defaults.json").read_text(encoding="utf-8"))
    harness = """
import assert from 'node:assert/strict';
import {reactive, ref, computed, watch, nextTick} from 'vue';
const onMounted = () => {}, onBeforeUnmount = () => {};
const ids = [60005,60006,60012,60013,60018,60022,60023,60024];
const rows = ids.map(id => ({id, name:`Site ${id}`, url:`https://site-${id}.invalid/`, source:'自定义站点'}));
rows.push({id:'native', name:'Native'});
const config = () => ({enabled_sites:[...ids,'native'], sign_sites:[60005], login_sites:[60006], site_browserless:[60005], custom_sites_data:rows.slice(0,8)});
const input = reactive({initialConfig:config(), api:{get:async () => ({data:{sites:rows}})}});
const defineProps = () => input;
const defineEmits = () => () => {};
"""
    checks = """
await loadSites();
const expected = [...ids.map(String), 'native'];
assert.deepEqual(selected.value.map(s=>s.id), expected);
assert.deepEqual(pickerSelected.value.map(s=>s.id), expected);
assert.ok(model.sign_sites.includes(selected.value[0].id));
assert.ok(model.login_sites.includes(selected.value[1].id));
assert.ok(siteEmulated(selected.value[0]));
assert.equal(typeof input.initialConfig.custom_sites_data[0].id, 'number');
// Editing an existing numeric-ID custom row must replace it, not duplicate it.
saveCustomSite({...model.custom_sites_data[0], name:'Renamed'});
assert.equal(selected.value.length, 9);
assert.equal(selected.value[0].name, 'Renamed');
assert.equal(model.custom_sites_data.length, 8);
deleteCustomSite('60005');
assert.ok(!sites.value.some(s=>s.id==='60005'));
assert.ok(!model.enabled_sites.includes('60005'));
assert.ok(!model.sign_sites.includes('60005'));
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
console.log('Config site ID regression: passed');
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", harness + "\nconst defaults = " + json.dumps(defaults) + ";\n" + setup + checks],
        cwd=PLUGIN / "frontend", capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
