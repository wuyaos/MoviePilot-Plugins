import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "d-flex align-center ga-1" };
const _hoisted_2 = { class: "stat-value" };
const _hoisted_3 = { class: "stat-value" };
const _hoisted_4 = { class: "stat-value" };
const _hoisted_5 = { class: "stat-value" };
const _hoisted_6 = { class: "title-cell" };
const _hoisted_7 = { key: 0 };

const {computed,getCurrentInstance,inject,onMounted,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'Hhanclubrescueseed' },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const toast = inject('moviepilot:toast', null);
const instance = getCurrentInstance();
const pluginApi = instance?.proxy?.$pluginApi || props.api;

const records = ref([]);
const autoDeleteEnabled = ref(false);
const loading = ref(false);
const deleting = ref('');
const error = ref('');

const headers = [
  { title: '名称', key: 'title', minWidth: '260px' },
  { title: '体积', key: 'size', width: '120px' },
  { title: '得分', key: 'score', width: '90px' },
  { title: '下载时间', key: 'added_on', width: '170px' },
  { title: '做种时长', key: 'seeding_time', width: '130px' },
  { title: '状态', key: 'status', width: '120px' },
  { title: '上传体积', key: 'uploaded', width: '130px' },
  { title: '操作', key: 'actions', sortable: false, align: 'end', width: '90px' },
];

function notify(type, message) {
  if (toast && typeof toast[type] === 'function') toast[type](message);
  else (type === 'error' ? console.error : console.log)(message);
}

function unwrap(response) {
  return response?.data && typeof response.data.success === 'boolean' ? response.data : response
}

function valueOf(record, ...keys) {
  for (const key of keys) if (record?.[key] !== undefined && record?.[key] !== null) return record[key]
  return ''
}

function toGb(value) {
  if (typeof value === 'number') return value
  const text = String(value || '').trim().toUpperCase();
  const amount = Number.parseFloat(text);
  if (!Number.isFinite(amount)) return 0
  if (text.includes('TB')) return amount * 1024
  if (text.includes('MB')) return amount / 1024
  if (text.includes('KB')) return amount / (1024 * 1024)
  return amount
}

function formatSize(value) {
  if (value === '' || value === null || value === undefined) return '-'
  if (typeof value === 'string' && /[A-Za-z]/.test(value)) return value
  return `${toGb(value).toFixed(2)} GB`
}

function formatAddedOn(record) {
  const value = valueOf(record, 'added_on', 'download_time');
  if (!value) return '-'
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatSeedingTime(value) {
  if (value === '' || value === null || value === undefined) return '-'
  if (typeof value === 'string' && /天\s*\d+小时/.test(value)) return value
  let hours = Number(value);
  if (!Number.isFinite(hours)) {
    const text = String(value);
    const dayMatch = text.match(/([\d.]+)\s*天/);
    const hourMatch = text.match(/([\d.]+)\s*小时/);
    if (dayMatch) hours = Number(dayMatch[1]) * 24 + (hourMatch ? Number(hourMatch[1]) : 0);
    else hours = Number.parseFloat(text);
    if (!Number.isFinite(hours)) return text
  }
  const days = Math.floor(hours / 24);
  const remainHours = Math.floor(hours % 24);
  if (!days) return `${remainHours}小时`
  return `${days}天${remainHours}小时`
}

function statusText(value) {
  const status = String(value || '').toLowerCase();
  if (status.includes('deleted') || status.includes('删除')) return '已删除'
  if (status.includes('paused') || status.includes('pause') || status.includes('暂停')) return '已暂停'
  if (status.includes('complete') || status.includes('达标')) return '已达标'
  if (status.includes('download') || status.includes('下载')) return '下载中'
  return '做种中'
}

function statusColor(value) {
  return { 做种中: 'success', 下载中: 'info', 已达标: 'primary', 已暂停: 'warning', 已删除: 'grey' }[statusText(value)]
}

const totalSize = computed(() => `${records.value.reduce((total, record) => total + toGb(record.size), 0).toFixed(2)} GB`);
const totalUploaded = computed(() => `${records.value.reduce((total, record) => total + toGb(record.uploaded), 0).toFixed(2)} GB`);
const qualifiedCount = computed(() => records.value.filter(record => statusText(record.status) === '已达标').length);

async function refreshData() {
  loading.value = true;
  error.value = '';
  try {
    const response = unwrap(await pluginApi.get(`plugin/Hhanclubrescueseed/download_records`));
    if (!response?.success) throw new Error(response?.message || '获取下载记录失败')
    const data = response.data || {};
    records.value = Array.isArray(data.records) ? data.records : [];
    autoDeleteEnabled.value = Boolean(data.auto_delete_enabled);
    emit('action');
  } catch (err) {
    error.value = err.message || '获取下载记录失败';
    records.value = [];
    notify('error', error.value);
  } finally {
    loading.value = false;
  }
}

async function deleteRecord(record) {
  const title = String(record?.title || '');
  if (!title) return
  deleting.value = title;
  try {
    const response = unwrap(await pluginApi.post(`plugin/Hhanclubrescueseed/delete_download_records`, [title]));
    records.value = records.value.filter(item => item.title !== title);
    notify('success', '记录已删除');
    emit('action');
  } catch (err) {
    notify('error', err.message || '删除记录失败');
  } finally {
    deleting.value = '';
  }
}

const cleaning = ref(false);

async function cleanupStale() {
  cleaning.value = true;
  try {
    const response = unwrap(await pluginApi.post(`plugin/Hhanclubrescueseed/cleanup_records`));
    if (!response?.success) throw new Error(response?.message || '清理失败')
    const { removed, total } = response.data || {};
    notify('success', `已清理 ${removed} 条失效记录，剩余 ${total} 条`);
    emit('action');
    await refreshData();
  } catch (err) {
    notify('error', err.message || '清理失败');
  } finally {
    cleaning.value = false;
  }
}

function close() {
  emit('close');
}

onMounted(refreshData);

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_card_subtitle = _resolveComponent("v-card-subtitle");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_item = _resolveComponent("v-card-item");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_data_table = _resolveComponent("v-data-table");
  const _component_v_card_text = _resolveComponent("v-card-text");

  return (_openBlock(), _createBlock(_component_v_card, { class: "plugin-page" }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card_item, null, {
        prepend: _withCtx(() => [
          _createVNode(_component_v_icon, { color: "primary" }, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("mdi-chart-box-outline", -1)
            ]))]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createElementVNode("div", _hoisted_1, [
            _createVNode(_component_v_btn, {
              icon: "mdi-cog-outline",
              variant: "text",
              "aria-label": "配置插件",
              title: "配置插件",
              onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
            }),
            _createVNode(_component_v_btn, {
              icon: "mdi-broom",
              variant: "text",
              "aria-label": "清理失效记录",
              title: "清理失效记录（下载器中已不存在的）",
              loading: cleaning.value,
              onClick: cleanupStale
            }, null, 8, ["loading"]),
            _createVNode(_component_v_btn, {
              icon: "mdi-refresh",
              variant: "text",
              "aria-label": "刷新",
              title: "刷新",
              onClick: refreshData
            }),
            _createVNode(_component_v_btn, {
              icon: "mdi-close",
              variant: "text",
              "aria-label": "关闭",
              onClick: close
            })
          ])
        ]),
        default: _withCtx(() => [
          _createVNode(_component_v_card_title, null, {
            default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
              _createTextVNode("憨憨保种区", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_card_subtitle, null, {
            default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
              _createTextVNode("本地下载记录与下载器实时状态", -1)
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
          (!autoDeleteEnabled.value)
            ? (_openBlock(), _createBlock(_component_v_alert, {
                key: 1,
                type: "info",
                variant: "tonal",
                class: "mb-4"
              }, {
                default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                  _createTextVNode("自动清理未启用：磁盘配额清理与卡死清理均不会执行", -1)
                ]))]),
                _: 1
              }))
            : _createCommentVNode("", true),
          _createVNode(_component_v_row, { class: "stats-row mb-2" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    class: "stat-card",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [
                      _cache[5] || (_cache[5] = _createElementVNode("div", { class: "stat-label" }, "保种总体积", -1)),
                      _createElementVNode("div", _hoisted_2, _toDisplayString(totalSize.value), 1),
                      _cache[6] || (_cache[6] = _createElementVNode("div", { class: "stat-meta" }, "当前记录汇总", -1))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    class: "stat-card",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [
                      _cache[7] || (_cache[7] = _createElementVNode("div", { class: "stat-label" }, "累计上传量", -1)),
                      _createElementVNode("div", _hoisted_3, _toDisplayString(totalUploaded.value), 1),
                      _cache[8] || (_cache[8] = _createElementVNode("div", { class: "stat-meta" }, "按下载记录汇总", -1))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    class: "stat-card",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [
                      _cache[10] || (_cache[10] = _createElementVNode("div", { class: "stat-label" }, "已达标数", -1)),
                      _createElementVNode("div", _hoisted_4, [
                        _createTextVNode(_toDisplayString(qualifiedCount.value), 1),
                        _cache[9] || (_cache[9] = _createElementVNode("small", null, " 条", -1))
                      ]),
                      _cache[11] || (_cache[11] = _createElementVNode("div", { class: "stat-meta" }, "达标标签已写入下载器", -1))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    class: "stat-card",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [
                      _cache[13] || (_cache[13] = _createElementVNode("div", { class: "stat-label" }, "下载记录数", -1)),
                      _createElementVNode("div", _hoisted_5, [
                        _createTextVNode(_toDisplayString(records.value.length), 1),
                        _cache[12] || (_cache[12] = _createElementVNode("small", null, " 条", -1))
                      ]),
                      _cache[14] || (_cache[14] = _createElementVNode("div", { class: "stat-meta" }, "本地保存的记录", -1))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _cache[16] || (_cache[16] = _createElementVNode("div", { class: "table-heading" }, [
            _createElementVNode("div", null, [
              _createElementVNode("h2", null, "下载记录"),
              _createElementVNode("p", null, "名称、体积和下载时间来自本地记录，状态数据按记录字段展示。得分为推送评分（体积50+需求40+稀缺10，人数热度 20 封顶），旧记录无得分显示 —。")
            ])
          ], -1)),
          (records.value.length)
            ? (_openBlock(), _createBlock(_component_v_data_table, {
                key: 2,
                height: "520",
                headers: headers,
                items: records.value,
                "item-value": "title",
                class: "records-table",
                "items-per-page": 10
              }, {
                "item.title": _withCtx(({ item }) => [
                  _createElementVNode("div", _hoisted_6, [
                    _createElementVNode("strong", null, _toDisplayString(item.title || '-'), 1),
                    (item.zh_title)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_7, _toDisplayString(item.zh_title), 1))
                      : _createCommentVNode("", true)
                  ])
                ]),
                "item.size": _withCtx(({ item }) => [
                  _createTextVNode(_toDisplayString(formatSize(item.size)), 1)
                ]),
                "item.score": _withCtx(({ item }) => [
                  _createTextVNode(_toDisplayString(typeof item.score === 'number' && Number.isFinite(item.score) ? item.score.toFixed(1) : '—'), 1)
                ]),
                "item.added_on": _withCtx(({ item }) => [
                  _createTextVNode(_toDisplayString(formatAddedOn(item)), 1)
                ]),
                "item.seeding_time": _withCtx(({ item }) => [
                  _createTextVNode(_toDisplayString(formatSeedingTime(valueOf(item, 'seeding_time', 'seeding_time_hours'))), 1)
                ]),
                "item.status": _withCtx(({ item }) => [
                  _createVNode(_component_v_chip, {
                    size: "small",
                    color: statusColor(item.status),
                    label: ""
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(statusText(item.status)), 1)
                    ]),
                    _: 2
                  }, 1032, ["color"])
                ]),
                "item.uploaded": _withCtx(({ item }) => [
                  _createTextVNode(_toDisplayString(formatSize(item.uploaded)), 1)
                ]),
                "item.actions": _withCtx(({ item }) => [
                  _createVNode(_component_v_btn, {
                    icon: "mdi-delete-outline",
                    size: "small",
                    variant: "text",
                    color: "error",
                    loading: deleting.value === item.title,
                    "aria-label": `删除 ${item.title}`,
                    onClick: $event => (deleteRecord(item))
                  }, null, 8, ["loading", "aria-label", "onClick"])
                ]),
                _: 1
              }, 8, ["items"]))
            : (_openBlock(), _createBlock(_component_v_alert, {
                key: 3,
                type: "info",
                variant: "tonal"
              }, {
                default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                  _createTextVNode("暂无下载记录", -1)
                ]))]),
                _: 1
              }))
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const PageComponent = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-41283029"]]);

export { PageComponent as default };
