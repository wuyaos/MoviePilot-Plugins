import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = { class: "farm-header bg-gradient-farm text-white" };
const _hoisted_2 = { class: "farm-header-row d-flex align-center ga-2 px-3 py-2" };
const _hoisted_3 = { class: "d-flex align-center ga-2 farm-header-left" };
const _hoisted_4 = { class: "d-flex flex-wrap align-center justify-end ga-3 farm-header-right" };
const _hoisted_5 = { class: "pa-4" };
const _hoisted_6 = { class: "pa-4" };
const _hoisted_7 = { class: "text-subtitle-1" };
const _hoisted_8 = { class: "d-flex flex-wrap align-center ga-2 mt-2" };

const {computed,onBeforeUnmount,reactive,ref,watch} = await importShared('vue');



const _sfc_main$1 = {
  __name: 'FarmConfigForm',
  props: {
  initialConfig: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
},
  emits: ['save', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const DEFAULT_CONFIG = {
  enabled: false,
  notify: true,
  run_once: false,
  mode: 'smart',
  site_ids: [],
  interval_minutes: 61,
  harvest_interval_minutes: 61,
  expire_threshold_minutes: 120,
  min_profit_rate: 0,
  max_profit_rate: 0,
  max_sell_per_run: 50,
  request_interval: 1,
  retry_count: 3,
  use_proxy: false,
  dry_run: false,
  auto_harvest: true,
  auto_plant: true,
  auto_sell: true,
  expiry_sale: true,
  siqi_auto_captcha_harvest: false,
  siqi_captcha_ocr: true,
  siqi_auto_buy_slot: false,
  siqi_auto_steal: false,
  siqi_auto_like: false,
  site_overrides: '{}',
};

const SITE_ITEMS = [
  { title: 'PlayLet', value: 'playlet' },
  { title: 'NovaHD', value: 'novahd' },
  { title: '好学', value: 'haoxue' },
  { title: '包子', value: 'baozi' },
  { title: '拾刻', value: 'skit' },
  { title: '思齐', value: 'siqi' },
];

const MODE_ITEMS = [
  { title: '智能交易', value: 'smart' },
  { title: '自动收获', value: 'harvest' },
];

const NUMERIC_OVERRIDE_FIELDS = [
  'min_profit_rate',
  'max_profit_rate',
  'expire_threshold_minutes',
  'max_sell_per_run',
  'request_interval',
];

const AUTOMATION_FIELDS = [
  'auto_harvest',
  'auto_plant',
  'auto_sell',
  'expiry_sale',
];

const props = __props;

const emit = __emit;
const activeTab = ref('global');
const config = reactive({ ...DEFAULT_CONFIG });
const sitePolicies = reactive({});
const error = ref('');
const successMessage = ref('');
let successTimer = null;
function setSuccess(msg) {
  successMessage.value = msg;
  if (successTimer) clearTimeout(successTimer);
  successTimer = setTimeout(() => { successMessage.value = ''; }, 3000);
}
onBeforeUnmount(() => { if (successTimer) clearTimeout(successTimer); });

const siteModeItems = computed(() => [
  { title: `继承全局（${config.mode === 'harvest' ? '自动收获' : '智能交易'}）`, value: 'inherit' },
  ...MODE_ITEMS,
]);

const OVERRIDE_UNITS = {
  min_profit_rate: '',
  max_profit_rate: '',
  expire_threshold_minutes: '分钟',
  max_sell_per_run: '',
  request_interval: '秒',
};

function inheritPlaceholder(field) {
  return `继承全局（${config[field]}${OVERRIDE_UNITS[field] || ''}）`
}

function booleanOverrideItems(field) {
  return [
    { title: `继承全局（${config[field] ? '启用' : '禁用'}）`, value: 'inherit' },
    { title: '启用', value: true },
    { title: '禁用', value: false },
  ]
}

function automationItems(field) {
  return [
    { title: `继承全局（${config[field] ? '开启' : '关闭'}）`, value: 'inherit' },
    { title: '开启', value: true },
    { title: '关闭', value: false },
  ]
}

function emptySitePolicy(enabled = false) {
  return {
    enabled,
    mode: 'inherit',
    min_profit_rate: null,
    max_profit_rate: null,
    expire_threshold_minutes: null,
    max_sell_per_run: null,
    request_interval: null,
    use_proxy: 'inherit',
    dry_run: 'inherit',
    auto_harvest: 'inherit',
    auto_plant: 'inherit',
    auto_sell: 'inherit',
    expiry_sale: 'inherit',
  }
}

function parseInitialOverrides(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '{}') : value;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('顶层必须是 JSON 对象')
    }
    return parsed
  } catch (parseError) {
    error.value = `初始单站覆盖 JSON 格式错误，已忽略：${parseError?.message || '无法解析'}`;
    return {}
  }
}

function policyFromOverride(siteId, overrides, selectedSiteIds) {
  const override = overrides[siteId];
  const source = override && !Array.isArray(override) && typeof override === 'object'
    ? override
    : {};
  const policy = emptySitePolicy(selectedSiteIds.includes(siteId) || source.enabled === true);

  if (source.mode === 'smart' || source.mode === 'harvest') policy.mode = source.mode;
  for (const field of NUMERIC_OVERRIDE_FIELDS) {
    if (typeof source[field] === 'number' && Number.isFinite(source[field])) {
      policy[field] = source[field];
    }
  }
  if (typeof source.use_proxy === 'boolean') policy.use_proxy = source.use_proxy;
  if (typeof source.dry_run === 'boolean') policy.dry_run = source.dry_run;
  for (const field of AUTOMATION_FIELDS) {
    if (typeof source[field] === 'boolean') policy[field] = source[field];
  }
  return policy
}

function buildOverrides() {
  const overrides = {};
  for (const site of SITE_ITEMS) {
    const policy = sitePolicies[site.value];
    if (!policy) continue

    const override = {};
    if (policy.mode === 'smart' || policy.mode === 'harvest') override.mode = policy.mode;
    for (const field of NUMERIC_OVERRIDE_FIELDS) {
      if (typeof policy[field] === 'number' && Number.isFinite(policy[field])) {
        override[field] = policy[field];
      }
    }
    if (typeof policy.use_proxy === 'boolean') override.use_proxy = policy.use_proxy;
    if (typeof policy.dry_run === 'boolean') override.dry_run = policy.dry_run;
    for (const field of AUTOMATION_FIELDS) {
      if (typeof policy[field] === 'boolean') override[field] = policy[field];
    }
    if (Object.keys(override).length) overrides[site.value] = override;
  }
  return overrides
}

function initialize(initialConfig) {
  Object.assign(config, DEFAULT_CONFIG, initialConfig || {});
  error.value = '';
  const selectedSiteIds = Array.isArray(config.site_ids) ? config.site_ids : [];
  const overrides = parseInitialOverrides(config.site_overrides);
  for (const site of SITE_ITEMS) {
    sitePolicies[site.value] = policyFromOverride(site.value, overrides, selectedSiteIds);
  }
}

watch(
  () => props.initialConfig,
  initialConfig => initialize(initialConfig),
  { deep: true, immediate: true },
);


function effectiveSiteValue(siteId, field) {
  const value = sitePolicies[siteId]?.[field];
  return value === null || value === undefined || value === '' || value === 'inherit'
    ? config[field]
    : value
}

function modeLabel(siteId) {
  return effectiveSiteValue(siteId, 'mode') === 'harvest' ? '自动收获' : '智能交易'
}

function profitSummary(siteId) {
  const minimum = effectiveSiteValue(siteId, 'min_profit_rate');
  const maximum = effectiveSiteValue(siteId, 'max_profit_rate');
  return `${minimum ?? 0} ~ ${maximum ? maximum : '不限'}`
}

function saveConfig() {
  error.value = '';
  const overrides = buildOverrides();
  const payload = {
    ...JSON.parse(JSON.stringify(config)),
    site_ids: SITE_ITEMS
      .filter(site => sitePolicies[site.value]?.enabled)
      .map(site => site.value),
    site_overrides: JSON.stringify(overrides),
  };
  emit('save', payload);
  setSuccess('配置已保存');
}

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_tab = _resolveComponent("v-tab");
  const _component_v_tabs = _resolveComponent("v-tabs");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_switch = _resolveComponent("v-switch");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_window_item = _resolveComponent("v-window-item");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_chip_group = _resolveComponent("v-chip-group");
  const _component_v_window = _resolveComponent("v-window");
  const _component_v_form = _resolveComponent("v-form");

  return (_openBlock$1(), _createBlock$1(_component_v_form, {
    class: "farm-config-form text-body-2",
    onSubmit: _withModifiers(saveConfig, ["prevent"])
  }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card, {
        flat: "",
        class: "rounded-lg border"
      }, {
        default: _withCtx(() => [
          _createElementVNode("div", _hoisted_1, [
            _createElementVNode("div", _hoisted_2, [
              _createElementVNode("div", _hoisted_3, [
                _createVNode(_component_v_icon, {
                  icon: "mdi-sprout",
                  color: "white",
                  size: "small"
                }),
                _cache[29] || (_cache[29] = _createElementVNode("span", { class: "text-subtitle-1 text-white font-weight-bold" }, "农场配置", -1))
              ]),
              _createVNode(_component_v_spacer),
              _createElementVNode("div", _hoisted_4, [
                _createVNode(_component_v_btn, {
                  icon: "mdi-content-save",
                  size: "default",
                  variant: "outlined",
                  color: "white",
                  border: "white",
                  loading: __props.loading,
                  onClick: saveConfig
                }, null, 8, ["loading"]),
                _createVNode(_component_v_btn, {
                  icon: "mdi-view-dashboard-outline",
                  size: "default",
                  variant: "outlined",
                  color: "white",
                  border: "white",
                  onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
                }),
                _createVNode(_component_v_btn, {
                  icon: "mdi-close",
                  size: "default",
                  variant: "outlined",
                  color: "white",
                  border: "white",
                  onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
                })
              ])
            ])
          ]),
          (error.value)
            ? (_openBlock$1(), _createBlock$1(_component_v_alert, {
                key: 0,
                type: "error",
                variant: "tonal",
                closable: "",
                class: "mb-4 text-body-2",
                "onClick:close": _cache[2] || (_cache[2] = $event => (error.value = ''))
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(error.value), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (successMessage.value)
            ? (_openBlock$1(), _createBlock$1(_component_v_alert, {
                key: 1,
                type: "success",
                variant: "tonal",
                closable: "",
                class: "mb-4 text-body-2",
                "onClick:close": _cache[3] || (_cache[3] = $event => (successMessage.value = ''))
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(successMessage.value), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          _createVNode(_component_v_tabs, {
            modelValue: activeTab.value,
            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((activeTab).value = $event)),
            color: "primary",
            density: "default",
            "show-arrows": "",
            class: "config-tabs mb-3"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_tab, {
                value: "global",
                "prepend-icon": "mdi-tune-variant"
              }, {
                default: _withCtx(() => [
                  _cache[30] || (_cache[30] = _createTextVNode("全局设置", -1)),
                  _createElementVNode("span", {
                    class: _normalizeClass(["tab-status-dot", config.enabled ? 'on' : 'off'])
                  }, null, 2)
                ]),
                _: 1
              }),
              (_openBlock$1(), _createElementBlock(_Fragment, null, _renderList(SITE_ITEMS, (site) => {
                return _createVNode(_component_v_tab, {
                  key: site.value,
                  value: site.value,
                  "prepend-icon": "mdi-web"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(site.title), 1),
                    _createElementVNode("span", {
                      class: _normalizeClass(["tab-status-dot", sitePolicies[site.value]?.enabled ? 'on' : 'off'])
                    }, null, 2)
                  ]),
                  _: 2
                }, 1032, ["value"])
              }), 64))
            ]),
            _: 1
          }, 8, ["modelValue"]),
          _createVNode(_component_v_window, {
            modelValue: activeTab.value,
            "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((activeTab).value = $event))
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_window_item, { value: "global" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_5, [
                    _createVNode(_component_v_card, {
                      flat: "",
                      class: "config-section rounded border mb-4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_card_title, { class: "config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_icon, {
                              icon: "mdi-cog-outline",
                              color: "primary",
                              size: "small",
                              class: "mr-2"
                            }),
                            _cache[31] || (_cache[31] = _createTextVNode(" 基础设置 ", -1))
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_card_text, { class: "pa-4" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_row, null, {
                              default: _withCtx(() => [
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.enabled,
                                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.enabled) = $event)),
                                      label: "启用插件",
                                      color: "primary",
                                      density: "compact",
                                      "hide-details": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.notify,
                                      "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.notify) = $event)),
                                      label: "发送通知",
                                      color: "primary",
                                      density: "compact",
                                      "hide-details": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.run_once,
                                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.run_once) = $event)),
                                      label: "立即运行一次",
                                      color: "primary",
                                      density: "compact",
                                      "hide-details": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_select, {
                                      modelValue: config.mode,
                                      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((config.mode) = $event)),
                                      items: MODE_ITEMS,
                                      label: "运行模式",
                                      density: "compact",
                                      variant: "outlined",
                                      hint: "smart=全自动交易，harvest=只收获+补种+临期出售，可再用下方开关微调",
                                      "persistent-hint": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.use_proxy,
                                      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((config.use_proxy) = $event)),
                                      label: "使用 MP 系统代理",
                                      color: "info",
                                      density: "compact",
                                      "hide-details": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.dry_run,
                                      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((config.dry_run) = $event)),
                                      label: "仅模拟（不发送操作请求）",
                                      color: "warning",
                                      density: "compact",
                                      "hide-details": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_card, {
                      flat: "",
                      class: "config-section rounded border mb-4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_card_title, { class: "config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_icon, {
                              icon: "mdi-robot-outline",
                              color: "success",
                              size: "small",
                              class: "mr-2"
                            }),
                            _cache[32] || (_cache[32] = _createTextVNode(" 自动化功能 ", -1))
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_card_text, { class: "pa-4" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_row, null, {
                              default: _withCtx(() => [
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.auto_harvest,
                                      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((config.auto_harvest) = $event)),
                                      label: "自动收获",
                                      hint: "成熟作物自动收获",
                                      "persistent-hint": "",
                                      color: "primary",
                                      density: "compact"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.auto_plant,
                                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((config.auto_plant) = $event)),
                                      label: "自动种植/养殖",
                                      hint: "空地自动补种",
                                      "persistent-hint": "",
                                      color: "primary",
                                      density: "compact"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.auto_sell,
                                      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((config.auto_sell) = $event)),
                                      label: "自动出售",
                                      hint: "盈利区间内自动出售",
                                      "persistent-hint": "",
                                      color: "primary",
                                      density: "compact"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_switch, {
                                      modelValue: config.expiry_sale,
                                      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((config.expiry_sale) = $event)),
                                      label: "临期自动出售",
                                      hint: "剩余时间低于阈值强制出售",
                                      "persistent-hint": "",
                                      color: "primary",
                                      density: "compact"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.expire_threshold_minutes,
                                      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((config.expire_threshold_minutes) = $event)),
                                      modelModifiers: { number: true },
                                      label: "临期阈值（分钟）",
                                      type: "number",
                                      min: "10",
                                      density: "compact",
                                      variant: "outlined",
                                      hint: "剩余时间低于此值强制出售（分钟）",
                                      "persistent-hint": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_card, {
                      flat: "",
                      class: "config-section rounded border mb-4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_card_title, { class: "config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_icon, {
                              icon: "mdi-timer-sand",
                              color: "info",
                              size: "small",
                              class: "mr-2"
                            }),
                            _cache[33] || (_cache[33] = _createTextVNode(" 调度与网络 ", -1))
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_card_text, { class: "pa-4" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_row, null, {
                              default: _withCtx(() => [
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "6",
                                  md: "3"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.interval_minutes,
                                      "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((config.interval_minutes) = $event)),
                                      modelModifiers: { number: true },
                                      label: "智能交易间隔（分钟）",
                                      type: "number",
                                      min: "1",
                                      density: "compact",
                                      variant: "outlined"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "6",
                                  md: "3"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.harvest_interval_minutes,
                                      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((config.harvest_interval_minutes) = $event)),
                                      modelModifiers: { number: true },
                                      label: "自动收获间隔（分钟）",
                                      type: "number",
                                      min: "5",
                                      density: "compact",
                                      variant: "outlined"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "6",
                                  md: "3"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.request_interval,
                                      "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((config.request_interval) = $event)),
                                      modelModifiers: { number: true },
                                      label: "请求间隔（秒）",
                                      type: "number",
                                      min: "0",
                                      step: "0.1",
                                      density: "compact",
                                      variant: "outlined"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "6",
                                  md: "3"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.retry_count,
                                      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((config.retry_count) = $event)),
                                      modelModifiers: { number: true },
                                      label: "重试次数",
                                      type: "number",
                                      min: "0",
                                      density: "compact",
                                      variant: "outlined",
                                      "hide-details": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_card, {
                      flat: "",
                      class: "config-section rounded border"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_card_title, { class: "config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_icon, {
                              icon: "mdi-chart-line",
                              color: "warning",
                              size: "small",
                              class: "mr-2"
                            }),
                            _cache[34] || (_cache[34] = _createTextVNode(" 交易策略 ", -1))
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_card_text, { class: "pa-4" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_row, null, {
                              default: _withCtx(() => [
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.min_profit_rate,
                                      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((config.min_profit_rate) = $event)),
                                      modelModifiers: { number: true },
                                      label: "最低利润率",
                                      type: "number",
                                      min: "0",
                                      step: "0.01",
                                      density: "compact",
                                      variant: "outlined",
                                      hint: "0.1 表示 10%",
                                      "persistent-hint": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.max_profit_rate,
                                      "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((config.max_profit_rate) = $event)),
                                      modelModifiers: { number: true },
                                      label: "最高利润率",
                                      type: "number",
                                      min: "0",
                                      step: "0.01",
                                      density: "compact",
                                      variant: "outlined",
                                      hint: "0 表示无上限",
                                      "persistent-hint": ""
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                }),
                                _createVNode(_component_v_col, {
                                  cols: "12",
                                  sm: "4"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_text_field, {
                                      modelValue: config.max_sell_per_run,
                                      "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((config.max_sell_per_run) = $event)),
                                      modelModifiers: { number: true },
                                      label: "单轮单站最大出售数",
                                      type: "number",
                                      min: "1",
                                      density: "compact",
                                      variant: "outlined"
                                    }, null, 8, ["modelValue"])
                                  ]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    })
                  ])
                ]),
                _: 1
              }),
              (_openBlock$1(), _createElementBlock(_Fragment, null, _renderList(SITE_ITEMS, (site) => {
                return _createVNode(_component_v_window_item, {
                  key: site.value,
                  value: site.value
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_6, [
                      _createVNode(_component_v_card, {
                        flat: "",
                        class: "config-section rounded border mb-4"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card_title, { class: "config-section-title section-title-bg d-flex flex-wrap align-center ga-2 px-4 py-3" }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_icon, {
                                icon: "mdi-web",
                                color: "warning",
                                size: "small"
                              }),
                              _createElementVNode("span", _hoisted_7, _toDisplayString(site.title) + " 策略", 1),
                              _createVNode(_component_v_spacer),
                              _createVNode(_component_v_switch, {
                                modelValue: sitePolicies[site.value].enabled,
                                "onUpdate:modelValue": $event => ((sitePolicies[site.value].enabled) = $event),
                                label: "启用该站点",
                                color: "success",
                                density: "compact",
                                "hide-details": ""
                              }, null, 8, ["modelValue", "onUpdate:modelValue"])
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(_component_v_card_text, { class: "pa-4" }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_alert, {
                                type: "info",
                                variant: "tonal",
                                class: "mb-4 pa-3 text-body-2"
                              }, {
                                default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                                  _createTextVNode(" 未填写的覆盖项会自动继承全局设置；禁用站点只会将其从 site_ids 中移除。 ", -1)
                                ]))]),
                                _: 1
                              }),
                              _createVNode(_component_v_row, null, {
                                default: _withCtx(() => [
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: sitePolicies[site.value].mode,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].mode) = $event),
                                        items: siteModeItems.value,
                                        label: "运行模式",
                                        density: "compact",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_text_field, {
                                        modelValue: sitePolicies[site.value].min_profit_rate,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].min_profit_rate) = $event),
                                        modelModifiers: { number: true },
                                        label: "最低利润率",
                                        type: "number",
                                        min: "0",
                                        step: "0.01",
                                        clearable: "",
                                        density: "compact",
                                        variant: "outlined",
                                        placeholder: inheritPlaceholder('min_profit_rate'),
                                        "onClick:clear": $event => (sitePolicies[site.value].min_profit_rate = null)
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "placeholder", "onClick:clear"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_text_field, {
                                        modelValue: sitePolicies[site.value].max_profit_rate,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].max_profit_rate) = $event),
                                        modelModifiers: { number: true },
                                        label: "最高利润率",
                                        type: "number",
                                        min: "0",
                                        step: "0.01",
                                        clearable: "",
                                        density: "compact",
                                        variant: "outlined",
                                        placeholder: inheritPlaceholder('max_profit_rate'),
                                        "onClick:clear": $event => (sitePolicies[site.value].max_profit_rate = null)
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "placeholder", "onClick:clear"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_text_field, {
                                        modelValue: sitePolicies[site.value].expire_threshold_minutes,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].expire_threshold_minutes) = $event),
                                        modelModifiers: { number: true },
                                        label: "临期阈值（分钟）",
                                        type: "number",
                                        min: "10",
                                        clearable: "",
                                        density: "compact",
                                        variant: "outlined",
                                        placeholder: inheritPlaceholder('expire_threshold_minutes'),
                                        "onClick:clear": $event => (sitePolicies[site.value].expire_threshold_minutes = null)
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "placeholder", "onClick:clear"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_text_field, {
                                        modelValue: sitePolicies[site.value].max_sell_per_run,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].max_sell_per_run) = $event),
                                        modelModifiers: { number: true },
                                        label: "单轮最大出售数",
                                        type: "number",
                                        min: "1",
                                        clearable: "",
                                        density: "compact",
                                        variant: "outlined",
                                        placeholder: inheritPlaceholder('max_sell_per_run'),
                                        "onClick:clear": $event => (sitePolicies[site.value].max_sell_per_run = null)
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "placeholder", "onClick:clear"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_text_field, {
                                        modelValue: sitePolicies[site.value].request_interval,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].request_interval) = $event),
                                        modelModifiers: { number: true },
                                        label: "请求间隔（秒）",
                                        type: "number",
                                        min: "0",
                                        step: "0.1",
                                        clearable: "",
                                        density: "compact",
                                        variant: "outlined",
                                        placeholder: inheritPlaceholder('request_interval'),
                                        "onClick:clear": $event => (sitePolicies[site.value].request_interval = null)
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "placeholder", "onClick:clear"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: sitePolicies[site.value].use_proxy,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].use_proxy) = $event),
                                        items: booleanOverrideItems('use_proxy'),
                                        label: "代理设置",
                                        density: "compact",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: sitePolicies[site.value].dry_run,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].dry_run) = $event),
                                        items: booleanOverrideItems('dry_run'),
                                        label: "模拟模式",
                                        density: "compact",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: sitePolicies[site.value].auto_harvest,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].auto_harvest) = $event),
                                        items: automationItems('auto_harvest'),
                                        label: "自动收获",
                                        density: "compact",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: sitePolicies[site.value].auto_plant,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].auto_plant) = $event),
                                        items: automationItems('auto_plant'),
                                        label: "自动种植/养殖",
                                        density: "compact",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: sitePolicies[site.value].auto_sell,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].auto_sell) = $event),
                                        items: automationItems('auto_sell'),
                                        label: "自动出售",
                                        density: "compact",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: sitePolicies[site.value].expiry_sale,
                                        "onUpdate:modelValue": $event => ((sitePolicies[site.value].expiry_sale) = $event),
                                        items: automationItems('expiry_sale'),
                                        label: "临期自动出售",
                                        density: "compact",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                                    ]),
                                    _: 2
                                  }, 1024)
                                ]),
                                _: 2
                              }, 1024),
                              _createElementVNode("div", _hoisted_8, [
                                _cache[36] || (_cache[36] = _createElementVNode("span", { class: "text-body-2 text-medium-emphasis" }, "生效摘要", -1)),
                                _createVNode(_component_v_chip_group, {
                                  column: "",
                                  class: "ga-2"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "primary"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("模式：" + _toDisplayString(modeLabel(site.value)), 1)
                                      ]),
                                      _: 2
                                    }, 1024),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "success"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("利润：" + _toDisplayString(profitSummary(site.value)), 1)
                                      ]),
                                      _: 2
                                    }, 1024),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "blue"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("最大出售：" + _toDisplayString(effectiveSiteValue(site.value, 'max_sell_per_run')), 1)
                                      ]),
                                      _: 2
                                    }, 1024),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "info"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("代理：" + _toDisplayString(effectiveSiteValue(site.value, 'use_proxy') ? '启用' : '禁用'), 1)
                                      ]),
                                      _: 2
                                    }, 1024),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: effectiveSiteValue(site.value, 'dry_run') ? 'warning' : 'success'
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(" Dry Run：" + _toDisplayString(effectiveSiteValue(site.value, 'dry_run') ? '启用' : '禁用'), 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["color"]),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "success"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("收获:" + _toDisplayString(effectiveSiteValue(site.value, 'auto_harvest') ? '开' : '关'), 1)
                                      ]),
                                      _: 2
                                    }, 1024),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "success"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("补种:" + _toDisplayString(effectiveSiteValue(site.value, 'auto_plant') ? '开' : '关'), 1)
                                      ]),
                                      _: 2
                                    }, 1024),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "success"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("出售:" + _toDisplayString(effectiveSiteValue(site.value, 'auto_sell') ? '开' : '关'), 1)
                                      ]),
                                      _: 2
                                    }, 1024),
                                    _createVNode(_component_v_chip, {
                                      size: "small",
                                      variant: "tonal",
                                      color: "success"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("临期:" + _toDisplayString(effectiveSiteValue(site.value, 'expiry_sale') ? '开' : '关'), 1)
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ]),
                                  _: 2
                                }, 1024)
                              ])
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1024),
                      (site.value === 'siqi')
                        ? (_openBlock$1(), _createBlock$1(_component_v_card, {
                            key: 0,
                            flat: "",
                            class: "config-section rounded border"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_card_title, { class: "config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3" }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_v_icon, {
                                    icon: "mdi-shield-alert-outline",
                                    color: "warning",
                                    size: "small",
                                    class: "mr-2"
                                  }),
                                  _cache[37] || (_cache[37] = _createTextVNode(" 思齐专属功能 ", -1))
                                ]),
                                _: 1
                              }),
                              _createVNode(_component_v_card_text, { class: "pa-4" }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_v_alert, {
                                    type: "warning",
                                    variant: "tonal",
                                    class: "mb-4 pa-3 text-body-2"
                                  }, {
                                    default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                                      _createTextVNode(" 验证码收获、偷菜、点赞和扩地属于高风险行为；除 OCR 外默认关闭，开启即表示自行承担账号风控风险。 ", -1)
                                    ]))]),
                                    _: 1
                                  }),
                                  _createVNode(_component_v_row, null, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_col, {
                                        cols: "12",
                                        sm: "6",
                                        md: "4"
                                      }, {
                                        default: _withCtx(() => [
                                          _createVNode(_component_v_switch, {
                                            modelValue: config.siqi_auto_captcha_harvest,
                                            "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((config.siqi_auto_captcha_harvest) = $event)),
                                            label: "验证码自动收获",
                                            color: "primary",
                                            density: "compact",
                                            "hide-details": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode(_component_v_col, {
                                        cols: "12",
                                        sm: "6",
                                        md: "4"
                                      }, {
                                        default: _withCtx(() => [
                                          _createVNode(_component_v_switch, {
                                            modelValue: config.siqi_captcha_ocr,
                                            "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((config.siqi_captcha_ocr) = $event)),
                                            label: "OCR 优先识别",
                                            color: "primary",
                                            density: "compact",
                                            "hide-details": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode(_component_v_col, {
                                        cols: "12",
                                        sm: "6",
                                        md: "4"
                                      }, {
                                        default: _withCtx(() => [
                                          _createVNode(_component_v_switch, {
                                            modelValue: config.siqi_auto_buy_slot,
                                            "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((config.siqi_auto_buy_slot) = $event)),
                                            label: "自动扩地",
                                            color: "primary",
                                            density: "compact",
                                            "hide-details": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode(_component_v_col, {
                                        cols: "12",
                                        sm: "6",
                                        md: "4"
                                      }, {
                                        default: _withCtx(() => [
                                          _createVNode(_component_v_switch, {
                                            modelValue: config.siqi_auto_steal,
                                            "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((config.siqi_auto_steal) = $event)),
                                            label: "每日偷菜",
                                            color: "primary",
                                            density: "compact",
                                            "hide-details": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode(_component_v_col, {
                                        cols: "12",
                                        sm: "6",
                                        md: "4"
                                      }, {
                                        default: _withCtx(() => [
                                          _createVNode(_component_v_switch, {
                                            modelValue: config.siqi_auto_like,
                                            "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((config.siqi_auto_like) = $event)),
                                            label: "每日点赞",
                                            color: "primary",
                                            density: "compact",
                                            "hide-details": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  })
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          }))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _: 2
                }, 1032, ["value"])
              }), 64))
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const FarmConfigForm = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-825bd720"]]);

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

return (_ctx, _cache) => {
  return (_openBlock(), _createBlock(FarmConfigForm, {
    "initial-config": props.initialConfig,
    onSave: _cache[0] || (_cache[0] = $event => (emit('save', $event))),
    onSwitch: _cache[1] || (_cache[1] = $event => (emit('switch'))),
    onClose: _cache[2] || (_cache[2] = $event => (emit('close')))
  }, null, 8, ["initial-config"]))
}
}

};

export { _sfc_main as default };
