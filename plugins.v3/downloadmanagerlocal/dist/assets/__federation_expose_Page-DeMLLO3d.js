import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, M as MODULE_ICONS, R as RowActionMenu, D as DownloaderBadge, g as getPluginApi, p as postPluginApi, a as postPluginJsonApi } from './RowActionMenu-Dvq7t7J-.js';

const {createElementVNode:_createElementVNode$6,renderList:_renderList$6,Fragment:_Fragment$5,openBlock:_openBlock$7,createElementBlock:_createElementBlock$6,createCommentVNode:_createCommentVNode$5,toDisplayString:_toDisplayString$6,createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$5,withCtx:_withCtx$4,createVNode:_createVNode$4,normalizeClass:_normalizeClass$2,createBlock:_createBlock$5} = await importShared('vue');


const _hoisted_1$6 = {
  key: 0,
  class: "dm-table-state dm-table-state--loading",
  role: "status",
  "aria-label": "正在加载记录",
  "aria-busy": "true"
};
const _hoisted_2$5 = {
  key: 1,
  class: "dm-table-state",
  role: "alert"
};
const _hoisted_3$5 = {
  key: 0,
  class: "dm-table-state-help dm-table-state-error"
};
const _hoisted_4$4 = {
  key: 2,
  class: "dm-table-state dm-table-state--refresh",
  role: "status"
};
const _hoisted_5$3 = { class: "dm-table-state-help" };
const _hoisted_6$3 = {
  key: 3,
  class: "dm-table-state",
  role: "status"
};
const _hoisted_7$3 = { class: "dm-table-state-title" };
const _hoisted_8$3 = {
  key: 0,
  class: "dm-table-state-help"
};

const {computed: computed$4} = await importShared('vue');


const _sfc_main$7 = {
  __name: 'TableState',
  props: {
  loading: { type: Boolean, default: false },
  error: { type: [Boolean, String], default: false },
  refreshFailed: { type: [Boolean, String], default: false },
  empty: { type: String, default: '', validator: value => ['', 'none', 'filtered', 'not-scanned', 'no-candidates', 'disabled'].includes(value) },
},
  emits: ['retry', 'reset-filters'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const emptyStates = {
  none: { icon: 'mdi-inbox-outline', title: '暂无记录', help: '' },
  filtered: { icon: 'mdi-filter-outline', title: '筛选无结果', help: '可重置筛选后查看全部记录。' },
  'not-scanned': { icon: 'mdi-magnify', title: '尚未扫描', help: '运行扫描后查看结果。' },
  'no-candidates': { icon: 'mdi-check-circle-outline', title: '扫描无候选', help: '本次扫描未发现候选项。' },
  disabled: { icon: 'mdi-pause-circle-outline', title: '模块已关闭', help: '启用模块后可生成新记录。' },
};
const emptyState = computed$4(() => emptyStates[props.empty]);

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$5("VBtn");

  return (__props.loading)
    ? (_openBlock$7(), _createElementBlock$6("div", _hoisted_1$6, [
        _cache[3] || (_cache[3] = _createElementVNode$6("span", { class: "dm-table-state-sr" }, "正在加载记录", -1)),
        (_openBlock$7(), _createElementBlock$6(_Fragment$5, null, _renderList$6(3, (row) => {
          return _createElementVNode$6("span", {
            key: row,
            class: "dm-table-skeleton",
            "aria-hidden": "true"
          })
        }), 64))
      ]))
    : (__props.error)
      ? (_openBlock$7(), _createElementBlock$6("div", _hoisted_2$5, [
          _cache[5] || (_cache[5] = _createElementVNode$6("span", {
            class: "mdi mdi-alert-circle-outline dm-table-state-icon dm-table-state-error",
            "aria-hidden": "true"
          }, null, -1)),
          _cache[6] || (_cache[6] = _createElementVNode$6("p", { class: "dm-table-state-title" }, "记录加载失败", -1)),
          (typeof __props.error === 'string')
            ? (_openBlock$7(), _createElementBlock$6("p", _hoisted_3$5, _toDisplayString$6(__props.error), 1))
            : _createCommentVNode$5("", true),
          _createVNode$4(_component_VBtn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            type: "button",
            class: "dm-table-state-button",
            onClick: _cache[0] || (_cache[0] = $event => (emit('retry')))
          }, {
            default: _withCtx$4(() => [...(_cache[4] || (_cache[4] = [
              _createTextVNode$4("重试", -1)
            ]))]),
            _: 1
          })
        ]))
      : (__props.refreshFailed)
        ? (_openBlock$7(), _createElementBlock$6("div", _hoisted_4$4, [
            _cache[8] || (_cache[8] = _createElementVNode$6("span", {
              class: "mdi mdi-alert-outline dm-table-state-icon",
              "aria-hidden": "true"
            }, null, -1)),
            _createElementVNode$6("p", _hoisted_5$3, "刷新失败，保留上次结果" + _toDisplayString$6(typeof __props.refreshFailed === 'string' ? '：' + __props.refreshFailed : ''), 1),
            _createVNode$4(_component_VBtn, {
              size: "small",
              variant: "tonal",
              color: "primary",
              type: "button",
              class: "dm-table-state-button",
              onClick: _cache[1] || (_cache[1] = $event => (emit('retry')))
            }, {
              default: _withCtx$4(() => [...(_cache[7] || (_cache[7] = [
                _createTextVNode$4("重试", -1)
              ]))]),
              _: 1
            })
          ]))
        : (emptyState.value)
          ? (_openBlock$7(), _createElementBlock$6("div", _hoisted_6$3, [
              _createElementVNode$6("span", {
                class: _normalizeClass$2(["mdi dm-table-state-icon", emptyState.value.icon]),
                "aria-hidden": "true"
              }, null, 2),
              _createElementVNode$6("p", _hoisted_7$3, _toDisplayString$6(emptyState.value.title), 1),
              (emptyState.value.help)
                ? (_openBlock$7(), _createElementBlock$6("p", _hoisted_8$3, _toDisplayString$6(emptyState.value.help), 1))
                : _createCommentVNode$5("", true),
              (__props.empty === 'filtered')
                ? (_openBlock$7(), _createBlock$5(_component_VBtn, {
                    key: 1,
                    size: "small",
                    variant: "tonal",
                    color: "primary",
                    type: "button",
                    class: "dm-table-state-button",
                    onClick: _cache[2] || (_cache[2] = $event => (emit('reset-filters')))
                  }, {
                    default: _withCtx$4(() => [...(_cache[9] || (_cache[9] = [
                      _createTextVNode$4("重置筛选", -1)
                    ]))]),
                    _: 1
                  }))
                : _createCommentVNode$5("", true)
            ]))
          : _createCommentVNode$5("", true)
}
}

};
const TableState = /*#__PURE__*/_export_sfc(_sfc_main$7, [['__scopeId',"data-v-6884839e"]]);

const {resolveComponent:_resolveComponent$4,openBlock:_openBlock$6,createBlock:_createBlock$4} = await importShared('vue');



const _sfc_main$6 = {
  __name: 'CompactSelect',
  props: {
  modelValue: { type: [String, Number], default: '' },
  items: { type: Array, default: () => [] },
  label: { type: String, required: true },
  disabled: { type: Boolean, default: false },
},
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {


const emit = __emit;

return (_ctx, _cache) => {
  const _component_VSelect = _resolveComponent$4("VSelect");

  return (_openBlock$6(), _createBlock$4(_component_VSelect, {
    class: "dm-compact-select",
    "model-value": __props.modelValue,
    items: __props.items,
    "aria-label": __props.label,
    disabled: __props.disabled,
    density: "compact",
    "single-line": "",
    "hide-details": "",
    variant: "outlined",
    "menu-props": { contentClass: 'dm-select-menu' },
    "list-props": { density: 'compact' },
    "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (emit('update:modelValue', $event)))
  }, null, 8, ["model-value", "items", "aria-label", "disabled"]))
}
}

};
const CompactSelect = /*#__PURE__*/_export_sfc(_sfc_main$6, [['__scopeId',"data-v-6d2bb59c"]]);

const {toDisplayString:_toDisplayString$5,createElementVNode:_createElementVNode$5,openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,createCommentVNode:_createCommentVNode$4,renderSlot:_renderSlot$1,createTextVNode:_createTextVNode$3,resolveComponent:_resolveComponent$3,withCtx:_withCtx$3,createBlock:_createBlock$3,mergeProps:_mergeProps$1,renderList:_renderList$5,Fragment:_Fragment$4,normalizeStyle:_normalizeStyle,createVNode:_createVNode$3,normalizeClass:_normalizeClass$1} = await importShared('vue');


const _hoisted_1$5 = ["aria-label", "aria-busy"];
const _hoisted_2$4 = { class: "dm-module-table-header" };
const _hoisted_3$4 = { class: "dm-module-table-heading" };
const _hoisted_4$3 = { class: "dm-module-table-title" };
const _hoisted_5$2 = {
  key: 0,
  class: "dm-table-count"
};
const _hoisted_6$2 = {
  key: 0,
  class: "dm-module-table-toolbar"
};
const _hoisted_7$2 = {
  key: 0,
  class: "dm-module-table-filters"
};
const _hoisted_8$2 = {
  key: 1,
  class: "dm-module-table-actions"
};
const _hoisted_9$2 = {
  key: 0,
  class: "dm-table-unavailable",
  role: "status"
};
const _hoisted_10$2 = ["aria-label"];
const _hoisted_11$1 = { class: "dm-table-sr" };
const _hoisted_12$1 = {
  key: 0,
  scope: "col",
  class: "dm-table-control"
};
const _hoisted_13$1 = {
  key: 1,
  scope: "col",
  class: "dm-table-control"
};
const _hoisted_14$1 = { key: 0 };
const _hoisted_15$1 = {
  key: 0,
  class: "dm-table-control"
};
const _hoisted_16$1 = {
  key: 1,
  class: "dm-table-control"
};
const _hoisted_17$1 = {
  key: 0,
  class: "dm-table-expanded"
};
const _hoisted_18$1 = ["colspan"];
const _hoisted_19$1 = { key: 1 };
const _hoisted_20$1 = ["colspan"];
const _hoisted_21$1 = {
  key: 0,
  class: "dm-table-unavailable",
  role: "status"
};
const _hoisted_22$1 = {
  key: 2,
  class: "dm-module-table-footer"
};
const _hoisted_23$1 = { "aria-live": "polite" };
const _hoisted_24$1 = ["aria-label"];
const _hoisted_25$1 = { class: "dm-table-page-size" };

const {computed: computed$3,ref: ref$1,watch: watch$1} = await importShared('vue');


const _sfc_main$5 = {
  __name: 'ModuleTable',
  props: {
  title: { type: String, required: true },
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  rowKey: { type: [String, Function], default: 'id' },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20, validator: value => [20, 50, 100].includes(value) },
  state: { type: Object, default: () => ({}) },
  pagination: { type: Boolean, default: true },
  unavailable: { type: String, default: '' },
  // Opt-in presentation action only; the consumer owns confirmation and IO.
  cleanupLabel: { type: String, default: '' },
  cleanupBlocked: { type: Boolean, default: false },
},
  emits: ['update:page', 'update:pageSize', 'retry', 'reset-filters', 'cleanup'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const pageSizes = [20, 50, 100];
const effectivePageSize = computed$3(() => pageSizes.includes(props.pageSize) ? props.pageSize : 20);
const pageCount = computed$3(() => Math.max(1, Math.ceil(props.total / effectivePageSize.value)));
const currentPage = computed$3(() => Math.min(Math.max(1, props.page), pageCount.value));
const cleanupDisabled = computed$3(() => props.cleanupBlocked || props.total === 0 || !!props.state.loading);
const expanded = ref$1(new Set());
const keyOf = row => typeof props.rowKey === 'function' ? props.rowKey(row) : row[props.rowKey];
watch$1(() => props.rows, rows => {
  const keys = new Set(rows.map(keyOf));
  expanded.value = new Set([...expanded.value].filter(key => keys.has(key)));
});
function toggleRow(row) {
  const key = keyOf(row);
  const next = new Set(expanded.value);
  next.has(key) ? next.delete(key) : next.add(key);
  expanded.value = next;
}
function changePageSize(value) {
  const size = Number(value);
  if (!pageSizes.includes(size)) return
  emit('update:pageSize', size);
  emit('update:page', 1);
}
// Only presentation types are inspected; no business keys, sorting or slicing.
function alignment(column) {
  return column.align || (props.rows.some(row => typeof row[column.key] === 'number') ? 'right' : 'left')
}
const tableState = computed$3(() => props.rows.length
  ? { refreshFailed: props.state.refreshFailed || props.state.error }
  : { ...props.state, empty: props.state.empty || 'none' });
const resetFilters = () => { emit('update:page', 1); emit('reset-filters'); };

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$3("VBtn");
  const _component_VIcon = _resolveComponent$3("VIcon");
  const _component_VTable = _resolveComponent$3("VTable");

  return (_openBlock$5(), _createElementBlock$5("section", {
    class: "dm-module-table",
    "aria-label": __props.title,
    "aria-busy": !!__props.state.loading
  }, [
    _createElementVNode$5("div", _hoisted_2$4, [
      _createElementVNode$5("div", _hoisted_3$4, [
        _createElementVNode$5("h3", _hoisted_4$3, _toDisplayString$5(__props.title), 1),
        (__props.pagination && !__props.unavailable)
          ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_5$2, "共 " + _toDisplayString$5(__props.total) + " 条", 1))
          : _createCommentVNode$4("", true)
      ]),
      (_ctx.$slots.filters || _ctx.$slots.toolbar || __props.cleanupLabel)
        ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_6$2, [
            (_ctx.$slots.filters)
              ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_7$2, [
                  _renderSlot$1(_ctx.$slots, "filters", {}, undefined, true)
                ]))
              : _createCommentVNode$4("", true),
            (_ctx.$slots.toolbar || __props.cleanupLabel)
              ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_8$2, [
                  _renderSlot$1(_ctx.$slots, "toolbar", { cleanupDisabled: cleanupDisabled.value }, undefined, true),
                  (__props.cleanupLabel)
                    ? (_openBlock$5(), _createBlock$3(_component_VBtn, {
                        key: 0,
                        type: "button",
                        size: "small",
                        variant: "tonal",
                        color: "primary",
                        class: "dm-table-button dm-table-cleanup",
                        disabled: cleanupDisabled.value,
                        onClick: _cache[0] || (_cache[0] = $event => (emit('cleanup')))
                      }, {
                        default: _withCtx$3(() => [
                          _createTextVNode$3(_toDisplayString$5(__props.cleanupLabel), 1)
                        ]),
                        _: 1
                      }, 8, ["disabled"]))
                    : _createCommentVNode$4("", true)
                ]))
              : _createCommentVNode$4("", true)
          ]))
        : _createCommentVNode$4("", true)
    ]),
    (__props.state.loading && __props.rows.length)
      ? (_openBlock$5(), _createElementBlock$5("p", _hoisted_9$2, "正在刷新记录，保留上次结果"))
      : _createCommentVNode$4("", true),
    (__props.rows.length && tableState.value.refreshFailed)
      ? (_openBlock$5(), _createBlock$3(TableState, _mergeProps$1({ key: 1 }, tableState.value, {
          onRetry: _cache[1] || (_cache[1] = $event => (emit('retry')))
        }), null, 16))
      : _createCommentVNode$4("", true),
    _createElementVNode$5("div", {
      class: "dm-table-scroll",
      role: "region",
      "aria-label": __props.title + '，可横向滚动',
      tabindex: "0"
    }, [
      _createVNode$3(_component_VTable, {
        class: "dm-table",
        density: "compact"
      }, {
        default: _withCtx$3(() => [
          _createElementVNode$5("caption", _hoisted_11$1, _toDisplayString$5(__props.title), 1),
          _createElementVNode$5("thead", null, [
            _createElementVNode$5("tr", null, [
              (_ctx.$slots.expand)
                ? (_openBlock$5(), _createElementBlock$5("th", _hoisted_12$1, [...(_cache[5] || (_cache[5] = [
                    _createElementVNode$5("span", { class: "dm-table-sr" }, "详情", -1)
                  ]))]))
                : _createCommentVNode$4("", true),
              (_openBlock$5(true), _createElementBlock$5(_Fragment$4, null, _renderList$5(__props.columns, (column) => {
                return (_openBlock$5(), _createElementBlock$5("th", {
                  key: column.key,
                  scope: "col",
                  style: _normalizeStyle({ textAlign: alignment(column), width: typeof column.width === 'number' ? column.width + 'px' : column.width })
                }, _toDisplayString$5(column.label), 5))
              }), 128)),
              (_ctx.$slots.rowActions)
                ? (_openBlock$5(), _createElementBlock$5("th", _hoisted_13$1, "操作"))
                : _createCommentVNode$4("", true)
            ])
          ]),
          (__props.rows.length)
            ? (_openBlock$5(), _createElementBlock$5("tbody", _hoisted_14$1, [
                (_openBlock$5(true), _createElementBlock$5(_Fragment$4, null, _renderList$5(__props.rows, (row) => {
                  return (_openBlock$5(), _createElementBlock$5(_Fragment$4, {
                    key: keyOf(row)
                  }, [
                    _createElementVNode$5("tr", null, [
                      (_ctx.$slots.expand)
                        ? (_openBlock$5(), _createElementBlock$5("td", _hoisted_15$1, [
                            _createVNode$3(_component_VBtn, {
                              type: "button",
                              size: "small",
                              variant: "text",
                              color: "primary",
                              class: "dm-table-button",
                              "aria-expanded": expanded.value.has(keyOf(row)),
                              "aria-label": (expanded.value.has(keyOf(row)) ? '收起' : '展开') + '记录详情',
                              onClick: $event => (toggleRow(row))
                            }, {
                              default: _withCtx$3(() => [
                                _createVNode$3(_component_VIcon, {
                                  icon: expanded.value.has(keyOf(row)) ? 'mdi-chevron-up' : 'mdi-chevron-down',
                                  size: "18",
                                  "aria-hidden": "true"
                                }, null, 8, ["icon"])
                              ]),
                              _: 2
                            }, 1032, ["aria-expanded", "aria-label", "onClick"])
                          ]))
                        : _createCommentVNode$4("", true),
                      (_openBlock$5(true), _createElementBlock$5(_Fragment$4, null, _renderList$5(__props.columns, (column) => {
                        return (_openBlock$5(), _createElementBlock$5("td", {
                          key: column.key,
                          style: _normalizeStyle({ textAlign: alignment(column) })
                        }, [
                          _createElementVNode$5("div", {
                            class: _normalizeClass$1({ 'dm-table-cell-text': column.lines }),
                            style: _normalizeStyle(column.lines ? { '-webkit-line-clamp': column.lines } : undefined)
                          }, [
                            _renderSlot$1(_ctx.$slots, 'cell-' + column.key, {
                              row: row,
                              value: row[column.key]
                            }, () => [
                              _createTextVNode$3(_toDisplayString$5(row[column.key]), 1)
                            ], true)
                          ], 6)
                        ], 4))
                      }), 128)),
                      (_ctx.$slots.rowActions)
                        ? (_openBlock$5(), _createElementBlock$5("td", _hoisted_16$1, [
                            _renderSlot$1(_ctx.$slots, "rowActions", { row: row }, undefined, true)
                          ]))
                        : _createCommentVNode$4("", true)
                    ]),
                    (_ctx.$slots.expand && expanded.value.has(keyOf(row)))
                      ? (_openBlock$5(), _createElementBlock$5("tr", _hoisted_17$1, [
                          _createElementVNode$5("td", {
                            colspan: __props.columns.length + 1 + (_ctx.$slots.rowActions ? 1 : 0)
                          }, [
                            _renderSlot$1(_ctx.$slots, "expand", { row: row }, undefined, true)
                          ], 8, _hoisted_18$1)
                        ]))
                      : _createCommentVNode$4("", true)
                  ], 64))
                }), 128))
              ]))
            : (_openBlock$5(), _createElementBlock$5("tbody", _hoisted_19$1, [
                _createElementVNode$5("tr", null, [
                  _createElementVNode$5("td", {
                    class: "dm-table-state-cell",
                    colspan: Math.max(1, __props.columns.length + (_ctx.$slots.expand ? 1 : 0) + (_ctx.$slots.rowActions ? 1 : 0))
                  }, [
                    (__props.unavailable)
                      ? (_openBlock$5(), _createElementBlock$5("p", _hoisted_21$1, _toDisplayString$5(__props.unavailable), 1))
                      : (_openBlock$5(), _createBlock$3(TableState, _mergeProps$1({ key: 1 }, tableState.value, {
                          onRetry: _cache[2] || (_cache[2] = $event => (emit('retry'))),
                          onResetFilters: resetFilters
                        }), null, 16))
                  ], 8, _hoisted_20$1)
                ])
              ]))
        ]),
        _: 3
      })
    ], 8, _hoisted_10$2),
    (__props.pagination && !__props.unavailable && __props.total > 0)
      ? (_openBlock$5(), _createElementBlock$5("footer", _hoisted_22$1, [
          _createElementVNode$5("span", _hoisted_23$1, "第 " + _toDisplayString$5(currentPage.value) + " / " + _toDisplayString$5(pageCount.value) + " 页", 1),
          _createElementVNode$5("div", {
            class: "dm-table-pagination",
            role: "navigation",
            "aria-label": __props.title + '分页'
          }, [
            _createElementVNode$5("div", _hoisted_25$1, [
              _cache[6] || (_cache[6] = _createElementVNode$5("span", null, "每页", -1)),
              _createVNode$3(CompactSelect, {
                "model-value": effectivePageSize.value,
                items: pageSizes,
                label: "每页条数",
                disabled: !!__props.state.loading,
                "onUpdate:modelValue": changePageSize
              }, null, 8, ["model-value", "disabled"]),
              _cache[7] || (_cache[7] = _createElementVNode$5("span", null, "条", -1))
            ]),
            _createVNode$3(_component_VBtn, {
              type: "button",
              size: "small",
              variant: "text",
              color: "primary",
              class: "dm-table-button",
              disabled: currentPage.value <= 1 || !!__props.state.loading,
              "aria-label": "上一页",
              onClick: _cache[3] || (_cache[3] = $event => (emit('update:page', currentPage.value - 1)))
            }, {
              default: _withCtx$3(() => [...(_cache[8] || (_cache[8] = [
                _createTextVNode$3("上一页", -1)
              ]))]),
              _: 1
            }, 8, ["disabled"]),
            _createVNode$3(_component_VBtn, {
              type: "button",
              size: "small",
              variant: "text",
              color: "primary",
              class: "dm-table-button",
              disabled: currentPage.value >= pageCount.value || !!__props.state.loading,
              "aria-label": "下一页",
              onClick: _cache[4] || (_cache[4] = $event => (emit('update:page', currentPage.value + 1)))
            }, {
              default: _withCtx$3(() => [...(_cache[9] || (_cache[9] = [
                _createTextVNode$3("下一页", -1)
              ]))]),
              _: 1
            }, 8, ["disabled"])
          ], 8, _hoisted_24$1)
        ]))
      : _createCommentVNode$4("", true)
  ], 8, _hoisted_1$5))
}
}

};
const ModuleTable = /*#__PURE__*/_export_sfc(_sfc_main$5, [['__scopeId',"data-v-39baad84"]]);

const {toDisplayString:_toDisplayString$4,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$3,renderSlot:_renderSlot,renderList:_renderList$4,Fragment:_Fragment$3,createElementVNode:_createElementVNode$4} = await importShared('vue');


const _hoisted_1$4 = { class: "dm-detail-panel" };
const _hoisted_2$3 = {
  key: 0,
  class: "dm-detail-title"
};
const _hoisted_3$3 = {
  key: 1,
  class: "text-caption text-medium-emphasis dm-detail-break"
};
const _hoisted_4$2 = {
  key: 2,
  class: "text-caption text-error dm-detail-break"
};
const _hoisted_5$1 = {
  key: 0,
  class: "dm-detail-grid"
};
const _hoisted_6$1 = {
  key: 1,
  class: "dm-detail-items"
};
const _hoisted_7$1 = { class: "dm-detail-item-title dm-detail-break" };
const _hoisted_8$1 = {
  key: 0,
  class: "text-caption text-medium-emphasis dm-detail-break"
};
const _hoisted_9$1 = {
  key: 2,
  class: "dm-detail-empty"
};
const _hoisted_10$1 = {
  key: 3,
  class: "text-caption text-medium-emphasis dm-detail-truncated"
};

const {computed: computed$2} = await importShared('vue');



const _sfc_main$4 = {
  __name: 'ModuleDetailPanel',
  props: {
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  rows: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  limit: { type: Number, default: 0 },
  truncated: { type: Boolean, default: false },
  error: { type: String, default: '' },
  emptyText: { type: String, default: '' },
},
  setup(__props) {

const props = __props;

const shownCount = computed$2(() => (props.items.length ? props.items.length : props.rows.length));

return (_ctx, _cache) => {
  return (_openBlock$4(), _createElementBlock$4("div", _hoisted_1$4, [
    (__props.title)
      ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_2$3, _toDisplayString$4(__props.title), 1))
      : _createCommentVNode$3("", true),
    (__props.subtitle)
      ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_3$3, _toDisplayString$4(__props.subtitle), 1))
      : _createCommentVNode$3("", true),
    (__props.error)
      ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_4$2, _toDisplayString$4(__props.error), 1))
      : _createCommentVNode$3("", true),
    _renderSlot(_ctx.$slots, "actions", {}, undefined, true),
    _renderSlot(_ctx.$slots, "default", {}, () => [
      (__props.rows.length)
        ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_5$1, [
            (_openBlock$4(true), _createElementBlock$4(_Fragment$3, null, _renderList$4(__props.rows, (row) => {
              return (_openBlock$4(), _createElementBlock$4("div", {
                key: `row-${row.label}`,
                class: "dm-detail-row"
              }, [
                _createElementVNode$4("span", null, _toDisplayString$4(row.label), 1),
                _createElementVNode$4("strong", null, _toDisplayString$4(row.value), 1)
              ]))
            }), 128))
          ]))
        : _createCommentVNode$3("", true),
      (__props.items.length)
        ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_6$1, [
            (_openBlock$4(true), _createElementBlock$4(_Fragment$3, null, _renderList$4(__props.items, (item, index) => {
              return (_openBlock$4(), _createElementBlock$4("div", {
                key: `item-${index}`,
                class: "dm-detail-item"
              }, [
                _createElementVNode$4("div", _hoisted_7$1, _toDisplayString$4(item.title), 1),
                (item.meta)
                  ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_8$1, _toDisplayString$4(item.meta), 1))
                  : _createCommentVNode$3("", true)
              ]))
            }), 128))
          ]))
        : _createCommentVNode$3("", true),
      (__props.emptyText && !__props.rows.length && !__props.items.length)
        ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_9$1, _toDisplayString$4(__props.emptyText), 1))
        : _createCommentVNode$3("", true),
      (__props.truncated)
        ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_10$1, " 仅显示前 " + _toDisplayString$4(shownCount.value) + " 条，共 " + _toDisplayString$4(__props.total) + " 条（上限 " + _toDisplayString$4(__props.limit) + " 条）；可在「总览」页调整明细条数。 ", 1))
        : _createCommentVNode$3("", true)
    ], true),
    _renderSlot(_ctx.$slots, "appendix", {}, undefined, true)
  ]))
}
}

};
const ModuleDetailPanel = /*#__PURE__*/_export_sfc(_sfc_main$4, [['__scopeId',"data-v-328ce9c4"]]);

const {resolveComponent:_resolveComponent$2,createVNode:_createVNode$2,normalizeClass:_normalizeClass,withCtx:_withCtx$2,toDisplayString:_toDisplayString$3,createElementVNode:_createElementVNode$3,createTextVNode:_createTextVNode$2,openBlock:_openBlock$3,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,renderList:_renderList$3,Fragment:_Fragment$2,createElementBlock:_createElementBlock$3} = await importShared('vue');


const _hoisted_1$3 = { class: "dm-module-header" };
const _hoisted_2$2 = { class: "dm-module-header-line" };
const _hoisted_3$2 = { class: "dm-module-title" };
const _hoisted_4$1 = {
  key: 0,
  class: "dm-module-badges",
  "aria-label": "模块统计"
};


const _sfc_main$3 = {
  __name: 'ModuleHeader',
  props: {
  title: { type: String, required: true },
  icon: { type: String, default: 'mdi-view-module-outline' },
  showStatus: { type: Boolean, default: true },
  enabled: { type: Boolean, default: false },
  observing: { type: Boolean, default: false },
  running: { type: Boolean, default: false },
  fault: { type: [Boolean, String], default: false },
  badges: { type: Array, default: () => [] },
},
  setup(__props) {


const tones = ['primary', 'secondary', 'success', 'warning', 'error'];

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VAvatar = _resolveComponent$2("VAvatar");
  const _component_VChip = _resolveComponent$2("VChip");

  return (_openBlock$3(), _createElementBlock$3("header", _hoisted_1$3, [
    _createElementVNode$3("div", _hoisted_2$2, [
      _createVNode$2(_component_VAvatar, {
        color: __props.fault ? 'error' : __props.observing ? 'warning' : (__props.enabled || __props.running) ? 'primary' : undefined,
        variant: "tonal",
        size: "30",
        rounded: "lg",
        class: _normalizeClass(["dm-module-icon", { 'dm-module-icon--enabled': __props.enabled }])
      }, {
        default: _withCtx$2(() => [
          _createVNode$2(_component_VIcon, {
            icon: __props.icon,
            size: "17",
            "aria-hidden": "true"
          }, null, 8, ["icon"])
        ]),
        _: 1
      }, 8, ["color", "class"]),
      _createElementVNode$3("h2", _hoisted_3$2, _toDisplayString$3(__props.title), 1),
      (__props.showStatus)
        ? (_openBlock$3(), _createBlock$2(_component_VChip, {
            key: 0,
            size: "x-small",
            variant: "tonal",
            color: __props.enabled ? 'success' : undefined,
            class: "dm-module-status"
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2(_toDisplayString$3(__props.enabled ? '已启用' : '已禁用'), 1)
            ]),
            _: 1
          }, 8, ["color"]))
        : _createCommentVNode$2("", true),
      (__props.observing)
        ? (_openBlock$3(), _createBlock$2(_component_VChip, {
            key: 1,
            size: "x-small",
            variant: "tonal",
            color: "warning",
            class: "dm-module-status"
          }, {
            default: _withCtx$2(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode$2("观察模式", -1)
            ]))]),
            _: 1
          }))
        : _createCommentVNode$2("", true),
      (__props.running)
        ? (_openBlock$3(), _createBlock$2(_component_VChip, {
            key: 2,
            size: "x-small",
            variant: "tonal",
            color: "primary",
            class: "dm-module-status",
            role: "status"
          }, {
            default: _withCtx$2(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode$2("执行中", -1)
            ]))]),
            _: 1
          }))
        : _createCommentVNode$2("", true),
      (__props.fault)
        ? (_openBlock$3(), _createBlock$2(_component_VChip, {
            key: 3,
            size: "x-small",
            variant: "tonal",
            color: "error",
            class: "dm-module-status",
            role: "status"
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2("故障" + _toDisplayString$3(typeof __props.fault === 'string' ? '：' + __props.fault : ''), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode$2("", true)
    ]),
    (__props.badges.length)
      ? (_openBlock$3(), _createElementBlock$3("ul", _hoisted_4$1, [
          (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$3(__props.badges, (badge, index) => {
            return (_openBlock$3(), _createElementBlock$3("li", {
              key: index,
              class: _normalizeClass(["dm-module-stat", tones.includes(badge.tone) ? 'dm-tone-' + badge.tone : ''])
            }, [
              _createElementVNode$3("span", null, _toDisplayString$3(badge.label), 1),
              _createElementVNode$3("span", null, _toDisplayString$3(badge.value), 1)
            ], 2))
          }), 128))
        ]))
      : _createCommentVNode$2("", true)
  ]))
}
}

};
const ModuleHeader = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-9fa8b562"]]);

const {createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,createVNode:_createVNode$1,toDisplayString:_toDisplayString$2,openBlock:_openBlock$2,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createElementVNode:_createElementVNode$2,createElementBlock:_createElementBlock$2,renderList:_renderList$2,createSlots:_createSlots} = await importShared('vue');


const _hoisted_1$2 = {
  key: 1,
  class: "dm-summary-long"
};
const _hoisted_2$1 = ["title"];
const _hoisted_3$1 = ["title"];

const _sfc_main$2 = {
  __name: 'ConfigSummary',
  props: { fields: { type: Array, default: () => [] } },
  emits: ['settings'],
  setup(__props, { emit: __emit }) {


const emit = __emit;

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VChip = _resolveComponent$1("VChip");

  return (_openBlock$2(), _createBlock$1(ModuleTable, {
    title: "配置摘要",
    columns: __props.fields.map(field => ({ key: field.key, label: field.label })),
    rows: [{ id: 'current' }],
    pagination: false
  }, _createSlots({
    toolbar: _withCtx$1(() => [
      _createVNode$1(_component_VBtn, {
        size: "small",
        variant: "text",
        "prepend-icon": "mdi-cog-outline",
        onClick: _cache[0] || (_cache[0] = $event => (emit('settings')))
      }, {
        default: _withCtx$1(() => [...(_cache[1] || (_cache[1] = [
          _createTextVNode$1("前往设置", -1)
        ]))]),
        _: 1
      })
    ]),
    _: 2
  }, [
    _renderList$2(__props.fields, (field) => {
      return {
        name: `cell-${field.key}`,
        fn: _withCtx$1(() => [
          (field.badge && field.value != null)
            ? (_openBlock$2(), _createBlock$1(_component_VChip, {
                key: 0,
                size: "x-small",
                variant: "tonal",
                color: field.color || 'default'
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString$2(field.value), 1)
                ]),
                _: 2
              }, 1032, ["color"]))
            : (field.long && field.value != null)
              ? (_openBlock$2(), _createElementBlock$2("details", _hoisted_1$2, [
                  _createElementVNode$2("summary", {
                    title: String(field.value)
                  }, _toDisplayString$2(field.value), 9, _hoisted_2$1),
                  _createElementVNode$2("p", null, _toDisplayString$2(field.value), 1)
                ]))
              : (_openBlock$2(), _createElementBlock$2("span", {
                  key: 2,
                  title: field.value == null ? '当前接口未提供' : String(field.value)
                }, _toDisplayString$2(field.value ?? '当前接口未提供'), 9, _hoisted_3$1))
        ])
      }
    })
  ]), 1032, ["columns"]))
}
}

};
const ConfigSummary = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-5c3fc233"]]);

const {renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,toDisplayString:_toDisplayString$1,createElementVNode:_createElementVNode$1} = await importShared('vue');


const _hoisted_1$1 = { class: "dm-record-details" };

const {computed: computed$1} = await importShared('vue');


const _sfc_main$1 = {
  __name: 'RecordDetails',
  props: { record: { type: Object, required: true } },
  setup(__props) {

const props = __props;
const labels = {
  hash: 'Hash', torrent_hash: 'Hash', source_hash: '源 Hash', target_hash: '目的 Hash',
  name: '完整名称', source_name: '源种子名称', original_name: '原始名称', after_name: '命名后',
  reason: '原因', error: '异常', message: '说明', archive_reason: '归档原因',
  from_path: '源数据路径', to_path: '目的数据路径', torrent_path: '种子文件目录',
  source_downloader: '源下载器', target_downloader: '目的下载器', downloader_id: '下载器', downloader: '下载器',
  site: '站点', status_text: '考核状态', phase: '阶段', deleted: '下载器中缺失',
  required_hours: '要求做种时长', seeding_time: '当前做种时长', ratio: '分享率',
  rule_source: '规则来源', missing_reason: '缺失原因', created_at: '创建时间', updated_at: '更新时间',
  source: '来源', scanned: '扫描', cleaned: '清理', failed: '失败', skipped: '跳过',
  frompath: '源数据路径', topath: '目的数据路径', fromtorrentpath: '种子文件目录', fromtorrentpath_exists: '种子目录存在',
  archived_at: '归档时间', last_failed_at: '最近失败时间', fail_count: '失败次数', category: '分类', category_label: '分类名称',
};
const fields = computed$1(() => Object.entries(labels).filter(([key]) => props.record[key] != null)
  .map(([key, label]) => ({ key, label, value: typeof props.record[key] === 'boolean' ? (props.record[key] ? '是' : '否') : props.record[key] })));

return (_ctx, _cache) => {
  return (_openBlock$1(), _createElementBlock$1("dl", _hoisted_1$1, [
    (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(fields.value, (field) => {
      return (_openBlock$1(), _createElementBlock$1(_Fragment$1, {
        key: field.key
      }, [
        _createElementVNode$1("dt", null, _toDisplayString$1(field.label), 1),
        _createElementVNode$1("dd", null, _toDisplayString$1(field.value), 1)
      ], 64))
    }), 128))
  ]))
}
}

};
const RecordDetails = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-320e24f2"]]);

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createBlock:_createBlock,createCommentVNode:_createCommentVNode,unref:_unref,mergeProps:_mergeProps,normalizeProps:_normalizeProps,guardReactiveProps:_guardReactiveProps} = await importShared('vue');


const _hoisted_1 = { class: "dm-page" };
const _hoisted_2 = { class: "dm-layout" };
const _hoisted_3 = { class: "dm-side" };
const _hoisted_4 = { class: "dm-main" };
const _hoisted_5 = {
  key: 2,
  class: "dm-state"
};
const _hoisted_6 = {
  key: 0,
  class: "dm-page-stack",
  "data-page": "overview"
};
const _hoisted_7 = { class: "dm-page-heading" };
const _hoisted_8 = { class: "dm-four-stats" };
const _hoisted_9 = { class: "dm-overview-cards" };
const _hoisted_10 = { class: "dm-hint" };
const _hoisted_11 = ["data-page"];
const _hoisted_12 = { class: "dm-page-heading" };
const _hoisted_13 = { class: "dm-page-actions" };
const _hoisted_14 = { key: 0 };
const _hoisted_15 = ["title"];
const _hoisted_16 = { class: "dm-hint" };
const _hoisted_17 = ["title"];
const _hoisted_18 = { class: "dm-hint" };
const _hoisted_19 = ["title"];
const _hoisted_20 = ["title"];
const _hoisted_21 = { class: "dm-runtime-details" };
const _hoisted_22 = { class: "dm-runtime-details" };
const _hoisted_23 = ["aria-busy"];
const _hoisted_24 = {
  class: "dm-runtime-details",
  "data-record-block": "tag-cleanup-snapshot"
};
const _hoisted_25 = {
  class: "dm-page-stack",
  "data-record-block": "upload-status",
  "data-runtime-section": "upload-limit"
};
const _hoisted_26 = { class: "dm-page-heading" };
const _hoisted_27 = { class: "dm-page-actions" };
const _hoisted_28 = {
  key: 0,
  class: "dm-hint"
};
const _hoisted_29 = ["aria-expanded", "onClick"];
const _hoisted_30 = { class: "dm-hint" };
const _hoisted_31 = { class: "dm-runtime-details" };
const _hoisted_32 = {
  key: 2,
  class: "dm-page-stack",
  "data-page": "diagnostics"
};
const _hoisted_33 = { class: "dm-page-heading" };
const _hoisted_34 = { class: "dm-four-stats" };
const _hoisted_35 = { class: "dm-hint" };
const _hoisted_36 = {
  key: 0,
  class: "dm-runtime-details"
};
const _hoisted_37 = { class: "dm-runtime-details" };
const {computed,nextTick,onBeforeUnmount,onMounted,reactive,ref,watch} = await importShared('vue');

const OVERVIEW_REFRESH_INTERVAL_MS = 30_000;
const unavailableHistory = '当前接口未提供逐条执行历史；此处不以候选、汇总或实时快照代替。';

const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'DownloadManagerLocal' },
  sourcePluginId: { type: String, default: 'DownloadManagerLocal' },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options);
const postApi = (path, payload = {}, options = {}) => postPluginApi(props.api, props.pluginId, path, payload, options);
const postJsonApi = (path, payload = {}, options = {}) => postPluginJsonApi(props.api, props.pluginId, path, payload, options);

const activeTab = ref('overview');
const detailLimit = ref(20);
const tabs = [
  { key: 'overview', title: '运行总览', icon: MODULE_ICONS.overview },
  { key: 'transfer', title: '转移做种', icon: MODULE_ICONS.transfer },
  { key: 'history', title: '命名历史', icon: MODULE_ICONS.rename },
  { key: 'hr', title: 'H&R 任务', icon: MODULE_ICONS.hr },
  { key: 'autoremove', title: '删种记录', icon: MODULE_ICONS.autoremove },
  { key: 'failclean', title: '失败清理', icon: MODULE_ICONS.failclean },
  { key: 'sitetag', title: '站点标签', icon: MODULE_ICONS.tag },
  { key: 'upload', title: '上传限速', icon: MODULE_ICONS.upload_limit },
  { key: 'diagnostics', title: '运行诊断', icon: MODULE_ICONS.diagnostics },
];
const tabModuleKeys = {
  transfer: 'transfer',
  history: 'rename',
  hr: 'hr',
  autoremove: 'autoremove',
  failclean: 'failclean',
  sitetag: 'tag',
  upload: 'upload_limit',
};

const overview = ref(null);
const diagnostics = ref(null);
const downloaderItems = ref([]);
const records = ref([]);
const archiveRecords = ref([]);
// Each block owns its result/error; the existing request revision also guards block retries.
const recordStates = reactive({
  history: { loading: false, loaded: false, error: '', revision: 0 },
  archive: { loading: false, loaded: false, error: '', revision: 0 },
  transfer: { loading: false, loaded: false, error: '', revision: 0 },
  hr: { loading: false, loaded: false, error: '', revision: 0 },
  autoremove: { loading: false, loaded: false, error: '', revision: 0 },
  failclean: { loading: false, loaded: false, error: '', revision: 0 },
});
function recordTableState(key, rows, empty = 'none', busyWithResult = false) {
  const state = recordStates[key];
  const hasResult = state.loaded || rows.length > 0;
  return {
    loading: state.loading,
    error: !hasResult ? state.error || false : false,
    refreshFailed: hasResult ? state.error || false : false,
    empty: rows.length ? '' : empty,
  }
}
const total = ref(0);
const archiveTotal = ref(0);
const page = ref(1);
const archivePage = ref(1);
const pageSize = ref(20);
const archivePageSize = ref(20);
const transferPageSize = ref(20);
const historyResultFilter = ref('all');
const transferResultFilter = ref('all');
const loading = ref(false);
const paging = ref(false);
const error = ref('');
const actionMsg = ref('');
const actionLevel = ref(''); // '' | 'success' | 'partial' | 'error'：code=0 成功 / code=2 部分完成（warning） / 其余失败

// 统一动作反馈格式：所有模块动作共用同一套 success/partial/error 判定与兜底文案。
function applyActionResp(resp, fallback) {
  const code = resp?.code;
  actionLevel.value = code === 0 ? 'success' : (code === 2 ? 'partial' : 'error');
  const verb = fallback.replace(/完成$|已触发$/, '');
  actionMsg.value = resp?.msg
    || (code === 0 ? fallback : (code === 2 ? `${verb}部分完成` : `${verb}失败`));
}

function applyActionError(e, fallback) {
  // unwrapResponse 抛错时 e.code 携带业务 code：code=2 部分完成按 warning 收尾
  if (e?.code === 2) return applyActionResp({ code: 2, msg: e?.message }, fallback)
  actionLevel.value = 'error';
  actionMsg.value = e?.message || `${fallback.replace(/完成$|已触发$/, '')}失败`;
}

const moduleRunning = ref('');
const expandedModules = reactive({});

const hrTasks = ref({ tasks: [], summary: {} });
const hrSkipStats = ref({});
const autoremoveStatus = ref({});
const failcleanStatus = ref({});
const siteTagStatus = ref({});
const transferStatus = ref({});
const transferPage = ref(1);
const renameStatus = ref({});
const autoremovePreview = ref(null);
const moduleConfigSummary = ref(null);

const retryingHash = ref('');
const restoringHash = ref('');
const deletingHash = ref('');

const hrClearing = ref(false);
const hrClearKey = ref('');
const hrClearDialog = ref(false);
const hrClearKind = ref('');
const hrClearTarget = ref(null);
const hrClearDialogDescription = computed(() => ({
  task: '只清除这一条 H&R 记录，不操作下载器任务',
  compliant: '清除所有已满足的 H&R 记录',
  missing: '清除种子已不在下载器的 H&R 记录',
}[hrClearKind.value] || '清除 H&R 记录，不操作下载器任务'));

const transferRunDialog = ref(false);

const cleanupDownloaders = ref([]);
const cleanupScan = ref(null);
const cleanupKeep = reactive({});
const cleanupScanning = ref(false);
const cleanupExecuting = ref(false);
const cleanupDialog = ref(false);
const cleanupMessage = ref('');
const cleanupStatus = ref('info');

let overviewRefreshTimer = null;
let overviewRefreshPending = false;
let pageRequestRevision = 0;
let recordRequestRevision = 0;
let diagnosticsRequestRevision = 0;
let pageDisposed = false;

function beginPageRequest() {
  return { revision: ++pageRequestRevision, pluginId: props.pluginId, tab: activeTab.value }
}
function isCurrentPageRequest(request) {
  return !pageDisposed && request.revision === pageRequestRevision
    && request.pluginId === props.pluginId && request.tab === activeTab.value
}
function beginRecordRequest(blocks = ['history', 'archive']) {
  const request = { revision: ++recordRequestRevision, pluginId: props.pluginId, tab: activeTab.value };
  for (const key of blocks) recordStates[key].revision = request.revision;
  return request
}
function isCurrentRecordRequest(request, key) {
  return !pageDisposed && request.revision === (key ? recordStates[key].revision : recordRequestRevision)
    && request.pluginId === props.pluginId && request.tab === activeTab.value
}
function beginDiagnosticsRequest() {
  return { revision: ++diagnosticsRequestRevision }
}
function isCurrentDiagnosticsRequest(request) {
  return !pageDisposed && request.revision === diagnosticsRequestRevision
}
function reportLoadError(request, e, fallback, { silent = false } = {}) {
  if (!isCurrentPageRequest(request)) return
  if (silent) {
    console.error(fallback, e);
    return
  }
  error.value = e?.message || fallback;
}
function reportRecordLoadError(request, e, fallback, key) {
  if (!isCurrentRecordRequest(request, key)) return
  recordStates[key].error = e?.message || fallback;
}

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  if (total <= 0) return '—'
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days} 天 ${hours} 小时`
  if (hours > 0) return `${hours} 小时 ${minutes} 分`
  return `${minutes} 分`
}

function formatTimestamp(value) {
  const seconds = Number(value || 0);
  if (!seconds) return '—'
  const date = new Date(seconds * 1000);
  const pad = part => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`
}

function formatUploadRate(value) {
  const rate = Number(value || 0);
  if (rate >= 1024 * 1024) return `${(rate / 1024 / 1024).toFixed(2)} MiB/s`
  return `${(rate / 1024).toFixed(1)} KiB/s`
}

function hrStatusColor(status) {
  return {
    Pending: 'warning',
    'In Progress': 'primary',
    Compliant: 'success',
    'Needs Seeding': 'warning',
    Overdue: 'error',
  }[status] || 'default'
}

const hrStatusFilter = ref('all');
const hrStatusFilterOptions = [
  { title: '全部状态', value: 'all' },
  { title: '待处理', value: 'Pending' },
  { title: '做种中', value: 'In Progress' },
  { title: '已达标', value: 'Compliant' },
  { title: '需做种', value: 'Needs Seeding' },
  { title: '已超期', value: 'Overdue' },
];
const hrSummary = computed(() => hrTasks.value.summary || {});
const hrTaskRows = computed(() => {
  const rows = hrTasks.value.tasks || [];
  if (hrStatusFilter.value === 'all') return rows
  return rows.filter(task => task.status === hrStatusFilter.value)
});
const hrSkipRowLabels = {
  transfer_source: '转移源端',
  auto_remove: '自动删种',
  transfer_failure: '整理失败',
  sync_delete: '同步删除',
};
const hrSkipRows = computed(() => Object.entries(hrSkipStats.value || {})
  .map(([key, value]) => ({ label: hrSkipRowLabels[key] || key, value: Number(value || 0) })));
computed(() => hrSkipRows.value.reduce((sum, row) => sum + row.value, 0));

const autoremoveCandidates = computed(() => autoremoveStatus.value.candidate_list || []);
const autoremoveRows = computed(() => (
  Array.isArray(autoremovePreview.value?.candidate_list)
    ? autoremovePreview.value.candidate_list
    : autoremoveCandidates.value
));
const autoremoveHasRun = computed(() => Number(autoremoveStatus.value.last_run_at || 0) > 0);
const autoremoveEmptyState = computed(() => {
  if (autoremoveRows.value.length) return ''
  if (autoremoveHasRun.value) return 'no-candidates'
  if (recordStates.autoremove.loaded && autoremoveStatus.value.enabled === false) return 'disabled'
  return 'not-scanned'
});
function failcleanMetric(value) {
  return value == null || value === '' ? null : value
}
function hasFailcleanActivity(source, keys) {
  return keys.some(key => Number(source?.[key] || 0) > 0)
}
const failcleanRows = computed(() => {
  const status = failcleanStatus.value || {};
  const rows = [];
  if (hasFailcleanActivity(status.event, ['deleted', 'failed', 'skipped'])) {
    rows.push({ source: '来源事件', scanned: null, cleaned: failcleanMetric(status.event.deleted), failed: failcleanMetric(status.event.failed), skipped: failcleanMetric(status.event.skipped) });
  }
  if (hasFailcleanActivity(status.scan, ['scanned', 'cleaned', 'failed', 'skipped'])) {
    rows.push({ source: '上轮巡检', scanned: failcleanMetric(status.scan.scanned), cleaned: failcleanMetric(status.scan.cleaned), failed: failcleanMetric(status.scan.failed), skipped: failcleanMetric(status.scan.skipped) });
  }
  if (hasFailcleanActivity(status.total, ['cleaned', 'failed', 'skipped'])) {
    rows.push({ source: '累计', scanned: null, cleaned: failcleanMetric(status.total.cleaned), failed: failcleanMetric(status.total.failed), skipped: failcleanMetric(status.total.skipped) });
  }
  return rows
});
const failcleanHasRun = computed(() => Number(failcleanStatus.value.last_scan_time || 0) > 0);
const failcleanHasResult = computed(() => failcleanHasRun.value || failcleanRows.value.length > 0);
const failcleanEmptyState = computed(() => {
  if (failcleanRows.value.length) return ''
  if (failcleanHasResult.value) return 'no-candidates'
  if (recordStates.failclean.loaded && failcleanStatus.value.enabled === false) return 'disabled'
  return 'not-scanned'
});
computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize.value)));
computed(() => Math.max(1, Math.ceil((archiveTotal.value || 0) / archivePageSize.value)));

const diagnosticsCards = computed(() => {
  const items = Array.isArray(diagnostics.value?.checks) ? diagnostics.value.checks : [];
  return items.map(item => ({
    ...item,
    statusText: item.status === 'ok' ? '正常' : item.status === 'error' ? '故障' : item.status === 'warn' ? '关注' : '未启用',
    icon: item.status === 'ok'
      ? 'mdi-check-circle-outline'
      : item.status === 'error'
        ? 'mdi-alert-octagon-outline'
        : item.status === 'warn'
          ? 'mdi-alert-circle-outline'
          : 'mdi-minus-circle-outline',
  }))
});
const diagnosticsOkCount = computed(() => diagnosticsCards.value.filter(item => item.status === 'ok').length);
computed(() => diagnosticsCards.value.length - diagnosticsOkCount.value);

const uploadLimit = computed(() => overview.value?.upload_limit || {});
const uploadLimitDownloaderRows = computed(() => uploadLimit.value.downloaders || []);
const uploadLimitSiteRows = computed(() => uploadLimit.value.sites || []);
const uploadLimitStatus = computed(() => {
  const status = uploadLimit.value.service_status;
  return {
    disabled: { label: '未启用', color: 'default' },
    starting: { label: '启动中', color: 'primary' },
    running: { label: '分配中', color: 'primary' },
    degraded: { label: '部分异常', color: 'warning' },
    error: { label: '状态异常', color: 'error' },
    observe_only: { label: '观察模式', color: 'warning' },
  }[status] || { label: '未启用', color: 'default' }
});

const overviewAttentionCount = computed(() => {
  const uploadErrors = Array.isArray(uploadLimit.value.errors) ? uploadLimit.value.errors.length : 0;
  const downloaderErrors = uploadLimitDownloaderRows.value.filter(item => item.error).length;
  const uploadStatusErrors = ['degraded', 'error'].includes(uploadLimit.value.service_status) && uploadErrors + downloaderErrors === 0 ? 1 : 0;
  return uploadErrors + downloaderErrors + uploadStatusErrors
});
const overviewPendingCount = computed(() => {
  const archive = overview.value?.archive || {};
  return Number(archive.active_failed || 0) + Number(archive.near_archive || 0)
});
const moduleFaultLabels = {
  transfer: '转移做种',
  rename: '种子重命名',
  tag: '站点标签与分类',
  hr: 'H&R 管理',
  autoremove: '自动删种',
  failclean: '失败清理',
  upload_limit: '上传限速',
};
/** 模块运行异常项：模块关闭时后端不产生故障记录，只有启用后运行出错才会出现。 */
const moduleFaultItems = computed(() => {
  const faults = diagnostics.value?.module_faults;
  if (!faults || typeof faults !== 'object') return []
  return Object.entries(faults)
    .filter(([module]) => moduleFaultLabels[module])
    .map(([module, reason]) => ({
      icon: 'mdi-alert-octagon-outline',
      color: 'error',
      title: `${moduleFaultLabels[module]}运行异常`,
      detail: String(reason || '未知原因'),
      target: module,
    }))
});
const overviewAttentionItems = computed(() => {
  const archive = overview.value?.archive || {};
  const items = [];
  if (archive.active_failed) {
    items.push({ icon: 'mdi-auto-fix', color: 'warning', title: '命名失败待处理', detail: `${archive.active_failed} 条记录连续失败`, target: 'rename' });
  }
  if (archive.near_archive) {
    items.push({ icon: 'mdi-archive-alert-outline', color: 'warning', title: '接近归档阈值', detail: `${archive.near_archive} 条记录需要关注`, target: 'rename' });
  }
  for (const runtimeError of uploadLimit.value.errors || []) {
    items.push({ icon: 'mdi-upload-network-outline', color: 'error', title: '上传限速异常', detail: runtimeError, target: 'upload_limit' });
  }
  for (const downloader of uploadLimitDownloaderRows.value.filter(item => item.error)) {
    items.push({ icon: 'mdi-download-network-outline', color: 'warning', title: `${downloader.id} 状态异常`, detail: downloader.error, target: 'upload_limit' });
  }
  if (['degraded', 'error'].includes(uploadLimit.value.service_status) && !uploadLimit.value.errors?.length && !uploadLimitDownloaderRows.value.some(item => item.error)) {
    items.push({ icon: 'mdi-upload-network-outline', color: 'error', title: '上传限速异常', detail: '服务返回异常状态，请展开上传限速卡详情查看运行数据', target: 'upload_limit' });
  }
  items.push(...moduleFaultItems.value);
  return items
});
computed(() => {
  const archive = overview.value?.archive || {};
  const uploadErrors = Array.isArray(uploadLimit.value.errors) ? uploadLimit.value.errors.length : 0;
  const downloaderErrors = uploadLimitDownloaderRows.value.filter(item => item.error).length;
  const uploadStatusErrors = ['degraded', 'error'].includes(uploadLimit.value.service_status) && uploadErrors + downloaderErrors === 0 ? 1 : 0;
  return [
    {
      title: '上传限速',
      icon: 'mdi-upload-network-outline',
      color: uploadLimitStatus.value.color,
      value: uploadLimitStatus.value.label,
      desc: `受限 ${uploadLimit.value.managed_torrents || 0} · 宽限 ${uploadLimit.value.grace_torrents || 0}`,
    },
    {
      title: '待关注',
      icon: 'mdi-bell-alert-outline',
      color: overviewPendingCount.value ? 'warning' : 'success',
      value: overviewPendingCount.value,
      desc: `命名 ${Number(archive.active_failed || 0) + Number(archive.near_archive || 0)}`,
    },
    {
      title: '异常数量',
      icon: 'mdi-alert-outline',
      color: overviewAttentionCount.value ? 'error' : 'success',
      value: overviewAttentionCount.value,
      desc: overviewAttentionCount.value
        ? `限速异常 ${uploadErrors + downloaderErrors + uploadStatusErrors}`
        : '当前无服务异常',
    },
  ]
});

const moduleCards = computed(() => {
  const cards = overview.value?.cards || {};
  const archive = overview.value?.archive || {};
  const transfer = cards.transfer || {};
  const seed = cards.seed || {};
  const hr = hrSummary.value;
  const auto = autoremoveStatus.value;
  const fail = failcleanStatus.value;
  const tag = siteTagStatus.value;
  const rename = renameStatus.value;
  const up = uploadLimit.value;
  return [
    {
      key: 'transfer',
      title: '转移做种',
      icon: MODULE_ICONS.transfer,
      color: transfer.active ? 'primary' : (transfer.enabled ? 'warning' : 'default'),
      value: transfer.active ? '运行中' : (transfer.enabled ? '未就绪' : '未启用'),
      desc: `今日成功 ${transfer.today_success || 0} · 今日兜底 ${transfer.today_fallback || 0}`,
      details: [
        { label: '累计成功', value: transfer.success_total || 0 },
        { label: '兜底累计', value: transfer.fallback_success || 0 },
        { label: '兜底扫描', value: transfer.fallback_enabled ? '已启用' : '未启用' },
      ],
      actions: [
        { key: 'transfer-run', label: '执行转移', icon: 'mdi-play-circle-outline', color: 'primary', run: () => { transferRunDialog.value = true; } },
      ],
    },
    {
      key: 'seed',
      title: '做种校验',
      icon: 'mdi-check-circle-outline',
      color: seed.autostart ? 'primary' : 'default',
      value: seed.autostart ? '自动开始' : '仅校验',
      desc: seed.skipverify ? '跳过校验' : '按需校验',
      details: [
        { label: '自动开始做种', value: seed.autostart ? '已启用' : '未启用' },
        { label: '跳过校验', value: seed.skipverify ? '已启用' : '未启用' },
      ],
      notes: [{ type: 'info', text: '做种校验按需触发：仅在转移做种或手动补刀添加种子后启动，队列为空后自动停止。' }],
      actions: [],
    },
    {
      key: 'hr',
      title: 'H&R',
      icon: MODULE_ICONS.hr,
      color: hr.overdue ? 'warning' : (hr.enabled ? 'primary' : 'default'),
      value: `${hr.total || 0} 条任务`,
      desc: `达标 ${hr.compliant || 0} · 超期 ${hr.overdue || 0} · 需做种 ${hr.needs_seeding || 0}`,
      detailTitle: '保护跳过计数',
      details: hrSkipRows.value,
      actions: [
        { key: 'hr-check', label: '检查 H&R', icon: 'mdi-clipboard-check-outline', color: 'primary', run: doHrCheck },
        { key: 'hr-scan', label: '发现任务', icon: 'mdi-radar', color: 'primary', run: doHrScan },
      ],
    },
    {
      key: 'autoremove',
      title: '自动删种',
      icon: MODULE_ICONS.autoremove,
      color: auto.enabled ? 'primary' : 'default',
      value: `${auto.deleted || 0} 个已删除`,
      desc: `候选 ${auto.candidates || 0} · 跳过保护 ${auto.skipped_protected || 0} · 失败 ${auto.failed || 0}`,
      details: [
        { label: '执行动作', value: auto.action === 'deletefile' ? '删除任务及文件' : (auto.action === 'delete' ? '删除任务' : '暂停任务') },
        { label: '运行中', value: auto.running ? '是' : '否' },
        { label: '保护闸门', value: auto.guard_unconfirmed ? '无法确认（已保守跳过）' : (auto.guard_enabled ? '已启用' : '未启用') },
      ],
      notes: auto.observe_only
        ? [{ type: 'warning', text: '迁移观察期：仅列出候选，不执行下载器写操作。' }]
        : (auto.config_error ? [{ type: 'error', text: auto.config_error }] : []),
      actions: [
        { key: 'autoremove-preview', label: '预览候选', icon: 'mdi-eye-outline', color: 'primary', run: doAutoremovePreview },
        { key: 'autoremove-run', label: auto.action === 'deletefile' ? '删除任务及文件' : (auto.action === 'delete' ? '删除任务' : '暂停任务'), icon: 'mdi-delete-clock-outline', color: auto.observe_only ? 'warning' : (auto.action === 'delete' || auto.action === 'deletefile' ? 'error' : 'primary'), run: doAutoremoveRun },
      ],
    },
    {
      key: 'failclean',
      title: '失败清理',
      icon: MODULE_ICONS.failclean,
      color: fail.enabled ? 'primary' : 'default',
      value: `巡检清理 ${fail.scan?.cleaned || 0}`,
      desc: `整理失败删源 ${fail.event?.deleted || 0} · 跳过 ${(fail.scan?.skipped || 0) + (fail.event?.skipped || 0)}`,
      details: [
        { label: '即时删源', value: fail.event?.deleted || 0 },
        { label: '巡检清理', value: fail.scan?.cleaned || 0 },
        { label: '失败合计', value: (fail.scan?.failed || 0) + (fail.event?.failed || 0) },
        { label: '累计清理', value: fail.total?.cleaned || 0 },
      ],
      actions: [
        { key: 'failclean-scan', label: '扫描残留', icon: 'mdi-radar', color: 'primary', run: doFailcleanScan },
      ],
    },
    {
      key: 'rename',
      title: '种子重命名',
      icon: MODULE_ICONS.rename,
      color: archive.archived ? 'warning' : 'primary',
      value: `${archive.active_failed || 0} / ${archive.archived || 0}`,
      desc: `待处理 / 已归档 · 阈值 ${archive.threshold || 3} 次`,
      details: [
        { label: '事件改名', value: rename.event?.renamed || 0 },
        { label: '定时补查', value: rename.cron?.renamed || 0 },
        { label: '本次失败', value: rename.failed || 0 },
        { label: '本次跳过', value: rename.skipped || 0 },
      ],
      actions: [
        { key: 'rename-retry', label: '重试', icon: 'mdi-auto-fix', color: 'primary', run: doRetryRenames },
      ],
    },
    {
      key: 'tag',
      title: '站点标签',
      icon: MODULE_ICONS.tag,
      color: tag.completed ? 'primary' : 'default',
      value: `${tag.completed || 0} 个补全`,
      desc: `补全成功 · 跳过 ${tag.skipped || 0}`,
      details: Object.entries(tag.matched || {}).map(([name, value]) => ({ label: name, value })),
      notes: Object.keys(tag.matched || {}).length ? [] : [{ type: 'info', text: '暂无本轮站点标签匹配统计；标签清理工具见下方「标签清理」区块。' }],
      actions: [
        { key: 'tag-complement', label: '补全分类标签', icon: 'mdi-tag-plus-outline', color: 'primary', run: doTagComplement },
      ],
    },
    {
      key: 'upload_limit',
      title: '上传限速',
      icon: MODULE_ICONS.upload_limit,
      color: uploadLimitStatus.value.color,
      value: uploadLimitStatus.value.label,
      desc: `受限 ${up.managed_torrents || 0} · 宽限 ${up.grace_torrents || 0}`,
      actions: [
        { key: 'upload-reallocate', label: '重新分配', icon: 'mdi-call-split', color: 'primary', run: doUploadReallocate },
        { key: 'upload-scan-sites', label: '扫描站点', icon: 'mdi-radar', color: 'primary', run: doUploadScanSites },
        { key: 'upload-clear-rules', label: '清空策略', icon: 'mdi-delete-sweep-outline', color: 'error', run: doUploadClearRules },
      ],
    },
  ]
});

// Header projections only consume existing snapshots; missing counters are not inferred from rows.
const headerMetric = (label, value, tone) => ({
  label, value: value ?? '—',
  tone: value == null ? 'secondary' : (
    ['今日失败', '失败', '失败归档'].includes(label) ? (Number(value) > 0 ? 'error' : 'secondary') :
    ['待重试', '待做种', '跳过'].includes(label) ? (Number(value) > 0 ? 'warning' : 'secondary') :
    ['今日成功', '累计成功', '成功', '清理', '已达标'].includes(label) ? 'success' :
    ['在途', '做种中', '上传中', '当前上传'].includes(label) ? 'primary' : 'secondary')
});
const moduleHeaders = computed(() => {
  const cards = overview.value?.cards || {};
  const config = diagnostics.value?.config || overview.value?.config || {};
  const observing = diagnostics.value?.module_observe_only || {};
  const faults = diagnostics.value?.module_faults || {};
  const transfer = transferStatus.value.summary || {};
  const archive = overview.value?.archive || {};
  const hr = hrSummary.value;
  const auto = autoremoveStatus.value;
  const fail = failcleanStatus.value;
  const rename = renameStatus.value;
  const tag = siteTagStatus.value;
  const up = uploadLimit.value;
  const headers = {
    transfer: {
      enabled: !!(cards.transfer?.enabled ?? config.transfer_enabled),
      badges: [
        headerMetric('在途', transfer.pending),
        headerMetric('今日成功', transfer.today_success ?? cards.transfer?.today_success),
        headerMetric('今日失败', transfer.today_failed),
        headerMetric('累计成功', transfer.success_total ?? cards.transfer?.success_total),
      ],
    },
    rename: {
      enabled: !!(cards.rename?.enabled ?? config.rename_enabled),
      running: !!renameStatus.value.batch_running,
      // today_success/today_failed 由后端 rename_status 直接提供（modules/rename/archive.py::today_stats）。
      badges: [headerMetric('今日成功', rename.today_success), headerMetric('今日失败', rename.today_failed),
        headerMetric('待重试', archive.active_failed), headerMetric('失败归档', archive.archived)],
    },
    tag: {
      enabled: !!config.tag_enabled,
      // round 为本轮补全投影；缺失时不回退到累计 completed/skipped。
      badges: [headerMetric('本轮检查', tag.round?.checked), headerMetric('成功', tag.round?.success),
        headerMetric('无需更新', tag.round?.no_update), headerMetric('失败', tag.round?.failed)],
    },
    hr: {
      enabled: !!hr.enabled,
      badges: [headerMetric('总数', hr.total), headerMetric('待做种', hr.needs_seeding),
        headerMetric('做种中', hr.in_progress), headerMetric('已达标', hr.compliant)],
    },
    autoremove: {
      enabled: !!auto.enabled,
      observing: !!auto.observe_only,
      running: !!auto.running,
      fault: !!auto.config_error,
      // skipped 为后端汇总的保护跳过 + 已消失跳过（modules/autoremove/service.py::get_module_status）。
      badges: [headerMetric('上轮候选', auto.candidates),
        headerMetric('成功', auto.observe_only ? undefined : (auto.action === 'pause' ? auto.paused : auto.deleted)),
        headerMetric('跳过', auto.skipped), headerMetric('失败', auto.failed)],
    },
    failclean: {
      enabled: !!fail.enabled,
      badges: [headerMetric('上轮扫描', fail.scan?.scanned), headerMetric('清理', fail.scan?.cleaned),
        headerMetric('跳过', fail.scan?.skipped), headerMetric('失败', fail.scan?.failed)],
    },
    upload_limit: {
      enabled: !!up.enabled,
      observing: up.service_status === 'observe_only',
      fault: ['degraded', 'error'].includes(up.service_status) || !!up.errors?.length || !!up.state_error,
      badges: [headerMetric('受管种子', up.managed_torrents), headerMetric('上传中', up.uploading_torrents),
        headerMetric('当前上传', up.upload_rate_bps == null ? undefined : formatUploadRate(up.upload_rate_bps)),
        headerMetric('已分配额度', up.allocated_kib == null ? undefined : `${up.allocated_kib} KiB/s`)],
    },
  };
  return Object.fromEntries(moduleCards.value.filter(card => headers[card.key]).map(card => {
    const header = headers[card.key];
    return [card.key, {
      ...header,
      title: card.key === 'hr' ? 'H&R 管理' : card.title,
      icon: card.icon,
      observing: !!(observing[card.key] || header.observing),
      running: !!(header.running || card.actions.some(action => action.key === moduleRunning.value)),
      fault: !!(faults[card.key] || header.fault),
    }]
  }))
});

computed(() => {
  if (activeTab.value === 'overview') return moduleCards.value
  const key = tabModuleKeys[activeTab.value];
  return key ? moduleCards.value.filter(card => card.key === key) : []
});

async function loadOverview(request, { silent = false } = {}) {
  try {
    const requestOptions = { feedback: 'silent' };
    const [overviewResp, uploadResp] = await Promise.all([
      getApi('overview', requestOptions),
      getApi('upload_limit_status', requestOptions).catch(err => {
        console.error('上传限速状态刷新失败，保留总览快照:', err);
        return null
      }),
    ]);
    if (!isCurrentPageRequest(request)) return
    if (overviewResp?.code && overviewResp.code !== 0 && !overviewResp.cards) {
      throw new Error(overviewResp?.msg || '总览加载失败')
    }
    const uploadStatus = uploadResp?.code === 0 || uploadResp?.service_status
      ? uploadResp
      : overviewResp?.upload_limit;
    overview.value = { ...(overviewResp || {}), upload_limit: uploadStatus || {} };
  } catch (e) {
    reportLoadError(request, e, '总览加载失败', { silent });
  }
}

async function loadRenameStatus(request) {
  const resp = await getApi('rename_status', { feedback: 'silent' }).catch(() => null);
  if (!isCurrentPageRequest(request) || !resp?.status) return
  renameStatus.value = resp.status;
}

async function loadHrStatus(request) {
  if (isCurrentPageRequest(request)) {
    recordStates.hr.loading = true;
    recordStates.hr.error = '';
  }
  const [tasksResp, skipResp] = await Promise.all([
    getApi('hr/tasks', { feedback: 'silent' }).catch(error => ({ __error: error })),
    getApi('hr/skip_stats', { feedback: 'silent' }).catch(() => null),
  ]);
  if (!isCurrentPageRequest(request)) return
  recordStates.hr.loading = false;
  if (!tasksResp || tasksResp.__error) {
    recordStates.hr.error = tasksResp?.__error?.message || 'H&R 任务加载失败';
    return
  }
  recordStates.hr.loaded = true;
  recordStates.hr.error = '';
  hrTasks.value = { tasks: tasksResp.tasks || [], summary: tasksResp.summary || {} };
  if (skipResp?.skip_stats) hrSkipStats.value = skipResp.skip_stats;
}

async function loadAutoremoveStatus(request) {
  const recordRequest = beginRecordRequest(['autoremove']);
  recordStates.autoremove.loading = true;
  recordStates.autoremove.error = '';
  try {
    const resp = await getApi('autoremove_status', { feedback: 'silent' });
    if (!isCurrentPageRequest(request) || !isCurrentRecordRequest(recordRequest, 'autoremove')) return
    if (!resp?.status) throw new Error(resp?.msg || '自动删种记录加载失败')
    autoremoveStatus.value = resp.status;
    recordStates.autoremove.loaded = true;
  } catch (e) {
    reportRecordLoadError(recordRequest, e, '自动删种记录加载失败', 'autoremove');
  } finally {
    if (isCurrentRecordRequest(recordRequest, 'autoremove')) recordStates.autoremove.loading = false;
  }
}

async function loadFailcleanStatus(request) {
  const recordRequest = beginRecordRequest(['failclean']);
  recordStates.failclean.loading = true;
  recordStates.failclean.error = '';
  try {
    const resp = await getApi('failclean_status', { feedback: 'silent' });
    if (!isCurrentPageRequest(request) || !isCurrentRecordRequest(recordRequest, 'failclean')) return
    if (!resp?.status) throw new Error(resp?.msg || '失败清理明细加载失败')
    failcleanStatus.value = resp.status;
    recordStates.failclean.loaded = true;
  } catch (e) {
    reportRecordLoadError(recordRequest, e, '失败清理明细加载失败', 'failclean');
  } finally {
    if (isCurrentRecordRequest(recordRequest, 'failclean')) recordStates.failclean.loading = false;
  }
}

async function loadSiteTagStatus(request) {
  const resp = await getApi('tag_status', { feedback: 'silent' }).catch(() => null);
  if (!isCurrentPageRequest(request) || !resp?.status) return
  siteTagStatus.value = resp.status;
}

const TRANSFER_PHASE_LABELS = {
  source_pausing: '暂停源种',
  adding: '添加目标',
  target_added: '已添加目标',
  // 旧版本写过的历史状态：后端仅作为「视同完成」读取（modules/transfer/service.py:419），
  // 当前 pipeline 不再产出，但 qnap 的历史记录里可能存在，缺映射会让界面漏出原始英文。
  stopped_after_add: '已添加目标（旧记录）',
  verifying: '做种校验',
  target_ready: '待确认做种',
  completed: '已完成',
  rollback: '回滚中',
  rolled_back: '已回滚',
  failed: '已放弃（超重试上限）',
};
computed(() => transferStatus.value.summary || {});
const transferTasks = computed(() => transferStatus.value.tasks || []);
const transferPending = computed(() => transferStatus.value.pending || []);
const transferRecords = computed(() => transferStatus.value.records || []);

function transferPhaseText(phase) {
  return TRANSFER_PHASE_LABELS[phase] || phase || '—'
}

function transferPhaseColor(phase) {
  if (phase === 'completed') return 'success'
  if (phase === 'rollback' || phase === 'rolled_back' || phase === 'failed') return 'error'
  if (phase === 'verifying' || phase === 'target_ready') return 'primary'
  if (phase === 'source_pausing') return 'warning'
  if (phase === 'target_added') return 'primary'
  if (phase === 'stopped_after_add') return 'warning'
  return 'default'
}

function transferShortHash(hash) {
  const text = String(hash || '');
  return text ? text.slice(0, 8) : '—'
}


/** 源种子名：转移记录写入端自 3.9.13 起落 `source_name`，旧记录为空串（名称未记录）。 */
function transferSourceName(record) {
  return String((record && record.source_name) || '').trim()
}

/** 转移列表主文案：有名字用名字，没有则明确写「名称未记录」，不拿 hash 冒充名称。 */
function transferPrimaryText(record) {
  return transferSourceName(record) || '名称未记录'
}

/** 转移列表次要文案：短 hash 作辅助；无 hash 时为占位符，完整 hash 仍在 title 提示里。 */
function transferSecondaryText(record) {
  return transferShortHash(record && record.source_hash)
}

/** H&R 任务主标题：种子名优先，缺失时「名称未记录 + 短 hash」，站点另作次级信息。 */
function hrTaskTitle(task) {
  const name = String((task && task.name) || '').trim();
  if (name) return name
  const short = transferShortHash(task && task.torrent_hash);
  return short === '—' ? '名称未记录' : `名称未记录 · ${short}`
}

/** 筛选条件摘要：与配置页任务列表口径一致，无条件时明确显示「不限分类」。 */
function transferFilterText(task) {
  const parts = [];
  const category = String(task.include_category || '').trim();
  parts.push(category ? `分类 ${category}` : '不限分类');
  const labels = String(task.include_labels || '').trim();
  if (labels) parts.push(`标签 ${labels}`);
  const excluded = String(task.exclude_labels || '').trim();
  if (excluded) parts.push(`排除 ${excluded}`);
  return parts.join(' · ')
}

/** 设置徽标：只列已启用的高级设置，未启用时前端显示「默认」。 */
function transferSettingBadges(task) {
  const badges = [];
  if (task.delete_source) badges.push({ text: '删源种', color: 'error' });
  if (task.delete_duplicate) badges.push({ text: '去重', color: 'warning' });
  if (!task.keep_category) badges.push({ text: '不保留分类', color: 'secondary' });
  if (!task.keep_tag) badges.push({ text: '不保留标签', color: 'secondary' });
  const tag = String(task.transfer_tag || '').trim();
  if (tag) badges.push({ text: `标签 ${tag}`, color: 'default' });
  return badges
}

async function loadTransferStatus(request) {
  const recordRequest = beginRecordRequest(['transfer']);
  recordStates.transfer.loading = true;
  recordStates.transfer.error = '';
  try {
    const resp = await getApi(`transfer_status?page=${transferPage.value}&page_size=${transferPageSize.value}&result_filter=${transferResultFilter.value}`, { feedback: 'silent' });
    if (!isCurrentPageRequest(request) || !isCurrentRecordRequest(recordRequest, 'transfer')) return
    if (!resp?.status) throw new Error(resp?.msg || '转移记录加载失败')
    transferStatus.value = resp.status;
    transferPage.value = resp.status.page || transferPage.value;
    recordStates.transfer.loaded = true;
  } catch (e) {
    reportRecordLoadError(recordRequest, e, '转移记录加载失败', 'transfer');
  } finally {
    if (isCurrentRecordRequest(recordRequest, 'transfer')) recordStates.transfer.loading = false;
  }
}

async function loadDownloaders(request) {
  const resp = await getApi('downloaders', { feedback: 'silent' }).catch(() => null);
  if (!isCurrentPageRequest(request) || !Array.isArray(resp)) return
  downloaderItems.value = resp;
}

async function loadModuleConfigSummary(request) {
  const resp = await getApi('module_config_summary', { feedback: 'silent' }).catch(() => null);
  if (!isCurrentPageRequest(request) || !resp) return
  moduleConfigSummary.value = resp;
}

async function loadUploadLimitStatus(request) {
  const resp = await getApi('upload_limit_status', { feedback: 'silent' }).catch(error => {
    console.error('上传限速状态刷新失败，保留总览快照:', error);
    return null
  });
  if (!isCurrentPageRequest(request) || !resp) return
  if (resp?.code === 0 || resp?.service_status) {
    overview.value = { ...(overview.value || {}), upload_limit: resp };
  }
}

async function loadModuleStatuses(request) {
  await Promise.all([
    loadModuleConfigSummary(request),
    loadRenameStatus(request),
    loadHrStatus(request),
    loadAutoremoveStatus(request),
    loadFailcleanStatus(request),
    loadSiteTagStatus(request),
    loadDownloaders(request),
  ]);
}

async function loadHistory(request) {
  recordStates.history.loading = true;
  recordStates.history.error = '';
  try {
    const resp = await getApi(`rename_history?page=${page.value}&page_size=${pageSize.value}&result_filter=${historyResultFilter.value}`);
    if (!isCurrentRecordRequest(request, 'history')) return
    records.value = Array.isArray(resp?.items) ? resp.items : [];
    total.value = resp?.total || 0;
    recordStates.history.loaded = true;
  } catch (e) {
    reportRecordLoadError(request, e, '命名历史加载失败', 'history');
  } finally {
    if (isCurrentRecordRequest(request, 'history')) { paging.value = false; recordStates.history.loading = false; }
  }
}

async function loadArchive(request) {
  recordStates.archive.loading = true;
  recordStates.archive.error = '';
  try {
    let resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${archivePageSize.value}`);
    if (!isCurrentRecordRequest(request, 'archive')) return
    const lastPage = Math.max(1, Math.ceil((resp?.total || 0) / archivePageSize.value));
    if (archivePage.value > lastPage) {
      archivePage.value = lastPage;
      resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${archivePageSize.value}`);
    }
    if (!isCurrentRecordRequest(request, 'archive')) return
    archiveRecords.value = Array.isArray(resp?.items) ? resp.items : [];
    archiveTotal.value = resp?.total || 0;
    recordStates.archive.loaded = true;
  } catch (e) {
    reportRecordLoadError(request, e, '归档加载失败', 'archive');
  } finally {
    if (isCurrentRecordRequest(request, 'archive')) { paging.value = false; recordStates.archive.loading = false; }
  }
}

async function loadDiagnostics(request) {
  const diagnosticsRequest = beginDiagnosticsRequest();
  try {
    const resp = await getApi(`diagnostics?detail_limit=${detailLimit.value}`);
    if (!isCurrentPageRequest(request) || !isCurrentDiagnosticsRequest(diagnosticsRequest)) return
    if (resp?.code && resp.code !== 0) {
      error.value = resp?.msg || '诊断失败';
      return
    }
    diagnostics.value = resp;
  } catch (e) {
    if (!isCurrentDiagnosticsRequest(diagnosticsRequest)) return
    reportLoadError(request, e, '诊断失败');
  }
}

// 明细条数只影响诊断读取：变化时只刷新诊断，不重载业务状态、不写配置。
watch(detailLimit, () => {
  const request = { revision: pageRequestRevision, pluginId: props.pluginId, tab: activeTab.value };
  void loadDiagnostics(request);
});

/** 数据清理白名单口径与后端 _cleanup_actions 一致；只清插件自身历史/统计。 */
const CLEANUP_TARGETS = {
  rename_archive: {
    label: '重命名归档',
    detail: '连续失败后归档的补刀记录',
    consequence: '归档状态一并删除，对应种子可重新识别与补刀。',
  },
  rename_history: {
    label: '重命名历史',
    detail: '已记录的成功与失败命名记录',
    consequence: '清理后无法再按记录恢复原名或补刀。',
  },
  transfer_stats: {
    label: '转移统计',
    detail: '转移成功计数与跳过计数',
    consequence: '运行总览的转移统计归零，不影响下载器任务。',
  },
  autoremove_state: {
    label: '删种执行记录',
    detail: '自动删种最近一次执行结果',
    consequence: '只清插件记录，下载器中的种子保持不变。',
  },
  failclean_state: {
    label: '失败清理记录',
    detail: '失败清理最近一次执行结果',
    consequence: '只清最近一次执行结果，累计清理统计保留；实际文件与种子保持不变。',
  },
};
const cleanupTargetKey = ref('');
const cleanupConfirmDialog = ref(false);
const cleanupRunning = ref(false);
const cleanupCounts = computed(() => diagnostics.value?.cleanup_data || {});
const cleanupTarget = computed(() => CLEANUP_TARGETS[cleanupTargetKey.value] || null);
const cleanupTargetCount = computed(() => cleanupCounts.value[cleanupTargetKey.value] || 0);


const moduleDetails = computed(() => diagnostics.value?.module_details || {});

function detailValue(value) {
  return value == null || value === '' ? '—' : value
}
function moduleDetail(key) {
  const detail = moduleDetails.value[key];
  const rows = Array.isArray(detail?.rows) ? detail.rows : [];
  const items = Array.isArray(detail?.items) ? detail.items : [];
  const totalValue = Number(detail?.total);
  const limitValue = Number(detail?.limit);
  const total = Number.isFinite(totalValue) && totalValue >= 0 ? totalValue : items.length;
  return {
    rows: rows.map(row => ({ ...row, value: detailValue(row.value) })),
    items,
    error: detail?.error || '',
    total,
    limit: Number.isFinite(limitValue) && limitValue > 0 ? limitValue : detailLimit.value,
    // 旧响应没有 total/truncated：按当前条目数处理，不虚构被截断
    truncated: typeof detail?.truncated === 'boolean' ? detail.truncated : total > items.length,
  }
}
function openCleanupDialog(key) {
  if (!CLEANUP_TARGETS[key]) return
  cleanupTargetKey.value = key;
  cleanupConfirmDialog.value = true;
}

/**
 * 总览卡「查看记录」落点：只切页签 + 各页签原有的 GET 刷新 + 展开 + 滚动定位，
 * 不触发扫描 / 预览 / 补全 / 重新分配等写操作。
 */
const MODULE_RECORD_VIEWS = {
  transfer: { tab: 'transfer', anchor: '[data-record-block="transfer-tasks"]' },
  rename: { tab: 'history', anchor: '[data-record-block="rename-history"]' },
  hr: { tab: 'hr', anchor: '[data-record-block="hr-tasks"]' },
  autoremove: { tab: 'autoremove', anchor: '[data-record-block="autoremove-preview"]' },
  // 失败清理没有逐条记录，只切页签看最近一次执行结果
  failclean: { tab: 'failclean', anchor: '' },
  tag: { tab: 'sitetag', anchor: '[data-record-block="tag-cleanup"]' },
  upload_limit: { tab: 'upload', anchor: '[data-runtime-section="upload-limit"]' },
};

function moduleRecordView(key) {
  return MODULE_RECORD_VIEWS[key] || null
}

function scrollToModuleAnchor(anchor) {
  // 测试 harness 的 document 桩没有 querySelector：没有真实 DOM 时直接跳过定位
  if (!anchor || typeof document === 'undefined' || typeof document.querySelector !== 'function') return
  const node = document.querySelector(anchor);
  if (!node || typeof node.scrollIntoView !== 'function') return
  node.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

async function openModuleRecords(key) {
  const view = moduleRecordView(key);
  if (!view || typeof view.tab !== 'string' || !view.tab) return
  await selectTab(view.tab);
  // 页签切换后目标块才挂载，必须等一次渲染再定位
  await nextTick();
  scrollToModuleAnchor(view.anchor);
}

async function confirmCleanupData() {
  const key = cleanupTargetKey.value;
  if (!CLEANUP_TARGETS[key] || cleanupRunning.value) return
  cleanupRunning.value = true;
  try {
    const resp = await postJsonApi('cleanup_module_data', { module: key });
    applyActionResp(resp, '清理完成');
    cleanupConfirmDialog.value = false;
    const request = beginPageRequest();
    await loadDiagnostics(request);
    if (key === 'rename_archive' || key === 'rename_history') {
      // 记录变少后可能停在已不存在的空页：先回第一页再刷新
      page.value = 1;
      archivePage.value = 1;
      const recordRequest = beginRecordRequest();
      await Promise.all([loadHistory(recordRequest), loadArchive(recordRequest)]);
    } else if (key === 'transfer_stats') {
      await loadOverview(request, { silent: true });
    } else if (key === 'autoremove_state') {
      // 记录已清空：同步清掉旧预览，避免「上轮候选」残留
      autoremovePreview.value = null;
      await loadAutoremoveStatus(request);
    } else if (key === 'failclean_state') {
      await loadFailcleanStatus(request);
    }
  } catch (e) {
    applyActionError(e, '清理完成');
  } finally {
    cleanupRunning.value = false;
  }
}

async function loadOverviewTab({ silent = false } = {}) {
  const request = beginPageRequest();
  if (!silent) {
    loading.value = true;
    error.value = '';
  }
  try {
    await Promise.all([
      loadOverview(request, { silent }),
      loadModuleStatuses(request),
      // 模块卡「运行明细」依赖诊断数据：首次进入总览就取一次，不必先打开诊断页
      loadDiagnostics(request),
    ]);
  } finally {
    if (isCurrentPageRequest(request)) loading.value = false;
  }
}

async function loadHistoryTab(request) {
  const recordRequest = beginRecordRequest();
  await Promise.all([
    loadHistory(recordRequest),
    loadArchive(recordRequest),
    loadRenameStatus(request),
  ]);
}

async function refreshActive() {
  if (activeTab.value === 'overview') return loadOverviewTab()
  const request = beginPageRequest();
  loading.value = true;
  error.value = '';
  try {
    const tasks = [];
    if (activeTab.value === 'history') {
      tasks.push(loadHistoryTab(request));
    } else if (activeTab.value === 'hr') {
      tasks.push(loadHrStatus(request));
    } else if (activeTab.value === 'autoremove') {
      tasks.push(loadAutoremoveStatus(request));
    } else if (activeTab.value === 'failclean') {
      tasks.push(loadFailcleanStatus(request));
    } else if (activeTab.value === 'transfer') {
      tasks.push(loadTransferStatus(request));
    } else if (activeTab.value === 'sitetag') {
      tasks.push(loadSiteTagStatus(request), loadDownloaders(request));
    } else if (activeTab.value === 'upload' || activeTab.value === 'diagnostics') {
      tasks.push(loadUploadLimitStatus(request));
    }
    // 模块页签同样展示模块卡与运行明细：每轮刷新固定取一次诊断
    tasks.push(loadModuleConfigSummary(request));
    tasks.push(loadDiagnostics(request));
    await Promise.all(tasks);
  } finally {
    if (isCurrentPageRequest(request)) loading.value = false;
  }
}

async function selectTab(key) {
  stopOverviewAutoRefresh();
  activeTab.value = key;
  if (tabModuleKeys[key]) expandedModules[tabModuleKeys[key]] = true;
  await refreshActive();
  syncOverviewAutoRefresh();
}

async function refreshLive() {
  if (!isOverviewVisible() || overviewRefreshPending || loading.value) return
  overviewRefreshPending = true;
  try {
    await loadOverviewTab({ silent: true });
  } finally {
    overviewRefreshPending = false;
  }
}

function isOverviewVisible() {
  return activeTab.value === 'overview' && document.visibilityState === 'visible'
}

function stopOverviewAutoRefresh() {
  if (!overviewRefreshTimer) return
  window.clearInterval(overviewRefreshTimer);
  overviewRefreshTimer = null;
}

function syncOverviewAutoRefresh({ refresh = false } = {}) {
  stopOverviewAutoRefresh();
  if (!isOverviewVisible()) return
  if (refresh) void refreshLive();
  overviewRefreshTimer = window.setInterval(() => { void refreshLive(); }, OVERVIEW_REFRESH_INTERVAL_MS);
}

function handleVisibilityChange() {
  syncOverviewAutoRefresh({ refresh: true });
}

async function runModuleAction(key, handler, fallback) {
  actionMsg.value = '';
  actionLevel.value = '';
  moduleRunning.value = key;
  try {
    const resp = await handler();
    applyActionResp(resp, fallback);
    return resp
  } catch (e) {
    applyActionError(e, fallback);
    return null
  } finally {
    moduleRunning.value = '';
  }
}

async function doTransferRun() {
  const resp = await runModuleAction('transfer-run', () => postApi('transfer_run', {}), '转移做种已触发');
  if (resp?.code !== 1) await refreshActive();
}

function confirmTransferRun() {
  transferRunDialog.value = false;
  void doTransferRun();
}

async function doHrScan() {
  const resp = await runModuleAction('hr-scan', () => postApi('hr_scan', {}), 'H&R 发现完成');
  if (resp?.code !== 1) await refreshActive();
}

async function doHrCheck() {
  const resp = await runModuleAction('hr-check', () => postApi('hr_check', {}), 'H&R 检查完成');
  if (resp?.code !== 1) await refreshActive();
}

function askHrClear(kind, task = null) {
  hrClearTarget.value = task;
  hrClearKind.value = kind;
  hrClearDialog.value = true;
}

async function confirmHrClear() {
  const kind = hrClearKind.value;
  const target = hrClearTarget.value;
  hrClearDialog.value = false;
  if (!kind) return
  actionMsg.value = '';
  actionLevel.value = '';
  hrClearing.value = true;
  hrClearKey.value = target ? `${target.downloader_id}-${target.torrent_hash}` : '';
  try {
    const payload = kind === 'task'
      ? { downloader_id: target?.downloader_id || '', torrent_hash: target?.torrent_hash || '' }
      : {};
    const resp = await postApi(`hr_clear_${kind}`, payload);
    applyActionResp(resp, '清除完成');
    if (resp?.code !== 1) await refreshActive();
  } catch (e) {
    applyActionError(e, '清除完成');
  } finally {
    hrClearing.value = false;
    hrClearKey.value = '';
    hrClearTarget.value = null;
  }
}

async function doAutoremoveRun() {
  const resp = await runModuleAction('autoremove-run', () => postApi('autoremove_run', {}), '自动删种执行完成');
  if (resp?.code !== 1) await refreshActive();
}

async function doAutoremovePreview() {
  const resp = await runModuleAction('autoremove-preview', async () => {
    const previewResp = await postApi('autoremove_preview', {});
    autoremovePreview.value = previewResp?.result || null;
    if (previewResp?.code !== 1) {
      const hits = Array.isArray(previewResp?.result?.candidate_list) ? previewResp.result.candidate_list.length : 0;
      return { ...previewResp, msg: `预览命中 ${hits} 个候选，未执行任何下载器写操作` }
    }
    return previewResp
  }, '候选预览完成');
  if (resp?.code !== 1) await refreshActive();
}

async function doFailcleanScan() {
  const resp = await runModuleAction('failclean-scan', () => postApi('failclean_scan', {}), '残留巡检完成');
  if (resp?.code !== 1) await refreshActive();
}

async function doRetryRenames() {
  const resp = await runModuleAction('rename-retry', () => postApi('retry_renames', {}), '补刀已在后台开始');
  if (resp?.code !== 1) await refreshActive();
}

async function doRenameScan() {
  const resp = await runModuleAction('rename-scan', () => postApi('rename_scan', {}), '扫描已在后台开始');
  if (resp?.code !== 1) await refreshActive();
}

async function doTagComplement() {
  const resp = await runModuleAction('tag-complement', () => postApi('tag_complement', {}), '站点标签补全完成');
  if (resp?.code !== 1) await refreshActive();
}

async function doUploadReallocate() {
  const resp = await runModuleAction('upload-reallocate', () => postJsonApi('upload_limit_reallocate', {}), '上传额度已重新分配');
  if (resp?.code !== 1) await refreshActive();
}

async function doUploadScanSites() {
  // 只发下载器列表：后端以已持久化站点策略为基底补充扫描到的站点名（见 handlers.api_upload_limit_site_tags）
  const downloaders = [...(uploadLimit.value.selected_downloaders || [])];
  const resp = await runModuleAction('upload-scan-sites', () => postJsonApi('upload_limit_site_tags', { downloaders }), '站点标签扫描完成');
  if (resp?.code !== 1) await refreshActive();
}

async function doUploadClearRules() {
  const resp = await runModuleAction('upload-clear-rules', () => postJsonApi('upload_limit_site_rules_update', { rules: {} }), '站点策略已清空');
  if (resp?.code !== 1) await refreshActive();
}

async function doRecovery(hash, downloader = '') {
  actionMsg.value = '';
  actionLevel.value = '';
  try {
    const resp = await postApi('recovery_torrent', { hash, downloader });
    applyActionResp(resp, '恢复成功');
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    applyActionError(e, '恢复成功');
  }
}

async function doDelete(hash, downloader = '') {
  actionMsg.value = '';
  actionLevel.value = '';
  try {
    const resp = await postApi('delete_rename_history', { hash, downloader });
    applyActionResp(resp, '已删除');
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    applyActionError(e, '已删除');
  }
}

async function doRetryRename(hash, downloader = '') {
  if (!hash || retryingHash.value) return
  actionMsg.value = '';
  actionLevel.value = '';
  retryingHash.value = hash;
  try {
    const resp = await postApi('retry_rename', { hash, downloader });
    applyActionResp(resp, '补刀完成');
  } catch (e) {
    applyActionError(e, '补刀完成');
  } finally {
    await reloadRecords();
    retryingHash.value = '';
  }
}

async function restoreArchive(hash, downloader = '') {
  actionMsg.value = '';
  actionLevel.value = '';
  restoringHash.value = hash;
  try {
    const resp = await postApi('restore_rename_archive', { hash, downloader });
    applyActionResp(resp, '已恢复');
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    applyActionError(e, '已恢复');
  } finally {
    restoringHash.value = '';
  }
}

function handleHistoryAction(action, row) {
  if (action === 'retry') return doRetryRename(row.hash, row.downloader)
  if (action === 'recover') return doRecovery(row.hash, row.downloader)
  if (action === 'delete') return doDelete(row.hash, row.downloader)
}
function handleArchiveAction(action, row) {
  if (action === 'retry') return doRetryRename(row.hash, row.downloader)
  if (action === 'restore') return restoreArchive(row.hash, row.downloader)
  if (action === 'delete' && window.confirm('确认删除“' + (row.name || row.hash) + '”的失败归档记录？仅清理记录，不删除种子或数据。')) return deleteArchive(row.hash, row.downloader)
}
async function deleteArchive(hash, downloader = '') {
  actionMsg.value = '';
  actionLevel.value = '';
  deletingHash.value = hash;
  try {
    const resp = await postApi('delete_rename_archive', { hash, downloader });
    applyActionResp(resp, '已删除');
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    applyActionError(e, '已删除');
  } finally {
    deletingHash.value = '';
  }
}

async function reloadRecords() {
  const request = beginRecordRequest();
  await Promise.all([loadHistory(request), loadArchive(request)]);
}

const qbDownloaderItems = computed(() => downloaderItems.value.filter(item => item.type === 'qbittorrent'));
const cleanupGroups = computed(() => cleanupScan.value?.downloaders || []);
computed(() => cleanupScan.value?.auto_removed?.length || 0);
const cleanupRemovals = computed(() => {
  const removals = [];
  for (const group of cleanupGroups.value) {
    for (const item of group.tags || []) {
      if (!cleanupKeep[tagSelectionKey(group.name, item.tag)]) {
        removals.push({ downloader: group.name, tag: item.tag, hashes: [...(item.hashes || [])] });
      }
    }
  }
  return removals
});
const cleanupRemovalAssociations = computed(() => cleanupRemovals.value.reduce((sum, item) => sum + item.hashes.length, 0));

function tagSelectionKey(downloader, tag) {
  return `${downloader}\u0000${tag}`
}

function resetCleanupKeep(groups) {
  Object.keys(cleanupKeep).forEach(key => delete cleanupKeep[key]);
  for (const group of groups || []) {
    for (const item of group.tags || []) {
      cleanupKeep[tagSelectionKey(group.name, item.tag)] = item.kind !== 'legacy_candidate';
    }
  }
}

async function scanCleanupTags() {
  cleanupMessage.value = '';
  if (!cleanupDownloaders.value.length) {
    cleanupStatus.value = 'warning';
    cleanupMessage.value = '请先选择下载器';
    return
  }
  cleanupScanning.value = true;
  try {
    const response = await postJsonApi('tag_cleanup_scan', { downloaders: cleanupDownloaders.value });
    cleanupScan.value = response || null;
    resetCleanupKeep(response?.downloaders || []);
    const errorCount = response?.errors?.length || 0;
    cleanupStatus.value = response?.code === 0 ? (errorCount ? 'warning' : 'success') : 'error';
    cleanupMessage.value = response?.code === 0
      ? `扫描完成 · 自动清理 ${response?.auto_removed?.length || 0} 个临时标签`
      : (response?.msg || '扫描失败');
  } catch (error) {
    cleanupStatus.value = 'error';
    cleanupMessage.value = error?.message || '扫描失败';
  } finally {
    cleanupScanning.value = false;
  }
}

async function executeCleanupTags() {
  cleanupExecuting.value = true;
  let response = null;
  try {
    response = await postJsonApi('tag_cleanup_execute', { removals: cleanupRemovals.value });
  } catch (error) {
    if (error?.code === 2) {
      // 部分失败（success=false 抛错）：按 warning 收尾，弹窗照常关闭并刷新列表
      response = { code: 2, msg: error.message };
    } else {
      cleanupStatus.value = 'error';
      cleanupMessage.value = error?.message || '清理失败';
      cleanupExecuting.value = false;
      return
    }
  }
  try {
    cleanupDialog.value = false;
    await scanCleanupTags();
    cleanupStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error');
    cleanupMessage.value = response?.msg || '清理完成';
  } finally {
    cleanupExecuting.value = false;
  }
}

watch(
  () => `${uploadLimit.value.service_status || ''}|${(uploadLimit.value.errors || []).join('|')}|${uploadLimitDownloaderRows.value.filter(item => item.error).map(item => item.id).join('|')}`,
  value => {
    if (value.startsWith('degraded|') || value.startsWith('error|')) expandedModules.upload_limit = true;
  },
);

// Page owns projections, filters and paging; shared components stay presentation-only.
const localPages = reactive({ hr: 1, pending: 1, candidates: 1, attention: 1, diagnostics: 1 });
const localSizes = reactive({ hr: 20, pending: 20, candidates: 20, attention: 20, diagnostics: 20 });
function visibleRows(key, rows) {
  const last = Math.max(1, Math.ceil(rows.length / localSizes[key]));
  const current = Math.min(localPages[key], last);
  return rows.slice((current - 1) * localSizes[key], current * localSizes[key])
}
function setLocalSize(key, size) { localSizes[key] = size; localPages[key] = 1; }
const autoRunConfirm = ref(false);
async function runDiagnostics() {
  const request = beginPageRequest();
  loading.value = true;
  error.value = '';
  try {
    const result = await getApi(`diagnostics?detail_limit=${detailLimit.value}&run=true`);
    if (!isCurrentPageRequest(request)) return
    if (result?.code && result.code !== 0) throw new Error(result.msg || '诊断失败')
    diagnostics.value = result;
  } catch (e) { reportLoadError(request, e, '诊断失败'); }
  finally { if (isCurrentPageRequest(request)) loading.value = false; }
}
const presenceFilter = ref('all');
const visibleHrRows = computed(() => hrTaskRows.value.filter(task => presenceFilter.value === 'all'
  || (typeof task.deleted === 'boolean' && (presenceFilter.value === 'missing' ? task.deleted : !task.deleted))));
watch([hrStatusFilter, presenceFilter], () => { localPages.hr = 1; });
const rowIdentity = row => `${row.downloader_id || row.source_downloader || ''}:${row.torrent_hash || row.source_hash || row.hash || row.name || row.id}`;
const columnsOf = labels => labels.map(([key, label]) => ({ key, label, ...(['name', 'original_name', 'after_name', 'reason', 'detail', 'message'].includes(key) ? { lines: 2 } : {}) }));
const recordColumns = {
  tasks: columnsOf([['name', '名称'], ['from_downloader', '源下载器'], ['to_downloader', '目的下载器'], ['mapping', '数据映射'], ['filters', '筛选条件'], ['settings', '设置']]),
  pending: columnsOf([['name', '种子'], ['route', '源 → 目的'], ['phase', '阶段'], ['wait', '已等待'], ['options', '选项']]),
  transfer: columnsOf([['name', '种子'], ['route', '源 → 目的'], ['phase', '结果'], ['updated', '更新时间']]),
  history: columnsOf([['time', '时间'], ['downloader', '下载器'], ['original_name', '原始名称'], ['after_name', '命名后'], ['success', '结果']]),
  archive: columnsOf([['archived_at', '归档时间'], ['downloader', '下载器'], ['name', '名称'], ['category', '分类'], ['fail_count', '失败次数'], ['reason', '原因']]),
  hr: columnsOf([['name', '种子'], ['downloader_id', '下载器'], ['site', '站点'], ['status', '考核状态'], ['deleted', '存在状态'], ['remain_seconds', '剩余时长'], ['deadline', '截止日期'], ['progress', '做种进度']]),
  candidates: columnsOf([['downloader_id', '下载器'], ['name', '名称'], ['site', '站点'], ['size_text', '体积'], ['ratio', '分享率'], ['seeding_hours', '做种时长'], ['reason', '命中原因']]),
  autoHistory: columnsOf([['time', '执行时间'], ['downloader', '下载器'], ['name', '名称'], ['action', '执行动作'], ['result', '结果'], ['reason', '原因']]),
  failHistory: columnsOf([['time', '时间'], ['downloader', '下载器'], ['name', '名称'], ['type', '清理类型'], ['source', '触发来源'], ['action', '动作'], ['result', '结果']]),
  tagHistory: columnsOf([['time', '时间'], ['downloader', '下载器'], ['name', '种子名称'], ['site', '站点'], ['tags', '标签变更'], ['category', '分类变更'], ['result', '结果']]),
  cleanupHistory: columnsOf([['time', '时间'], ['scope', '清理范围'], ['tags', '清理标签数'], ['success', '成功'], ['failed', '失败'], ['result', '结果']]),
  uploadHistory: columnsOf([['time', '时间'], ['downloader', '下载器'], ['target', '作用对象'], ['action', '动作'], ['before', '调整前'], ['after', '调整后'], ['result', '结果']]),
  sites: columnsOf([['name', '站点'], ['torrent_count', '受管种子'], ['uploading_torrents', '上传中'], ['upload_rate_bps', '当前上传'], ['allocated_kib', '已分配额度'], ['state', '状态']]),
  diagnostics: columnsOf([['name', '检查项'], ['module', '所属模块'], ['stateLabel', '状态'], ['message', '检查结果']]),
  attention: columnsOf([['level', '级别'], ['module', '模块'], ['detail', '问题']]),
};
const currentModule = computed(() => tabModuleKeys[activeTab.value]);
const currentHeader = computed(() => moduleHeaders.value[currentModule.value]);
const settings = () => emit('switch');
const moduleActions = computed(() => {
  const card = moduleCards.value.find(item => item.key === currentModule.value);
  if (!card) return []
  if (card.key === 'rename') return [{ key: 'rename-scan', label: '扫描重命名', run: doRenameScan }]
  if (card.key === 'autoremove') return card.actions.filter(action => action.key === 'autoremove-preview')
  if (card.key === 'upload_limit') return card.actions.filter(action => action.key === 'upload-reallocate')
  return card.actions
});
const enabledValue = value => typeof value === 'boolean' ? (value ? '开启' : '关闭') : null;
const configField = (key, label, value, options = {}) => ({ key, label, value, ...options,
  color: options.color || (['观察模式', '跳过校验'].includes(value) || (['verify', 'guard'].includes(key) && value === '开启') ? 'warning' :
    value === '开启' || value === '正常执行' ? 'primary' : 'default'),
});
const summaryValue = key => {
  const fields = moduleConfigSummary.value?.modules?.[currentModule.value]?.fields;
  if (!Array.isArray(fields)) return null
  const item = fields.find(f => f.key === key);
  return item ? item.value : null
};
const summaryFields = computed(() => {
  const config = diagnostics.value?.config || overview.value?.config || {};
  const mode = currentHeader.value?.observing ? '观察模式' : (currentHeader.value?.enabled ? '正常执行' : null);
  const field = configField;
  switch (currentModule.value) {
    case 'transfer': return [field('event', '入列触发', summaryValue('event')), field('fallback', '定时兜底', enabledValue(config.transfer_fallback_enabled), { badge: true }), field('start', '自动开始', enabledValue(config.seed_autostart), { badge: true }), field('verify', '跳过校验', enabledValue(config.seed_skipverify), { badge: true }), field('interval', '检查间隔', summaryValue('interval'))]
    case 'rename': return [field('event', '入列触发', summaryValue('event')), field('cron', '定时补查及周期', summaryValue('cron')), field('movie', '电影模板', summaryValue('movie'), { long: true }), field('tv', '剧集模板', summaryValue('tv'), { long: true })]
    case 'hr': return [field('downloaders', '下载器范围', summaryValue('downloaders')), field('sites', '站点范围', summaryValue('sites')), field('rules', '规则来源', summaryValue('rules')), field('interval', '检查周期', summaryValue('interval')), field('guard', '删除保护', enabledValue(hrSummary.value.protection_enabled), { badge: true })]
    case 'autoremove': return [field('mode', '运行模式', mode, { badge: true }), field('action', '执行动作', ({ pause: '暂停任务', delete: '删除任务', deletefile: '删除任务及文件' })[autoremoveStatus.value.action]), field('downloaders', '下载器范围', summaryValue('downloaders')), field('rules', '命中规则', summaryValue('rules')), field('cron', '执行周期', summaryValue('cron')), field('guard', 'H&R保护', enabledValue(autoremoveStatus.value.guard_enabled), { badge: true })]
    case 'failclean': return [field('scope', '清理范围', summaryValue('scope')), field('event', '事件触发', '整理失败事件（固有行为）'), field('cron', '定时巡检及周期', summaryValue('cron')), field('action', '清理动作', summaryValue('action'))]
    case 'tag': return [field('mode', '运行模式', mode, { badge: true }), field('downloaders', '下载器范围', summaryValue('downloaders')), field('site', '站点标签', summaryValue('site')), field('media', '媒体标签', summaryValue('media')), field('category', '下载分类', summaryValue('category')), field('cron', '执行周期', summaryValue('cron'))]
    case 'upload_limit': return [field('mode', '运行模式', uploadLimitStatus.value.label, { badge: true, color: uploadLimitStatus.value.color }), field('downloaders', '下载器范围', summaryValue('downloaders')), field('global', '全局限速', summaryValue('global')), field('sites', '站点限速', summaryValue('sites')), field('dynamic', '动态调速', summaryValue('dynamic')), field('interval', '调整周期', summaryValue('interval'))]
    default: return []
  }
});
const sevenCards = computed(() => moduleCards.value.filter(card => card.key !== 'seed'));
const overviewStats = computed(() => {
  if (!overview.value) return ['已启用模块', '正在执行', '观察模式', '异常模块'].map(label => headerMetric(label))
  const headers = Object.values(moduleHeaders.value);
  return [headerMetric('已启用模块', headers.filter(item => item.enabled).length), headerMetric('正在执行', headers.filter(item => item.running).length), headerMetric('观察模式', headers.filter(item => item.observing).length), headerMetric('异常模块', headers.filter(item => item.fault).length)]
});
const attentionModuleFilter = ref('all');
const attentionRows = computed(() => overviewAttentionItems.value.map((item, index) => ({ ...item, id: index,
  level: item.color === 'error' ? '异常' : '关注', module: moduleHeaders.value[item.target]?.title || item.target || '插件',
})).filter(item => attentionModuleFilter.value === 'all' || item.target === attentionModuleFilter.value));
const moduleFilterItems = computed(() => [{ title: '全部模块', value: 'all' }, ...sevenCards.value.map(card => ({ title: moduleHeaders.value[card.key].title, value: card.key }))]);
const diagnosticModuleFilter = ref('all');
const diagnosticStateFilter = ref('all');
const selectedDiagnostic = ref(null);
const diagnosticModule = name => {
  if (/源下载器|目标下载器|种子文件|转移/.test(name)) return 'transfer'
  if (/重命名|补刀|命名/.test(name)) return 'rename'
  if (/H&R/.test(name)) return 'hr'
  if (/自动删种/.test(name)) return 'autoremove'
  if (/失败|同步删除/.test(name)) return 'failclean'
  if (/标签|分类/.test(name)) return 'tag'
  if (/上传|限速/.test(name)) return 'upload_limit'
  return 'plugin'
};
const diagnosticRows = computed(() => (diagnostics.value?.checks || []).map((item, index) => {
  const name = item.label || item.name || '未命名检查';
  const moduleKey = item.target || item.module || diagnosticModule(name);
  const state = item.status === 'off' ? 'off' : (item.state || ({ ok: 'normal', warn: 'attention', error: 'error' })[item.status] || 'pending');
  return { ...item, name, message: item.detail || item.message || '—', id: `${index}:${name}`, moduleKey, module: moduleHeaders.value[moduleKey]?.title || '插件', state,
    stateLabel: ({ normal: '正常', ok: '正常', attention: '需关注', warn: '需关注', error: '异常', pending: '未检查', unchecked: '未检查', off: '不适用' })[state] || '未检查' }
}));
const filteredDiagnosticRows = computed(() => diagnosticRows.value.filter(item => (diagnosticModuleFilter.value === 'all' || item.moduleKey === diagnosticModuleFilter.value)
  && (diagnosticStateFilter.value === 'all' || item.stateLabel === diagnosticStateFilter.value)));
const diagnosticStats = computed(() => ['正常', '需关注', '异常', '未检查'].map(label => headerMetric(label === '正常' ? '正常项' : label === '异常' ? '异常项' : label,
  diagnostics.value?.checked === false ? (label === '未检查' ? '尚未执行诊断' : '—') : diagnosticRows.value.filter(item => item.stateLabel === label).length)));
watch([diagnosticModuleFilter, diagnosticStateFilter], () => { localPages.diagnostics = 1; });
watch(diagnostics, () => { selectedDiagnostic.value = null; });
watch(attentionModuleFilter, () => { localPages.attention = 1; });
const uploadDownloaderFilter = ref('all');
const uploadSiteFilter = ref('');
const closedUploadGroups = reactive({});
const uploadGroups = computed(() => {
  const groups = uploadLimitDownloaderRows.value.filter(item => uploadDownloaderFilter.value === 'all' || String(item.id) === uploadDownloaderFilter.value)
    .map(item => ({ ...item, key: String(item.id), title: item.name || item.id, rows: [] }));
  const shared = [];
  for (const site of uploadLimitSiteRows.value) {
    if (uploadSiteFilter.value && !String(site.name || '').toLowerCase().includes(uploadSiteFilter.value.toLowerCase())) continue
    const owners = site.downloaders || [];
    const group = owners.length === 1 ? groups.find(item => item.key === String(owners[0])) : null;
    if (group) group.rows.push(site);
    else if (owners.length !== 1 && (uploadDownloaderFilter.value === 'all' || owners.map(String).includes(uploadDownloaderFilter.value))) shared.push(site);
  }
  if (shared.length) groups.push({ key: 'shared', title: '跨下载器站点汇总（当前接口未拆分）', rows: shared, aggregate: true });
  return groups
});
const cleanupPanel = ref(false);
const cleanupSearch = ref('');
const cleanupTagMatrix = computed(() => {
  const merged = new Map();
  for (const group of cleanupGroups.value) for (const item of group.tags || []) {
    if (!merged.has(item.tag)) merged.set(item.tag, { tag: item.tag, owners: [], keep: true });
    const tag = merged.get(item.tag);
    tag.owners.push(group.name);
    tag.keep = tag.keep && !!cleanupKeep[tagSelectionKey(group.name, item.tag)];
  }
  return [...merged.values()].sort((a, b) => a.tag.localeCompare(b.tag))
});
computed(() => cleanupTagMatrix.value.filter(item => item.tag.toLowerCase().includes(cleanupSearch.value.toLowerCase())));
async function openTagCleanup() {
  cleanupPanel.value = true;
  const request = { revision: pageRequestRevision, pluginId: props.pluginId, tab: activeTab.value };
  await loadDownloaders(request);
  if (isCurrentPageRequest(request)) cleanupDownloaders.value = qbDownloaderItems.value.map(item => item.name);
}
function pageRecordChange(kind, value) {
  if (kind === 'history') { page.value = value; void loadHistory(beginRecordRequest(['history'])); }
  if (kind === 'archive') { archivePage.value = value; void loadArchive(beginRecordRequest(['archive'])); }
  if (kind === 'transfer') { transferPage.value = value; void loadTransferStatus(beginPageRequest()); }
}
function sizeRecordChange(kind, value) {
  if (kind === 'history') pageSize.value = value;
  if (kind === 'archive') archivePageSize.value = value;
  if (kind === 'transfer') transferPageSize.value = value;
  // ModuleTable emits update:page(1) after size changes, issuing one request.
}
function resetHistoryFilter() { historyResultFilter.value = 'all'; pageRecordChange('history', 1); }
function resetTransferFilter() { transferResultFilter.value = 'all'; pageRecordChange('transfer', 1); }
function routeText(row) { return `${row.source_downloader || row.from_downloader || '—'} → ${row.target_downloader || row.to_downloader || '—'}` }
onMounted(() => {
  document.addEventListener('visibilitychange', handleVisibilityChange);
  void refreshActive();
  syncOverviewAutoRefresh();
});
onBeforeUnmount(() => {
  pageDisposed = true;
  pageRequestRevision++;
  stopOverviewAutoRefresh();
  document.removeEventListener('visibilitychange', handleVisibilityChange);
});

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VListItemSubtitle = _resolveComponent("VListItemSubtitle");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "dm-toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-download",
          class: "ms-3 me-2",
          color: "primary"
        }),
        _cache[52] || (_cache[52] = _createElementVNode("div", { class: "dm-title" }, "下载中心", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          color: "primary",
          size: "small",
          variant: "tonal",
          "prepend-icon": "mdi-refresh",
          class: "text-none me-2",
          onClick: _cache[0] || (_cache[0] = $event => (refreshActive())),
          loading: loading.value
        }, {
          default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
            _createTextVNode("刷新数据", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          color: "primary",
          size: "small",
          variant: "tonal",
          "prepend-icon": "mdi-cog-outline",
          class: "text-none",
          onClick: _cache[1] || (_cache[1] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[51] || (_cache[51] = [
            _createTextVNode("配置插件", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          size: "small",
          "aria-label": "关闭窗口",
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[2] || (_cache[2] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      _createElementVNode("nav", _hoisted_3, [
        _createVNode(_component_VList, {
          density: "compact",
          nav: "",
          class: "dm-side-list py-2"
        }, {
          default: _withCtx(() => [
            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
              return _createVNode(_component_VListItem, {
                key: tab.key,
                active: activeTab.value === tab.key,
                color: "primary",
                rounded: "lg",
                class: "dm-side-item",
                onClick: $event => (selectTab(tab.key))
              }, {
                prepend: _withCtx(() => [
                  _createVNode(_component_VIcon, {
                    icon: tab.icon
                  }, null, 8, ["icon"])
                ]),
                default: _withCtx(() => [
                  _createVNode(_component_VListItemTitle, null, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(tab.title), 1)
                    ]),
                    _: 2
                  }, 1024)
                ]),
                _: 2
              }, 1032, ["active", "onClick"])
            }), 64))
          ]),
          _: 1
        })
      ]),
      _createElementVNode("main", _hoisted_4, [
        (actionMsg.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 0,
              type: actionLevel.value === 'success' ? 'success' : (actionLevel.value === 'partial' ? 'warning' : 'error'),
              variant: "tonal",
              class: "mb-3",
              closable: "",
              density: "compact"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(actionMsg.value), 1)
              ]),
              _: 1
            }, 8, ["type"]))
          : _createCommentVNode("", true),
        (error.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 1,
              type: "error",
              variant: "tonal",
              class: "mb-3",
              density: "compact"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(error.value), 1)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (loading.value && !['history', 'transfer', 'hr', 'autoremove', 'failclean'].includes(activeTab.value))
          ? (_openBlock(), _createElementBlock("div", _hoisted_5, [
              _createVNode(_component_VProgressCircular, {
                indeterminate: "",
                color: "primary"
              })
            ]))
          : (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
              (activeTab.value === 'overview')
                ? (_openBlock(), _createElementBlock("section", _hoisted_6, [
                    _createElementVNode("div", _hoisted_7, [
                      _createVNode(ModuleHeader, {
                        title: "运行总览",
                        icon: _unref(MODULE_ICONS).overview,
                        "show-status": false,
                        enabled: ""
                      }, null, 8, ["icon"])
                    ]),
                    _createElementVNode("div", _hoisted_8, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewStats.value, (stat) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: stat.label
                        }, [
                          _createElementVNode("span", null, _toDisplayString(stat.label), 1),
                          _createElementVNode("strong", null, _toDisplayString(stat.value), 1)
                        ]))
                      }), 128))
                    ]),
                    _createElementVNode("div", _hoisted_9, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sevenCards.value, (card) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: card.key,
                          class: "dm-overview-card"
                        }, [
                          _createVNode(ModuleHeader, _mergeProps({ ref_for: true }, moduleHeaders.value[card.key], {
                            badges: moduleHeaders.value[card.key].badges.slice(0, 2)
                          }), null, 16, ["badges"]),
                          _createVNode(_component_VBtn, {
                            size: "small",
                            variant: "text",
                            "aria-label": '打开' + moduleHeaders.value[card.key].title,
                            icon: "mdi-arrow-top-right",
                            onClick: $event => (openModuleRecords(card.key))
                          }, null, 8, ["aria-label", "onClick"]),
                          _createElementVNode("p", _hoisted_10, "最近时间：" + _toDisplayString(moduleDetail(card.key).time || '当前接口未提供'), 1)
                        ]))
                      }), 128))
                    ]),
                    _createVNode(ModuleTable, {
                      title: "待处理事项",
                      columns: recordColumns.attention,
                      rows: visibleRows('attention', attentionRows.value),
                      total: attentionRows.value.length,
                      page: localPages.attention,
                      "page-size": localSizes.attention,
                      state: { empty: attentionModuleFilter.value === 'all' ? 'none' : 'filtered' },
                      "onUpdate:page": _cache[4] || (_cache[4] = $event => (localPages.attention = $event)),
                      "onUpdate:pageSize": _cache[5] || (_cache[5] = $event => (setLocalSize('attention', $event))),
                      onResetFilters: _cache[6] || (_cache[6] = $event => (attentionModuleFilter.value = 'all'))
                    }, {
                      filters: _withCtx(() => [
                        _createVNode(CompactSelect, {
                          modelValue: attentionModuleFilter.value,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((attentionModuleFilter).value = $event)),
                          items: moduleFilterItems.value,
                          label: "模块",
                          class: "dm-filter"
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      rowActions: _withCtx(({ row }) => [
                        _createVNode(RowActionMenu, {
                          label: row.name || row.title || '待处理项',
                          actions: [{key:'view',label:'查看',icon:'mdi-open-in-new'}],
                          onSelect: $event => (openModuleRecords(row.target))
                        }, null, 8, ["label", "onSelect"])
                      ]),
                      _: 1
                    }, 8, ["columns", "rows", "total", "page", "page-size", "state"])
                  ]))
                : _createCommentVNode("", true),
              (currentHeader.value)
                ? (_openBlock(), _createElementBlock("section", {
                    key: 1,
                    class: "dm-page-stack",
                    "data-page": currentModule.value
                  }, [
                    _createElementVNode("div", _hoisted_12, [
                      _createVNode(ModuleHeader, _normalizeProps(_guardReactiveProps(currentHeader.value)), null, 16),
                      _createElementVNode("div", _hoisted_13, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(moduleActions.value, (action) => {
                          return (_openBlock(), _createBlock(_component_VBtn, {
                            key: action.key,
                            size: "small",
                            variant: "tonal",
                            color: action.color || 'primary',
                            loading: moduleRunning.value === action.key,
                            disabled: moduleRunning.value !== '' || (action.key === 'rename-scan' && renameStatus.value.batch_running),
                            onClick: $event => (action.run())
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(action.label), 1)
                            ]),
                            _: 2
                          }, 1032, ["color", "loading", "disabled", "onClick"]))
                        }), 128)),
                        (currentModule.value === 'tag')
                          ? (_openBlock(), _createBlock(_component_VBtn, {
                              key: 0,
                              color: "primary",
                              size: "small",
                              variant: "tonal",
                              onClick: openTagCleanup
                            }, {
                              default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                                _createTextVNode("标签清理", -1)
                              ]))]),
                              _: 1
                            }))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _createVNode(ConfigSummary, {
                      fields: summaryFields.value,
                      onSettings: settings
                    }, null, 8, ["fields"]),
                    (activeTab.value === 'transfer')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                          _createVNode(ModuleTable, {
                            title: "任务配置",
                            "data-record-block": "transfer-tasks",
                            columns: recordColumns.tasks,
                            rows: transferTasks.value,
                            "row-key": "name",
                            pagination: false,
                            state: recordTableState('transfer', transferTasks.value),
                            onRetry: refreshActive
                          }, {
                            "cell-from_downloader": _withCtx(({ value }) => [
                              _createVNode(DownloaderBadge, { name: value }, null, 8, ["name"])
                            ]),
                            "cell-to_downloader": _withCtx(({ value }) => [
                              _createVNode(DownloaderBadge, { name: value }, null, 8, ["name"])
                            ]),
                            "cell-mapping": _withCtx(({ row }) => [
                              _createElementVNode("span", null, _toDisplayString(row.from_path || '—') + " → " + _toDisplayString(row.to_path || '—'), 1)
                            ]),
                            "cell-filters": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(transferFilterText(row)), 1)
                            ]),
                            "cell-settings": _withCtx(({ row }) => [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(transferSettingBadges(row), (badge) => {
                                return (_openBlock(), _createBlock(_component_VChip, {
                                  key: badge.text,
                                  color: badge.color,
                                  size: "x-small",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(badge.text), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"]))
                              }), 128)),
                              (!transferSettingBadges(row).length)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_14, "默认"))
                                : _createCommentVNode("", true)
                            ]),
                            rowActions: _withCtx(() => [
                              _createVNode(RowActionMenu, {
                                label: "转移任务",
                                actions: [{key:'settings',label:'设置',icon:'mdi-cog-outline'}],
                                onSelect: settings
                              })
                            ]),
                            _: 1
                          }, 8, ["columns", "rows", "state"]),
                          _createVNode(ModuleTable, {
                            title: "在途事务",
                            columns: recordColumns.pending,
                            rows: visibleRows('pending', transferPending.value),
                            total: transferPending.value.length,
                            "row-key": rowIdentity,
                            page: localPages.pending,
                            "page-size": localSizes.pending,
                            state: recordTableState('transfer', transferPending.value),
                            "onUpdate:page": _cache[7] || (_cache[7] = $event => (localPages.pending = $event)),
                            "onUpdate:pageSize": _cache[8] || (_cache[8] = $event => (setLocalSize('pending', $event))),
                            onRetry: refreshActive
                          }, {
                            "cell-name": _withCtx(({ row }) => [
                              _createElementVNode("span", {
                                title: transferSourceName(row)
                              }, _toDisplayString(transferPrimaryText(row)), 9, _hoisted_15),
                              _createElementVNode("div", _hoisted_16, _toDisplayString(transferSecondaryText(row)), 1)
                            ]),
                            "cell-route": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(routeText(row)), 1)
                            ]),
                            "cell-phase": _withCtx(({ row }) => [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: transferPhaseColor(row.phase),
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(transferPhaseText(row.phase)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            "cell-wait": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(row.waited_minutes != null ? formatDuration(Number(row.waited_minutes) * 60) : '当前接口未提供'), 1)
                            ]),
                            "cell-options": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(row.delete_source === true ? '含删源' : row.delete_source === false ? '保留源' : '见详情'), 1)
                            ]),
                            expand: _withCtx(({ row }) => [
                              _createVNode(RecordDetails, { record: row }, null, 8, ["record"])
                            ]),
                            _: 1
                          }, 8, ["columns", "rows", "total", "page", "page-size", "state"]),
                          _createVNode(ModuleTable, {
                            title: "最近记录",
                            "data-record-block": "transfer-records",
                            "data-record-state": "transfer",
                            columns: recordColumns.transfer,
                            rows: transferRecords.value,
                            total: transferStatus.value.total || 0,
                            "row-key": rowIdentity,
                            page: transferPage.value,
                            "page-size": transferPageSize.value,
                            state: recordTableState('transfer', transferRecords.value, transferResultFilter.value === 'all' ? 'none' : 'filtered'),
                            onRetry: refreshActive,
                            onResetFilters: resetTransferFilter,
                            "onUpdate:page": _cache[11] || (_cache[11] = $event => (pageRecordChange('transfer', $event))),
                            "onUpdate:pageSize": _cache[12] || (_cache[12] = $event => (sizeRecordChange('transfer', $event)))
                          }, {
                            filters: _withCtx(() => [
                              _createVNode(CompactSelect, {
                                modelValue: transferResultFilter.value,
                                "onUpdate:modelValue": [
                                  _cache[9] || (_cache[9] = $event => ((transferResultFilter).value = $event)),
                                  _cache[10] || (_cache[10] = $event => (pageRecordChange('transfer', 1)))
                                ],
                                items: [{title:'全部结果',value:'all'},{title:'成功',value:'success'},{title:'失败',value:'failed'},{title:'源端待处理',value:'source_pending'},{title:'回滚',value:'rollback'}],
                                label: "结果",
                                class: "dm-filter"
                              }, null, 8, ["modelValue"])
                            ]),
                            "cell-name": _withCtx(({ row }) => [
                              _createElementVNode("span", {
                                title: transferSourceName(row)
                              }, _toDisplayString(transferPrimaryText(row)), 9, _hoisted_17),
                              _createElementVNode("div", _hoisted_18, _toDisplayString(transferSecondaryText(row)), 1)
                            ]),
                            "cell-route": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(routeText(row)), 1)
                            ]),
                            "cell-phase": _withCtx(({ row }) => [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: transferPhaseColor(row.phase),
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(transferPhaseText(row.phase)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            "cell-updated": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(formatTimestamp(row.updated_at || row.timestamp || row.created_at)), 1)
                            ]),
                            expand: _withCtx(({ row }) => [
                              _createVNode(RecordDetails, { record: row }, null, 8, ["record"])
                            ]),
                            _: 1
                          }, 8, ["columns", "rows", "total", "page", "page-size", "state"])
                        ], 64))
                      : _createCommentVNode("", true),
                    (activeTab.value === 'history')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                          _createVNode(ModuleTable, {
                            title: "执行记录",
                            "data-record-block": "rename-history",
                            "data-record-state": "history",
                            columns: recordColumns.history,
                            rows: records.value,
                            total: total.value,
                            "row-key": "hash",
                            page: page.value,
                            "page-size": pageSize.value,
                            state: recordTableState('history', records.value, historyResultFilter.value === 'all' ? 'none' : 'filtered'),
                            "cleanup-blocked": !cleanupCounts.value.rename_history,
                            "cleanup-label": "清历史",
                            onCleanup: _cache[15] || (_cache[15] = $event => (openCleanupDialog('rename_history'))),
                            onRetry: _cache[16] || (_cache[16] = $event => (loadHistory(beginRecordRequest(['history'])))),
                            onResetFilters: resetHistoryFilter,
                            "onUpdate:page": _cache[17] || (_cache[17] = $event => (pageRecordChange('history', $event))),
                            "onUpdate:pageSize": _cache[18] || (_cache[18] = $event => (sizeRecordChange('history', $event)))
                          }, {
                            filters: _withCtx(() => [
                              _createVNode(CompactSelect, {
                                modelValue: historyResultFilter.value,
                                "onUpdate:modelValue": [
                                  _cache[13] || (_cache[13] = $event => ((historyResultFilter).value = $event)),
                                  _cache[14] || (_cache[14] = $event => (pageRecordChange('history', 1)))
                                ],
                                items: [{title:'全部结果',value:'all'},{title:'成功',value:'success'},{title:'失败',value:'failed'}],
                                label: "结果",
                                class: "dm-filter"
                              }, null, 8, ["modelValue"])
                            ]),
                            toolbar: _withCtx(() => [
                              _createVNode(_component_VBtn, {
                                color: "primary",
                                size: "small",
                                variant: "tonal",
                                loading: renameStatus.value.batch_running || moduleRunning.value === 'rename-retry',
                                disabled: !!moduleRunning.value || renameStatus.value.batch_running,
                                onClick: doRetryRenames
                              }, {
                                default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
                                  _createTextVNode("重试失败项", -1)
                                ]))]),
                                _: 1
                              }, 8, ["loading", "disabled"])
                            ]),
                            "cell-downloader": _withCtx(({ row }) => [
                              _createVNode(DownloaderBadge, {
                                name: row.downloader || row.downloader_id || '未记录'
                              }, null, 8, ["name"])
                            ]),
                            "cell-success": _withCtx(({ row }) => [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: row.success ? 'success' : 'error',
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(row.success ? '成功' : '失败'), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            rowActions: _withCtx(({ row }) => [
                              _createVNode(RowActionMenu, {
                                label: row.name || row.hash,
                                busy: retryingHash.value === row.hash,
                                actions: [
                    {key:'retry',label:'重试',icon:'mdi-refresh',disabled:!!retryingHash.value || !!moduleRunning.value},
                    ...(row.success ? [{key:'recover',label:'恢复原名',icon:'mdi-undo',color:'warning'}] : []),
                    {key:'delete',label:'删除记录',icon:'mdi-delete-outline',color:'error'},
                  ],
                                onSelect: $event => (handleHistoryAction($event, row))
                              }, null, 8, ["label", "busy", "actions", "onSelect"])
                            ]),
                            expand: _withCtx(({ row }) => [
                              _createVNode(RecordDetails, { record: row }, null, 8, ["record"])
                            ]),
                            _: 1
                          }, 8, ["columns", "rows", "total", "page", "page-size", "state", "cleanup-blocked"]),
                          _createVNode(ModuleTable, {
                            title: "失败归档",
                            "data-record-block": "rename-archive",
                            "data-record-state": "archive",
                            columns: recordColumns.archive,
                            rows: archiveRecords.value,
                            total: archiveTotal.value,
                            "row-key": "hash",
                            page: archivePage.value,
                            "page-size": archivePageSize.value,
                            state: recordTableState('archive', archiveRecords.value),
                            "cleanup-blocked": !cleanupCounts.value.rename_archive,
                            "cleanup-label": "清归档",
                            onCleanup: _cache[19] || (_cache[19] = $event => (openCleanupDialog('rename_archive'))),
                            onRetry: _cache[20] || (_cache[20] = $event => (loadArchive(beginRecordRequest(['archive'])))),
                            "onUpdate:page": _cache[21] || (_cache[21] = $event => (pageRecordChange('archive', $event))),
                            "onUpdate:pageSize": _cache[22] || (_cache[22] = $event => (sizeRecordChange('archive', $event)))
                          }, {
                            "cell-archived_at": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(row.archived_at || row.last_failed_at || '—'), 1)
                            ]),
                            "cell-downloader": _withCtx(({ row }) => [
                              _createVNode(DownloaderBadge, {
                                name: row.downloader || row.downloader_id || '未记录'
                              }, null, 8, ["name"])
                            ]),
                            "cell-category": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(row.category_label || row.category || '—'), 1)
                            ]),
                            "cell-reason": _withCtx(({ row }) => [
                              _createElementVNode("span", {
                                title: row.archive_reason || row.reason
                              }, _toDisplayString(row.archive_reason || row.reason || '—'), 9, _hoisted_19)
                            ]),
                            rowActions: _withCtx(({ row }) => [
                              _createVNode(RowActionMenu, {
                                label: row.name || row.hash,
                                busy: retryingHash.value === row.hash || restoringHash.value === row.hash || deletingHash.value === row.hash,
                                actions: [
                      { key: 'retry', label: '重试', icon: 'mdi-refresh', disabled: !!retryingHash.value || restoringHash.value === row.hash || deletingHash.value === row.hash },
                      { key: 'restore', label: '恢复记录', icon: 'mdi-archive-arrow-up-outline', disabled: retryingHash.value === row.hash },
                      { key: 'delete', label: '删除记录', icon: 'mdi-delete-outline', color: 'error', disabled: retryingHash.value === row.hash },
                    ],
                                onSelect: $event => (handleArchiveAction($event, row))
                              }, null, 8, ["label", "busy", "actions", "onSelect"])
                            ]),
                            expand: _withCtx(({ row }) => [
                              _createVNode(RecordDetails, { record: row }, null, 8, ["record"])
                            ]),
                            _: 1
                          }, 8, ["columns", "rows", "total", "page", "page-size", "state", "cleanup-blocked"])
                        ], 64))
                      : _createCommentVNode("", true),
                    (activeTab.value === 'hr')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                          _createVNode(ModuleTable, {
                            title: "H&R 任务",
                            "data-record-block": "hr-tasks",
                            "data-record-state": "hr",
                            columns: recordColumns.hr,
                            rows: visibleRows('hr', visibleHrRows.value),
                            total: visibleHrRows.value.length,
                            "row-key": rowIdentity,
                            page: localPages.hr,
                            "page-size": localSizes.hr,
                            state: recordTableState('hr', visibleHrRows.value, hrStatusFilter.value === 'all' && presenceFilter.value === 'all' ? 'none' : 'filtered'),
                            onRetry: refreshActive,
                            onResetFilters: _cache[27] || (_cache[27] = $event => {hrStatusFilter.value = 'all'; presenceFilter.value = 'all';}),
                            "onUpdate:page": _cache[28] || (_cache[28] = $event => (localPages.hr = $event)),
                            "onUpdate:pageSize": _cache[29] || (_cache[29] = $event => (setLocalSize('hr', $event)))
                          }, {
                            filters: _withCtx(() => [
                              _createVNode(CompactSelect, {
                                modelValue: hrStatusFilter.value,
                                "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((hrStatusFilter).value = $event)),
                                items: hrStatusFilterOptions,
                                label: "考核状态",
                                class: "dm-filter"
                              }, null, 8, ["modelValue"]),
                              _createVNode(CompactSelect, {
                                modelValue: presenceFilter.value,
                                "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((presenceFilter).value = $event)),
                                items: [{title:'全部',value:'all'},{title:'存在',value:'present'},{title:'缺失',value:'missing'}],
                                label: "存在状态",
                                class: "dm-filter"
                              }, null, 8, ["modelValue"])
                            ]),
                            toolbar: _withCtx(() => [
                              _createVNode(_component_VBtn, {
                                color: "primary",
                                size: "small",
                                variant: "tonal",
                                disabled: hrClearing.value || !hrSummary.value.compliant,
                                onClick: _cache[25] || (_cache[25] = $event => (askHrClear('compliant')))
                              }, {
                                default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                                  _createTextVNode("清理达标记录", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled"]),
                              _createVNode(_component_VBtn, {
                                color: "primary",
                                size: "small",
                                variant: "tonal",
                                disabled: hrClearing.value || !hrSummary.value.deleted,
                                onClick: _cache[26] || (_cache[26] = $event => (askHrClear('missing')))
                              }, {
                                default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                                  _createTextVNode("清理缺失记录", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled"])
                            ]),
                            "cell-name": _withCtx(({ row }) => [
                              _createElementVNode("span", {
                                title: row.name || row.torrent_hash
                              }, _toDisplayString(hrTaskTitle(row)), 9, _hoisted_20)
                            ]),
                            "cell-downloader_id": _withCtx(({ value }) => [
                              _createVNode(DownloaderBadge, {
                                name: value || '未记录'
                              }, null, 8, ["name"])
                            ]),
                            "cell-status": _withCtx(({ row }) => [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: hrStatusColor(row.status),
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(row.status_text || row.status), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            "cell-deleted": _withCtx(({ value }) => [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: value === true ? 'warning' : 'default',
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(value === true ? '缺失' : value === false ? '存在' : '未知'), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            "cell-remain_seconds": _withCtx(({ value }) => [
                              _createTextVNode(_toDisplayString(value == null ? '—' : formatDuration(value)), 1)
                            ]),
                            "cell-deadline": _withCtx(({ value }) => [
                              _createTextVNode(_toDisplayString(formatTimestamp(value)), 1)
                            ]),
                            "cell-progress": _withCtx(({ value }) => [
                              _createTextVNode(_toDisplayString(value == null ? '—' : formatPercent(value)), 1)
                            ]),
                            rowActions: _withCtx(({ row }) => [
                              _createVNode(RowActionMenu, {
                                label: hrTaskTitle(row),
                                busy: hrClearing.value,
                                actions: [{key:'clear',label:'清理记录',icon:'mdi-delete-outline',color:'error',disabled:hrClearing.value}],
                                onSelect: $event => (askHrClear('task', row))
                              }, null, 8, ["label", "busy", "actions", "onSelect"])
                            ]),
                            expand: _withCtx(({ row }) => [
                              _createVNode(RecordDetails, { record: row }, null, 8, ["record"])
                            ]),
                            _: 1
                          }, 8, ["columns", "rows", "total", "page", "page-size", "state"]),
                          _createElementVNode("details", _hoisted_21, [
                            _cache[57] || (_cache[57] = _createElementVNode("summary", null, "保护跳过统计", -1)),
                            _createElementVNode("dl", null, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(hrSkipRows.value, (row) => {
                                return (_openBlock(), _createElementBlock(_Fragment, {
                                  key: row.label
                                }, [
                                  _createElementVNode("dt", null, _toDisplayString(row.label), 1),
                                  _createElementVNode("dd", null, _toDisplayString(row.value), 1)
                                ], 64))
                              }), 128))
                            ])
                          ])
                        ], 64))
                      : _createCommentVNode("", true),
                    (activeTab.value === 'autoremove')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                          _createVNode(ModuleTable, {
                            title: "候选清单",
                            "data-record-block": "autoremove-preview",
                            "data-record-state": "autoremove",
                            columns: recordColumns.candidates,
                            rows: visibleRows('candidates', autoremoveRows.value),
                            total: autoremoveRows.value.length,
                            "row-key": rowIdentity,
                            page: localPages.candidates,
                            "page-size": localSizes.candidates,
                            state: recordTableState('autoremove', autoremoveRows.value, autoremoveEmptyState.value, true),
                            onRetry: refreshActive,
                            "onUpdate:page": _cache[31] || (_cache[31] = $event => (localPages.candidates = $event)),
                            "onUpdate:pageSize": _cache[32] || (_cache[32] = $event => (setLocalSize('candidates', $event)))
                          }, {
                            toolbar: _withCtx(() => [
                              _createVNode(_component_VChip, {
                                size: "small",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(autoremovePreview.value ? '本次预览' : '上轮候选'), 1)
                                ]),
                                _: 1
                              }),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                color: autoremoveStatus.value.observe_only ? 'warning' : autoremoveStatus.value.action === 'pause' ? 'primary' : 'error',
                                variant: "tonal",
                                disabled: !!moduleRunning.value,
                                onClick: _cache[30] || (_cache[30] = $event => (autoRunConfirm.value = true))
                              }, {
                                default: _withCtx(() => [...(_cache[58] || (_cache[58] = [
                                  _createTextVNode("按当前配置执行", -1)
                                ]))]),
                                _: 1
                              }, 8, ["color", "disabled"])
                            ]),
                            "cell-name": _withCtx(({ row }) => [
                              _createTextVNode(_toDisplayString(row.name || '名称未记录'), 1)
                            ]),
                            "cell-downloader_id": _withCtx(({ value }) => [
                              _createVNode(DownloaderBadge, {
                                name: value || '未记录'
                              }, null, 8, ["name"])
                            ]),
                            expand: _withCtx(({ row }) => [
                              _createVNode(RecordDetails, { record: row }, null, 8, ["record"])
                            ]),
                            _: 1
                          }, 8, ["columns", "rows", "total", "page", "page-size", "state"]),
                          _cache[61] || (_cache[61] = _createElementVNode("p", { class: "dm-hint" }, "预览不锁定执行清单；执行时后端会按当前配置重新判断。", -1)),
                          _createVNode(ModuleTable, {
                            title: "执行记录",
                            columns: recordColumns.autoHistory,
                            unavailable: unavailableHistory
                          }, null, 8, ["columns"]),
                          _createElementVNode("details", _hoisted_22, [
                            _cache[60] || (_cache[60] = _createElementVNode("summary", null, "最近运行详情", -1)),
                            _createVNode(_component_VBtn, {
                              color: "primary",
                              size: "small",
                              variant: "tonal",
                              disabled: !cleanupCounts.value.autoremove_state,
                              onClick: _cache[33] || (_cache[33] = $event => (openCleanupDialog('autoremove_state')))
                            }, {
                              default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                                _createTextVNode("清最近运行记录", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled"]),
                            _createVNode(ModuleDetailPanel, {
                              rows: moduleDetail('autoremove').rows,
                              items: moduleDetail('autoremove').items,
                              total: moduleDetail('autoremove').total,
                              limit: moduleDetail('autoremove').limit,
                              truncated: moduleDetail('autoremove').truncated,
                              error: moduleDetail('autoremove').error
                            }, null, 8, ["rows", "items", "total", "limit", "truncated", "error"])
                          ])
                        ], 64))
                      : _createCommentVNode("", true),
                    (activeTab.value === 'failclean')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
                          _createVNode(ModuleTable, {
                            title: "执行记录",
                            columns: recordColumns.failHistory,
                            unavailable: unavailableHistory
                          }, null, 8, ["columns"]),
                          _createElementVNode("details", {
                            class: "dm-runtime-details",
                            "data-record-state": "failclean",
                            "aria-busy": recordStates.failclean.loading
                          }, [
                            _cache[63] || (_cache[63] = _createElementVNode("summary", null, "事件与最近巡检详情", -1)),
                            _createVNode(_component_VBtn, {
                              color: "primary",
                              size: "small",
                              variant: "tonal",
                              disabled: !cleanupCounts.value.failclean_state,
                              onClick: _cache[34] || (_cache[34] = $event => (openCleanupDialog('failclean_state')))
                            }, {
                              default: _withCtx(() => [...(_cache[62] || (_cache[62] = [
                                _createTextVNode("清最近运行记录", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled"]),
                            (!failcleanRows.value.length || recordStates.failclean.error)
                              ? (_openBlock(), _createBlock(TableState, _mergeProps({ key: 0 }, recordTableState('failclean', failcleanRows.value, failcleanEmptyState.value), { onRetry: refreshActive }), null, 16))
                              : _createCommentVNode("", true),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(failcleanRows.value, (row) => {
                              return (_openBlock(), _createBlock(RecordDetails, {
                                key: row.source,
                                record: { source: row.source, scanned: row.scanned, cleaned: row.cleaned, failed: row.failed, skipped: row.skipped }
                              }, null, 8, ["record"]))
                            }), 128))
                          ], 8, _hoisted_23)
                        ], 64))
                      : _createCommentVNode("", true),
                    (activeTab.value === 'sitetag')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 5 }, [
                          _createVNode(ModuleTable, {
                            title: "补全执行记录",
                            columns: recordColumns.tagHistory,
                            unavailable: unavailableHistory
                          }, null, 8, ["columns"]),
                          _createVNode(ModuleTable, {
                            title: "标签清理记录",
                            "data-record-block": "tag-cleanup",
                            columns: recordColumns.cleanupHistory,
                            unavailable: unavailableHistory
                          }, null, 8, ["columns"]),
                          _createElementVNode("details", _hoisted_24, [
                            _cache[64] || (_cache[64] = _createElementVNode("summary", null, "最近标签清理快照（非逐条历史）", -1)),
                            _createVNode(ModuleDetailPanel, {
                              rows: moduleDetail('tagcleanup').rows,
                              items: moduleDetail('tagcleanup').items,
                              total: moduleDetail('tagcleanup').total,
                              limit: moduleDetail('tagcleanup').limit,
                              truncated: moduleDetail('tagcleanup').truncated,
                              error: moduleDetail('tagcleanup').error
                            }, null, 8, ["rows", "items", "total", "limit", "truncated", "error"])
                          ])
                        ], 64))
                      : _createCommentVNode("", true),
                    (activeTab.value === 'upload')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 6 }, [
                          _createElementVNode("section", _hoisted_25, [
                            _createElementVNode("div", _hoisted_26, [
                              _cache[65] || (_cache[65] = _createElementVNode("h3", null, "实时监控", -1)),
                              _createElementVNode("div", _hoisted_27, [
                                _createVNode(CompactSelect, {
                                  modelValue: uploadDownloaderFilter.value,
                                  "onUpdate:modelValue": _cache[35] || (_cache[35] = $event => ((uploadDownloaderFilter).value = $event)),
                                  items: [{title:'全部下载器',value:'all'}, ...uploadLimitDownloaderRows.value.map(item => ({title:item.name || item.id,value:String(item.id)}))],
                                  label: "下载器",
                                  class: "dm-filter"
                                }, null, 8, ["modelValue", "items"]),
                                _createVNode(_component_VTextField, {
                                  modelValue: uploadSiteFilter.value,
                                  "onUpdate:modelValue": _cache[36] || (_cache[36] = $event => ((uploadSiteFilter).value = $event)),
                                  label: "搜索站点",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": "",
                                  class: "dm-filter"
                                }, null, 8, ["modelValue"])
                              ])
                            ]),
                            (!uploadGroups.value.length)
                              ? (_openBlock(), _createElementBlock("p", _hoisted_28, _toDisplayString(uploadDownloaderFilter.value !== 'all' || uploadSiteFilter.value ? '筛选无结果' : '当前快照没有下载器状态'), 1))
                              : _createCommentVNode("", true),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(uploadGroups.value, (group) => {
                              return (_openBlock(), _createElementBlock("section", {
                                key: group.key,
                                class: "dm-upload-group"
                              }, [
                                _createElementVNode("button", {
                                  type: "button",
                                  class: "dm-group-heading",
                                  "aria-expanded": !closedUploadGroups[group.key],
                                  onClick: $event => (closedUploadGroups[group.key] = !closedUploadGroups[group.key])
                                }, [
                                  _createElementVNode("span", null, _toDisplayString(closedUploadGroups[group.key] ? '▸' : '▾') + " " + _toDisplayString(group.title), 1),
                                  (!group.aggregate)
                                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                        _createElementVNode("span", null, _toDisplayString(group.error ? '异常：' + group.error : group.connected === false ? '未连接' : '状态：' + (group.status || '当前接口未提供')), 1),
                                        _createElementVNode("span", null, "当前上传 " + _toDisplayString(group.upload_rate_bps == null ? '—' : formatUploadRate(group.upload_rate_bps)), 1),
                                        _createElementVNode("span", null, "全局限速 " + _toDisplayString(group.global_limit_kib == null ? '—' : group.global_limit_kib + ' KiB/s'), 1),
                                        _createElementVNode("span", null, "受管 " + _toDisplayString(group.managed_torrents ?? '—'), 1),
                                        _createElementVNode("span", null, "更新时间 " + _toDisplayString(group.updated_at || '当前接口未提供'), 1)
                                      ], 64))
                                    : _createCommentVNode("", true)
                                ], 8, _hoisted_29),
                                (!closedUploadGroups[group.key])
                                  ? (_openBlock(), _createBlock(ModuleTable, {
                                      key: 0,
                                      title: group.title + ' · 站点额度',
                                      columns: recordColumns.sites,
                                      rows: group.rows,
                                      "row-key": "key",
                                      pagination: false
                                    }, {
                                      "cell-upload_rate_bps": _withCtx(({ value }) => [
                                        _createTextVNode(_toDisplayString(value == null ? '—' : formatUploadRate(value)), 1)
                                      ]),
                                      "cell-allocated_kib": _withCtx(({ value }) => [
                                        _createTextVNode(_toDisplayString(value == null ? '—' : value + ' KiB/s'), 1)
                                      ]),
                                      "cell-uploading_torrents": _withCtx(({ value }) => [
                                        _createTextVNode(_toDisplayString(value ?? '当前接口未提供'), 1)
                                      ]),
                                      "cell-state": _withCtx(({ row }) => [
                                        _createTextVNode(_toDisplayString(row.state || '当前接口未提供'), 1)
                                      ]),
                                      expand: _withCtx(({ row }) => [
                                        _createElementVNode("p", _hoisted_30, "关联下载器：" + _toDisplayString(row.downloaders?.join('、') || '当前接口未提供') + "；种子级明细当前接口未提供。", 1)
                                      ]),
                                      _: 1
                                    }, 8, ["title", "columns", "rows"]))
                                  : _createCommentVNode("", true)
                              ]))
                            }), 128))
                          ]),
                          _createVNode(ModuleTable, {
                            title: "执行记录",
                            columns: recordColumns.uploadHistory,
                            unavailable: unavailableHistory
                          }, null, 8, ["columns"]),
                          _cache[69] || (_cache[69] = _createElementVNode("p", { class: "dm-hint" }, "实际上传与分配额度是不同指标；MP 或插件离线后，下载器可能保留最后写入的限速。", -1)),
                          _createElementVNode("details", _hoisted_31, [
                            _cache[68] || (_cache[68] = _createElementVNode("summary", null, "站点识别与策略操作", -1)),
                            _createVNode(_component_VBtn, {
                              color: "primary",
                              size: "small",
                              variant: "tonal",
                              disabled: !!moduleRunning.value,
                              onClick: doUploadScanSites
                            }, {
                              default: _withCtx(() => [...(_cache[66] || (_cache[66] = [
                                _createTextVNode("扫描站点", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled"]),
                            _createVNode(_component_VBtn, {
                              size: "small",
                              variant: "tonal",
                              color: "error",
                              disabled: !!moduleRunning.value,
                              onClick: doUploadClearRules
                            }, {
                              default: _withCtx(() => [...(_cache[67] || (_cache[67] = [
                                _createTextVNode("清空策略", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled"])
                          ])
                        ], 64))
                      : _createCommentVNode("", true)
                  ], 8, _hoisted_11))
                : _createCommentVNode("", true),
              (activeTab.value === 'diagnostics')
                ? (_openBlock(), _createElementBlock("section", _hoisted_32, [
                    _createElementVNode("div", _hoisted_33, [
                      _createVNode(ModuleHeader, {
                        title: "运行诊断",
                        icon: _unref(MODULE_ICONS).diagnostics,
                        "show-status": false,
                        enabled: ""
                      }, null, 8, ["icon"]),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        size: "small",
                        variant: "tonal",
                        loading: loading.value,
                        onClick: runDiagnostics
                      }, {
                        default: _withCtx(() => [...(_cache[70] || (_cache[70] = [
                          _createTextVNode("刷新诊断", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"])
                    ]),
                    _createElementVNode("div", _hoisted_34, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(diagnosticStats.value, (stat) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: stat.label
                        }, [
                          _createElementVNode("span", null, _toDisplayString(stat.label), 1),
                          _createElementVNode("strong", null, _toDisplayString(stat.value), 1)
                        ]))
                      }), 128))
                    ]),
                    _createElementVNode("p", _hoisted_35, "最近检查：" + _toDisplayString(diagnostics.value?.time || '未检查') + " · 当前显示最近快照，刷新诊断会进行只读检查（可能访问下载器）。", 1),
                    _createVNode(ModuleTable, {
                      title: "检查结果",
                      columns: recordColumns.diagnostics,
                      rows: visibleRows('diagnostics', filteredDiagnosticRows.value),
                      total: filteredDiagnosticRows.value.length,
                      page: localPages.diagnostics,
                      "page-size": localSizes.diagnostics,
                      state: { empty: diagnosticModuleFilter.value === 'all' && diagnosticStateFilter.value === 'all' ? 'none' : 'filtered' },
                      "onUpdate:page": _cache[39] || (_cache[39] = $event => (localPages.diagnostics = $event)),
                      "onUpdate:pageSize": _cache[40] || (_cache[40] = $event => (setLocalSize('diagnostics', $event))),
                      onResetFilters: _cache[41] || (_cache[41] = $event => {diagnosticModuleFilter.value = 'all'; diagnosticStateFilter.value = 'all';})
                    }, {
                      filters: _withCtx(() => [
                        _createVNode(CompactSelect, {
                          modelValue: diagnosticModuleFilter.value,
                          "onUpdate:modelValue": _cache[37] || (_cache[37] = $event => ((diagnosticModuleFilter).value = $event)),
                          items: [...moduleFilterItems.value, {title:'插件',value:'plugin'}],
                          label: "模块",
                          class: "dm-filter"
                        }, null, 8, ["modelValue", "items"]),
                        _createVNode(CompactSelect, {
                          modelValue: diagnosticStateFilter.value,
                          "onUpdate:modelValue": _cache[38] || (_cache[38] = $event => ((diagnosticStateFilter).value = $event)),
                          items: ['all','正常','需关注','异常','未检查','不适用'],
                          label: "状态",
                          class: "dm-filter"
                        }, null, 8, ["modelValue"])
                      ]),
                      rowActions: _withCtx(({ row }) => [
                        _createVNode(RowActionMenu, {
                          label: row.name || row.title || '诊断项',
                          actions: [{key:'detail',label:'详情',icon:'mdi-text-box-search-outline'}],
                          onSelect: $event => (selectedDiagnostic.value = row)
                        }, null, 8, ["label", "onSelect"])
                      ]),
                      _: 1
                    }, 8, ["columns", "rows", "total", "page", "page-size", "state"]),
                    (selectedDiagnostic.value)
                      ? (_openBlock(), _createElementBlock("section", _hoisted_36, [
                          _createElementVNode("h3", null, _toDisplayString(selectedDiagnostic.value.name), 1),
                          _createElementVNode("dl", null, [
                            _cache[71] || (_cache[71] = _createElementVNode("dt", null, "问题", -1)),
                            _createElementVNode("dd", null, _toDisplayString(selectedDiagnostic.value.reason || selectedDiagnostic.value.message || '—'), 1),
                            _cache[72] || (_cache[72] = _createElementVNode("dt", null, "影响范围", -1)),
                            _createElementVNode("dd", null, _toDisplayString(selectedDiagnostic.value.target || selectedDiagnostic.value.module), 1),
                            _cache[73] || (_cache[73] = _createElementVNode("dt", null, "建议", -1)),
                            _createElementVNode("dd", null, _toDisplayString(selectedDiagnostic.value.suggestion || '当前检查项未提供建议'), 1),
                            _cache[74] || (_cache[74] = _createElementVNode("dt", null, "检查时间 / 来源", -1)),
                            _createElementVNode("dd", null, _toDisplayString(diagnostics.value?.time || '未检查') + " / 最近诊断快照", 1)
                          ])
                        ]))
                      : _createCommentVNode("", true),
                    _createElementVNode("details", _hoisted_37, [
                      _cache[75] || (_cache[75] = _createElementVNode("summary", null, "环境信息", -1)),
                      _createElementVNode("p", null, "插件版本：" + _toDisplayString(diagnostics.value?.plugin?.version || '—'), 1),
                      _createVNode(RecordDetails, {
                        record: diagnostics.value?.paths || {}
                      }, null, 8, ["record"])
                    ])
                  ]))
                : _createCommentVNode("", true)
            ], 64))
      ])
    ]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-page",
      modelValue: transferRunDialog.value,
      "onUpdate:modelValue": _cache[43] || (_cache[43] = $event => ((transferRunDialog).value = $event)),
      "max-width": "520"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VAvatar, {
                  color: "primary",
                  variant: "tonal",
                  size: "40",
                  rounded: "lg"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, { icon: "mdi-transfer" })
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "dm-title" }, {
                  default: _withCtx(() => [...(_cache[76] || (_cache[76] = [
                    _createTextVNode("确认立即运行转移做种", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint dm-risk" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-alert-outline",
                      size: "16"
                    }),
                    _cache[77] || (_cache[77] = _createTextVNode("按当前配置扫描源下载器并转移种子；若配置了删源，转移完成后会删除源任务。", -1))
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  size: "small",
                  variant: "tonal",
                  disabled: moduleRunning.value === 'transfer-run',
                  onClick: _cache[42] || (_cache[42] = $event => (transferRunDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[78] || (_cache[78] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "primary",
                  variant: "flat",
                  "prepend-icon": "mdi-play-circle-outline",
                  loading: moduleRunning.value === 'transfer-run',
                  onClick: confirmTransferRun
                }, {
                  default: _withCtx(() => [...(_cache[79] || (_cache[79] = [
                    _createTextVNode("运行转移", -1)
                  ]))]),
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
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-page",
      modelValue: cleanupConfirmDialog.value,
      "onUpdate:modelValue": _cache[45] || (_cache[45] = $event => ((cleanupConfirmDialog).value = $event)),
      "max-width": "520"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VAvatar, {
                  color: "warning",
                  variant: "tonal",
                  size: "40",
                  rounded: "lg"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, { icon: "mdi-delete-sweep-outline" })
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "dm-title" }, {
                  default: _withCtx(() => [
                    _createTextVNode("确认清理" + _toDisplayString(cleanupTarget.value?.label), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint" }, {
                  default: _withCtx(() => [
                    _createTextVNode("将删除 " + _toDisplayString(cleanupTargetCount.value) + " 条" + _toDisplayString(cleanupTarget.value?.detail), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "dm-body-text" }, {
              default: _withCtx(() => [
                _createElementVNode("div", null, _toDisplayString(cleanupTarget.value?.consequence), 1),
                _cache[80] || (_cache[80] = _createElementVNode("div", { class: "dm-hint mt-2" }, " 不修改下载器任务与文件，不影响 H&R 安全状态、活动队列与限速恢复状态。 ", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  size: "small",
                  variant: "tonal",
                  disabled: cleanupRunning.value,
                  onClick: _cache[44] || (_cache[44] = $event => (cleanupConfirmDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[81] || (_cache[81] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "error",
                  variant: "flat",
                  "prepend-icon": "mdi-delete-sweep-outline",
                  loading: cleanupRunning.value,
                  disabled: cleanupTargetCount.value === 0,
                  onClick: confirmCleanupData
                }, {
                  default: _withCtx(() => [...(_cache[82] || (_cache[82] = [
                    _createTextVNode("清理记录", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading", "disabled"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-page",
      modelValue: hrClearDialog.value,
      "onUpdate:modelValue": _cache[47] || (_cache[47] = $event => ((hrClearDialog).value = $event)),
      "max-width": "520"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VAvatar, {
                  color: "error",
                  variant: "tonal",
                  size: "40",
                  rounded: "lg"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, { icon: "mdi-delete-outline" })
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "dm-title" }, {
                  default: _withCtx(() => [...(_cache[83] || (_cache[83] = [
                    _createTextVNode("确认清除 H&R 记录", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint dm-risk" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-alert-outline",
                      size: "16"
                    }),
                    _createTextVNode(_toDisplayString(hrClearDialogDescription.value), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            (hrClearKind.value === 'task')
              ? (_openBlock(), _createBlock(_component_VCardText, {
                  key: 0,
                  class: "dm-body-text"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(hrClearTarget.value?.site || hrClearTarget.value?.name || hrClearTarget.value?.torrent_hash), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  size: "small",
                  variant: "tonal",
                  disabled: hrClearing.value,
                  onClick: _cache[46] || (_cache[46] = $event => (hrClearDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[84] || (_cache[84] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "error",
                  variant: "flat",
                  "prepend-icon": "mdi-delete-outline",
                  loading: hrClearing.value,
                  onClick: confirmHrClear
                }, {
                  default: _withCtx(() => [...(_cache[85] || (_cache[85] = [
                    _createTextVNode("清理记录", -1)
                  ]))]),
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
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-page",
      modelValue: cleanupDialog.value,
      "onUpdate:modelValue": _cache[49] || (_cache[49] = $event => ((cleanupDialog).value = $event)),
      "max-width": "620"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VAvatar, {
                  color: "warning",
                  variant: "tonal",
                  size: "40",
                  rounded: "lg"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, { icon: "mdi-tag-remove-outline" })
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "dm-title" }, {
                  default: _withCtx(() => [...(_cache[86] || (_cache[86] = [
                    _createTextVNode("确认标签清理", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint" }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(cleanupRemovals.value.length) + " 个标签 · " + _toDisplayString(cleanupRemovalAssociations.value) + " 条任务关联", 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VList, {
              density: "compact",
              class: "dm-cleanup-preview-list"
            }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupRemovals.value, (item) => {
                  return (_openBlock(), _createBlock(_component_VListItem, {
                    key: `${item.downloader}-${item.tag}`
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-tag-outline",
                        size: "18"
                      })
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.tag), 1)
                        ]),
                        _: 2
                      }, 1024),
                      _createVNode(_component_VListItemSubtitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.downloader) + " · " + _toDisplayString(item.hashes.length) + " 个任务", 1)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1024))
                }), 128))
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  size: "small",
                  variant: "tonal",
                  disabled: cleanupExecuting.value,
                  onClick: _cache[48] || (_cache[48] = $event => (cleanupDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[87] || (_cache[87] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "error",
                  variant: "flat",
                  "prepend-icon": "mdi-tag-remove-outline",
                  loading: cleanupExecuting.value,
                  onClick: executeCleanupTags
                }, {
                  default: _withCtx(() => [...(_cache[88] || (_cache[88] = [
                    _createTextVNode("删除标签", -1)
                  ]))]),
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cdf4b31f"]]);

export { Page as default };
