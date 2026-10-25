import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = { class: "config-section" };
const _hoisted_2 = { class: "section-heading" };
const _hoisted_3 = { class: "config-section" };
const _hoisted_4 = { class: "section-heading" };
const _hoisted_5 = { class: "config-section" };
const _hoisted_6 = { class: "section-heading" };
const _hoisted_7 = { class: "filter-block" };
const _hoisted_8 = { class: "filter-block" };
const _hoisted_9 = { class: "config-section" };
const _hoisted_10 = { class: "section-heading monitor-heading" };
const _hoisted_11 = { class: "danger-block" };
const _hoisted_12 = { class: "danger-title" };
const _hoisted_13 = { class: "actions" };

const {getCurrentInstance,inject,onMounted,reactive,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'Hhanclubrescueseed' },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const toast = inject('moviepilot:toast', null);
const instance = getCurrentInstance();
const pluginApi = instance?.proxy?.$pluginApi || props.api;

const defaults = {
  enable: false, run_once: false, history_rescue_enabled: false,
  cron: '*/20 14-15 * * *', monitor_cron: '*/10 * * * *',
  downloader: null, save_path: null, custom_tag: '憨憨保种', reward_tag: null,
  reward_hours: 18, enable_notification: false, notify_on_zero_torrents: false,
  force_resume: false, auto_delete_enabled: false, delete_files: true,
  disk_quota_gb: null, stuck_days: 7, seeding_count: '1-3', torrent_size: null,
  download_limit: 5, max_downloading: 3, max_pages: 5, min_downloaders: 1,
  completion_ratio_max: 20, connect_time_max_hours: null, free: false,
};
const CONFIG_KEYS = Object.keys(defaults);
function projectInitialConfig(source) {
  return CONFIG_KEYS.reduce((result, key) => {
    if (Object.prototype.hasOwnProperty.call(source || {}, key) && source[key] != null) result[key] = source[key];
    return result
  }, {})
}
const form = reactive({ ...defaults, ...projectInitialConfig(props.initialConfig) });
const savedForm = ref({ ...form });
const downloaders = ref([]);
const loading = ref(false);
const loadingConfig = ref(false);
const error = ref('');

function notify(type, message) {
  if (toast && typeof toast[type] === 'function') toast[type](message);
  else (type === 'error' ? console.error : console.log)(message);
}
function unwrap(response) {
  return response?.data && typeof response.data.success === 'boolean' ? response.data : response
}
function projectConfig() {
  return CONFIG_KEYS.reduce((payload, key) => {
    payload[key] = form[key];
    return payload
  }, {})
}
async function loadConfig() {
  loadingConfig.value = true;
  error.value = '';
  try {
    const response = unwrap(await pluginApi.get(`plugin/Hhanclubrescueseed/config`));
    if (!response?.success) throw new Error(response?.message || '获取配置失败')
    const data = response.data || {};
    const serverConfig = data.config || data;
    Object.assign(form, defaults, projectServerConfig(serverConfig));
    if (typeof data.enabled === 'boolean') form.enable = data.enabled;
    downloaders.value = data.downloaders || data.all_downloaders || serverConfig.downloaders || [];
    savedForm.value = { ...form };
  } catch (err) {
    error.value = err.message || '获取配置失败';
    Object.assign(form, defaults);
    downloaders.value = [];
    savedForm.value = { ...form };
    notify('error', error.value);
  } finally {
    loadingConfig.value = false;
  }
}
function projectServerConfig(source) {
  return CONFIG_KEYS.reduce((result, key) => {
    if (Object.prototype.hasOwnProperty.call(source || {}, key) && source[key] != null) result[key] = source[key];
    return result
  }, {})
}
async function saveConfig() {
  if (!String(form.downloader || '').trim()) {
    error.value = '请选择下载器';
    notify('warning', error.value);
    return
  }
  loading.value = true;
  error.value = '';
  try {
    const payload = projectConfig();
    savedForm.value = { ...form };
    emit('save', JSON.parse(JSON.stringify(payload)));
    notify('success', '配置已保存');
  } catch (err) {
    error.value = err.message || '保存配置失败';
    notify('error', error.value);
  } finally {
    loading.value = false;
  }
}
function resetForm() { Object.assign(form, savedForm.value); error.value = ''; }
function close() { emit('close'); }
onMounted(loadConfig);

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_card_subtitle = _resolveComponent("v-card-subtitle");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_item = _resolveComponent("v-card-item");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_switch = _resolveComponent("v-switch");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_VCronField = _resolveComponent("VCronField");
  const _component_v_form = _resolveComponent("v-form");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_card = _resolveComponent("v-card");

  return (_openBlock(), _createBlock(_component_v_card, {
    class: "plugin-config",
    loading: loadingConfig.value
  }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card_item, null, {
        prepend: _withCtx(() => [
          _createVNode(_component_v_icon, { color: "primary" }, {
            default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
              _createTextVNode("mdi-shield-check-outline", -1)
            ]))]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createVNode(_component_v_btn, {
            icon: "mdi-close",
            variant: "text",
            "aria-label": "关闭",
            onClick: close
          })
        ]),
        default: _withCtx(() => [
          _createVNode(_component_v_card_title, null, {
            default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
              _createTextVNode("憨憨保种区配置", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_card_subtitle, null, {
            default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
              _createTextVNode("按列表页粗筛、详情页精筛和下载器并发控制保种任务", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_v_card_text, null, {
        default: _withCtx(() => [
          (error.value)
            ? (_openBlock(), _createBlock(_component_v_alert, {
                key: 0,
                type: "error",
                variant: "tonal",
                class: "mb-4"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(error.value), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          _createVNode(_component_v_form, {
            onSubmit: _withModifiers(saveConfig, ["prevent"])
          }, {
            default: _withCtx(() => [
              _createElementVNode("section", _hoisted_1, [
                _createElementVNode("div", _hoisted_2, [
                  _createVNode(_component_v_icon, { color: "primary" }, {
                    default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                      _createTextVNode("mdi-power", -1)
                    ]))]),
                    _: 1
                  }),
                  _cache[30] || (_cache[30] = _createElementVNode("div", null, [
                    _createElementVNode("h3", null, "运行开关"),
                    _createElementVNode("p", null, "控制插件运行，以及是否立即执行一次任务。")
                  ], -1))
                ]),
                _createVNode(_component_v_row, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_switch, {
                          modelValue: form.enable,
                          "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enable) = $event)),
                          color: "primary",
                          label: "启用插件",
                          hint: "按获取任务调度自动获取保种种子",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_switch, {
                          modelValue: form.run_once,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.run_once) = $event)),
                          color: "primary",
                          label: "立即运行普通保种",
                          hint: "保存后执行一次普通保种任务",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_switch, {
                          modelValue: form.history_rescue_enabled,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.history_rescue_enabled) = $event)),
                          color: "primary",
                          label: "立即运行历史保种",
                          hint: "保存后执行一次历史保种任务，UID由站点自动解析",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _createElementVNode("section", _hoisted_3, [
                _createElementVNode("div", _hoisted_4, [
                  _createVNode(_component_v_icon, { color: "primary" }, {
                    default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                      _createTextVNode("mdi-tune", -1)
                    ]))]),
                    _: 1
                  }),
                  _cache[32] || (_cache[32] = _createElementVNode("div", null, [
                    _createElementVNode("h3", null, "基础配置"),
                    _createElementVNode("p", null, "定义下载器、路径、标签和通知策略。")
                  ], -1))
                ]),
                _createVNode(_component_v_row, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_switch, {
                          modelValue: form.force_resume,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.force_resume) = $event)),
                          color: "primary",
                          label: "qb 强制作种",
                          hint: "仅 qBittorrent 支持",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_switch, {
                          modelValue: form.enable_notification,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.enable_notification) = $event)),
                          color: "primary",
                          label: "发送通知",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_switch, {
                          modelValue: form.notify_on_zero_torrents,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.notify_on_zero_torrents) = $event)),
                          color: "primary",
                          label: "无新种子时也通知",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_row, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_select, {
                          modelValue: form.downloader,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.downloader) = $event)),
                          items: downloaders.value,
                          "item-title": "title",
                          "item-value": "value",
                          label: "全局下载器",
                          placeholder: "请选择下载器",
                          rules: [value => !!value || '请选择下载器'],
                          variant: "outlined",
                          density: "comfortable"
                        }, null, 8, ["modelValue", "items", "rules"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_text_field, {
                          modelValue: form.save_path,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.save_path) = $event)),
                          label: "保存路径",
                          placeholder: "留空使用下载器默认",
                          variant: "outlined",
                          density: "comfortable"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_text_field, {
                          modelValue: form.custom_tag,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.custom_tag) = $event)),
                          label: "下载标签",
                          hint: "本插件管理标签，可用逗号分隔多个标签",
                          "persistent-hint": "",
                          variant: "outlined",
                          density: "comfortable"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _createElementVNode("section", _hoisted_5, [
                _createElementVNode("div", _hoisted_6, [
                  _createVNode(_component_v_icon, { color: "primary" }, {
                    default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                      _createTextVNode("mdi-download-box-outline", -1)
                    ]))]),
                    _: 1
                  }),
                  _cache[34] || (_cache[34] = _createElementVNode("div", null, [
                    _createElementVNode("h3", null, "获取规则"),
                    _createElementVNode("p", null, "先用列表页粗筛，再按需读取详情页下载者精筛。")
                  ], -1))
                ]),
                _createVNode(_component_v_row, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.cron,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.cron) = $event)),
                          label: "获取任务调度",
                          hint: "保种区每天 14:00 更新种子",
                          "persistent-hint": ""
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
                          modelValue: form.max_pages,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.max_pages) = $event)),
                          modelModifiers: { number: true },
                          label: "翻页数",
                          type: "number",
                          variant: "outlined",
                          density: "comfortable"
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
                          modelValue: form.download_limit,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.download_limit) = $event)),
                          modelModifiers: { number: true },
                          label: "本轮下载配额",
                          hint: "0 = 不限",
                          "persistent-hint": "",
                          type: "number",
                          variant: "outlined",
                          density: "comfortable"
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
                          modelValue: form.max_downloading,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.max_downloading) = $event)),
                          modelModifiers: { number: true },
                          label: "最大同时下载数",
                          hint: "下载器并发上限",
                          "persistent-hint": "",
                          type: "number",
                          variant: "outlined",
                          density: "comfortable"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_7, [
                  _cache[35] || (_cache[35] = _createElementVNode("div", { class: "filter-label" }, "列表页粗筛", -1)),
                  _createVNode(_component_v_row, { dense: "" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.seeding_count,
                            "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.seeding_count) = $event)),
                            label: "做种数区间/多档",
                            hint: "支持单值、a-b 或逗号分隔多档，如 1-3,5,8-10",
                            "persistent-hint": "",
                            variant: "outlined",
                            density: "comfortable"
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.min_downloaders,
                            "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.min_downloaders) = $event)),
                            modelModifiers: { number: true },
                            label: "最小下载数",
                            hint: "列表页下载数不足时跳过",
                            type: "number",
                            variant: "outlined",
                            density: "comfortable"
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.torrent_size,
                            "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.torrent_size) = $event)),
                            label: "体积区间（GB）",
                            hint: "如 1-100，留空不限",
                            variant: "outlined",
                            density: "comfortable"
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_switch, {
                            modelValue: form.free,
                            "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.free) = $event)),
                            color: "primary",
                            label: "仅下载免费种子",
                            hint: "免费属于列表页粗筛条件",
                            "persistent-hint": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _createElementVNode("div", _hoisted_8, [
                  _cache[36] || (_cache[36] = _createElementVNode("div", { class: "filter-label" }, "详情页精筛", -1)),
                  _createVNode(_component_v_row, { dense: "" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.completion_ratio_max,
                            "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.completion_ratio_max) = $event)),
                            label: "详情页下载者完成率上限（%）",
                            placeholder: "留空不启用精筛",
                            type: "number",
                            hint: "留空不启用精筛；每轮详情请求 ≤15 个",
                            "persistent-hint": "",
                            variant: "outlined",
                            density: "comfortable"
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
                            modelValue: form.connect_time_max_hours,
                            "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.connect_time_max_hours) = $event)),
                            label: "详情页下载者连接时间上限（小时）",
                            placeholder: "留空不启用精筛",
                            type: "number",
                            hint: "留空不启用精筛；每轮详情请求 ≤15 个",
                            "persistent-hint": "",
                            variant: "outlined",
                            density: "comfortable"
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ])
              ]),
              _createElementVNode("section", _hoisted_9, [
                _createElementVNode("div", _hoisted_10, [
                  _createVNode(_component_v_icon, { color: "primary" }, {
                    default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                      _createTextVNode("mdi-radar", -1)
                    ]))]),
                    _: 1
                  }),
                  _cache[38] || (_cache[38] = _createElementVNode("div", null, [
                    _createElementVNode("h3", null, "监控与清理"),
                    _createElementVNode("p", null, "达标打标、体积配额清理和卡死清理。")
                  ], -1)),
                  _cache[39] || (_cache[39] = _createElementVNode("span", { class: "section-note" }, "默认关闭，只触碰本插件标签", -1))
                ]),
                _createVNode(_component_v_row, {
                  dense: "",
                  class: "monitor-row"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.monitor_cron,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.monitor_cron) = $event)),
                          label: "监控任务调度",
                          hint: "留空禁用监控任务；启用自动删除后建议保持足够监控频率（如 */10）以便及时清理",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_text_field, {
                          modelValue: form.reward_tag,
                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.reward_tag) = $event)),
                          label: "达标标签",
                          hint: "达标后添加，需与下载标签不同",
                          "persistent-hint": "",
                          variant: "outlined",
                          density: "comfortable"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_col, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_text_field, {
                          modelValue: form.reward_hours,
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.reward_hours) = $event)),
                          modelModifiers: { number: true },
                          label: "达标做种时长（小时）",
                          hint: "已完成且做种满时长后达标",
                          "persistent-hint": "",
                          type: "number",
                          variant: "outlined",
                          density: "comfortable"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_11, [
                  _createElementVNode("div", _hoisted_12, [
                    _createVNode(_component_v_icon, { color: "error" }, {
                      default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                        _createTextVNode("mdi-alert-circle-outline", -1)
                      ]))]),
                      _: 1
                    }),
                    _cache[41] || (_cache[41] = _createElementVNode("strong", null, "危险操作", -1))
                  ]),
                  _createVNode(_component_v_row, { dense: "" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_switch, {
                            modelValue: form.auto_delete_enabled,
                            "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.auto_delete_enabled) = $event)),
                            color: "error",
                            label: "自动删除种子",
                            hint: "总开关：关闭时仅监控和打标",
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
                          _createVNode(_component_v_switch, {
                            modelValue: form.delete_files,
                            "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.delete_files) = $event)),
                            color: "error",
                            label: "删种时同时删除文件",
                            hint: "关闭则保留磁盘文件",
                            "persistent-hint": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_row, { dense: "" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: form.disk_quota_gb,
                            "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((form.disk_quota_gb) = $event)),
                            modelModifiers: { number: true },
                            label: "保种体积配额（GB）",
                            placeholder: "留空 = 不限",
                            hint: "留空禁用体积清理",
                            "persistent-hint": "",
                            type: "number",
                            variant: "outlined",
                            density: "comfortable"
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
                            modelValue: form.stuck_days,
                            "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.stuck_days) = $event)),
                            modelModifiers: { number: true },
                            label: "卡死清理（天）",
                            hint: "未完成超 N 天清理；0 = 禁用",
                            "persistent-hint": "",
                            type: "number",
                            variant: "outlined",
                            density: "comfortable"
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ])
              ]),
              _cache[44] || (_cache[44] = _createElementVNode("section", { class: "logic-notes" }, [
                _createElementVNode("div", null, [
                  _createElementVNode("strong", null, "两阶段获取"),
                  _createElementVNode("span", null, "列表页只做免费、做种数、下载数和体积粗筛；命中完成率或连接时间任一详情条件时，再请求 viewpeerlist.php 读取详情页下载者，每轮最多15次。")
                ]),
                _createElementVNode("div", null, [
                  _createElementVNode("strong", null, "下载者口径"),
                  _createElementVNode("span", null, "完成率和连接时间均针对详情页下载者，所有启用条件必须严格低于上限；请求失败、坏行或表结构变化按未知处理，不放行下载。")
                ]),
                _createElementVNode("div", null, [
                  _createElementVNode("strong", null, "历史任务"),
                  _createElementVNode("span", null, "历史保种任务使用站点自动解析的当前 UID，保持独立历史页流程，不纳入普通任务的详情页精筛。")
                ])
              ], -1)),
              _createElementVNode("div", _hoisted_13, [
                _createVNode(_component_v_btn, {
                  variant: "text",
                  onClick: resetForm
                }, {
                  default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                    _createTextVNode("重置", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  color: "primary",
                  type: "submit",
                  loading: loading.value
                }, {
                  default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                    _createTextVNode("保存配置", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ])
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["loading"]))
}
}

};
const ConfigComponent = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-a46139a1"]]);

export { ConfigComponent as default };
