import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { g as getPluginApi, e as errorText, p as postPluginJsonApi } from './api-Dwb_bXKu.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createBlock:_createBlock,normalizeStyle:_normalizeStyle,createCommentVNode:_createCommentVNode} = await importShared('vue');


const _hoisted_1 = { class: "text-h5" };
const _hoisted_2 = { class: "text-h5" };
const _hoisted_3 = { class: "text-h5" };
const _hoisted_4 = { class: "text-h5" };
const _hoisted_5 = { class: "d-flex flex-wrap ga-2 my-4" };
const _hoisted_6 = { class: "d-flex flex-wrap ga-2 mb-3" };
const _hoisted_7 = { key: 0 };
const _hoisted_8 = { class: "d-flex flex-wrap align-center ga-2 mb-3" };
const _hoisted_9 = { class: "text-caption text-medium-emphasis" };
const _hoisted_10 = { key: 0 };
const _hoisted_11 = {
  colspan: "6",
  class: "text-center text-medium-emphasis py-4"
};
const _hoisted_12 = { class: "d-flex flex-wrap align-center ga-2 mb-3" };
const _hoisted_13 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_14 = { class: "d-flex flex-wrap ga-2 mb-3" };
const _hoisted_15 = { class: "text-body-2" };
const _hoisted_16 = { key: 0 };
const _hoisted_17 = {
  colspan: "5",
  class: "text-center text-medium-emphasis py-4"
};
const _hoisted_18 = { class: "d-flex flex-wrap align-center ga-2 mb-3" };
const _hoisted_19 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_20 = {
  key: 0,
  class: "mse-cover-grid"
};
const _hoisted_21 = {
  key: 1,
  class: "text-caption text-medium-emphasis d-flex align-center justify-center",
  style: {"height":"180px"}
};
const _hoisted_22 = { class: "text-body-2 mt-2 text-truncate" };
const _hoisted_23 = { class: "text-caption text-medium-emphasis text-truncate" };
const _hoisted_24 = {
  key: 1,
  class: "text-center text-medium-emphasis py-8"
};
const _hoisted_25 = { class: "d-flex flex-wrap align-center ga-2 mb-3" };
const _hoisted_26 = { class: "text-caption text-medium-emphasis" };
const _hoisted_27 = {
  key: 0,
  class: "d-flex flex-column ga-3"
};
const _hoisted_28 = { class: "d-flex align-center ga-2 mb-2" };
const _hoisted_29 = { class: "text-body-1 font-weight-medium" };
const _hoisted_30 = { class: "text-caption text-medium-emphasis" };
const _hoisted_31 = {
  key: 1,
  class: "d-flex flex-wrap ga-2 mb-2"
};
const _hoisted_32 = {
  key: 3,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_33 = {
  key: 1,
  class: "text-center text-medium-emphasis py-8"
};
const _hoisted_34 = { class: "d-flex flex-wrap align-center ga-2 mb-3" };
const _hoisted_35 = { class: "text-caption text-medium-emphasis" };
const _hoisted_36 = {
  class: "text-medium-emphasis",
  style: {"min-width":"120px"}
};
const _hoisted_37 = {
  class: "text-medium-emphasis",
  style: {"min-width":"120px"}
};
const _hoisted_38 = {
  class: "text-medium-emphasis",
  style: {"min-width":"120px"}
};
const _hoisted_39 = { class: "font-weight-medium" };
const _hoisted_40 = {
  class: "text-medium-emphasis",
  style: {"min-width":"96px"}
};
const _hoisted_41 = { class: "text-truncate" };
const _hoisted_42 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'MediaServerEnhance' },
  sourcePluginId: { type: String, default: 'MediaServerEnhance' },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

const tabs = [
  { key: 'overview', title: '总览' },
  { key: 'refresh', title: '服务器与刷新' },
  { key: 'audit', title: '媒体库体检' },
  { key: 'covers', title: '封面工坊' },
  { key: 'capabilities', title: '服务端能力' },
  { key: 'diagnostics', title: '诊断' },
];

const MODULE_LABELS = {
  refresh: '服务器与刷新',
  audit: '媒体库体检',
  covers: '封面工坊',
  capabilities: '服务端能力',
};

const AUDIT_LABELS = {
  missing_episode: '缺集',
  duplicate: '重复',
  empty_dir: '空目录',
  orphan_meta: '孤立旁车',
  missing_image: '缺封面',
  invalid_path: '路径失效',
};

const activeTab = ref('overview');
const overview = ref(null);
const overviewLoading = ref(false);
const jobs = ref([]);
const jobsLoading = ref(false);
const auditReport = ref(null);
const auditLoading = ref(false);
const coverItems = ref([]);
const coverMessage = ref('');
const coverLoading = ref(false);
const coverStyle = ref('poster');
const coverLimit = ref(6);
const capabilities = ref(null);
const capabilityLoading = ref(false);
const diagnostics = ref(null);
const diagnosticsLoading = ref(false);
const busy = ref('');
const notice = ref({ show: false, text: '', color: 'success' });

const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options);
const postApi = (path, payload = {}, options = {}) => postPluginJsonApi(props.api, props.pluginId, path, payload, options);

function toast(text, color = 'success') {
  notice.value = { show: true, text: String(text || ''), color };
}

function errorToast(error) {
  toast(errorText(error), 'error');
}

const serverRows = computed(() => (overview.value?.servers || []));
const moduleStates = computed(() => (overview.value?.module_states || {}));
const auditCounts = computed(() => {
  const counts = auditReport.value?.counts || {};
  return Object.keys(AUDIT_LABELS)
    .filter((key) => Number(counts[key] || 0) > 0)
    .map((key) => ({ key, title: AUDIT_LABELS[key], value: Number(counts[key] || 0) }))
});

const serverHeaders = [
  { title: '服务器', key: 'name' },
  { title: '类型', key: 'type', width: 100 },
  { title: '状态', key: 'online', width: 90 },
  { title: '媒体库', key: 'library_count', width: 90 },
  { title: '条目', key: 'item_count', width: 100 },
  { title: '插件', key: 'plugin_count', width: 90 },
];

const jobHeaders = [
  { title: '时间', key: 'started_at', width: 170 },
  { title: '模块', key: 'module', width: 130 },
  { title: '触发器', key: 'trigger', width: 130 },
  { title: '状态', key: 'status', width: 100 },
  { title: '成功/失败/跳过', key: 'counts', width: 140 },
  { title: '说明', key: 'message' },
];

const auditHeaders = [
  { title: '问题', key: 'issue_type', width: 120 },
  { title: '服务器', key: 'server', width: 120 },
  { title: '媒体库', key: 'library_name', width: 140 },
  { title: '标题', key: 'title' },
  { title: '详情', key: 'detail' },
];

const pluginHeaders = [
  { title: '服务端插件', key: 'name' },
  { title: '版本', key: 'version', width: 120 },
  { title: '状态', key: 'status', width: 120 },
];

function moduleLabel(value) {
  return MODULE_LABELS[value] || value || '未知'
}

function statusColor(value) {
  if (value === 'success' || value === 'generated' || value === 'online') return 'success'
  if (value === 'partial' || value === 'running') return 'warning'
  if (value === 'failed' || value === 'error') return 'error'
  return 'grey'
}

function jobCountsText(row) {
  const parts = [];
  if (row.success) parts.push(`成功 ${row.success}`);
  if (row.failed) parts.push(`失败 ${row.failed}`);
  if (row.skipped) parts.push(`跳过 ${row.skipped}`);
  return parts.join(' / ') || '-'
}

async function loadOverview() {
  overviewLoading.value = true;
  try {
    overview.value = await getApi('overview', { feedback: 'silent' });
  } catch (error) {
    errorToast(error);
  } finally {
    overviewLoading.value = false;
  }
}

async function loadJobs(module = '') {
  jobsLoading.value = true;
  try {
    const query = module ? `?module=${encodeURIComponent(module)}` : '';
    const result = await getApi(`jobs/1/30${query}`, { feedback: 'silent' });
    jobs.value = Array.isArray(result?.items) ? result.items : [];
  } catch (error) {
    jobs.value = [];
    errorToast(error);
  } finally {
    jobsLoading.value = false;
  }
}

async function loadAudit() {
  auditLoading.value = true;
  try {
    auditReport.value = await getApi('audit', { feedback: 'silent' });
  } catch (error) {
    errorToast(error);
  } finally {
    auditLoading.value = false;
  }
}

async function loadCapabilities() {
  capabilityLoading.value = true;
  try {
    capabilities.value = await getApi('capabilities', { feedback: 'silent' });
  } catch (error) {
    errorToast(error);
  } finally {
    capabilityLoading.value = false;
  }
}

async function loadDiagnostics() {
  diagnosticsLoading.value = true;
  try {
    diagnostics.value = await getApi('diagnostics', { feedback: 'silent' });
  } catch (error) {
    errorToast(error);
  } finally {
    diagnosticsLoading.value = false;
  }
}

async function runRefresh(mode = 'library') {
  busy.value = 'refresh';
  try {
    const result = await postApi('refresh', { mode, recent_count: 20 });
    toast(result?.message || '刷新任务已提交', result?.ok ? 'success' : 'warning');
    await Promise.all([loadOverview(), loadJobs('refresh')]);
  } catch (error) {
    errorToast(error);
  } finally {
    busy.value = '';
  }
}

async function flushPending() {
  busy.value = 'pending';
  try {
    const result = await postApi('refresh_pending', {});
    toast(result?.message || '已提交待刷新条目', result?.ok ? 'success' : 'warning');
    await Promise.all([loadOverview(), loadJobs('refresh')]);
  } catch (error) {
    errorToast(error);
  } finally {
    busy.value = '';
  }
}

async function runAudit() {
  busy.value = 'audit';
  auditLoading.value = true;
  try {
    const result = await postApi('audit_run', {});
    await loadAudit();
    toast(result?.message || '体检已完成', result?.ok ? 'success' : 'warning');
    await Promise.all([loadOverview(), loadJobs('audit')]);
  } catch (error) {
    errorToast(error);
  } finally {
    busy.value = '';
    auditLoading.value = false;
  }
}

async function previewCovers() {
  coverLoading.value = true;
  coverMessage.value = '';
  try {
    const result = await postApi('cover_preview', { style: coverStyle.value, limit: coverLimit.value });
    coverItems.value = Array.isArray(result?.items) ? result.items : [];
    coverMessage.value = result?.message || `已生成 ${result?.generated || 0} 张封面（未上传）`;
    if (!coverItems.value.length) toast(coverMessage.value, 'warning');
  } catch (error) {
    coverItems.value = [];
    errorToast(error);
  } finally {
    coverLoading.value = false;
  }
}

async function runCovers() {
  busy.value = 'covers';
  try {
    const result = await postApi('cover_run', { style: coverStyle.value, limit: coverLimit.value, upload: true });
    toast(result?.message || '封面任务已提交', result?.ok ? 'success' : 'warning');
    await Promise.all([loadOverview(), loadJobs('covers')]);
  } catch (error) {
    errorToast(error);
  } finally {
    busy.value = '';
  }
}

async function probeCapabilities() {
  capabilityLoading.value = true;
  try {
    capabilities.value = await postApi('capabilities_probe', {});
    toast('服务端能力探测已完成');
    await Promise.all([loadOverview(), loadJobs('capabilities')]);
  } catch (error) {
    errorToast(error);
  } finally {
    capabilityLoading.value = false;
  }
}

async function clearHistory(target, module = '') {
  busy.value = `clear-${target}`;
  try {
    const result = await postApi('history_clear', { target, module });
    toast(result?.message || '已清理');
    if (target === 'jobs') await loadJobs('');
    if (target === 'audit') auditReport.value = null;
    if (target === 'covers') coverItems.value = [];
    if (target === 'capabilities') capabilities.value = null;
  } catch (error) {
    errorToast(error);
  } finally {
    busy.value = '';
  }
}

function onTabChange(key) {
  if (key === 'overview') loadOverview();
  if (key === 'refresh') loadJobs('refresh');
  if (key === 'audit' && !auditReport.value) loadAudit();
  if (key === 'capabilities' && !capabilities.value) loadCapabilities();
  if (key === 'diagnostics' && !diagnostics.value) loadDiagnostics();
}

onMounted(() => {
  loadOverview();
  loadJobs('');
});

return (_ctx, _cache) => {
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_tab = _resolveComponent("v-tab");
  const _component_v_tabs = _resolveComponent("v-tabs");
  const _component_v_divider = _resolveComponent("v-divider");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_table = _resolveComponent("v-table");
  const _component_v_expansion_panel_text = _resolveComponent("v-expansion-panel-text");
  const _component_v_expansion_panel = _resolveComponent("v-expansion-panel");
  const _component_v_expansion_panels = _resolveComponent("v-expansion-panels");
  const _component_v_window_item = _resolveComponent("v-window-item");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_img = _resolveComponent("v-img");
  const _component_v_window = _resolveComponent("v-window");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_snackbar = _resolveComponent("v-snackbar");

  return (_openBlock(), _createBlock(_component_v_card, {
    rounded: "lg",
    variant: "flat"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card_title, { class: "d-flex align-center ga-2 py-3" }, {
        default: _withCtx(() => [
          _cache[17] || (_cache[17] = _createElementVNode("span", { class: "text-subtitle-1 font-weight-medium" }, "媒体服务器增强", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal",
            color: overview.value?.enabled ? 'success' : 'grey'
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(overview.value?.enabled ? '运行中' : '已停用'), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            loading: overviewLoading.value,
            "prepend-icon": "mdi-refresh",
            onClick: loadOverview
          }, {
            default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
              _createTextVNode("刷新数据", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
          }, {
            default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
              _createTextVNode("配置", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
          }, {
            default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
              _createTextVNode("关闭", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_v_tabs, {
        modelValue: activeTab.value,
        "onUpdate:modelValue": [
          _cache[2] || (_cache[2] = $event => ((activeTab).value = $event)),
          onTabChange
        ],
        density: "compact",
        color: "primary",
        "show-arrows": ""
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
        style: {"max-height":"62vh","overflow-y":"auto"}
      }, {
        default: _withCtx(() => [
          _createVNode(_component_v_window, {
            modelValue: activeTab.value,
            "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((activeTab).value = $event))
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_window_item, { value: "overview" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_row, { dense: "" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "tonal",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[18] || (_cache[18] = _createElementVNode("div", { class: "text-caption" }, "服务器在线", -1)),
                              _createElementVNode("div", _hoisted_1, _toDisplayString(overview.value?.online_count || 0) + " / " + _toDisplayString(overview.value?.server_count || 0), 1)
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "tonal",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[19] || (_cache[19] = _createElementVNode("div", { class: "text-caption" }, "媒体库", -1)),
                              _createElementVNode("div", _hoisted_2, _toDisplayString(overview.value?.library_count || 0), 1)
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "tonal",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[20] || (_cache[20] = _createElementVNode("div", { class: "text-caption" }, "今日任务 / 失败", -1)),
                              _createElementVNode("div", _hoisted_3, _toDisplayString(overview.value?.today_jobs || 0) + " / " + _toDisplayString(overview.value?.failed_jobs || 0), 1)
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "tonal",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[21] || (_cache[21] = _createElementVNode("div", { class: "text-caption" }, "体检问题 / 封面", -1)),
                              _createElementVNode("div", _hoisted_4, _toDisplayString(overview.value?.audit_issue_count || 0) + " / " + _toDisplayString(overview.value?.cover_total || 0), 1)
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createElementVNode("div", _hoisted_5, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(moduleStates.value, (enabled, key) => {
                      return (_openBlock(), _createBlock(_component_v_chip, {
                        key: key,
                        size: "small",
                        variant: "tonal",
                        color: enabled ? 'success' : 'grey'
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(moduleLabel(key)) + _toDisplayString(enabled ? ' 已启用' : ' 未启用'), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"]))
                    }), 128))
                  ]),
                  _createElementVNode("div", _hoisted_6, [
                    _createVNode(_component_v_btn, {
                      size: "small",
                      color: "primary",
                      loading: busy.value === 'refresh',
                      onClick: _cache[3] || (_cache[3] = $event => (runRefresh('library')))
                    }, {
                      default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                        _createTextVNode(" 立即刷新 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: busy.value === 'pending',
                      onClick: flushPending
                    }, {
                      default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                        _createTextVNode(" 提交待刷新 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: busy.value === 'audit',
                      onClick: runAudit
                    }, {
                      default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                        _createTextVNode(" 立即体检 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: capabilityLoading.value,
                      onClick: probeCapabilities
                    }, {
                      default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                        _createTextVNode(" 探测服务端能力 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _createVNode(_component_v_table, {
                    density: "compact",
                    hover: ""
                  }, {
                    default: _withCtx(() => [
                      _createElementVNode("thead", null, [
                        _createElementVNode("tr", null, [
                          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(serverHeaders, (head) => {
                            return _createElementVNode("th", {
                              key: head.key,
                              style: _normalizeStyle({ width: head.width ? `${head.width}px` : undefined })
                            }, _toDisplayString(head.title), 5)
                          }), 64))
                        ])
                      ]),
                      _createElementVNode("tbody", null, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(serverRows.value, (row) => {
                          return (_openBlock(), _createElementBlock("tr", {
                            key: row.name
                          }, [
                            _createElementVNode("td", null, _toDisplayString(row.name), 1),
                            _createElementVNode("td", null, _toDisplayString(row.type || '-'), 1),
                            _createElementVNode("td", null, [
                              _createVNode(_component_v_chip, {
                                size: "x-small",
                                variant: "tonal",
                                color: row.online ? 'success' : 'error'
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(row.online ? '在线' : '离线'), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("td", null, _toDisplayString(row.library_count), 1),
                            _createElementVNode("td", null, _toDisplayString(row.item_count), 1),
                            _createElementVNode("td", null, _toDisplayString(row.plugins_supported ? row.plugin_count : '-'), 1)
                          ]))
                        }), 128)),
                        (!serverRows.value.length)
                          ? (_openBlock(), _createElementBlock("tr", _hoisted_7, [...(_cache[26] || (_cache[26] = [
                              _createElementVNode("td", {
                                colspan: "6",
                                class: "text-center text-medium-emphasis py-4"
                              }, "未发现已配置的媒体服务器", -1)
                            ]))]))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _: 1
                  }),
                  (serverRows.value.some((row) => row.error))
                    ? (_openBlock(), _createBlock(_component_v_expansion_panels, {
                        key: 0,
                        variant: "accordion",
                        class: "mt-3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_expansion_panel, { title: "连接异常详情" }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_expansion_panel_text, null, {
                                default: _withCtx(() => [
                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(serverRows.value.filter((item) => item.error), (row) => {
                                    return (_openBlock(), _createElementBlock("div", {
                                      key: row.name,
                                      class: "text-body-2 mb-1"
                                    }, [
                                      _createElementVNode("strong", null, _toDisplayString(row.name), 1),
                                      _createTextVNode("：" + _toDisplayString(row.error), 1)
                                    ]))
                                  }), 128))
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
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "refresh" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_8, [
                    _createVNode(_component_v_btn, {
                      size: "small",
                      color: "primary",
                      loading: busy.value === 'refresh',
                      onClick: _cache[4] || (_cache[4] = $event => (runRefresh('library')))
                    }, {
                      default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                        _createTextVNode(" 整库刷新 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: busy.value === 'refresh',
                      onClick: _cache[5] || (_cache[5] = $event => (runRefresh('recent')))
                    }, {
                      default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                        _createTextVNode(" 刷新最近条目 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: busy.value === 'pending',
                      onClick: flushPending
                    }, {
                      default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                        _createTextVNode(" 提交待刷新 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_spacer),
                    _createElementVNode("span", _hoisted_9, "最近刷新：" + _toDisplayString(overview.value?.last_refresh || '暂无'), 1)
                  ]),
                  _createVNode(_component_v_table, {
                    density: "compact",
                    hover: ""
                  }, {
                    default: _withCtx(() => [
                      _createElementVNode("thead", null, [
                        _createElementVNode("tr", null, [
                          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(jobHeaders, (head) => {
                            return _createElementVNode("th", {
                              key: head.key,
                              style: _normalizeStyle({ width: head.width ? `${head.width}px` : undefined })
                            }, _toDisplayString(head.title), 5)
                          }), 64))
                        ])
                      ]),
                      _createElementVNode("tbody", null, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(jobs.value, (row) => {
                          return (_openBlock(), _createElementBlock("tr", {
                            key: row.job_id
                          }, [
                            _createElementVNode("td", null, _toDisplayString(row.started_at), 1),
                            _createElementVNode("td", null, _toDisplayString(moduleLabel(row.module)), 1),
                            _createElementVNode("td", null, _toDisplayString(row.trigger), 1),
                            _createElementVNode("td", null, [
                              _createVNode(_component_v_chip, {
                                size: "x-small",
                                variant: "tonal",
                                color: statusColor(row.status)
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(row.status), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("td", null, _toDisplayString(jobCountsText(row)), 1),
                            _createElementVNode("td", null, _toDisplayString(row.message || '-'), 1)
                          ]))
                        }), 128)),
                        (!jobs.value.length)
                          ? (_openBlock(), _createElementBlock("tr", _hoisted_10, [
                              _createElementVNode("td", _hoisted_11, _toDisplayString(jobsLoading.value ? '加载中…' : '暂无刷新任务记录'), 1)
                            ]))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "audit" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_12, [
                    _createVNode(_component_v_btn, {
                      size: "small",
                      color: "primary",
                      loading: busy.value === 'audit',
                      onClick: runAudit
                    }, {
                      default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                        _createTextVNode("运行体检", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: auditLoading.value,
                      onClick: loadAudit
                    }, {
                      default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                        _createTextVNode("读取上次报告", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      loading: busy.value === 'clear-audit',
                      onClick: _cache[6] || (_cache[6] = $event => (clearHistory('audit')))
                    }, {
                      default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                        _createTextVNode(" 清空报告 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_spacer),
                    (auditReport.value?.time)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_13, _toDisplayString(auditReport.value.time) + " · 扫描 " + _toDisplayString(auditReport.value.scanned_items) + " 条目 / " + _toDisplayString(auditReport.value.scanned_libraries) + " 库 ", 1))
                      : _createCommentVNode("", true)
                  ]),
                  (auditReport.value?.truncated)
                    ? (_openBlock(), _createBlock(_component_v_alert, {
                        key: 0,
                        density: "compact",
                        type: "warning",
                        variant: "tonal",
                        class: "mb-3"
                      }, {
                        default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                          _createTextVNode(" 条目数超过单次扫描上限，结果已截断。可提高上限或缩小媒体库范围后重跑。 ", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_14, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(auditCounts.value, (item) => {
                      return (_openBlock(), _createBlock(_component_v_chip, {
                        key: item.key,
                        size: "small",
                        variant: "tonal",
                        color: "warning"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.title) + " " + _toDisplayString(item.value), 1)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128)),
                    (auditReport.value && !auditCounts.value.length)
                      ? (_openBlock(), _createBlock(_component_v_chip, {
                          key: 0,
                          size: "small",
                          variant: "tonal",
                          color: "success"
                        }, {
                          default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                            _createTextVNode(" 未发现问题 ", -1)
                          ]))]),
                          _: 1
                        }))
                      : _createCommentVNode("", true)
                  ]),
                  _createVNode(_component_v_table, {
                    density: "compact",
                    hover: ""
                  }, {
                    default: _withCtx(() => [
                      _createElementVNode("thead", null, [
                        _createElementVNode("tr", null, [
                          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(auditHeaders, (head) => {
                            return _createElementVNode("th", {
                              key: head.key,
                              style: _normalizeStyle({ width: head.width ? `${head.width}px` : undefined })
                            }, _toDisplayString(head.title), 5)
                          }), 64))
                        ])
                      ]),
                      _createElementVNode("tbody", null, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((auditReport.value?.issues || []), (row, index) => {
                          return (_openBlock(), _createElementBlock("tr", {
                            key: `${row.server}-${row.item_id}-${index}`
                          }, [
                            _createElementVNode("td", null, _toDisplayString(AUDIT_LABELS[row.issue_type] || row.issue_type), 1),
                            _createElementVNode("td", null, _toDisplayString(row.server), 1),
                            _createElementVNode("td", null, _toDisplayString(row.library_name || row.library), 1),
                            _createElementVNode("td", null, _toDisplayString(row.title) + _toDisplayString(row.year ? ` (${row.year})` : ''), 1),
                            _createElementVNode("td", _hoisted_15, _toDisplayString(row.detail), 1)
                          ]))
                        }), 128)),
                        (!(auditReport.value?.issues || []).length)
                          ? (_openBlock(), _createElementBlock("tr", _hoisted_16, [
                              _createElementVNode("td", _hoisted_17, _toDisplayString(auditLoading.value ? '加载中…' : '暂无体检数据'), 1)
                            ]))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _: 1
                  }),
                  ((auditReport.value?.errors || []).length)
                    ? (_openBlock(), _createBlock(_component_v_expansion_panels, {
                        key: 1,
                        variant: "accordion",
                        class: "mt-3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_expansion_panel, {
                            title: `扫描错误 ${auditReport.value.errors.length} 条`
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_expansion_panel_text, null, {
                                default: _withCtx(() => [
                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(auditReport.value.errors, (item, index) => {
                                    return (_openBlock(), _createElementBlock("div", {
                                      key: index,
                                      class: "text-body-2"
                                    }, _toDisplayString(item), 1))
                                  }), 128))
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          }, 8, ["title"])
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode("", true)
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "covers" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_18, [
                    _createVNode(_component_v_select, {
                      modelValue: coverStyle.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((coverStyle).value = $event)),
                      items: [
              { title: '底部渐变', value: 'poster' },
              { title: '底部色条', value: 'clean' },
              { title: '侧栏竖条', value: 'gradient' },
            ],
                      density: "compact",
                      variant: "outlined",
                      label: "风格",
                      "hide-details": "",
                      style: {"max-width":"180px"}
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_v_text_field, {
                      modelValue: coverLimit.value,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((coverLimit).value = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      max: "50",
                      density: "compact",
                      variant: "outlined",
                      label: "数量",
                      "hide-details": "",
                      style: {"max-width":"120px"}
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      color: "primary",
                      loading: coverLoading.value,
                      onClick: previewCovers
                    }, {
                      default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                        _createTextVNode("生成预览", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: busy.value === 'covers',
                      onClick: runCovers
                    }, {
                      default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                        _createTextVNode("生成并上传", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_spacer),
                    (coverMessage.value)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_19, _toDisplayString(coverMessage.value), 1))
                      : _createCommentVNode("", true)
                  ]),
                  (coverItems.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_20, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(coverItems.value, (item, index) => {
                          return (_openBlock(), _createBlock(_component_v_card, {
                            key: `${item.item_id}-${index}`,
                            variant: "outlined",
                            class: "pa-2"
                          }, {
                            default: _withCtx(() => [
                              (item.preview)
                                ? (_openBlock(), _createBlock(_component_v_img, {
                                    key: 0,
                                    src: item.preview,
                                    height: "180",
                                    cover: "",
                                    class: "rounded"
                                  }, null, 8, ["src"]))
                                : (_openBlock(), _createElementBlock("div", _hoisted_21, "无预览图")),
                              _createElementVNode("div", _hoisted_22, _toDisplayString(item.title || item.item_id), 1),
                              _createElementVNode("div", _hoisted_23, _toDisplayString(item.server) + " · " + _toDisplayString(item.status), 1)
                            ]),
                            _: 2
                          }, 1024))
                        }), 128))
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_24, " 还没有预览。选择风格与数量后点击「生成预览」，预览不会上传到服务器。 "))
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "capabilities" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_25, [
                    _createVNode(_component_v_btn, {
                      size: "small",
                      color: "primary",
                      loading: capabilityLoading.value,
                      onClick: probeCapabilities
                    }, {
                      default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                        _createTextVNode(" 立即探测 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      loading: capabilityLoading.value,
                      onClick: loadCapabilities
                    }, {
                      default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                        _createTextVNode(" 读取快照 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      onClick: _cache[9] || (_cache[9] = $event => (clearHistory('capabilities')))
                    }, {
                      default: _withCtx(() => [...(_cache[39] || (_cache[39] = [
                        _createTextVNode("清空快照", -1)
                      ]))]),
                      _: 1
                    }),
                    _createVNode(_component_v_spacer),
                    _createElementVNode("span", _hoisted_26, "快照时间：" + _toDisplayString(capabilities.value?.time || '暂无'), 1)
                  ]),
                  ((capabilities.value?.servers || []).length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_27, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(capabilities.value.servers, (row) => {
                          return (_openBlock(), _createBlock(_component_v_card, {
                            key: row.server,
                            variant: "outlined",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _createElementVNode("div", _hoisted_28, [
                                _createElementVNode("span", _hoisted_29, _toDisplayString(row.server), 1),
                                _createVNode(_component_v_chip, {
                                  size: "x-small",
                                  variant: "tonal",
                                  color: "grey"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(row.type || '未知'), 1)
                                  ]),
                                  _: 2
                                }, 1024),
                                _createVNode(_component_v_chip, {
                                  size: "x-small",
                                  variant: "tonal",
                                  color: row.supported ? 'success' : 'warning'
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(row.supported ? '支持插件查询' : '不支持'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"]),
                                _createVNode(_component_v_spacer),
                                _createElementVNode("span", _hoisted_30, _toDisplayString(row.checked_at), 1)
                              ]),
                              (row.error)
                                ? (_openBlock(), _createBlock(_component_v_alert, {
                                    key: 0,
                                    density: "compact",
                                    type: "error",
                                    variant: "tonal",
                                    class: "mb-2"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(row.error), 1)
                                    ]),
                                    _: 2
                                  }, 1024))
                                : _createCommentVNode("", true),
                              ((row.watched || []).length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_31, [
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(row.watched, (hit) => {
                                      return (_openBlock(), _createBlock(_component_v_chip, {
                                        key: hit.name || hit.keyword,
                                        size: "small",
                                        variant: "tonal",
                                        color: hit.found ? 'success' : 'grey'
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(hit.title || hit.name || hit.keyword) + _toDisplayString(hit.found ? ' 已就绪' : ' 未发现'), 1)
                                        ]),
                                        _: 2
                                      }, 1032, ["color"]))
                                    }), 128))
                                  ]))
                                : _createCommentVNode("", true),
                              ((row.plugins || []).length)
                                ? (_openBlock(), _createBlock(_component_v_table, {
                                    key: 2,
                                    density: "compact"
                                  }, {
                                    default: _withCtx(() => [
                                      _createElementVNode("thead", null, [
                                        _createElementVNode("tr", null, [
                                          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(pluginHeaders, (head) => {
                                            return _createElementVNode("th", {
                                              key: head.key,
                                              style: _normalizeStyle({ width: head.width ? `${head.width}px` : undefined })
                                            }, _toDisplayString(head.title), 5)
                                          }), 64))
                                        ])
                                      ]),
                                      _createElementVNode("tbody", null, [
                                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(row.plugins, (plugin) => {
                                          return (_openBlock(), _createElementBlock("tr", {
                                            key: plugin.name
                                          }, [
                                            _createElementVNode("td", null, _toDisplayString(plugin.name), 1),
                                            _createElementVNode("td", null, _toDisplayString(plugin.version || '-'), 1),
                                            _createElementVNode("td", null, _toDisplayString(plugin.status || '-'), 1)
                                          ]))
                                        }), 128))
                                      ])
                                    ]),
                                    _: 2
                                  }, 1024))
                                : (_openBlock(), _createElementBlock("div", _hoisted_32, "未读取到服务端插件列表"))
                            ]),
                            _: 2
                          }, 1024))
                        }), 128))
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_33, _toDisplayString(capabilityLoading.value ? '探测中…' : '还没有服务端能力快照，点击「立即探测」获取。'), 1))
                ]),
                _: 1
              }),
              _createVNode(_component_v_window_item, { value: "diagnostics" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_34, [
                    _createVNode(_component_v_btn, {
                      size: "small",
                      color: "primary",
                      loading: diagnosticsLoading.value,
                      onClick: loadDiagnostics
                    }, {
                      default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                        _createTextVNode(" 重新诊断 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      loading: busy.value === 'clear-jobs',
                      onClick: _cache[10] || (_cache[10] = $event => (clearHistory('jobs')))
                    }, {
                      default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                        _createTextVNode(" 清空任务历史 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      onClick: _cache[11] || (_cache[11] = $event => (clearHistory('covers')))
                    }, {
                      default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                        _createTextVNode("清空封面历史", -1)
                      ]))]),
                      _: 1
                    }),
                    _createVNode(_component_v_spacer),
                    _createElementVNode("span", _hoisted_35, _toDisplayString(diagnostics.value?.time || ''), 1)
                  ]),
                  (diagnostics.value && diagnostics.value.checked === false)
                    ? (_openBlock(), _createBlock(_component_v_alert, {
                        key: 0,
                        density: "compact",
                        type: "error",
                        variant: "tonal",
                        class: "mb-3"
                      }, {
                        default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                          _createTextVNode(" 诊断执行失败 ", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode("", true),
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((diagnostics.value?.warnings || []), (item, index) => {
                    return (_openBlock(), _createBlock(_component_v_alert, {
                      key: index,
                      density: "compact",
                      type: "warning",
                      variant: "tonal",
                      class: "mb-2"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(item), 1)
                      ]),
                      _: 2
                    }, 1024))
                  }), 128)),
                  _createVNode(_component_v_row, { dense: "" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[44] || (_cache[44] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "插件", -1)),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((diagnostics.value?.plugin || {}), (value, key) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: key,
                                  class: "text-body-2 d-flex"
                                }, [
                                  _createElementVNode("span", _hoisted_36, _toDisplayString(key), 1),
                                  _createElementVNode("span", null, _toDisplayString(value), 1)
                                ]))
                              }), 128))
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
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[45] || (_cache[45] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "配置", -1)),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((diagnostics.value?.config || {}), (value, key) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: key,
                                  class: "text-body-2 d-flex"
                                }, [
                                  _createElementVNode("span", _hoisted_37, _toDisplayString(key), 1),
                                  _createElementVNode("span", null, _toDisplayString(value), 1)
                                ]))
                              }), 128))
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
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[46] || (_cache[46] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "历史", -1)),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((diagnostics.value?.history || {}), (value, key) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: key,
                                  class: "text-body-2 d-flex"
                                }, [
                                  _createElementVNode("span", _hoisted_38, _toDisplayString(key), 1),
                                  _createElementVNode("span", null, _toDisplayString(value), 1)
                                ]))
                              }), 128))
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
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "pa-3"
                          }, {
                            default: _withCtx(() => [
                              _cache[47] || (_cache[47] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "服务器", -1)),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((diagnostics.value?.servers || []), (row, index) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: index,
                                  class: "text-body-2 mb-2"
                                }, [
                                  _createElementVNode("div", _hoisted_39, _toDisplayString(row.name), 1),
                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(row, (value, key) => {
                                    return (_openBlock(), _createElementBlock("div", {
                                      key: key,
                                      class: "d-flex"
                                    }, [
                                      _createElementVNode("span", _hoisted_40, _toDisplayString(key), 1),
                                      _createElementVNode("span", _hoisted_41, _toDisplayString(value), 1)
                                    ]))
                                  }), 128))
                                ]))
                              }), 128)),
                              (!(diagnostics.value?.servers || []).length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_42, " 暂无服务器诊断信息 "))
                                : _createCommentVNode("", true)
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
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _: 1
      }),
      _createVNode(_component_v_snackbar, {
        modelValue: notice.value.show,
        "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((notice.value.show) = $event)),
        color: notice.value.color,
        timeout: "4000",
        location: "bottom"
      }, {
        default: _withCtx(() => [
          _createTextVNode(_toDisplayString(notice.value.text), 1)
        ]),
        _: 1
      }, 8, ["modelValue", "color"])
    ]),
    _: 1
  }))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-84676056"]]);

export { Page as default };
