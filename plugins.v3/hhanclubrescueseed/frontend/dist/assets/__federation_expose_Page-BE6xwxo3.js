import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,withKeys:_withKeys,createElementVNode:_createElementVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "plugin-page" };
const _hoisted_2 = { key: 2 };
const _hoisted_3 = { class: "mt-4" };
const _hoisted_4 = { class: "d-flex align-center justify-space-between mb-2" };
const _hoisted_5 = {
  key: 0,
  class: "text-success"
};
const _hoisted_6 = {
  key: 1,
  class: "text-grey"
};
const _hoisted_7 = { key: 0 };
const _hoisted_8 = { key: 1 };

const {computed,inject,onMounted,ref} = await importShared('vue');


// 接收初始配置和宿主能力

const _sfc_main = {
  __name: 'Page',
  props: {
  model: {
    type: Object,
    default: () => ({}),
  },
  api: {
    type: Object,
    default: () => ({}),
  },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

// 使用主应用统一 Toast
const hostToast = inject('moviepilot:toast', null);
const $toast = hostToast || {
  success: msg => console.log('[toast]', msg),
  error: msg => console.error('[toast]', msg),
  warning: msg => console.warn('[toast]', msg),
  info: msg => console.log('[toast]', msg),
};

// 组件状态
const title = ref('憨憨保种区');
const loading = ref(true);
const deleting = ref(false);
const error = ref(null);
const downloadRecords = ref([]);
const searchTitle = ref('');
const minSeeders = ref('');
const maxSeeders = ref('');
const selectedRecords = ref([]);
const deleteDialog = ref(false);

// 过滤后的记录
const filteredRecords = computed(() => {
  let records = [...downloadRecords.value];

  // 按标题搜索
  if (searchTitle.value) {
    const searchLower = searchTitle.value.toLowerCase();
    records = records.filter(record =>
      (record.title && record.title.toLowerCase().includes(searchLower)) ||
      (record.zh_title && record.zh_title.toLowerCase().includes(searchLower)),
    );
  }

  // 按做种人数筛选
  if (minSeeders.value !== '') {
    const min = parseInt(minSeeders.value);
    if (!isNaN(min)) {
      records = records.filter(record => {
        const seeders = parseInt(record.seeders);
        return !isNaN(seeders) && seeders >= min
      });
    }
  }

  if (maxSeeders.value !== '') {
    const max = parseInt(maxSeeders.value);
    if (!isNaN(max)) {
      records = records.filter(record => {
        const seeders = parseInt(record.seeders);
        return !isNaN(seeders) && seeders <= max
      });
    }
  }

  return records
});

const downloadHeaders = ref([
  { title: '英文标题', key: 'title' },
  { title: '中文标题', key: 'zh_title' },
  { title: '种子大小', key: 'size' },
  { title: '做种人数', key: 'seeders' },
  { title: '种子Hash', key: 'torrent_hash' },
  { title: '下载时间', key: 'download_time' },
]);

// 格式化时间
function formatTime(timeStr) {
  // 检查是否为有效日期字符串
  if (!timeStr) return 'N/A'

  // 尝试解析日期
  const date = new Date(timeStr);
  if (isNaN(date.getTime())) {
    // 如果是无效日期，直接返回原始字符串
    return timeStr
  }

  // 返回本地化的时间字符串
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// 获取和刷新数据
async function refreshData() {
  loading.value = true;
  error.value = null;

  try {
    // 获取下载记录
    const response = await props.api.get(`plugin/Hhanclubrescueseed/download_records`);
    if (!response.success) {
      throw new Error(response.message || '获取下载记录失败')
    }
    downloadRecords.value = Array.isArray(response.data) ? response.data : [];
  } catch (err) {
    console.error('获取下载记录失败:', err);
    error.value = '获取下载记录失败: ' + (err.message || '未知错误');
    $toast.error(error.value);
    downloadRecords.value = [];
  } finally {
    loading.value = false;
    // 通知主应用组件已更新
    emit('action');
  }
}

// 过滤记录
function filterRecords() {
  // 通过computed属性自动过滤，无需额外操作
}

// 删除选中记录
function confirmDeleteSelected() {
  deleteDialog.value = true;
}

// 确认删除
async function deleteConfirmed() {
  deleting.value = true;
  try {
    // 删除选中记录
    await deleteMultipleRecords(selectedRecords.value);
    selectedRecords.value = [];

    // 重新加载数据
    await refreshData();
  } catch (err) {
    console.error('删除记录失败:', err);
    error.value = '删除记录失败: ' + err.message;
    $toast.error(error.value);
  } finally {
    deleteDialog.value = false;
    deleting.value = false;
  }
}

// 批量删除记录
async function deleteMultipleRecords(recordTitles) {
  // 根据标题从downloadRecords中获取完整的记录对象
  const records = recordTitles
    .map(title => downloadRecords.value.find(record => record.title === title))
    .filter(record => record !== undefined); // 过滤掉未找到的记录

  // 分离有hash和无hash的记录
  const recordsWithHash = records.filter(record => record && record.torrent_hash);

  // 如果有包含hash的记录，先批量删除种子
  if (recordsWithHash.length > 0) {
    const hashes = recordsWithHash.map(record => record.torrent_hash);
    try {
      const response = await props.api.post(`plugin/Hhanclubrescueseed/delete_torrents`, hashes);
      if (!response.success) {
        console.error('删除种子失败:', response.message);
        $toast.error('删除种子失败: ' + (response.message || '未知错误'));
        // 即使部分失败，也继续删除记录
      }
    } catch (err) {
      console.error('删除种子API调用失败:', err);
      $toast.error('删除种子API调用失败:' + err.message);
      // 即使API调用失败，也要继续删除记录
    }
  }

  // 删除所有选中的记录
  const titles = records.map(record => record.title);

  // 同时调用后端API删除数据库中的记录
  try {
    const response = await props.api.post(`plugin/Hhanclubrescueseed/delete_download_records`, titles);
    if (!response.success) {
      console.error('删除下载记录失败:', response.message);
      $toast.error('删除下载记录失败: ' + (response.message || '未知错误'));
    }
  } catch (err) {
    console.error('删除下载记录API调用失败:', err);
    $toast.error('删除下载记录API调用失败: ' + (err.message || '未知错误'));
  }
}

// 通知主应用切换到配置页面
function notifySwitch() {
  emit('switch');
}

// 通知主应用关闭组件
function notifyClose() {
  emit('close');
}

// 组件挂载时加载数据
onMounted(() => {
  refreshData();
});

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_card_item = _resolveComponent("v-card-item");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_skeleton_loader = _resolveComponent("v-skeleton-loader");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_data_table = _resolveComponent("v-data-table");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_card_actions = _resolveComponent("v-card-actions");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_progress_circular = _resolveComponent("v-progress-circular");
  const _component_v_dialog = _resolveComponent("v-dialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_v_card, null, {
      default: _withCtx(() => [
        _createVNode(_component_v_card_item, null, {
          append: _withCtx(() => [
            _createVNode(_component_v_btn, {
              icon: "",
              color: "primary",
              variant: "text",
              onClick: notifyClose
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, null, {
                  default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                    _createTextVNode("mdi-close", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, null, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(title.value), 1)
              ]),
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
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(error.value), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            (loading.value)
              ? (_openBlock(), _createBlock(_component_v_skeleton_loader, {
                  key: 1,
                  type: "table"
                }))
              : (_openBlock(), _createElementBlock("div", _hoisted_2, [
                  _createVNode(_component_v_row, { class: "mb-4" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: searchTitle.value,
                            "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((searchTitle).value = $event)),
                            label: "搜索标题",
                            placeholder: "输入标题关键词",
                            clearable: "",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": "",
                            onKeyup: _withKeys(filterRecords, ["enter"])
                          }, {
                            "prepend-inner": _withCtx(() => [
                              _createVNode(_component_v_icon, null, {
                                default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                                  _createTextVNode("mdi-magnify", -1)
                                ]))]),
                                _: 1
                              })
                            ]),
                            _: 1
                          }, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_text_field, {
                            modelValue: minSeeders.value,
                            "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((minSeeders).value = $event)),
                            label: "最小做种人数",
                            type: "number",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": "",
                            onKeyup: _withKeys(filterRecords, ["enter"])
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
                            modelValue: maxSeeders.value,
                            "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((maxSeeders).value = $event)),
                            label: "最大做种人数",
                            type: "number",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": "",
                            onKeyup: _withKeys(filterRecords, ["enter"])
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "2"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_btn, {
                            color: "primary",
                            block: "",
                            disabled: !searchTitle.value && !minSeeders.value && !maxSeeders.value,
                            onClick: filterRecords
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_icon, { start: "" }, {
                                default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                                  _createTextVNode("mdi-filter", -1)
                                ]))]),
                                _: 1
                              }),
                              _cache[9] || (_cache[9] = _createTextVNode(" 筛选 ", -1))
                            ]),
                            _: 1
                          }, 8, ["disabled"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createElementVNode("div", _hoisted_3, [
                    _createElementVNode("div", _hoisted_4, [
                      _cache[11] || (_cache[11] = _createElementVNode("div", { class: "text-h6" }, "下载记录", -1)),
                      (selectedRecords.value.length > 0)
                        ? (_openBlock(), _createBlock(_component_v_btn, {
                            key: 0,
                            color: "error",
                            disabled: selectedRecords.value.length === 0,
                            onClick: confirmDeleteSelected
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_icon, { start: "" }, {
                                default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
                                  _createTextVNode("mdi-delete", -1)
                                ]))]),
                                _: 1
                              }),
                              _createTextVNode(" 删除选中 (" + _toDisplayString(selectedRecords.value.length) + ") ", 1)
                            ]),
                            _: 1
                          }, 8, ["disabled"]))
                        : _createCommentVNode("", true)
                    ]),
                    (filteredRecords.value && filteredRecords.value.length > 0)
                      ? (_openBlock(), _createBlock(_component_v_data_table, {
                          key: 0,
                          modelValue: selectedRecords.value,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((selectedRecords).value = $event)),
                          headers: downloadHeaders.value,
                          items: filteredRecords.value,
                          "items-per-page": 10,
                          "footer-props": { 'items-per-page-options': [5, 10, 20, -1] },
                          "item-value": "title",
                          "show-select": "",
                          class: "elevation-1"
                        }, {
                          "item.download_time": _withCtx(({ item }) => [
                            _createTextVNode(_toDisplayString(formatTime(item.download_time)), 1)
                          ]),
                          "item.torrent_hash": _withCtx(({ item }) => [
                            (item.torrent_hash)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_5, _toDisplayString(item.torrent_hash.substring(0, 8)) + "...", 1))
                              : (_openBlock(), _createElementBlock("span", _hoisted_6, "-"))
                          ]),
                          _: 1
                        }, 8, ["modelValue", "headers", "items"]))
                      : (_openBlock(), _createBlock(_component_v_alert, {
                          key: 1,
                          type: "info",
                          class: "mt-4"
                        }, {
                          default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                            _createTextVNode(" 暂无下载记录 ", -1)
                          ]))]),
                          _: 1
                        }))
                  ])
                ]))
          ]),
          _: 1
        }),
        _createVNode(_component_v_card_actions, null, {
          default: _withCtx(() => [
            _createVNode(_component_v_btn, {
              color: "primary",
              loading: loading.value,
              onClick: refreshData
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { start: "" }, {
                  default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                    _createTextVNode("mdi-refresh", -1)
                  ]))]),
                  _: 1
                }),
                _cache[14] || (_cache[14] = _createTextVNode(" 刷新数据 ", -1))
              ]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_v_spacer),
            _createVNode(_component_v_btn, {
              color: "primary",
              onClick: notifySwitch
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { start: "" }, {
                  default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                    _createTextVNode("mdi-cog", -1)
                  ]))]),
                  _: 1
                }),
                _cache[16] || (_cache[16] = _createTextVNode(" 配置 ", -1))
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_v_dialog, {
      modelValue: deleteDialog.value,
      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((deleteDialog).value = $event)),
      "max-width": "500"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_v_card, null, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, null, {
              default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                _createTextVNode("确认删除", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_v_card_text, null, {
              default: _withCtx(() => [
                (selectedRecords.value.length > 0)
                  ? (_openBlock(), _createElementBlock("p", _hoisted_7, " 确定要删除 " + _toDisplayString(selectedRecords.value.length) + " 条记录吗？包含种子hash的记录将同时删除下载器中的种子。 ", 1))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_actions, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  onClick: _cache[4] || (_cache[4] = $event => (deleteDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                    _createTextVNode(" 取消 ", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  color: "error",
                  loading: deleting.value,
                  onClick: deleteConfirmed
                }, {
                  default: _withCtx(() => [
                    (deleting.value)
                      ? (_openBlock(), _createBlock(_component_v_progress_circular, {
                          key: 0,
                          size: "20",
                          width: "2",
                          indeterminate: ""
                        }))
                      : (_openBlock(), _createElementBlock("span", _hoisted_8, "确认删除"))
                  ]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};

export { _sfc_main as default };
