import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { e as errorText, g as getPluginApi } from './api-Dwb_bXKu.js';

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "text-caption text-medium-emphasis mt-1" };

const {computed,onMounted,reactive,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerEnhance' },
  sourcePluginId: { type: String, default: 'MediaServerEnhance' },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

const DEFAULTS = {
  enabled: false,
  observe_only: false,
  notify: false,
  history_limit: 300,
  request_timeout: 30,
  refresh_enabled: false,
  refresh_servers: [],
  refresh_libraries: [],
  refresh_on_transfer: true,
  refresh_debounce_seconds: 30,
  refresh_delay_seconds: 0,
  refresh_recent_enabled: false,
  refresh_recent_count: 20,
  refresh_cron: '',
  audit_enabled: false,
  audit_servers: [],
  audit_libraries: [],
  audit_checks: ['missing_episode', 'duplicate', 'empty_dir', 'orphan_meta', 'missing_image', 'invalid_path'],
  audit_max_items: 20000,
  audit_cron: '',
  covers_enabled: false,
  covers_servers: [],
  covers_libraries: [],
  covers_style: 'poster',
  covers_limit: 20,
  covers_upload: false,
  covers_font: '',
  covers_output_dir: '',
  covers_cron: '',
  capabilities_enabled: false,
  capabilities_servers: [],
  capabilities_watch: ['StrmAssistant', '神医'],
  capabilities_cron: '',
};

const AUDIT_CHECK_ITEMS = [
  { title: '缺集 / 断季', value: 'missing_episode' },
  { title: '重复媒体 / 多版本', value: 'duplicate' },
  { title: '空壳目录', value: 'empty_dir' },
  { title: '孤立旁车文件', value: 'orphan_meta' },
  { title: '缺少封面图', value: 'missing_image' },
  { title: '失效路径', value: 'invalid_path' },
];

const COVER_STYLES = [
  { title: '底部渐变', value: 'poster' },
  { title: '底部色条', value: 'clean' },
  { title: '侧栏竖条', value: 'gradient' },
];

const CRON_HINTS = {
  '': '留空表示不启用定时任务（仍可用页面按钮或远程命令手动触发）',
};

const tabs = [
  { key: 'general', title: '通用' },
  { key: 'refresh', title: '服务器与刷新' },
  { key: 'audit', title: '媒体库体检' },
  { key: 'covers', title: '封面工坊' },
  { key: 'capabilities', title: '服务端能力' },
];

const form = reactive({ ...DEFAULTS });
const activeTab = ref('general');
const serverItems = ref([]);
const librariesByServer = ref({});
const serverLoading = ref(false);
const saveMessage = ref('');
const saveError = ref(false);
const savePending = ref(false);

const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options);

function listValue(value) {
  if (Array.isArray(value)) return value.filter((item) => item !== null && item !== undefined && item !== '')
  if (value === null || value === undefined || value === '') return []
  return String(value).split(',').map((item) => item.trim()).filter(Boolean)
}

function assignConfig(config) {
  const source = config && typeof config === 'object' ? config : {};
  Object.keys(DEFAULTS).forEach((key) => {
    const fallback = DEFAULTS[key];
    const raw = source[key];
    if (Array.isArray(fallback)) {
      form[key] = listValue(raw === undefined || raw === null ? fallback : raw);
    } else if (typeof fallback === 'boolean') {
      form[key] = raw === undefined || raw === null ? fallback : raw === true || raw === 'true';
    } else if (typeof fallback === 'number') {
      const parsed = Number(raw);
      form[key] = Number.isFinite(parsed) ? parsed : fallback;
    } else {
      form[key] = raw === undefined || raw === null ? fallback : String(raw);
    }
  });
}

watch(() => props.initialConfig, (value) => assignConfig(value), { immediate: true, deep: true });

const serverOptions = computed(() => serverItems.value.map((item) => ({
  title: `${item.name}（${item.type || '未知'}）`,
  value: item.name,
})));

const capabilityWatchText = computed({
  get: () => (form.capabilities_watch || []).join(', '),
  set: (value) => {
    form.capabilities_watch = listValue(value);
  },
});
function libraryOptions(servers) {
  const options = []
  ;(servers || []).forEach((server) => {
    const rows = librariesByServer.value[server] || [];
    rows.forEach((row) => {
      options.push({
        title: `${server} / ${row.name || row.id}`,
        value: `${server}|${row.id}`,
      });
    });
  });
  return options
}

async function loadServers() {
  serverLoading.value = true;
  try {
    const rows = await getApi('servers', { feedback: 'silent' });
    serverItems.value = Array.isArray(rows) ? rows : [];
  } catch (error) {
    serverItems.value = [];
    saveError.value = true;
    saveMessage.value = `读取媒体服务器列表失败：${errorText(error)}`;
  } finally {
    serverLoading.value = false;
  }
}

async function loadLibraries(servers) {
  const targets = (servers || []).filter((server) => !librariesByServer.value[server]);
  if (!targets.length) return
  await Promise.all(targets.map(async (server) => {
    try {
      const rows = await getApi(`libraries/${encodeURIComponent(server)}`, { feedback: 'silent' });
      librariesByServer.value = { ...librariesByServer.value, [server]: Array.isArray(rows) ? rows : [] };
    } catch (error) {
      librariesByServer.value = { ...librariesByServer.value, [server]: [] };
    }
  }));
}

function refreshLibraries(servers) {
  loadLibraries(servers);
}

onMounted(() => {
  loadServers();
});

async function saveConfig() {
  savePending.value = true;
  saveError.value = false;
  saveMessage.value = '';
  const payload = { ...form };
  Object.keys(payload).forEach((key) => {
    if (Array.isArray(DEFAULTS[key])) payload[key] = listValue(payload[key]);
  });
  try {
    const response = await props.api.put(`plugin/${props.pluginId}`, payload);
    if (response?.success === false || response?.data?.success === false) {
      throw new Error(response.message || response.data?.message || '保存配置失败')
    }
    saveMessage.value = '配置已保存，窗口保持打开。刷新插件或页面后生效。';
  } catch (error) {
    saveError.value = true;
    saveMessage.value = errorText(error);
  } finally {
    savePending.value = false;
  }
}

function close() {
  emit('close');
}

return (_ctx, _cache) => {
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_tab = _resolveComponent("v-tab");
  const _component_v_tabs = _resolveComponent("v-tabs");
  const _component_v_divider = _resolveComponent("v-divider");
  const _component_v_switch = _resolveComponent("v-switch");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_window_item = _resolveComponent("v-window-item");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_window = _resolveComponent("v-window");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_actions = _resolveComponent("v-card-actions");
  const _component_v_card = _resolveComponent("v-card");

  return (_openBlock(), _createBlock(_component_v_card, {
    rounded: "lg",
    variant: "flat"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card_title, { class: "d-flex align-center ga-2 py-3" }, {
        default: _withCtx(() => [
          _cache[37] || (_cache[37] = _createElementVNode("span", { class: "text-subtitle-1 font-weight-medium" }, "媒体服务器增强 · 配置", -1)),
          _createVNode(_component_v_spacer),
          (form.enabled)
            ? (_openBlock(), _createBlock(_component_v_chip, {
                key: 0,
                color: "success",
                size: "small",
                variant: "tonal"
              }, {
                default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                  _createTextVNode("总开关已开", -1)
                ]))]),
                _: 1
              }))
            : (_openBlock(), _createBlock(_component_v_chip, {
                key: 1,
                color: "grey",
                size: "small",
                variant: "tonal"
              }, {
                default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                  _createTextVNode("总开关已关", -1)
                ]))]),
                _: 1
              }))
        ]),
        _: 1
      }),
      _createVNode(_component_v_tabs, {
        modelValue: activeTab.value,
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((activeTab).value = $event)),
        density: "compact",
        color: "primary"
      }, {
        default: _withCtx(() => [
          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
            return _createVNode(_component_v_tab, {
              key: tab.key,
              value: tab.key
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(tab.title), 1)
              ]),
              _: 2
            }, 1032, ["value"])
          }), 64))
        ]),
        _: 1
      }, 8, ["modelValue"]),
      _createVNode(_component_v_divider),
      _createVNode(_component_v_card_text, {
        class: "pt-4",
        style: {"max-height":"58vh","overflow-y":"auto"}
      }, {
        default: _withCtx(() => [
          _createVNode(_component_v_window, {
            modelValue: activeTab.value,
            "onUpdate:modelValue": _cache[34] || (_cache[34] = $event => ((activeTab).value = $event))
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_window_item, { value: "general" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_row, { dense: "" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_switch, {
                            modelValue: form.enabled,
                            "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.enabled) = $event)),
                            color: "primary",
                            density: "compact",
                            "hide-details": "",
                            label: "启用插件"
                          }, null, 8, ["modelValue"]),
                          _cache[38] || (_cache[38] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-3" }, " 关闭后全部模块停止工作，定时任务不再注册，事件也不再响应。 ", -1))
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_switch, {
                            modelValue: form.notify,
                            "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.notify) = $event)),
                            color: "primary",
                            density: "compact",
                            "hide-details": "",
                            label: "推送运行通知"
                          }, null, 8, ["modelValue"]),
                          _cache[40] || (_cache[40] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-3" }, " 仅在任务失败或部分失败时推送，成功任务不打扰。 ", -1)),
                          _createVNode(_component_v_col, { cols: "12" }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_switch, {
                                modelValue: form.observe_only,
                                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.observe_only) = $event)),
                                color: "primary",
                                density: "compact",
                                "hide-details": "",
                                label: "观察模式（只记录不执行）"
                              }, null, 8, ["modelValue"]),
                              _cache[39] || (_cache[39] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-3" }, " 开启后体检等只读检查照常运行，但所有刷新请求与封面上传都被跳过， 任务时间线会记录「观察模式」结果。适合先观察插件会做什么再放开执行。 ", -1))
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.history_limit,
                            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.history_limit) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "20",
                            max: "5000",
                            density: "compact",
                            variant: "outlined",
                            label: "任务历史保留条数",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.request_timeout,
                            "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.request_timeout) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "5",
                            max: "300",
                            density: "compact",
                            variant: "outlined",
                            label: "请求超时（秒）",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_alert, {
                    class: "mt-4",
                    density: "compact",
                    type: "info",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                      _createTextVNode(" 媒体服务器连接统一由 MoviePilot 的「媒体服务器」设置提供，本插件不重复维护实例。 ", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "refresh" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: form.refresh_enabled,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.refresh_enabled) = $event)),
                    color: "primary",
                    density: "compact",
                    "hide-details": "",
                    label: "启用服务器与刷新模块"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_row, {
                    dense: "",
                    class: "mt-2"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.refresh_servers,
                            "onUpdate:modelValue": [
                              _cache[7] || (_cache[7] = $event => ((form.refresh_servers) = $event)),
                              refreshLibraries
                            ],
                            items: serverOptions.value,
                            loading: serverLoading.value,
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            label: "作用服务器（留空=全部）",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "items", "loading"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.refresh_libraries,
                            "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.refresh_libraries) = $event)),
                            items: libraryOptions(form.refresh_servers),
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            label: "作用媒体库（留空=全部）",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "items"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_switch, {
                            modelValue: form.refresh_on_transfer,
                            "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.refresh_on_transfer) = $event)),
                            color: "primary",
                            density: "compact",
                            "hide-details": "",
                            label: "整理完成后自动刷新"
                          }, null, 8, ["modelValue"]),
                          _cache[42] || (_cache[42] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " 命中媒体库路径的入库条目会在防抖窗口结束后合并成一次刷新。 ", -1))
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.refresh_debounce_seconds,
                            "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.refresh_debounce_seconds) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "0",
                            max: "3600",
                            density: "compact",
                            variant: "outlined",
                            label: "防抖窗口（秒）",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.refresh_delay_seconds,
                            "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.refresh_delay_seconds) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "0",
                            max: "86400",
                            density: "compact",
                            variant: "outlined",
                            label: "延迟刷新（秒）",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_switch, {
                            modelValue: form.refresh_recent_enabled,
                            "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.refresh_recent_enabled) = $event)),
                            color: "primary",
                            density: "compact",
                            "hide-details": "",
                            label: "定时任务只刷新最近媒体"
                          }, null, 8, ["modelValue"]),
                          _cache[43] || (_cache[43] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " 关闭时定时任务执行整库刷新；开启时只刷新最近条目，压力更小。 ", -1))
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.refresh_recent_count,
                            "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.refresh_recent_count) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "1",
                            max: "200",
                            density: "compact",
                            variant: "outlined",
                            label: "最近条目数量",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.refresh_cron,
                            "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.refresh_cron) = $event)),
                            density: "compact",
                            variant: "outlined",
                            label: "定时刷新 Cron",
                            placeholder: "0 3 * * *",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createElementVNode("div", _hoisted_1, _toDisplayString(CRON_HINTS['']), 1)
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "audit" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: form.audit_enabled,
                    "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.audit_enabled) = $event)),
                    color: "primary",
                    density: "compact",
                    "hide-details": "",
                    label: "启用媒体库体检模块"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_row, {
                    dense: "",
                    class: "mt-2"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.audit_servers,
                            "onUpdate:modelValue": [
                              _cache[16] || (_cache[16] = $event => ((form.audit_servers) = $event)),
                              refreshLibraries
                            ],
                            items: serverOptions.value,
                            loading: serverLoading.value,
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            label: "作用服务器（留空=全部）",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "items", "loading"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.audit_libraries,
                            "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.audit_libraries) = $event)),
                            items: libraryOptions(form.audit_servers),
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            label: "作用媒体库（留空=全部）",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "items"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, { cols: "12" }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.audit_checks,
                            "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.audit_checks) = $event)),
                            items: AUDIT_CHECK_ITEMS,
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            density: "compact",
                            variant: "outlined",
                            label: "检查项",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.audit_max_items,
                            "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.audit_max_items) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "100",
                            max: "200000",
                            density: "compact",
                            variant: "outlined",
                            label: "单次扫描条目上限",
                            "hide-details": ""
                          }, null, 8, ["modelValue"]),
                          _cache[44] || (_cache[44] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " 超出上限时报告会标记「已截断」，可在体检页单独重跑某个媒体库。 ", -1))
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.audit_cron,
                            "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.audit_cron) = $event)),
                            density: "compact",
                            variant: "outlined",
                            label: "定时体检 Cron",
                            placeholder: "0 4 * * 1",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_alert, {
                    class: "mt-3",
                    density: "compact",
                    type: "warning",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                      _createTextVNode(" 体检只读：不删除文件、不改数据库，只读取服务器返回的条目与本地目录状态。 ", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "covers" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: form.covers_enabled,
                    "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.covers_enabled) = $event)),
                    color: "primary",
                    density: "compact",
                    "hide-details": "",
                    label: "启用封面工坊模块"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_row, {
                    dense: "",
                    class: "mt-2"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.covers_servers,
                            "onUpdate:modelValue": [
                              _cache[22] || (_cache[22] = $event => ((form.covers_servers) = $event)),
                              refreshLibraries
                            ],
                            items: serverOptions.value,
                            loading: serverLoading.value,
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            label: "作用服务器（留空=全部）",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "items", "loading"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.covers_libraries,
                            "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.covers_libraries) = $event)),
                            items: libraryOptions(form.covers_servers),
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            label: "作用媒体库（留空=全部）",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "items"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.covers_style,
                            "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((form.covers_style) = $event)),
                            items: COVER_STYLES,
                            density: "compact",
                            variant: "outlined",
                            label: "封面风格",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.covers_limit,
                            "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.covers_limit) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "1",
                            max: "500",
                            density: "compact",
                            variant: "outlined",
                            label: "单次生成上限",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_switch, {
                            modelValue: form.covers_upload,
                            "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((form.covers_upload) = $event)),
                            color: "primary",
                            density: "compact",
                            "hide-details": "",
                            label: "生成后上传回服务器"
                          }, null, 8, ["modelValue"]),
                          _cache[46] || (_cache[46] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " 关闭时只落地到本地目录，可在运行页预览后再决定是否上传。 ", -1))
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.covers_font,
                            "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((form.covers_font) = $event)),
                            density: "compact",
                            variant: "outlined",
                            label: "字体文件路径（可选）",
                            placeholder: "C:/Windows/Fonts/msyhbd.ttc",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.covers_output_dir,
                            "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((form.covers_output_dir) = $event)),
                            density: "compact",
                            variant: "outlined",
                            label: "输出目录（可选）",
                            placeholder: "留空使用插件数据目录",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.covers_cron,
                            "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((form.covers_cron) = $event)),
                            density: "compact",
                            variant: "outlined",
                            label: "定时生成 Cron",
                            placeholder: "0 5 * * *",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_alert, {
                    class: "mt-3",
                    density: "compact",
                    type: "info",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                      _createTextVNode(" 封面渲染依赖宿主已安装的 Pillow；缺失时模块会跳过渲染并在运行页提示。 ", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "capabilities" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: form.capabilities_enabled,
                    "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((form.capabilities_enabled) = $event)),
                    color: "primary",
                    density: "compact",
                    "hide-details": "",
                    label: "启用服务端能力模块"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_row, {
                    dense: "",
                    class: "mt-2"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_select, {
                            modelValue: form.capabilities_servers,
                            "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((form.capabilities_servers) = $event)),
                            items: serverOptions.value,
                            loading: serverLoading.value,
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            label: "作用服务器（留空=全部）",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "items", "loading"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: capabilityWatchText.value,
                            "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((capabilityWatchText).value = $event)),
                            density: "compact",
                            variant: "outlined",
                            label: "关注的插件关键词（逗号分隔）",
                            hint: "命中即视为该能力已就绪",
                            "persistent-hint": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.capabilities_cron,
                            "onUpdate:modelValue": _cache[33] || (_cache[33] = $event => ((form.capabilities_cron) = $event)),
                            density: "compact",
                            variant: "outlined",
                            label: "定时探测 Cron",
                            placeholder: "0 6 * * *",
                            "hide-details": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_alert, {
                    class: "mt-3",
                    density: "compact",
                    type: "info",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                      _createTextVNode(" 本节只识别 Emby/Jellyfin 已安装的服务端插件，不代为安装，也不修改其配置。 ", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _: 1
      }),
      _createVNode(_component_v_divider),
      _createVNode(_component_v_card_actions, { class: "px-4 py-3" }, {
        default: _withCtx(() => [
          _createVNode(_component_v_btn, {
            color: "primary",
            loading: savePending.value,
            onClick: saveConfig
          }, {
            default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
              _createTextVNode("保存配置", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_v_btn, {
            variant: "text",
            onClick: close
          }, {
            default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
              _createTextVNode("关闭", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_spacer),
          (saveMessage.value)
            ? (_openBlock(), _createElementBlock("span", {
                key: 0,
                class: _normalizeClass(["text-caption", saveError.value ? 'text-error' : 'text-success'])
              }, _toDisplayString(saveMessage.value), 3))
            : _createCommentVNode("", true)
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};

export { _sfc_main as default };
