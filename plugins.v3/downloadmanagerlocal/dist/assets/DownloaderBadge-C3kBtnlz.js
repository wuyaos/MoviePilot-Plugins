import { importShared } from './__federation_fn_import-JrT3xvdd.js';

function isStandardEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response).sort();
  return keys.length === 3
    && keys[0] === 'data'
    && keys[1] === 'message'
    && keys[2] === 'success'
    && typeof response.success === 'boolean'
}

function pluginPath(pluginId, path = '') {
  const normalizedId = String(pluginId || '').trim();
  if (!normalizedId) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '');
  return suffix ? `plugin/${normalizedId}/${suffix}` : `plugin/${normalizedId}`
}

function unwrapResponse(response) {
  if (!isStandardEnvelope(response)) return response
  if (!response.success) throw new Error(response.message || '请求失败')
  return response.data
}
async function postPluginApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const params = new URLSearchParams();
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, value);
  });
  const query = params.toString();
  const url = `${pluginPath(pluginId, path)}${query ? `?${query}` : ''}`;
  const response = await api.post(url, payload, options);
  return unwrapResponse(response)
}
async function postPluginJsonApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(pluginPath(pluginId, path), payload, options);
  return unwrapResponse(response)
}
async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(pluginPath(pluginId, path), options);
  return unwrapResponse(response)
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {toDisplayString:_toDisplayString,normalizeStyle:_normalizeStyle,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,resolveComponent:_resolveComponent,createBlock:_createBlock,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = ["title"];
const _hoisted_2 = { class: "dm-downloader-badge-name" };

const {computed} = await importShared('vue');


/**
 * 下载器品牌徽标：品牌色圆标 + 实例名（如 QB1）。
 * Config.vue（转移任务列表）与 Page.vue（诊断/总览）复用同一组件；
 * 未知类型用通用图标；纯本地样式，不联网加载、不引入图标框架。
 */

const _sfc_main = {
  __name: 'DownloaderBadge',
  props: {
  name: { type: String, default: '' },
  type: { type: String, default: '' },
  size: { type: [Number, String], default: 20 },
},
  setup(__props) {

const props = __props;

const BRANDS = {
  qbittorrent: { text: 'Q', color: '#2f7ac0', label: 'qBittorrent' },
  transmission: { text: 'T', color: '#b52025', label: 'Transmission' },
  rtorrent: { text: 'R', color: '#5f7a8a', label: 'rTorrent' },
};

const brand = computed(() => BRANDS[String(props.type || '').toLowerCase()] || null);
const displayName = computed(() => props.name || '—');
const title = computed(() => `${displayName.value}${brand.value ? ` · ${brand.value.label}` : ''}`);
const markSize = computed(() => `${Number(props.size) || 20}px`);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");

  return (_openBlock(), _createElementBlock("span", {
    class: "dm-downloader-badge",
    title: title.value
  }, [
    (brand.value)
      ? (_openBlock(), _createElementBlock("span", {
          key: 0,
          class: "dm-downloader-badge-mark",
          style: _normalizeStyle({ background: brand.value.color, width: markSize.value, height: markSize.value, fontSize: `calc(${markSize.value} * 0.6)` })
        }, _toDisplayString(brand.value.text), 5))
      : (_openBlock(), _createBlock(_component_VIcon, {
          key: 1,
          icon: "mdi-download-outline",
          class: "dm-downloader-badge-mark dm-downloader-badge-mark--unknown",
          style: _normalizeStyle({ width: markSize.value, height: markSize.value, fontSize: markSize.value })
        }, null, 8, ["style"])),
    _createElementVNode("span", _hoisted_2, _toDisplayString(displayName.value), 1)
  ], 8, _hoisted_1))
}
}

};
const DownloaderBadge = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-1ec087bc"]]);

export { DownloaderBadge as D, _export_sfc as _, postPluginJsonApi as a, getPluginApi as g, postPluginApi as p };
