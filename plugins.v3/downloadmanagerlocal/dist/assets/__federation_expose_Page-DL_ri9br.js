import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, D as DownloaderBadge, g as getPluginApi, p as postPluginApi, a as postPluginJsonApi } from './DownloaderBadge-C3kBtnlz.js';

const {createElementVNode:_createElementVNode$3,renderList:_renderList$3,Fragment:_Fragment$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createCommentVNode:_createCommentVNode$3,toDisplayString:_toDisplayString$3,normalizeClass:_normalizeClass$2} = await importShared('vue');


const _hoisted_1$3 = {
  key: 0,
  class: "dm-table-state dm-table-state--loading",
  role: "status",
  "aria-label": "正在加载记录",
  "aria-busy": "true"
};
const _hoisted_2$3 = {
  key: 1,
  class: "dm-table-state",
  role: "alert"
};
const _hoisted_3$3 = {
  key: 0,
  class: "dm-table-state-help dm-table-state-error"
};
const _hoisted_4$3 = {
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

const {computed: computed$2} = await importShared('vue');


const _sfc_main$3 = {
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
const emptyState = computed$2(() => emptyStates[props.empty]);

return (_ctx, _cache) => {
  return (__props.loading)
    ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_1$3, [
        _cache[3] || (_cache[3] = _createElementVNode$3("span", { class: "dm-table-state-sr" }, "正在加载记录", -1)),
        (_openBlock$3(), _createElementBlock$3(_Fragment$3, null, _renderList$3(3, (row) => {
          return _createElementVNode$3("span", {
            key: row,
            class: "dm-table-skeleton",
            "aria-hidden": "true"
          })
        }), 64))
      ]))
    : (__props.error)
      ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_2$3, [
          _cache[4] || (_cache[4] = _createElementVNode$3("span", {
            class: "mdi mdi-alert-circle-outline dm-table-state-icon dm-table-state-error",
            "aria-hidden": "true"
          }, null, -1)),
          _cache[5] || (_cache[5] = _createElementVNode$3("p", { class: "dm-table-state-title" }, "记录加载失败", -1)),
          (typeof __props.error === 'string')
            ? (_openBlock$3(), _createElementBlock$3("p", _hoisted_3$3, _toDisplayString$3(__props.error), 1))
            : _createCommentVNode$3("", true),
          _createElementVNode$3("button", {
            type: "button",
            class: "dm-table-state-button",
            onClick: _cache[0] || (_cache[0] = $event => (emit('retry')))
          }, "重试")
        ]))
      : (__props.refreshFailed)
        ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_4$3, [
            _cache[6] || (_cache[6] = _createElementVNode$3("span", {
              class: "mdi mdi-alert-outline dm-table-state-icon",
              "aria-hidden": "true"
            }, null, -1)),
            _createElementVNode$3("p", _hoisted_5$3, "刷新失败，保留上次结果" + _toDisplayString$3(typeof __props.refreshFailed === 'string' ? '：' + __props.refreshFailed : ''), 1),
            _createElementVNode$3("button", {
              type: "button",
              class: "dm-table-state-button",
              onClick: _cache[1] || (_cache[1] = $event => (emit('retry')))
            }, "重试")
          ]))
        : (emptyState.value)
          ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_6$3, [
              _createElementVNode$3("span", {
                class: _normalizeClass$2(["mdi dm-table-state-icon", emptyState.value.icon]),
                "aria-hidden": "true"
              }, null, 2),
              _createElementVNode$3("p", _hoisted_7$3, _toDisplayString$3(emptyState.value.title), 1),
              (emptyState.value.help)
                ? (_openBlock$3(), _createElementBlock$3("p", _hoisted_8$3, _toDisplayString$3(emptyState.value.help), 1))
                : _createCommentVNode$3("", true),
              (__props.empty === 'filtered')
                ? (_openBlock$3(), _createElementBlock$3("button", {
                    key: 1,
                    type: "button",
                    class: "dm-table-state-button",
                    onClick: _cache[2] || (_cache[2] = $event => (emit('reset-filters')))
                  }, "重置筛选"))
                : _createCommentVNode$3("", true)
            ]))
          : _createCommentVNode$3("", true)
}
}

};
const TableState = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-ec2c9e2f"]]);

const {toDisplayString:_toDisplayString$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$2,renderSlot:_renderSlot,renderList:_renderList$2,Fragment:_Fragment$2,createElementVNode:_createElementVNode$2} = await importShared('vue');


const _hoisted_1$2 = { class: "dm-detail-panel" };
const _hoisted_2$2 = {
  key: 0,
  class: "dm-detail-title"
};
const _hoisted_3$2 = {
  key: 1,
  class: "text-caption text-medium-emphasis dm-detail-break"
};
const _hoisted_4$2 = {
  key: 2,
  class: "text-caption text-error dm-detail-break"
};
const _hoisted_5$2 = {
  key: 0,
  class: "dm-detail-grid"
};
const _hoisted_6$2 = {
  key: 1,
  class: "dm-detail-items"
};
const _hoisted_7$2 = { class: "dm-detail-item-title dm-detail-break" };
const _hoisted_8$2 = {
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

const {computed: computed$1} = await importShared('vue');



const _sfc_main$2 = {
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

const shownCount = computed$1(() => (props.items.length ? props.items.length : props.rows.length));

return (_ctx, _cache) => {
  return (_openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
    (__props.title)
      ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_2$2, _toDisplayString$2(__props.title), 1))
      : _createCommentVNode$2("", true),
    (__props.subtitle)
      ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_3$2, _toDisplayString$2(__props.subtitle), 1))
      : _createCommentVNode$2("", true),
    (__props.error)
      ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_4$2, _toDisplayString$2(__props.error), 1))
      : _createCommentVNode$2("", true),
    _renderSlot(_ctx.$slots, "actions", {}, undefined, true),
    _renderSlot(_ctx.$slots, "default", {}, () => [
      (__props.rows.length)
        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_5$2, [
            (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.rows, (row) => {
              return (_openBlock$2(), _createElementBlock$2("div", {
                key: `row-${row.label}`,
                class: "dm-detail-row"
              }, [
                _createElementVNode$2("span", null, _toDisplayString$2(row.label), 1),
                _createElementVNode$2("strong", null, _toDisplayString$2(row.value), 1)
              ]))
            }), 128))
          ]))
        : _createCommentVNode$2("", true),
      (__props.items.length)
        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_6$2, [
            (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.items, (item, index) => {
              return (_openBlock$2(), _createElementBlock$2("div", {
                key: `item-${index}`,
                class: "dm-detail-item"
              }, [
                _createElementVNode$2("div", _hoisted_7$2, _toDisplayString$2(item.title), 1),
                (item.meta)
                  ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_8$2, _toDisplayString$2(item.meta), 1))
                  : _createCommentVNode$2("", true)
              ]))
            }), 128))
          ]))
        : _createCommentVNode$2("", true),
      (__props.emptyText && !__props.rows.length && !__props.items.length)
        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_9$1, _toDisplayString$2(__props.emptyText), 1))
        : _createCommentVNode$2("", true),
      (__props.truncated)
        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_10$1, " 仅显示前 " + _toDisplayString$2(shownCount.value) + " 条，共 " + _toDisplayString$2(__props.total) + " 条（上限 " + _toDisplayString$2(__props.limit) + " 条）；可在「总览」页调整明细条数。 ", 1))
        : _createCommentVNode$2("", true)
    ], true),
    _renderSlot(_ctx.$slots, "appendix", {}, undefined, true)
  ]))
}
}

};
const ModuleDetailPanel = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-328ce9c4"]]);

const {normalizeClass:_normalizeClass$1,createElementVNode:_createElementVNode$1,toDisplayString:_toDisplayString$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,renderList:_renderList$1,Fragment:_Fragment$1} = await importShared('vue');


const _hoisted_1$1 = { class: "dm-module-header" };
const _hoisted_2$1 = { class: "dm-module-header-line" };
const _hoisted_3$1 = { class: "dm-module-title" };
const _hoisted_4$1 = { class: "dm-module-status" };
const _hoisted_5$1 = {
  key: 0,
  class: "dm-module-status dm-tone-warning"
};
const _hoisted_6$1 = {
  key: 1,
  class: "dm-module-status dm-tone-primary",
  role: "status"
};
const _hoisted_7$1 = {
  key: 2,
  class: "dm-module-status dm-tone-error",
  role: "status"
};
const _hoisted_8$1 = {
  key: 0,
  class: "dm-module-badges",
  "aria-label": "模块统计"
};


const _sfc_main$1 = {
  __name: 'ModuleHeader',
  props: {
  title: { type: String, required: true },
  icon: { type: String, default: 'mdi-view-module-outline' },
  enabled: { type: Boolean, default: false },
  observing: { type: Boolean, default: false },
  running: { type: Boolean, default: false },
  fault: { type: [Boolean, String], default: false },
  badges: { type: Array, default: () => [] },
},
  setup(__props) {


const tones = ['primary', 'secondary', 'success', 'warning', 'error'];

return (_ctx, _cache) => {
  return (_openBlock$1(), _createElementBlock$1("header", _hoisted_1$1, [
    _createElementVNode$1("div", _hoisted_2$1, [
      _createElementVNode$1("span", {
        class: _normalizeClass$1(["mdi dm-module-icon", [__props.icon, { 'dm-module-icon--enabled': __props.enabled }]]),
        "aria-hidden": "true"
      }, null, 2),
      _createElementVNode$1("h2", _hoisted_3$1, _toDisplayString$1(__props.title), 1),
      _createElementVNode$1("span", _hoisted_4$1, _toDisplayString$1(__props.enabled ? '已启用' : '已禁用'), 1),
      (__props.observing)
        ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_5$1, "观察模式"))
        : _createCommentVNode$1("", true),
      (__props.running)
        ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_6$1, "执行中"))
        : _createCommentVNode$1("", true),
      (__props.fault)
        ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_7$1, "故障" + _toDisplayString$1(typeof __props.fault === 'string' ? '：' + __props.fault : ''), 1))
        : _createCommentVNode$1("", true)
    ]),
    (__props.badges.length)
      ? (_openBlock$1(), _createElementBlock$1("ul", _hoisted_8$1, [
          (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(__props.badges, (badge, index) => {
            return (_openBlock$1(), _createElementBlock$1("li", {
              key: index,
              class: _normalizeClass$1(["dm-module-stat", tones.includes(badge.tone) ? 'dm-tone-' + badge.tone : ''])
            }, [
              _createElementVNode$1("span", null, _toDisplayString$1(badge.label), 1),
              _createElementVNode$1("span", null, _toDisplayString$1(badge.value), 1)
            ], 2))
          }), 128))
        ]))
      : _createCommentVNode$1("", true)
  ]))
}
}

};
const ModuleHeader = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-cab98917"]]);

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,withKeys:_withKeys,mergeProps:_mergeProps,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


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
  class: "dm-overview-band"
};
const _hoisted_7 = { class: "dm-overview-stat-grid" };
const _hoisted_8 = { class: "dm-overview-stat-content" };
const _hoisted_9 = { class: "dm-overview-stat-label dm-hint" };
const _hoisted_10 = { class: "dm-overview-stat-value" };
const _hoisted_11 = { class: "dm-overview-stat-desc dm-hint" };
const _hoisted_12 = { class: "dm-overview-section mt-3" };
const _hoisted_13 = { class: "dm-flow" };
const _hoisted_14 = { class: "dm-flow-label" };
const _hoisted_15 = { class: "dm-flow-row" };
const _hoisted_16 = { class: "dm-flow-step" };
const _hoisted_17 = {
  key: 0,
  class: "dm-attention-panel mt-3"
};
const _hoisted_18 = { class: "dm-section-heading" };
const _hoisted_19 = { class: "dm-attention-list" };
const _hoisted_20 = ["role", "tabindex", "onClick", "onKeyup"];
const _hoisted_21 = { class: "min-w-0" };
const _hoisted_22 = { class: "dm-hint dm-break-text" };
const _hoisted_23 = {
  key: 0,
  class: "dm-section-heading"
};
const _hoisted_24 = { class: "dm-module-grid mt-2" };
const _hoisted_25 = ["id"];
const _hoisted_26 = {
  key: 0,
  class: "dm-card-heading"
};
const _hoisted_27 = {
  key: 1,
  class: "dm-module-head"
};
const _hoisted_28 = { class: "min-w-0" };
const _hoisted_29 = { class: "dm-module-title dm-hint" };
const _hoisted_30 = { class: "dm-module-value" };
const _hoisted_31 = { class: "dm-hint dm-break-text" };
const _hoisted_32 = { key: 0 };
const _hoisted_33 = { class: "dm-module-actions" };
const _hoisted_34 = { class: "dm-module-detail" };
const _hoisted_35 = {
  key: 0,
  class: "dm-upload-status-grid"
};
const _hoisted_36 = { class: "dm-upload-status-head" };
const _hoisted_37 = { class: "min-w-0" };
const _hoisted_38 = { class: "dm-body-text" };
const _hoisted_39 = { class: "dm-hint" };
const _hoisted_40 = { class: "dm-upload-values" };
const _hoisted_41 = {
  key: 0,
  class: "dm-hint text-error mt-2 dm-break-text"
};
const _hoisted_42 = {
  key: 1,
  class: "dm-monitor-empty dm-hint"
};
const _hoisted_43 = {
  key: 2,
  class: "dm-upload-site-status"
};
const _hoisted_44 = { class: "min-w-0" };
const _hoisted_45 = { class: "dm-body-text" };
const _hoisted_46 = { class: "dm-hint" };
const _hoisted_47 = { class: "dm-hint" };
const _hoisted_48 = { class: "dm-hint" };
const _hoisted_49 = { class: "dm-hint" };
const _hoisted_50 = {
  key: 3,
  class: "dm-monitor-empty dm-hint"
};
const _hoisted_51 = {
  key: 0,
  class: "dm-module-detail-title"
};
const _hoisted_52 = {
  key: 1,
  class: "dm-module-detail-grid"
};
const _hoisted_53 = {
  key: 2,
  class: "dm-record-block mt-3",
  "data-record-block": "rename-history"
};
const _hoisted_54 = { class: "dm-record-block-head" };
const _hoisted_55 = { class: "dm-hint" };
const _hoisted_56 = ["aria-busy"];
const _hoisted_57 = {
  key: 0,
  role: "status",
  class: "dm-hint"
};
const _hoisted_58 = { class: "dm-table-scroll dm-desktop-table" };
const _hoisted_59 = { key: 0 };
const _hoisted_60 = { colspan: "5" };
const _hoisted_61 = { class: "dm-body-text text-no-wrap" };
const _hoisted_62 = ["title"];
const _hoisted_63 = ["title"];
const _hoisted_64 = { class: "d-flex ga-1" };
const _hoisted_65 = { class: "dm-mobile-list dm-history-list" };
const _hoisted_66 = { class: "dm-record-head" };
const _hoisted_67 = ["title"];
const _hoisted_68 = { class: "dm-record-meta" };
const _hoisted_69 = { class: "dm-record-row" };
const _hoisted_70 = { class: "dm-record-value" };
const _hoisted_71 = { class: "dm-record-row" };
const _hoisted_72 = ["title"];
const _hoisted_73 = { class: "dm-record-row" };
const _hoisted_74 = ["title"];
const _hoisted_75 = { class: "dm-record-actions" };
const _hoisted_76 = {
  key: 0,
  class: "d-flex align-center justify-center pa-3"
};
const _hoisted_77 = { class: "dm-hint mx-1" };
const _hoisted_78 = {
  key: 3,
  class: "dm-record-block mt-3",
  "data-record-block": "rename-archive"
};
const _hoisted_79 = { class: "dm-record-block-head" };
const _hoisted_80 = { class: "dm-hint" };
const _hoisted_81 = ["aria-busy"];
const _hoisted_82 = {
  key: 0,
  role: "status",
  class: "dm-hint"
};
const _hoisted_83 = { class: "dm-table-scroll dm-desktop-table" };
const _hoisted_84 = { key: 0 };
const _hoisted_85 = { colspan: "6" };
const _hoisted_86 = { class: "dm-body-text text-no-wrap" };
const _hoisted_87 = ["title"];
const _hoisted_88 = { class: "dm-body-text" };
const _hoisted_89 = ["title"];
const _hoisted_90 = { class: "d-flex ga-1" };
const _hoisted_91 = { class: "dm-mobile-list dm-archive-list" };
const _hoisted_92 = { class: "dm-record-head" };
const _hoisted_93 = ["title"];
const _hoisted_94 = { class: "dm-record-meta" };
const _hoisted_95 = { class: "dm-record-row" };
const _hoisted_96 = { class: "dm-record-value" };
const _hoisted_97 = { class: "dm-record-row" };
const _hoisted_98 = { class: "dm-record-value" };
const _hoisted_99 = { class: "dm-record-row" };
const _hoisted_100 = { class: "dm-record-value" };
const _hoisted_101 = { class: "dm-record-actions" };
const _hoisted_102 = {
  key: 0,
  class: "d-flex align-center justify-center pa-3"
};
const _hoisted_103 = { class: "dm-hint mx-1" };
const _hoisted_104 = {
  key: 4,
  class: "dm-record-block mt-3",
  "data-record-block": "autoremove-preview"
};
const _hoisted_105 = { class: "dm-record-block-head" };
const _hoisted_106 = {
  key: 0,
  class: "dm-hint dm-risk mt-2"
};
const _hoisted_107 = {
  key: 1,
  class: "dm-state text-center dm-hint"
};
const _hoisted_108 = { class: "dm-table-scroll dm-desktop-table mt-2" };
const _hoisted_109 = { class: "dm-body-text text-no-wrap" };
const _hoisted_110 = ["title"];
const _hoisted_111 = { class: "dm-body-text" };
const _hoisted_112 = { class: "dm-body-text text-no-wrap" };
const _hoisted_113 = { class: "dm-body-text" };
const _hoisted_114 = { class: "dm-body-text text-no-wrap" };
const _hoisted_115 = ["title"];
const _hoisted_116 = { class: "dm-mobile-list mt-2" };
const _hoisted_117 = { class: "dm-record-head" };
const _hoisted_118 = ["title"];
const _hoisted_119 = { class: "dm-record-meta" };
const _hoisted_120 = { class: "dm-record-row" };
const _hoisted_121 = { class: "dm-record-value" };
const _hoisted_122 = { class: "dm-record-row" };
const _hoisted_123 = { class: "dm-record-value" };
const _hoisted_124 = { class: "dm-record-row" };
const _hoisted_125 = { class: "dm-record-value" };
const _hoisted_126 = { class: "dm-record-row" };
const _hoisted_127 = { class: "dm-record-value" };
const _hoisted_128 = { class: "dm-record-row" };
const _hoisted_129 = { class: "dm-record-value" };
const _hoisted_130 = ["aria-busy"];
const _hoisted_131 = { class: "dm-record-block-head" };
const _hoisted_132 = { class: "dm-hint" };
const _hoisted_133 = { class: "d-flex flex-wrap ga-2 align-center" };
const _hoisted_134 = { class: "dm-table-scroll dm-desktop-table mt-2" };
const _hoisted_135 = { key: 0 };
const _hoisted_136 = { colspan: "6" };
const _hoisted_137 = ["title"];
const _hoisted_138 = {
  key: 0,
  class: "dm-hint"
};
const _hoisted_139 = { class: "dm-body-text text-no-wrap" };
const _hoisted_140 = { class: "dm-body-text text-no-wrap" };
const _hoisted_141 = { class: "dm-body-text" };
const _hoisted_142 = { class: "dm-mobile-list mt-2" };
const _hoisted_143 = { class: "dm-record-head" };
const _hoisted_144 = ["title"];
const _hoisted_145 = {
  key: 0,
  class: "dm-hint"
};
const _hoisted_146 = { class: "dm-record-meta" };
const _hoisted_147 = { class: "dm-record-row" };
const _hoisted_148 = { class: "dm-record-value" };
const _hoisted_149 = { class: "dm-record-row" };
const _hoisted_150 = { class: "dm-record-value" };
const _hoisted_151 = { class: "dm-record-row" };
const _hoisted_152 = { class: "dm-record-value" };
const _hoisted_153 = { class: "dm-record-actions" };
const _hoisted_154 = {
  key: 6,
  class: "dm-record-block mt-3",
  "data-record-block": "transfer-tasks"
};
const _hoisted_155 = { class: "dm-record-block-head" };
const _hoisted_156 = { class: "dm-hint" };
const _hoisted_157 = { class: "d-flex flex-wrap ga-2" };
const _hoisted_158 = { class: "d-flex flex-wrap ga-1 mt-2" };
const _hoisted_159 = {
  key: 0,
  class: "dm-state text-center dm-hint"
};
const _hoisted_160 = {
  key: 1,
  class: "dm-table-scroll dm-desktop-table mt-2"
};
const _hoisted_161 = ["title"];
const _hoisted_162 = { class: "dm-body-text" };
const _hoisted_163 = { class: "dm-body-text" };
const _hoisted_164 = ["title"];
const _hoisted_165 = ["title"];
const _hoisted_166 = {
  key: 0,
  class: "d-flex flex-wrap ga-1"
};
const _hoisted_167 = {
  key: 1,
  class: "dm-hint"
};
const _hoisted_168 = {
  key: 2,
  class: "dm-state text-center dm-hint"
};
const _hoisted_169 = {
  key: 3,
  class: "dm-table-scroll dm-desktop-table mt-2"
};
const _hoisted_170 = { class: "dm-body-text" };
const _hoisted_171 = ["title"];
const _hoisted_172 = { class: "dm-hint" };
const _hoisted_173 = { class: "dm-body-text text-no-wrap" };
const _hoisted_174 = { class: "d-flex flex-wrap ga-1" };
const _hoisted_175 = ["aria-busy"];
const _hoisted_176 = {
  key: 0,
  role: "status",
  class: "dm-hint"
};
const _hoisted_177 = { class: "dm-table-scroll dm-desktop-table mt-2" };
const _hoisted_178 = { key: 0 };
const _hoisted_179 = { colspan: "4" };
const _hoisted_180 = { class: "dm-body-text" };
const _hoisted_181 = ["title"];
const _hoisted_182 = { class: "dm-hint" };
const _hoisted_183 = { class: "d-flex flex-wrap ga-1 align-center" };
const _hoisted_184 = { class: "dm-body-text text-no-wrap" };
const _hoisted_185 = { class: "dm-mobile-list mt-2" };
const _hoisted_186 = { class: "d-flex align-center justify-space-between ga-2" };
const _hoisted_187 = { class: "dm-body-text dm-ellipsis" };
const _hoisted_188 = { class: "dm-hint mt-1" };
const _hoisted_189 = {
  key: 4,
  class: "d-flex align-center justify-center ga-2 mt-2"
};
const _hoisted_190 = { class: "dm-hint" };
const _hoisted_191 = {
  key: 7,
  class: "dm-record-block mt-3",
  "data-record-block": "tag-cleanup"
};
const _hoisted_192 = { class: "dm-cleanup-toolbar mt-2" };
const _hoisted_193 = {
  key: 2,
  class: "dm-state text-center dm-hint"
};
const _hoisted_194 = {
  key: 3,
  class: "dm-cleanup-results mt-4"
};
const _hoisted_195 = { class: "dm-cleanup-summary" };
const _hoisted_196 = { class: "dm-hint" };
const _hoisted_197 = { class: "d-flex ga-1 flex-wrap justify-end" };
const _hoisted_198 = { class: "dm-tag-group-head" };
const _hoisted_199 = { class: "d-flex align-center ga-2 min-w-0" };
const _hoisted_200 = { class: "dm-body-text" };
const _hoisted_201 = { class: "dm-hint" };
const _hoisted_202 = {
  key: 0,
  class: "dm-monitor-empty dm-hint"
};
const _hoisted_203 = {
  key: 1,
  class: "dm-tag-list"
};
const _hoisted_204 = { class: "dm-tag-content" };
const _hoisted_205 = { class: "dm-tag-line" };
const _hoisted_206 = ["title"];
const _hoisted_207 = { class: "dm-hint" };
const _hoisted_208 = ["title"];
const _hoisted_209 = { class: "dm-cleanup-actions" };
const _hoisted_210 = { class: "dm-hint" };
const _hoisted_211 = {
  key: 8,
  class: "dm-runtime-section mt-4",
  "data-runtime-section": "upload-limit"
};
const _hoisted_212 = { class: "dm-runtime-heading mt-2" };
const _hoisted_213 = { class: "dm-runtime-actions" };
const _hoisted_214 = { class: "dm-upload-summary mt-3" };
const _hoisted_215 = { class: "dm-monitor-metric" };
const _hoisted_216 = { class: "dm-monitor-metric" };
const _hoisted_217 = { class: "dm-monitor-metric" };
const _hoisted_218 = { class: "dm-monitor-metric" };
const _hoisted_219 = {
  key: 9,
  class: "dm-pane mt-4"
};
const _hoisted_220 = {
  key: 0,
  class: "dm-diagnostics mt-2"
};
const _hoisted_221 = { class: "dm-stat-grid mb-3" };
const _hoisted_222 = { class: "dm-stat" };
const _hoisted_223 = { class: "dm-section-title" };
const _hoisted_224 = { class: "dm-stat" };
const _hoisted_225 = { class: "dm-stat" };
const _hoisted_226 = { class: "dm-stat" };
const _hoisted_227 = { class: "dm-section-title" };
const _hoisted_228 = { class: "dm-hint" };
const _hoisted_229 = { class: "dm-diagnostics-panel mb-3" };
const _hoisted_230 = { class: "dm-diagnostics-head" };
const _hoisted_231 = { class: "dm-diagnostics-title" };
const _hoisted_232 = { class: "dm-diagnostics-icon" };
const _hoisted_233 = { class: "dm-diagnostics-score" };
const _hoisted_234 = { key: 0 };
const _hoisted_235 = { class: "dm-diagnostics-grid" };
const _hoisted_236 = { class: "dm-diagnostic-state" };
const _hoisted_237 = { class: "dm-diagnostic-content" };
const _hoisted_238 = { class: "dm-diagnostic-name" };
const _hoisted_239 = { class: "dm-diagnostic-value" };
const _hoisted_240 = { class: "dm-diagnostic-note dm-hint" };
const _hoisted_241 = { class: "dm-diagnostics-footer dm-hint" };
const _hoisted_242 = {
  key: 0,
  class: "dm-diagnostics-attention"
};
const _hoisted_243 = {
  key: 0,
  class: "dm-hint py-2"
};
const _hoisted_244 = {
  key: 1,
  class: "dm-table-scroll"
};
const _hoisted_245 = { class: "dm-body-text text-no-wrap" };
const _hoisted_246 = ["title"];
const _hoisted_247 = { class: "dm-body-text" };
const _hoisted_248 = {
  class: "dm-record-block mt-3",
  "data-record-block": "module-data-cleanup"
};
const _hoisted_249 = { class: "dm-cleanup-list mt-2" };
const _hoisted_250 = { class: "dm-cleanup-info" };
const _hoisted_251 = { class: "dm-body-text" };
const _hoisted_252 = { class: "dm-hint" };
const _hoisted_253 = {
  key: 1,
  class: "dm-state text-center dm-hint"
};
const {computed,nextTick,onBeforeUnmount,onMounted,reactive,ref,watch} = await importShared('vue');

const pageSize = 15;
const OVERVIEW_REFRESH_INTERVAL_MS = 30_000;

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
const DETAIL_LIMIT_CHOICES = [20, 50, 100, 200];
const detailLimit = ref(20);
const tabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'transfer', title: '转移做种', icon: 'mdi-swap-horizontal' },
  { key: 'history', title: '命名历史', icon: 'mdi-history' },
  { key: 'hr', title: 'H&R 任务', icon: 'mdi-timer-alert-outline' },
  { key: 'autoremove', title: '删种记录', icon: 'mdi-delete-clock-outline' },
  { key: 'failclean', title: '失败清理', icon: 'mdi-broom' },
  { key: 'sitetag', title: '站点标签', icon: 'mdi-tag-multiple' },
  { key: 'upload', title: '上传限速', icon: 'mdi-upload-network-outline' },
  { key: 'diagnostics', title: '运行诊断', icon: 'mdi-stethoscope' },
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
const runtimeFlows = [
  { label: '转移做种', steps: ['下载完成', '延迟等待', '目标转移', '公共链路'] },
  { label: '公共链路', steps: ['命名处理', '站点标签', '做种校验'] },
  { label: '上传限速', steps: ['全局限速', '站点识别', '按需设限', '合计限速', '动态调速', '停用恢复'] },
  { label: '兜底补刀', steps: ['异常命名', '定时补查', '失败计数', '归档恢复'] },
];

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
});
function recordTableState(key, rows, empty = 'none') {
  const state = recordStates[key];
  const hasResult = state.loaded || rows.length > 0;
  return {
    loading: state.loading && !hasResult,
    error: !hasResult ? state.error || false : false,
    refreshFailed: hasResult ? state.error || false : false,
    empty: rows.length ? '' : empty,
  }
}
const total = ref(0);
const archiveTotal = ref(0);
const page = ref(1);
const archivePage = ref(1);
const loading = ref(false);
const paging = ref(false);
const error = ref('');
const actionMsg = ref('');
const actionOk = ref(false);

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
    Pending: 'default',
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

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)));
const archiveTotalPages = computed(() => Math.max(1, Math.ceil((archiveTotal.value || 0) / pageSize)));

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
const diagnosticsAttentionCount = computed(() => diagnosticsCards.value.length - diagnosticsOkCount.value);

const uploadLimit = computed(() => overview.value?.upload_limit || {});
const uploadLimitDownloaderRows = computed(() => uploadLimit.value.downloaders || []);
const uploadLimitSiteRows = computed(() => uploadLimit.value.sites || []);
const uploadLimitStatus = computed(() => {
  const status = uploadLimit.value.service_status;
  return {
    disabled: { label: '未启用', color: 'default' },
    starting: { label: '启动中', color: 'info' },
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
const overviewCoreCards = computed(() => {
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
      icon: 'mdi-transfer',
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
      icon: 'mdi-timer-alert-outline',
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
      icon: 'mdi-delete-clock-outline',
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
      icon: 'mdi-broom',
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
      icon: 'mdi-auto-fix',
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
      icon: 'mdi-tag-multiple',
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
      icon: 'mdi-upload-network-outline',
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
const headerMetric = (label, value, tone) => ({ label, value: value ?? '—', tone });
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
  const up = uploadLimit.value;
  const headers = {
    transfer: {
      enabled: !!(cards.transfer?.enabled ?? config.transfer_enabled),
      badges: [
        headerMetric('在途', transfer.pending),
        headerMetric('今日成功', transfer.today_success ?? cards.transfer?.today_success),
        headerMetric('累计成功', transfer.success_total ?? cards.transfer?.success_total),
      ],
    },
    rename: {
      enabled: !!(cards.rename?.enabled ?? config.rename_enabled),
      running: !!renameStatus.value.batch_running,
      // The current rename snapshot has per-run, not persisted daily counters.
      badges: [headerMetric('今日成功'), headerMetric('今日失败'),
        headerMetric('待重试', archive.active_failed), headerMetric('失败归档', archive.archived)],
    },
    tag: {
      enabled: !!config.tag_enabled,
      // completed/skipped mix event and complement results, not a full round projection.
      badges: [headerMetric('本轮检查'), headerMetric('成功'), headerMetric('无需更新'), headerMetric('失败')],
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
      // The backend exposes action-specific success counts, but no combined skip count.
      badges: [headerMetric('上轮候选', auto.candidates),
        headerMetric('成功', auto.observe_only ? undefined : (auto.action === 'pause' ? auto.paused : auto.deleted)),
        headerMetric('跳过'), headerMetric('失败', auto.failed)],
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

const moduleGridCards = computed(() => {
  if (activeTab.value === 'overview') return moduleCards.value
  const key = tabModuleKeys[activeTab.value];
  return key ? moduleCards.value.filter(card => card.key === key) : []
});

function focusModule(key) {
  if (!key) return
  expandedModules[key] = true;
  void nextTick(() => {
    const element = document.getElementById(`dm-module-${key}`);
    if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

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
  const resp = await getApi('autoremove_status', { feedback: 'silent' }).catch(() => null);
  if (!isCurrentPageRequest(request) || !resp?.status) return
  autoremoveStatus.value = resp.status;
}

async function loadFailcleanStatus(request) {
  const resp = await getApi('failclean_status', { feedback: 'silent' }).catch(() => null);
  if (!isCurrentPageRequest(request) || !resp?.status) return
  failcleanStatus.value = resp.status;
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
const transferSummary = computed(() => transferStatus.value.summary || {});
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
  if (phase === 'target_added' || phase === 'stopped_after_add') return 'success'
  return 'grey'
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
  if (tag) badges.push({ text: `标签 ${tag}`, color: 'primary' });
  return badges
}

async function loadTransferStatus(request) {
  const recordRequest = beginRecordRequest(['transfer']);
  recordStates.transfer.loading = true;
  recordStates.transfer.error = '';
  try {
    const resp = await getApi(`transfer_status?page=${transferPage.value}&page_size=15`, { feedback: 'silent' });
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

function changeTransferPage(page) {
  const total = transferStatus.value.total_pages || 1;
  transferPage.value = Math.min(Math.max(1, page), total);
  void refreshActive();
}

async function loadDownloaders(request) {
  const resp = await getApi('downloaders', { feedback: 'silent' }).catch(() => null);
  if (!isCurrentPageRequest(request) || !Array.isArray(resp)) return
  downloaderItems.value = resp;
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
    const resp = await getApi(`rename_history?page=${page.value}&page_size=${pageSize}`);
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
    let resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${pageSize}`);
    if (!isCurrentRecordRequest(request, 'archive')) return
    const lastPage = Math.max(1, Math.ceil((resp?.total || 0) / pageSize));
    if (archivePage.value > lastPage) {
      archivePage.value = lastPage;
      resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${pageSize}`);
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

function moduleDetailVisible(key) {
  const detail = moduleDetail(key);
  return Boolean(detail.rows.length || detail.items.length || detail.error)
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

/** 模块卡上的清理按钮：严格对应后端白名单对象，未列出的模块不显示清理入口。 */
const MODULE_CLEANUP_KEYS = {
  // 重命名历史与归档是两个独立对象，不做「全部清理」
  rename: [
    { key: 'rename_history', label: '清理历史' },
    { key: 'rename_archive', label: '清理归档' },
  ],
  autoremove: [{ key: 'autoremove_state', label: '清理记录' }],
  failclean: [{ key: 'failclean_state', label: '清理记录' }],
};

function moduleRecordView(key) {
  return MODULE_RECORD_VIEWS[key] || null
}

function moduleCleanupButtons(key) {
  return (MODULE_CLEANUP_KEYS[key] || []).map(item => ({ ...item, count: cleanupCounts.value[item.key] || 0 }))
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
    actionOk.value = !!resp && resp.code !== 1;
    actionMsg.value = resp?.msg || (actionOk.value ? '清理完成' : '清理失败');
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
    actionOk.value = false;
    actionMsg.value = e?.message || '清理失败';
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
  actionOk.value = false;
  moduleRunning.value = key;
  try {
    const resp = await handler();
    actionOk.value = !!resp && resp.code !== 1;
    actionMsg.value = resp?.msg || (actionOk.value ? fallback : `${fallback.replace(/完成$|已触发$/, '')}失败`);
    return resp
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || `${fallback.replace(/完成$|已触发$/, '')}失败`;
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
  actionOk.value = false;
  hrClearing.value = true;
  hrClearKey.value = target ? `${target.downloader_id}-${target.torrent_hash}` : '';
  try {
    const payload = kind === 'task'
      ? { downloader_id: target?.downloader_id || '', torrent_hash: target?.torrent_hash || '' }
      : {};
    const resp = await postApi(`hr_clear_${kind}`, payload);
    actionOk.value = resp?.code === 0;
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '清除完成' : '清除失败');
    if (resp?.code !== 1) await refreshActive();
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '清除失败';
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

async function doRecovery(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  try {
    const resp = await postApi('recovery_torrent', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '恢复失败';
  }
}

async function doDelete(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  try {
    const resp = await postApi('delete_rename_history', { hash });
    actionOk.value = resp?.code === 0;
    actionMsg.value = resp?.msg || '已删除';
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '删除失败';
  }
}

async function doRetryRename(hash) {
  if (!hash || retryingHash.value) return
  actionMsg.value = '';
  actionOk.value = false;
  retryingHash.value = hash;
  try {
    const resp = await postApi('retry_rename', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败');
    actionOk.value = resp?.code === 0;
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '补刀失败';
  } finally {
    await reloadRecords();
    retryingHash.value = '';
  }
}

async function restoreArchive(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  restoringHash.value = hash;
  try {
    const resp = await postApi('restore_rename_archive', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已恢复' : '恢复失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '恢复失败';
  } finally {
    restoringHash.value = '';
  }
}

async function deleteArchive(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  deletingHash.value = hash;
  try {
    const resp = await postApi('delete_rename_archive', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已删除' : '删除失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await reloadRecords();
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '删除失败';
  } finally {
    deletingHash.value = '';
  }
}

async function reloadRecords() {
  const request = beginRecordRequest();
  await Promise.all([loadHistory(request), loadArchive(request)]);
}

function prevPage() {
  if (page.value <= 1 || paging.value) return
  paging.value = true;
  page.value--;
  void loadHistory(beginRecordRequest(['history']));
}
function nextPage() {
  if (page.value >= totalPages.value || paging.value) return
  paging.value = true;
  page.value++;
  void loadHistory(beginRecordRequest(['history']));
}
function prevArchivePage() {
  if (archivePage.value <= 1 || paging.value) return
  paging.value = true;
  archivePage.value--;
  void loadArchive(beginRecordRequest(['archive']));
}
function nextArchivePage() {
  if (archivePage.value >= archiveTotalPages.value || paging.value) return
  paging.value = true;
  archivePage.value++;
  void loadArchive(beginRecordRequest(['archive']));
}

const qbDownloaderItems = computed(() => downloaderItems.value.filter(item => item.type === 'qbittorrent'));
const cleanupGroups = computed(() => cleanupScan.value?.downloaders || []);
const cleanupAutoRemovedCount = computed(() => cleanupScan.value?.auto_removed?.length || 0);
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

function setAllCleanupTags(keep) {
  for (const group of cleanupGroups.value) {
    for (const item of group.tags || []) cleanupKeep[tagSelectionKey(group.name, item.tag)] = keep;
  }
}

function cleanupKindMeta(kind) {
  return {
    site: { label: '站点', color: 'primary' },
    managed: { label: '业务', color: 'success' },
    temporary: { label: '临时', color: 'warning' },
    legacy_temporary: { label: '旧临时', color: 'warning' },
    legacy_candidate: { label: '疑似旧临时', color: 'warning' },
    active_temporary: { label: '使用中', color: 'info' },
    other: { label: '其他', color: 'default' },
  }[kind] || { label: '其他', color: 'default' }
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

function previewCleanupTags() {
  if (!cleanupRemovals.value.length) {
    cleanupStatus.value = 'warning';
    cleanupMessage.value = '没有需要清理的标签';
    return
  }
  cleanupDialog.value = true;
}

async function executeCleanupTags() {
  cleanupExecuting.value = true;
  try {
    const response = await postJsonApi('tag_cleanup_execute', { removals: cleanupRemovals.value });
    cleanupDialog.value = false;
    await scanCleanupTags();
    cleanupStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error');
    cleanupMessage.value = response?.msg || '清理完成';
  } catch (error) {
    cleanupStatus.value = 'error';
    cleanupMessage.value = error?.message || '清理失败';
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
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VExpandTransition = _resolveComponent("VExpandTransition");
  const _component_VTable = _resolveComponent("VTable");
  const _component_VCheckboxBtn = _resolveComponent("VCheckboxBtn");
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
        _cache[32] || (_cache[32] = _createElementVNode("div", { class: "dm-title" }, "下载中心", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-refresh",
          class: "text-none me-2",
          onClick: _cache[0] || (_cache[0] = $event => (refreshActive())),
          loading: loading.value
        }, {
          default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
            _createTextVNode("刷新数据", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-cog-outline",
          class: "text-none",
          onClick: _cache[1] || (_cache[1] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
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
              type: actionOk.value ? 'success' : 'error',
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
        (loading.value && !['history', 'transfer', 'hr'].includes(activeTab.value))
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
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewCoreCards.value, (card) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: card.title,
                          class: _normalizeClass(["dm-overview-stat", `dm-overview-stat--${card.color}`])
                        }, [
                          _createVNode(_component_VAvatar, {
                            color: card.color,
                            variant: "tonal",
                            size: "32",
                            rounded: "lg"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VIcon, {
                                icon: card.icon,
                                size: "18"
                              }, null, 8, ["icon"])
                            ]),
                            _: 2
                          }, 1032, ["color"]),
                          _createElementVNode("div", _hoisted_8, [
                            _createElementVNode("div", _hoisted_9, _toDisplayString(card.title), 1),
                            _createElementVNode("div", _hoisted_10, _toDisplayString(card.value), 1),
                            _createElementVNode("div", _hoisted_11, _toDisplayString(card.desc), 1)
                          ])
                        ], 2))
                      }), 128))
                    ]),
                    _createElementVNode("div", _hoisted_12, [
                      _cache[33] || (_cache[33] = _createElementVNode("div", { class: "dm-section-title" }, "运行链路", -1)),
                      _createElementVNode("div", _hoisted_13, [
                        (_openBlock(), _createElementBlock(_Fragment, null, _renderList(runtimeFlows, (flow) => {
                          return _createElementVNode("div", {
                            key: flow.label,
                            class: "dm-flow-block"
                          }, [
                            _createElementVNode("div", _hoisted_14, _toDisplayString(flow.label), 1),
                            _createElementVNode("div", _hoisted_15, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(flow.steps, (step, index) => {
                                return (_openBlock(), _createElementBlock(_Fragment, {
                                  key: `${flow.label}-${step}`
                                }, [
                                  _createElementVNode("span", _hoisted_16, _toDisplayString(step), 1),
                                  (index < flow.steps.length - 1)
                                    ? (_openBlock(), _createBlock(_component_VIcon, {
                                        key: 0,
                                        class: "dm-flow-arrow",
                                        icon: "mdi-arrow-right",
                                        size: "14"
                                      }))
                                    : _createCommentVNode("", true)
                                ], 64))
                              }), 128))
                            ])
                          ])
                        }), 64))
                      ])
                    ]),
                    (overviewAttentionItems.value.length)
                      ? (_openBlock(), _createElementBlock("section", _hoisted_17, [
                          _createElementVNode("div", _hoisted_18, [
                            _cache[34] || (_cache[34] = _createElementVNode("div", null, [
                              _createElementVNode("div", { class: "dm-section-title" }, "需要关注"),
                              _createElementVNode("div", { class: "dm-hint" }, "点击条目可展开对应模块卡并定位。")
                            ], -1)),
                            _createVNode(_component_VChip, {
                              color: "warning",
                              size: "small",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(overviewAttentionItems.value.length) + " 项", 1)
                              ]),
                              _: 1
                            })
                          ]),
                          _createElementVNode("div", _hoisted_19, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewAttentionItems.value, (item) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: `${item.title}-${item.detail}`,
                                class: _normalizeClass(["dm-attention-item", { 'dm-attention-item--linked': !!item.target }]),
                                role: item.target ? 'button' : null,
                                tabindex: item.target ? 0 : null,
                                onClick: $event => (focusModule(item.target)),
                                onKeyup: _withKeys($event => (focusModule(item.target)), ["enter"])
                              }, [
                                _createVNode(_component_VIcon, {
                                  icon: item.icon,
                                  color: item.color,
                                  size: "18"
                                }, null, 8, ["icon", "color"]),
                                _createElementVNode("div", _hoisted_21, [
                                  _createElementVNode("strong", null, _toDisplayString(item.title), 1),
                                  _createElementVNode("div", _hoisted_22, _toDisplayString(item.detail), 1)
                                ])
                              ], 42, _hoisted_20))
                            }), 128))
                          ])
                        ]))
                      : _createCommentVNode("", true)
                  ]))
                : _createCommentVNode("", true),
              (moduleGridCards.value.length)
                ? (_openBlock(), _createElementBlock("section", {
                    key: 1,
                    class: _normalizeClass(["dm-module-section", activeTab.value === 'overview' ? 'mt-4' : 'mt-3'])
                  }, [
                    (activeTab.value === 'overview')
                      ? (_openBlock(), _createElementBlock("div", _hoisted_23, [
                          _cache[35] || (_cache[35] = _createElementVNode("div", null, [
                            _createElementVNode("div", { class: "dm-section-title" }, "功能状态与操作"),
                            _createElementVNode("div", { class: "dm-hint" }, "每个模块卡给出状态摘要与手动操作，需要时展开查看运行明细，明细条数可调。")
                          ], -1)),
                          _createVNode(_component_VSelect, {
                            density: "compact",
                            modelValue: detailLimit.value,
                            "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((detailLimit).value = $event)),
                            items: DETAIL_LIMIT_CHOICES,
                            label: "明细条数",
                            variant: "outlined",
                            "hide-details": "",
                            class: "dm-detail-limit-select"
                          }, null, 8, ["modelValue"])
                        ]))
                      : _createCommentVNode("", true),
                    _createElementVNode("div", _hoisted_24, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(moduleGridCards.value, (card) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: card.key,
                          id: `dm-module-${card.key}`,
                          class: "dm-module-card"
                        }, [
                          (moduleHeaders.value[card.key])
                            ? (_openBlock(), _createElementBlock("div", _hoisted_26, [
                                _createVNode(ModuleHeader, _mergeProps({ ref_for: true }, moduleHeaders.value[card.key]), null, 16),
                                (moduleRecordView(card.key))
                                  ? (_openBlock(), _createBlock(_component_VBtn, {
                                      key: 0,
                                      size: "small",
                                      variant: "text",
                                      class: "text-none dm-card-data-link",
                                      "prepend-icon": "mdi-text-box-search-outline",
                                      onClick: $event => (openModuleRecords(card.key))
                                    }, {
                                      default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                                        _createTextVNode("查看数据", -1)
                                      ]))]),
                                      _: 1
                                    }, 8, ["onClick"]))
                                  : _createCommentVNode("", true)
                              ]))
                            : (_openBlock(), _createElementBlock("div", _hoisted_27, [
                                _createVNode(_component_VAvatar, {
                                  color: card.color,
                                  variant: "tonal",
                                  size: "30",
                                  rounded: "lg"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_VIcon, {
                                      icon: card.icon,
                                      size: "17"
                                    }, null, 8, ["icon"])
                                  ]),
                                  _: 2
                                }, 1032, ["color"]),
                                _createElementVNode("div", _hoisted_28, [
                                  _createElementVNode("div", _hoisted_29, _toDisplayString(card.title), 1),
                                  _createElementVNode("div", _hoisted_30, _toDisplayString(card.value), 1)
                                ])
                              ])),
                          _createElementVNode("div", _hoisted_31, [
                            (moduleHeaders.value[card.key])
                              ? (_openBlock(), _createElementBlock("span", _hoisted_32, _toDisplayString(card.value) + " · ", 1))
                              : _createCommentVNode("", true),
                            _createTextVNode(_toDisplayString(card.desc), 1)
                          ]),
                          _createElementVNode("div", _hoisted_33, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(card.actions, (action) => {
                              return (_openBlock(), _createBlock(_component_VBtn, {
                                size: "small",
                                key: action.key,
                                variant: "tonal",
                                color: action.color || 'primary',
                                "prepend-icon": action.icon,
                                class: "text-none",
                                loading: moduleRunning.value === action.key,
                                disabled: moduleRunning.value !== '' && moduleRunning.value !== action.key,
                                onClick: $event => (action.run())
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(action.label), 1)
                                ]),
                                _: 2
                              }, 1032, ["color", "prepend-icon", "loading", "disabled", "onClick"]))
                            }), 128)),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(moduleCleanupButtons(card.key), (item) => {
                              return (_openBlock(), _createBlock(_component_VBtn, {
                                size: "small",
                                key: item.key,
                                variant: "text",
                                class: "text-none",
                                color: "warning",
                                "prepend-icon": "mdi-delete-sweep-outline",
                                disabled: item.count === 0,
                                onClick: $event => (openCleanupDialog(item.key))
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.label), 1)
                                ]),
                                _: 2
                              }, 1032, ["disabled", "onClick"]))
                            }), 128)),
                            _createVNode(_component_VBtn, {
                              size: "small",
                              variant: "text",
                              class: "text-none ml-auto",
                              "append-icon": expandedModules[card.key] ? 'mdi-chevron-up' : 'mdi-chevron-down',
                              onClick: $event => (expandedModules[card.key] = !expandedModules[card.key])
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(expandedModules[card.key] ? '收起' : '详情'), 1)
                              ]),
                              _: 2
                            }, 1032, ["append-icon", "onClick"])
                          ]),
                          _createVNode(_component_VExpandTransition, null, {
                            default: _withCtx(() => [
                              _withDirectives(_createElementVNode("div", _hoisted_34, [
                                (card.key === 'upload_limit')
                                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(uploadLimit.value.errors || [], (runtimeError) => {
                                        return (_openBlock(), _createBlock(_component_VAlert, {
                                          key: runtimeError,
                                          type: "error",
                                          variant: "tonal",
                                          density: "compact",
                                          class: "mb-2"
                                        }, {
                                          default: _withCtx(() => [
                                            _createTextVNode(_toDisplayString(runtimeError), 1)
                                          ]),
                                          _: 2
                                        }, 1024))
                                      }), 128)),
                                      _createVNode(ModuleDetailPanel, {
                                        class: "mt-3",
                                        title: "运行明细",
                                        rows: moduleDetail('upload_limit').rows,
                                        error: moduleDetail('upload_limit').error
                                      }, {
                                        appendix: _withCtx(() => [
                                          _cache[43] || (_cache[43] = _createElementVNode("div", { class: "dm-module-detail-title mt-3" }, "下载器状态", -1)),
                                          (uploadLimitDownloaderRows.value.length)
                                            ? (_openBlock(), _createElementBlock("div", _hoisted_35, [
                                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(uploadLimitDownloaderRows.value, (item) => {
                                                  return (_openBlock(), _createElementBlock("div", {
                                                    key: item.id,
                                                    class: "dm-upload-status-card"
                                                  }, [
                                                    _createElementVNode("div", _hoisted_36, [
                                                      _createElementVNode("div", _hoisted_37, [
                                                        _createElementVNode("strong", _hoisted_38, _toDisplayString(item.id), 1),
                                                        _createElementVNode("div", _hoisted_39, _toDisplayString(item.type === 'transmission' ? 'Transmission' : 'qBittorrent'), 1)
                                                      ]),
                                                      _createVNode(_component_VChip, {
                                                        size: "x-small",
                                                        color: item.error ? 'warning' : 'success',
                                                        variant: "tonal"
                                                      }, {
                                                        default: _withCtx(() => [
                                                          _createTextVNode(_toDisplayString(item.error ? '异常' : '正常'), 1)
                                                        ]),
                                                        _: 2
                                                      }, 1032, ["color"])
                                                    ]),
                                                    _createElementVNode("div", _hoisted_40, [
                                                      _createElementVNode("span", null, [
                                                        _cache[37] || (_cache[37] = _createTextVNode("实时 ", -1)),
                                                        _createElementVNode("strong", null, _toDisplayString(formatUploadRate(item.upload_rate_bps)), 1)
                                                      ]),
                                                      _createElementVNode("span", null, [
                                                        _createTextVNode(_toDisplayString(item.type === 'transmission' ? 'Session 全局上限' : 'QB 全局上限') + " ", 1),
                                                        _createElementVNode("strong", null, _toDisplayString(item.total_limit_kib) + " KiB/s", 1)
                                                      ]),
                                                      _createElementVNode("span", null, [
                                                        _cache[38] || (_cache[38] = _createTextVNode("受限任务 ", -1)),
                                                        _createElementVNode("strong", null, _toDisplayString(item.managed_torrents || 0), 1)
                                                      ]),
                                                      _createElementVNode("span", null, [
                                                        _cache[39] || (_cache[39] = _createTextVNode("宽限任务 ", -1)),
                                                        _createElementVNode("strong", null, _toDisplayString(item.grace_torrents || 0), 1)
                                                      ])
                                                    ]),
                                                    (item.error)
                                                      ? (_openBlock(), _createElementBlock("div", _hoisted_41, _toDisplayString(item.error), 1))
                                                      : _createCommentVNode("", true)
                                                  ]))
                                                }), 128))
                                              ]))
                                            : (_openBlock(), _createElementBlock("div", _hoisted_42, "当前没有启用的限速下载器")),
                                          _cache[44] || (_cache[44] = _createElementVNode("div", { class: "dm-module-detail-title mt-3" }, "受限站点", -1)),
                                          (uploadLimitSiteRows.value.length)
                                            ? (_openBlock(), _createElementBlock("div", _hoisted_43, [
                                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(uploadLimitSiteRows.value, (item) => {
                                                  return (_openBlock(), _createElementBlock("div", {
                                                    key: item.key,
                                                    class: "dm-upload-site-status-row"
                                                  }, [
                                                    _createElementVNode("div", _hoisted_44, [
                                                      _createElementVNode("strong", _hoisted_45, _toDisplayString(item.name), 1),
                                                      _createElementVNode("div", _hoisted_46, _toDisplayString(item.torrent_count) + " 个任务 · " + _toDisplayString(item.downloaders?.join('、')), 1)
                                                    ]),
                                                    _createElementVNode("span", _hoisted_47, [
                                                      _cache[40] || (_cache[40] = _createTextVNode("实时 ", -1)),
                                                      _createElementVNode("strong", null, _toDisplayString(formatUploadRate(item.upload_rate_bps)), 1)
                                                    ]),
                                                    _createElementVNode("span", _hoisted_48, [
                                                      _cache[41] || (_cache[41] = _createTextVNode("站点额度 ", -1)),
                                                      _createElementVNode("strong", null, _toDisplayString(item.allocated_kib) + " KiB/s", 1)
                                                    ]),
                                                    _createElementVNode("span", _hoisted_49, [
                                                      _cache[42] || (_cache[42] = _createTextVNode("站点上限 ", -1)),
                                                      _createElementVNode("strong", null, _toDisplayString(item.limit_kib) + " KiB/s", 1)
                                                    ])
                                                  ]))
                                                }), 128))
                                              ]))
                                            : (_openBlock(), _createElementBlock("div", _hoisted_50, "当前没有填写正数上限的受限站点")),
                                          _cache[45] || (_cache[45] = _createElementVNode("div", { class: "dm-hint mt-2" }, "实时速率是下载器当前实际上传流量；站点额度是插件写入单种限速的合计值，两者不是同一指标。", -1))
                                        ]),
                                        _: 1
                                      }, 8, ["rows", "error"])
                                    ], 64))
                                  : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                      (card.detailTitle)
                                        ? (_openBlock(), _createElementBlock("div", _hoisted_51, _toDisplayString(card.detailTitle), 1))
                                        : _createCommentVNode("", true),
                                      (card.details?.length)
                                        ? (_openBlock(), _createElementBlock("div", _hoisted_52, [
                                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(card.details, (row) => {
                                              return (_openBlock(), _createElementBlock("div", {
                                                key: row.label,
                                                class: "dm-module-detail-row"
                                              }, [
                                                _createElementVNode("span", null, _toDisplayString(row.label), 1),
                                                _createElementVNode("strong", null, _toDisplayString(detailValue(row.value)), 1)
                                              ]))
                                            }), 128))
                                          ]))
                                        : _createCommentVNode("", true),
                                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(card.notes || [], (note) => {
                                        return (_openBlock(), _createElementBlock("div", {
                                          key: note.text,
                                          class: _normalizeClass(["dm-hint mt-2", { 'dm-risk': note.type === 'warning', 'dm-error': note.type === 'error' }])
                                        }, [
                                          (note.type === 'warning' || note.type === 'error')
                                            ? (_openBlock(), _createBlock(_component_VIcon, {
                                                key: 0,
                                                icon: note.type === 'error' ? 'mdi-alert-circle-outline' : 'mdi-alert-outline',
                                                size: "16"
                                              }, null, 8, ["icon"]))
                                            : _createCommentVNode("", true),
                                          _createTextVNode(_toDisplayString(note.text), 1)
                                        ], 2))
                                      }), 128)),
                                      (moduleDetailVisible(card.key))
                                        ? (_openBlock(), _createBlock(ModuleDetailPanel, {
                                            key: 2,
                                            class: "mt-3",
                                            title: "运行明细",
                                            rows: moduleDetail(card.key).rows,
                                            items: moduleDetail(card.key).items,
                                            total: moduleDetail(card.key).total,
                                            limit: moduleDetail(card.key).limit,
                                            truncated: moduleDetail(card.key).truncated,
                                            error: moduleDetail(card.key).error
                                          }, null, 8, ["rows", "items", "total", "limit", "truncated", "error"]))
                                        : _createCommentVNode("", true)
                                    ], 64))
                              ], 512), [
                                [_vShow, expandedModules[card.key]]
                              ])
                            ]),
                            _: 2
                          }, 1024)
                        ], 8, _hoisted_25))
                      }), 128))
                    ])
                  ], 2))
                : _createCommentVNode("", true),
              (activeTab.value === 'history')
                ? (_openBlock(), _createElementBlock("div", _hoisted_53, [
                    _createElementVNode("div", _hoisted_54, [
                      _createElementVNode("div", null, [
                        _cache[46] || (_cache[46] = _createElementVNode("div", { class: "dm-record-block-title" }, "命名历史", -1)),
                        _createElementVNode("div", _hoisted_55, "共 " + _toDisplayString(total.value) + " 条，逐条可补刀、恢复原始名称或删除记录。", 1)
                      ]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        "prepend-icon": "mdi-auto-fix",
                        class: "text-none",
                        loading: moduleRunning.value === 'rename-retry' || renameStatus.value.batch_running,
                        disabled: (moduleRunning.value !== '' && moduleRunning.value !== 'rename-retry') || renameStatus.value.batch_running,
                        onClick: doRetryRenames
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(renameStatus.value.batch_running ? '重试中…' : '重试'), 1)
                        ]),
                        _: 1
                      }, 8, ["loading", "disabled"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        "prepend-icon": "mdi-radar",
                        class: "text-none ml-2",
                        loading: moduleRunning.value === 'rename-scan',
                        disabled: moduleRunning.value !== '' && moduleRunning.value !== 'rename-scan',
                        onClick: doRenameScan
                      }, {
                        default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                          _createTextVNode("扫描重命名", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading", "disabled"])
                    ]),
                    _createElementVNode("div", {
                      "data-record-state": "history",
                      "aria-busy": recordStates.history.loading
                    }, [
                      (recordStates.history.loading && (recordStates.history.loaded || records.value.length))
                        ? (_openBlock(), _createElementBlock("p", _hoisted_57, "正在刷新记录，保留上次结果"))
                        : _createCommentVNode("", true),
                      _createElementVNode("div", _hoisted_58, [
                        _createVNode(_component_VTable, {
                          density: "compact",
                          class: "dm-table"
                        }, {
                          default: _withCtx(() => [
                            _cache[51] || (_cache[51] = _createElementVNode("thead", null, [
                              _createElementVNode("tr", null, [
                                _createElementVNode("th", { class: "dm-table-head" }, "时间"),
                                _createElementVNode("th", { class: "dm-table-head" }, "原始名称"),
                                _createElementVNode("th", { class: "dm-table-head" }, "命名后"),
                                _createElementVNode("th", { class: "dm-table-head" }, "状态"),
                                _createElementVNode("th", { class: "dm-table-head" }, "操作")
                              ])
                            ], -1)),
                            _createElementVNode("tbody", null, [
                              (!records.value.length || recordStates.history.error)
                                ? (_openBlock(), _createElementBlock("tr", _hoisted_59, [
                                    _createElementVNode("td", _hoisted_60, [
                                      _createVNode(TableState, _mergeProps(recordTableState('history', records.value), {
                                        onRetry: _cache[4] || (_cache[4] = $event => (loadHistory(beginRecordRequest(['history']))))
                                      }), null, 16)
                                    ])
                                  ]))
                                : _createCommentVNode("", true),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(records.value, (r) => {
                                return (_openBlock(), _createElementBlock("tr", {
                                  key: r.hash
                                }, [
                                  _createElementVNode("td", _hoisted_61, _toDisplayString(r.time), 1),
                                  _createElementVNode("td", {
                                    class: "dm-body-text dm-ellipsis",
                                    title: r.original_name
                                  }, _toDisplayString(r.original_name), 9, _hoisted_62),
                                  _createElementVNode("td", {
                                    class: "dm-body-text dm-ellipsis",
                                    title: r.after_name
                                  }, _toDisplayString(r.after_name), 9, _hoisted_63),
                                  _createElementVNode("td", null, [
                                    _createVNode(_component_VChip, {
                                      size: "x-small",
                                      color: r.success ? 'success' : 'error',
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(r.success ? '成功' : (r.reason || '失败')), 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["color"])
                                  ]),
                                  _createElementVNode("td", null, [
                                    _createElementVNode("div", _hoisted_64, [
                                      _createVNode(_component_VBtn, {
                                        size: "small",
                                        variant: "tonal",
                                        color: "primary",
                                        onClick: $event => (doRetryRename(r.hash)),
                                        loading: retryingHash.value === r.hash
                                      }, {
                                        default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                                          _createTextVNode("重试", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["onClick", "loading"]),
                                      (r.success)
                                        ? (_openBlock(), _createBlock(_component_VBtn, {
                                            key: 0,
                                            size: "small",
                                            variant: "tonal",
                                            color: "warning",
                                            onClick: $event => (doRecovery(r.hash))
                                          }, {
                                            default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                                              _createTextVNode("恢复名称", -1)
                                            ]))]),
                                            _: 1
                                          }, 8, ["onClick"]))
                                        : _createCommentVNode("", true),
                                      _createVNode(_component_VBtn, {
                                        size: "small",
                                        variant: "text",
                                        color: "error",
                                        onClick: $event => (doDelete(r.hash))
                                      }, {
                                        default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
                                          _createTextVNode("删除记录", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["onClick"])
                                    ])
                                  ])
                                ]))
                              }), 128))
                            ])
                          ]),
                          _: 1
                        })
                      ]),
                      _createElementVNode("div", _hoisted_65, [
                        _createVNode(TableState, _mergeProps(recordTableState('history', records.value), {
                          onRetry: _cache[5] || (_cache[5] = $event => (loadHistory(beginRecordRequest(['history']))))
                        }), null, 16),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(records.value, (r) => {
                          return (_openBlock(), _createElementBlock("article", {
                            key: r.hash,
                            class: "dm-record-card dm-history-card"
                          }, [
                            _createElementVNode("div", _hoisted_66, [
                              _createElementVNode("div", {
                                class: "dm-record-title",
                                title: r.after_name || r.original_name
                              }, _toDisplayString(r.after_name || r.original_name || r.hash), 9, _hoisted_67),
                              _createVNode(_component_VChip, {
                                class: "dm-record-status",
                                size: "x-small",
                                color: r.success ? 'success' : 'error',
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(r.success ? '成功' : (r.reason || '失败')), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("div", _hoisted_68, [
                              _createElementVNode("div", _hoisted_69, [
                                _cache[52] || (_cache[52] = _createElementVNode("span", { class: "dm-record-label" }, "时间", -1)),
                                _createElementVNode("span", _hoisted_70, _toDisplayString(r.time || '-'), 1)
                              ]),
                              _createElementVNode("div", _hoisted_71, [
                                _cache[53] || (_cache[53] = _createElementVNode("span", { class: "dm-record-label" }, "原始", -1)),
                                _createElementVNode("span", {
                                  class: "dm-record-value",
                                  title: r.original_name
                                }, _toDisplayString(r.original_name || '-'), 9, _hoisted_72)
                              ]),
                              _createElementVNode("div", _hoisted_73, [
                                _cache[54] || (_cache[54] = _createElementVNode("span", { class: "dm-record-label" }, "命名后", -1)),
                                _createElementVNode("span", {
                                  class: "dm-record-value",
                                  title: r.after_name
                                }, _toDisplayString(r.after_name || '-'), 9, _hoisted_74)
                              ])
                            ]),
                            _createElementVNode("div", _hoisted_75, [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                color: "primary",
                                "prepend-icon": "mdi-auto-fix",
                                onClick: $event => (doRetryRename(r.hash)),
                                loading: retryingHash.value === r.hash
                              }, {
                                default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                                  _createTextVNode("重试", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick", "loading"]),
                              (r.success)
                                ? (_openBlock(), _createBlock(_component_VBtn, {
                                    key: 0,
                                    size: "small",
                                    variant: "tonal",
                                    color: "warning",
                                    "prepend-icon": "mdi-undo",
                                    onClick: $event => (doRecovery(r.hash))
                                  }, {
                                    default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                                      _createTextVNode("恢复名称", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["onClick"]))
                                : _createCommentVNode("", true),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "text",
                                color: "error",
                                "prepend-icon": "mdi-delete-outline",
                                onClick: $event => (doDelete(r.hash))
                              }, {
                                default: _withCtx(() => [...(_cache[57] || (_cache[57] = [
                                  _createTextVNode("删除记录", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick"])
                            ])
                          ]))
                        }), 128))
                      ])
                    ], 8, _hoisted_56),
                    (records.value.length && total.value > pageSize)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_76, [
                          _createVNode(_component_VBtn, {
                            size: "small",
                            "aria-label": "上一页",
                            variant: "tonal",
                            icon: "mdi-chevron-left",
                            disabled: page.value <= 1 || paging.value,
                            onClick: prevPage,
                            class: "mr-2"
                          }, null, 8, ["disabled"]),
                          _createElementVNode("span", _hoisted_77, _toDisplayString(page.value) + " / " + _toDisplayString(totalPages.value) + "（共 " + _toDisplayString(total.value) + " 条）", 1),
                          _createVNode(_component_VBtn, {
                            size: "small",
                            "aria-label": "下一页",
                            variant: "tonal",
                            icon: "mdi-chevron-right",
                            disabled: page.value >= totalPages.value || paging.value,
                            onClick: nextPage,
                            class: "ml-2"
                          }, null, 8, ["disabled"])
                        ]))
                      : _createCommentVNode("", true)
                  ]))
                : _createCommentVNode("", true),
              (activeTab.value === 'history')
                ? (_openBlock(), _createElementBlock("div", _hoisted_78, [
                    _createElementVNode("div", _hoisted_79, [
                      _createElementVNode("div", null, [
                        _cache[58] || (_cache[58] = _createElementVNode("div", { class: "dm-record-block-title" }, "重命名归档", -1)),
                        _createElementVNode("div", _hoisted_80, "共 " + _toDisplayString(archiveTotal.value) + " 条连续失败后归档的记录，可补刀、恢复或删除。", 1)
                      ])
                    ]),
                    _createElementVNode("div", {
                      "data-record-state": "archive",
                      "aria-busy": recordStates.archive.loading
                    }, [
                      (recordStates.archive.loading && (recordStates.archive.loaded || archiveRecords.value.length))
                        ? (_openBlock(), _createElementBlock("p", _hoisted_82, "正在刷新记录，保留上次结果"))
                        : _createCommentVNode("", true),
                      _createElementVNode("div", _hoisted_83, [
                        _createVNode(_component_VTable, {
                          density: "compact",
                          class: "dm-table"
                        }, {
                          default: _withCtx(() => [
                            _cache[62] || (_cache[62] = _createElementVNode("thead", null, [
                              _createElementVNode("tr", null, [
                                _createElementVNode("th", { class: "dm-table-head" }, "归档时间"),
                                _createElementVNode("th", { class: "dm-table-head" }, "名称"),
                                _createElementVNode("th", { class: "dm-table-head" }, "分类"),
                                _createElementVNode("th", { class: "dm-table-head" }, "次数"),
                                _createElementVNode("th", { class: "dm-table-head" }, "原因"),
                                _createElementVNode("th", { class: "dm-table-head" }, "操作")
                              ])
                            ], -1)),
                            _createElementVNode("tbody", null, [
                              (!archiveRecords.value.length || recordStates.archive.error)
                                ? (_openBlock(), _createElementBlock("tr", _hoisted_84, [
                                    _createElementVNode("td", _hoisted_85, [
                                      _createVNode(TableState, _mergeProps(recordTableState('archive', archiveRecords.value), {
                                        onRetry: _cache[6] || (_cache[6] = $event => (loadArchive(beginRecordRequest(['archive']))))
                                      }), null, 16)
                                    ])
                                  ]))
                                : _createCommentVNode("", true),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveRecords.value, (r) => {
                                return (_openBlock(), _createElementBlock("tr", {
                                  key: r.hash
                                }, [
                                  _createElementVNode("td", _hoisted_86, _toDisplayString(r.archived_at || r.last_failed_at), 1),
                                  _createElementVNode("td", {
                                    class: "dm-body-text dm-ellipsis",
                                    title: r.name
                                  }, _toDisplayString(r.name || r.hash), 9, _hoisted_87),
                                  _createElementVNode("td", null, [
                                    _createVNode(_component_VChip, {
                                      size: "x-small",
                                      color: "warning",
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(r.category_label || r.category), 1)
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ]),
                                  _createElementVNode("td", _hoisted_88, _toDisplayString(r.fail_count), 1),
                                  _createElementVNode("td", {
                                    class: "dm-body-text dm-ellipsis",
                                    title: r.archive_reason || r.reason
                                  }, _toDisplayString(r.archive_reason || r.reason), 9, _hoisted_89),
                                  _createElementVNode("td", null, [
                                    _createElementVNode("div", _hoisted_90, [
                                      _createVNode(_component_VBtn, {
                                        size: "small",
                                        variant: "tonal",
                                        color: "primary",
                                        onClick: $event => (doRetryRename(r.hash)),
                                        loading: retryingHash.value === r.hash,
                                        disabled: !!retryingHash.value || restoringHash.value === r.hash || deletingHash.value === r.hash
                                      }, {
                                        default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                                          _createTextVNode("重试", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["onClick", "loading", "disabled"]),
                                      _createVNode(_component_VBtn, {
                                        size: "small",
                                        variant: "tonal",
                                        color: "primary",
                                        onClick: $event => (restoreArchive(r.hash)),
                                        loading: restoringHash.value === r.hash,
                                        disabled: retryingHash.value === r.hash
                                      }, {
                                        default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
                                          _createTextVNode("恢复记录", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["onClick", "loading", "disabled"]),
                                      _createVNode(_component_VBtn, {
                                        size: "small",
                                        variant: "text",
                                        color: "error",
                                        onClick: $event => (deleteArchive(r.hash)),
                                        loading: deletingHash.value === r.hash,
                                        disabled: retryingHash.value === r.hash
                                      }, {
                                        default: _withCtx(() => [...(_cache[61] || (_cache[61] = [
                                          _createTextVNode("删除记录", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["onClick", "loading", "disabled"])
                                    ])
                                  ])
                                ]))
                              }), 128))
                            ])
                          ]),
                          _: 1
                        })
                      ]),
                      _createElementVNode("div", _hoisted_91, [
                        _createVNode(TableState, _mergeProps(recordTableState('archive', archiveRecords.value), {
                          onRetry: _cache[7] || (_cache[7] = $event => (loadArchive(beginRecordRequest(['archive']))))
                        }), null, 16),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveRecords.value, (r) => {
                          return (_openBlock(), _createElementBlock("article", {
                            key: r.hash,
                            class: "dm-record-card dm-archive-card"
                          }, [
                            _createElementVNode("div", _hoisted_92, [
                              _createElementVNode("div", {
                                class: "dm-record-title",
                                title: r.name || r.hash
                              }, _toDisplayString(r.name || r.hash), 9, _hoisted_93),
                              _createVNode(_component_VChip, {
                                class: "dm-record-status",
                                size: "x-small",
                                color: "warning",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(r.category_label || r.category), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _createElementVNode("div", _hoisted_94, [
                              _createElementVNode("div", _hoisted_95, [
                                _cache[63] || (_cache[63] = _createElementVNode("span", { class: "dm-record-label" }, "归档", -1)),
                                _createElementVNode("span", _hoisted_96, _toDisplayString(r.archived_at || r.last_failed_at || '-'), 1)
                              ]),
                              _createElementVNode("div", _hoisted_97, [
                                _cache[64] || (_cache[64] = _createElementVNode("span", { class: "dm-record-label" }, "次数", -1)),
                                _createElementVNode("span", _hoisted_98, _toDisplayString(r.fail_count), 1)
                              ]),
                              _createElementVNode("div", _hoisted_99, [
                                _cache[65] || (_cache[65] = _createElementVNode("span", { class: "dm-record-label" }, "原因", -1)),
                                _createElementVNode("span", _hoisted_100, _toDisplayString(r.archive_reason || r.reason || '-'), 1)
                              ])
                            ]),
                            _createElementVNode("div", _hoisted_101, [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                color: "primary",
                                "prepend-icon": "mdi-auto-fix",
                                onClick: $event => (doRetryRename(r.hash)),
                                loading: retryingHash.value === r.hash,
                                disabled: !!retryingHash.value || restoringHash.value === r.hash || deletingHash.value === r.hash
                              }, {
                                default: _withCtx(() => [...(_cache[66] || (_cache[66] = [
                                  _createTextVNode("重试", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick", "loading", "disabled"]),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                color: "warning",
                                "prepend-icon": "mdi-undo",
                                onClick: $event => (restoreArchive(r.hash)),
                                loading: restoringHash.value === r.hash,
                                disabled: retryingHash.value === r.hash
                              }, {
                                default: _withCtx(() => [...(_cache[67] || (_cache[67] = [
                                  _createTextVNode("恢复记录", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick", "loading", "disabled"]),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "text",
                                color: "error",
                                "prepend-icon": "mdi-delete-outline",
                                onClick: $event => (deleteArchive(r.hash)),
                                loading: deletingHash.value === r.hash,
                                disabled: retryingHash.value === r.hash
                              }, {
                                default: _withCtx(() => [...(_cache[68] || (_cache[68] = [
                                  _createTextVNode("删除记录", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick", "loading", "disabled"])
                            ])
                          ]))
                        }), 128))
                      ])
                    ], 8, _hoisted_81),
                    (archiveRecords.value.length && archiveTotal.value > pageSize)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_102, [
                          _createVNode(_component_VBtn, {
                            size: "small",
                            "aria-label": "上一页",
                            variant: "tonal",
                            icon: "mdi-chevron-left",
                            disabled: archivePage.value <= 1 || paging.value,
                            onClick: prevArchivePage,
                            class: "mr-2"
                          }, null, 8, ["disabled"]),
                          _createElementVNode("span", _hoisted_103, _toDisplayString(archivePage.value) + " / " + _toDisplayString(archiveTotalPages.value) + "（共 " + _toDisplayString(archiveTotal.value) + " 条）", 1),
                          _createVNode(_component_VBtn, {
                            size: "small",
                            "aria-label": "下一页",
                            variant: "tonal",
                            icon: "mdi-chevron-right",
                            disabled: archivePage.value >= archiveTotalPages.value || paging.value,
                            onClick: nextArchivePage,
                            class: "ml-2"
                          }, null, 8, ["disabled"])
                        ]))
                      : _createCommentVNode("", true)
                  ]))
                : _createCommentVNode("", true),
              (activeTab.value === 'autoremove')
                ? (_openBlock(), _createElementBlock("div", _hoisted_104, [
                    _createElementVNode("div", _hoisted_105, [
                      _cache[69] || (_cache[69] = _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "dm-record-block-title" }, "删种预览记录"),
                        _createElementVNode("div", { class: "dm-hint" }, " 自动删种的候选清单；点「预览」重新收集候选，不写下载器。 ")
                      ], -1)),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal",
                        color: autoremovePreview.value ? 'primary' : 'default'
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(autoremovePreview.value ? `预览命中 ${autoremoveRows.value.length} 个候选` : `上轮候选 ${autoremoveRows.value.length} 个`), 1)
                        ]),
                        _: 1
                      }, 8, ["color"])
                    ]),
                    (autoremoveStatus.value.observe_only)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_106, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[70] || (_cache[70] = _createTextVNode(" 迁移观察期：仅列出候选，不执行下载器写操作。 ", -1))
                        ]))
                      : _createCommentVNode("", true),
                    (autoremoveRows.value.length === 0)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_107, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-delete-clock-outline",
                            size: "48",
                            color: "grey-lighten-1",
                            class: "mb-2"
                          }),
                          _cache[71] || (_cache[71] = _createElementVNode("div", null, "暂无候选记录", -1))
                        ]))
                      : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                          _createElementVNode("div", _hoisted_108, [
                            _createVNode(_component_VTable, {
                              density: "compact",
                              class: "dm-table"
                            }, {
                              default: _withCtx(() => [
                                _cache[72] || (_cache[72] = _createElementVNode("thead", null, [
                                  _createElementVNode("tr", null, [
                                    _createElementVNode("th", { class: "dm-table-head" }, "下载器"),
                                    _createElementVNode("th", { class: "dm-table-head" }, "名称"),
                                    _createElementVNode("th", { class: "dm-table-head" }, "站点"),
                                    _createElementVNode("th", { class: "dm-table-head" }, "体积"),
                                    _createElementVNode("th", { class: "dm-table-head" }, "分享率"),
                                    _createElementVNode("th", { class: "dm-table-head" }, "做种时长"),
                                    _createElementVNode("th", { class: "dm-table-head" }, "原因")
                                  ])
                                ], -1)),
                                _createElementVNode("tbody", null, [
                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(autoremoveRows.value, (item) => {
                                    return (_openBlock(), _createElementBlock("tr", {
                                      key: `${item.downloader_id}-${item.torrent_hash}`
                                    }, [
                                      _createElementVNode("td", _hoisted_109, _toDisplayString(item.downloader_id), 1),
                                      _createElementVNode("td", {
                                        class: "dm-body-text dm-ellipsis",
                                        title: item.name
                                      }, _toDisplayString(item.name), 9, _hoisted_110),
                                      _createElementVNode("td", _hoisted_111, _toDisplayString(item.site || '-'), 1),
                                      _createElementVNode("td", _hoisted_112, _toDisplayString(item.size_text), 1),
                                      _createElementVNode("td", _hoisted_113, _toDisplayString(item.ratio), 1),
                                      _createElementVNode("td", _hoisted_114, _toDisplayString(item.seeding_hours) + " 小时", 1),
                                      _createElementVNode("td", {
                                        class: "dm-body-text dm-ellipsis",
                                        title: item.reason
                                      }, _toDisplayString(item.reason), 9, _hoisted_115)
                                    ]))
                                  }), 128))
                                ])
                              ]),
                              _: 1
                            })
                          ]),
                          _createElementVNode("div", _hoisted_116, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(autoremoveRows.value, (item) => {
                              return (_openBlock(), _createElementBlock("article", {
                                key: `${item.downloader_id}-${item.torrent_hash}`,
                                class: "dm-record-card"
                              }, [
                                _createElementVNode("div", _hoisted_117, [
                                  _createElementVNode("div", {
                                    class: "dm-record-title",
                                    title: item.name
                                  }, _toDisplayString(item.name), 9, _hoisted_118),
                                  _createVNode(_component_VChip, {
                                    class: "dm-record-status",
                                    size: "x-small",
                                    color: "warning",
                                    variant: "tonal"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(item.reason), 1)
                                    ]),
                                    _: 2
                                  }, 1024)
                                ]),
                                _createElementVNode("div", _hoisted_119, [
                                  _createElementVNode("div", _hoisted_120, [
                                    _cache[73] || (_cache[73] = _createElementVNode("span", { class: "dm-record-label" }, "下载器", -1)),
                                    _createElementVNode("span", _hoisted_121, _toDisplayString(item.downloader_id), 1)
                                  ]),
                                  _createElementVNode("div", _hoisted_122, [
                                    _cache[74] || (_cache[74] = _createElementVNode("span", { class: "dm-record-label" }, "站点", -1)),
                                    _createElementVNode("span", _hoisted_123, _toDisplayString(item.site || '-'), 1)
                                  ]),
                                  _createElementVNode("div", _hoisted_124, [
                                    _cache[75] || (_cache[75] = _createElementVNode("span", { class: "dm-record-label" }, "体积", -1)),
                                    _createElementVNode("span", _hoisted_125, _toDisplayString(item.size_text), 1)
                                  ]),
                                  _createElementVNode("div", _hoisted_126, [
                                    _cache[76] || (_cache[76] = _createElementVNode("span", { class: "dm-record-label" }, "分享率", -1)),
                                    _createElementVNode("span", _hoisted_127, _toDisplayString(item.ratio), 1)
                                  ]),
                                  _createElementVNode("div", _hoisted_128, [
                                    _cache[77] || (_cache[77] = _createElementVNode("span", { class: "dm-record-label" }, "做种", -1)),
                                    _createElementVNode("span", _hoisted_129, _toDisplayString(item.seeding_hours) + " 小时", 1)
                                  ])
                                ])
                              ]))
                            }), 128))
                          ])
                        ], 64))
                  ]))
                : _createCommentVNode("", true),
              (activeTab.value === 'hr')
                ? (_openBlock(), _createElementBlock("div", {
                    key: 5,
                    class: "dm-record-block mt-3",
                    "data-record-block": "hr-tasks",
                    "data-record-state": "hr",
                    "aria-busy": recordStates.hr.loading
                  }, [
                    _createElementVNode("div", _hoisted_131, [
                      _createElementVNode("div", null, [
                        _cache[78] || (_cache[78] = _createElementVNode("div", { class: "dm-record-block-title" }, "H&R 任务", -1)),
                        _createElementVNode("div", _hoisted_132, "任务总数 " + _toDisplayString(hrSummary.value.total || 0) + " · 达标 " + _toDisplayString(hrSummary.value.compliant || 0) + " · 超期 " + _toDisplayString(hrSummary.value.overdue || 0) + " · 需做种 " + _toDisplayString(hrSummary.value.needs_seeding || 0), 1)
                      ]),
                      _createElementVNode("div", _hoisted_133, [
                        _createVNode(_component_VSelect, {
                          modelValue: hrStatusFilter.value,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((hrStatusFilter).value = $event)),
                          items: hrStatusFilterOptions,
                          label: "状态筛选",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          class: "dm-hr-filter"
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "tonal",
                          "prepend-icon": "mdi-check-decagram-outline",
                          class: "text-none",
                          onClick: _cache[9] || (_cache[9] = $event => (askHrClear('compliant'))),
                          disabled: hrClearing.value || !(hrSummary.value.compliant || 0)
                        }, {
                          default: _withCtx(() => [...(_cache[79] || (_cache[79] = [
                            _createTextVNode("清理达标记录", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"]),
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "tonal",
                          "prepend-icon": "mdi-link-off",
                          class: "text-none",
                          onClick: _cache[10] || (_cache[10] = $event => (askHrClear('missing'))),
                          disabled: hrClearing.value || !(hrSummary.value.needs_seeding || 0)
                        }, {
                          default: _withCtx(() => [...(_cache[80] || (_cache[80] = [
                            _createTextVNode("清理失效记录", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_134, [
                      _createVNode(_component_VTable, {
                        density: "compact",
                        class: "dm-table"
                      }, {
                        default: _withCtx(() => [
                          _cache[82] || (_cache[82] = _createElementVNode("thead", null, [
                            _createElementVNode("tr", null, [
                              _createElementVNode("th", { class: "dm-table-head" }, "种子"),
                              _createElementVNode("th", { class: "dm-table-head" }, "状态"),
                              _createElementVNode("th", { class: "dm-table-head" }, "剩余时长"),
                              _createElementVNode("th", { class: "dm-table-head" }, "截止日期"),
                              _createElementVNode("th", { class: "dm-table-head" }, "做种进度"),
                              _createElementVNode("th", { class: "dm-table-head" }, "操作")
                            ])
                          ], -1)),
                          _createElementVNode("tbody", null, [
                            (!hrTaskRows.value.length || recordStates.hr.error)
                              ? (_openBlock(), _createElementBlock("tr", _hoisted_135, [
                                  _createElementVNode("td", _hoisted_136, [
                                    _createVNode(TableState, _mergeProps(recordTableState('hr', hrTaskRows.value, hrStatusFilter.value !== 'all' ? 'filtered' : 'none'), {
                                      onRetry: _cache[11] || (_cache[11] = $event => (loadHrStatus(beginPageRequest())))
                                    }), null, 16)
                                  ])
                                ]))
                              : _createCommentVNode("", true),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(hrTaskRows.value, (task) => {
                              return (_openBlock(), _createElementBlock("tr", {
                                key: `${task.downloader_id}-${task.torrent_hash}`
                              }, [
                                _createElementVNode("td", {
                                  class: "dm-body-text dm-ellipsis",
                                  title: task.name || task.torrent_hash
                                }, [
                                  _createTextVNode(_toDisplayString(hrTaskTitle(task)), 1),
                                  (task.site)
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_138, " · " + _toDisplayString(task.site), 1))
                                    : _createCommentVNode("", true)
                                ], 8, _hoisted_137),
                                _createElementVNode("td", null, [
                                  _createVNode(_component_VChip, {
                                    size: "x-small",
                                    color: hrStatusColor(task.status),
                                    variant: "tonal"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(task.status_text || task.status), 1)
                                    ]),
                                    _: 2
                                  }, 1032, ["color"])
                                ]),
                                _createElementVNode("td", _hoisted_139, _toDisplayString(formatDuration(task.remain_seconds)), 1),
                                _createElementVNode("td", _hoisted_140, _toDisplayString(formatTimestamp(task.deadline)), 1),
                                _createElementVNode("td", _hoisted_141, _toDisplayString(formatPercent(task.progress)), 1),
                                _createElementVNode("td", null, [
                                  _createVNode(_component_VBtn, {
                                    size: "small",
                                    variant: "text",
                                    color: "error",
                                    loading: hrClearing.value && hrClearKey.value === `${task.downloader_id}-${task.torrent_hash}`,
                                    onClick: $event => (askHrClear('task', task))
                                  }, {
                                    default: _withCtx(() => [...(_cache[81] || (_cache[81] = [
                                      _createTextVNode("清理记录", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["loading", "onClick"])
                                ])
                              ]))
                            }), 128))
                          ])
                        ]),
                        _: 1
                      })
                    ]),
                    _createElementVNode("div", _hoisted_142, [
                      (!hrTaskRows.value.length || recordStates.hr.error)
                        ? (_openBlock(), _createBlock(TableState, _mergeProps({ key: 0 }, recordTableState('hr', hrTaskRows.value, hrStatusFilter.value !== 'all' ? 'filtered' : 'none'), {
                            onRetry: _cache[12] || (_cache[12] = $event => (loadHrStatus(beginPageRequest())))
                          }), null, 16))
                        : _createCommentVNode("", true),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(hrTaskRows.value, (task) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: `${task.downloader_id}-${task.torrent_hash}`,
                          class: "dm-record-card"
                        }, [
                          _createElementVNode("div", _hoisted_143, [
                            _createElementVNode("div", {
                              class: "dm-record-title",
                              title: task.name || task.torrent_hash
                            }, [
                              _createTextVNode(_toDisplayString(hrTaskTitle(task)), 1),
                              (task.site)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_145, " · " + _toDisplayString(task.site), 1))
                                : _createCommentVNode("", true)
                            ], 8, _hoisted_144),
                            _createVNode(_component_VChip, {
                              class: "dm-record-status",
                              size: "x-small",
                              color: hrStatusColor(task.status),
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(task.status_text || task.status), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"])
                          ]),
                          _createElementVNode("div", _hoisted_146, [
                            _createElementVNode("div", _hoisted_147, [
                              _cache[83] || (_cache[83] = _createElementVNode("span", { class: "dm-record-label" }, "剩余", -1)),
                              _createElementVNode("span", _hoisted_148, _toDisplayString(formatDuration(task.remain_seconds)), 1)
                            ]),
                            _createElementVNode("div", _hoisted_149, [
                              _cache[84] || (_cache[84] = _createElementVNode("span", { class: "dm-record-label" }, "截止", -1)),
                              _createElementVNode("span", _hoisted_150, _toDisplayString(formatTimestamp(task.deadline)), 1)
                            ]),
                            _createElementVNode("div", _hoisted_151, [
                              _cache[85] || (_cache[85] = _createElementVNode("span", { class: "dm-record-label" }, "进度", -1)),
                              _createElementVNode("span", _hoisted_152, _toDisplayString(formatPercent(task.progress)), 1)
                            ])
                          ]),
                          _createElementVNode("div", _hoisted_153, [
                            _createVNode(_component_VBtn, {
                              size: "small",
                              variant: "text",
                              color: "error",
                              loading: hrClearing.value && hrClearKey.value === `${task.downloader_id}-${task.torrent_hash}`,
                              onClick: $event => (askHrClear('task', task))
                            }, {
                              default: _withCtx(() => [...(_cache[86] || (_cache[86] = [
                                _createTextVNode("清理记录", -1)
                              ]))]),
                              _: 1
                            }, 8, ["loading", "onClick"])
                          ])
                        ]))
                      }), 128))
                    ])
                  ], 8, _hoisted_130))
                : _createCommentVNode("", true),
              (activeTab.value === 'transfer')
                ? (_openBlock(), _createElementBlock("div", _hoisted_154, [
                    _createElementVNode("div", _hoisted_155, [
                      _createElementVNode("div", null, [
                        _cache[87] || (_cache[87] = _createElementVNode("div", { class: "dm-record-block-title" }, "任务配置", -1)),
                        _createElementVNode("div", _hoisted_156, "启用任务 " + _toDisplayString(transferTasks.value.length) + " 条 · 在途 " + _toDisplayString(transferSummary.value.pending || 0) + " · 已完成 " + _toDisplayString(transferSummary.value.completed || 0) + " · 累计成功 " + _toDisplayString(transferSummary.value.success_total || 0), 1)
                      ]),
                      _createElementVNode("div", _hoisted_157, [
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          "prepend-icon": "mdi-refresh",
                          class: "text-none",
                          onClick: refreshActive
                        }, {
                          default: _withCtx(() => [...(_cache[88] || (_cache[88] = [
                            _createTextVNode("刷新数据", -1)
                          ]))]),
                          _: 1
                        })
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_158, [
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal",
                        color: "primary"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("在途 " + _toDisplayString(transferSummary.value.pending || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal",
                        color: transferSummary.value.rollback ? 'error' : 'grey'
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("回滚 " + _toDisplayString(transferSummary.value.rollback || 0), 1)
                        ]),
                        _: 1
                      }, 8, ["color"]),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal",
                        color: "success"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("今日成功 " + _toDisplayString(transferSummary.value.today_success || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal",
                        color: "primary"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("累计成功 " + _toDisplayString(transferSummary.value.success_total || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal",
                        color: "warning"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("兜底成功 " + _toDisplayString(transferSummary.value.fallback_success || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal",
                        color: "info"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("H&R 保护 " + _toDisplayString(transferSummary.value.hr_protected || 0), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _cache[101] || (_cache[101] = _createElementVNode("div", { class: "dm-section-title mt-4" }, "任务配置", -1)),
                    (!transferTasks.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_159, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-swap-horizontal",
                            size: "48",
                            color: "grey-lighten-1",
                            class: "mb-2"
                          }),
                          _cache[89] || (_cache[89] = _createElementVNode("div", null, "暂无启用的转移任务", -1))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_160, [
                          _createVNode(_component_VTable, {
                            density: "compact",
                            class: "dm-table"
                          }, {
                            default: _withCtx(() => [
                              _cache[90] || (_cache[90] = _createElementVNode("thead", null, [
                                _createElementVNode("tr", null, [
                                  _createElementVNode("th", { class: "dm-table-head" }, "名称"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "源下载器"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "目的下载器"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "数据映射"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "筛选条件"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "设置")
                                ])
                              ], -1)),
                              _createElementVNode("tbody", null, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(transferTasks.value, (task) => {
                                  return (_openBlock(), _createElementBlock("tr", {
                                    key: task.name
                                  }, [
                                    _createElementVNode("td", {
                                      class: "dm-body-text dm-ellipsis",
                                      title: task.name
                                    }, _toDisplayString(task.name), 9, _hoisted_161),
                                    _createElementVNode("td", _hoisted_162, _toDisplayString(task.from_downloader), 1),
                                    _createElementVNode("td", _hoisted_163, _toDisplayString(task.to_downloader), 1),
                                    _createElementVNode("td", {
                                      class: "dm-body-text dm-ellipsis",
                                      title: `${task.from_path} → ${task.to_path}`
                                    }, _toDisplayString(task.from_path) + " → " + _toDisplayString(task.to_path), 9, _hoisted_164),
                                    _createElementVNode("td", {
                                      class: "dm-body-text dm-ellipsis",
                                      title: transferFilterText(task)
                                    }, _toDisplayString(transferFilterText(task)), 9, _hoisted_165),
                                    _createElementVNode("td", null, [
                                      (transferSettingBadges(task).length)
                                        ? (_openBlock(), _createElementBlock("div", _hoisted_166, [
                                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(transferSettingBadges(task), (badge) => {
                                              return (_openBlock(), _createBlock(_component_VChip, {
                                                key: badge.text,
                                                size: "x-small",
                                                variant: "tonal",
                                                color: badge.color
                                              }, {
                                                default: _withCtx(() => [
                                                  _createTextVNode(_toDisplayString(badge.text), 1)
                                                ]),
                                                _: 2
                                              }, 1032, ["color"]))
                                            }), 128))
                                          ]))
                                        : (_openBlock(), _createElementBlock("span", _hoisted_167, "默认"))
                                    ])
                                  ]))
                                }), 128))
                              ])
                            ]),
                            _: 1
                          })
                        ])),
                    _cache[102] || (_cache[102] = _createElementVNode("div", { class: "dm-section-title mt-4" }, "在途事务", -1)),
                    (!transferPending.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_168, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-check-circle-outline",
                            size: "48",
                            color: "grey-lighten-1",
                            class: "mb-2"
                          }),
                          _cache[91] || (_cache[91] = _createElementVNode("div", null, "暂无在途转移事务", -1))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_169, [
                          _createVNode(_component_VTable, {
                            density: "compact",
                            class: "dm-table"
                          }, {
                            default: _withCtx(() => [
                              _cache[96] || (_cache[96] = _createElementVNode("thead", null, [
                                _createElementVNode("tr", null, [
                                  _createElementVNode("th", { class: "dm-table-head" }, "源 → 目的"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "种子"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "阶段"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "已等待"),
                                  _createElementVNode("th", { class: "dm-table-head" }, "选项")
                                ])
                              ], -1)),
                              _createElementVNode("tbody", null, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(transferPending.value, (item) => {
                                  return (_openBlock(), _createElementBlock("tr", {
                                    key: item.key
                                  }, [
                                    _createElementVNode("td", _hoisted_170, _toDisplayString(item.source_downloader) + " → " + _toDisplayString(item.downloader), 1),
                                    _createElementVNode("td", {
                                      class: "dm-body-text dm-ellipsis",
                                      title: item.source_hash
                                    }, [
                                      _createTextVNode(_toDisplayString(transferPrimaryText(item)), 1),
                                      _createElementVNode("span", _hoisted_172, " · " + _toDisplayString(transferSecondaryText(item)), 1)
                                    ], 8, _hoisted_171),
                                    _createElementVNode("td", null, [
                                      _createVNode(_component_VChip, {
                                        size: "x-small",
                                        variant: "tonal",
                                        color: transferPhaseColor(item.phase)
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(transferPhaseText(item.phase)), 1)
                                        ]),
                                        _: 2
                                      }, 1032, ["color"])
                                    ]),
                                    _createElementVNode("td", _hoisted_173, _toDisplayString(item.waited_minutes) + " 分钟", 1),
                                    _createElementVNode("td", null, [
                                      _createElementVNode("div", _hoisted_174, [
                                        (item.fallback)
                                          ? (_openBlock(), _createBlock(_component_VChip, {
                                              key: 0,
                                              size: "x-small",
                                              variant: "tonal",
                                              color: "warning"
                                            }, {
                                              default: _withCtx(() => [...(_cache[92] || (_cache[92] = [
                                                _createTextVNode("兜底", -1)
                                              ]))]),
                                              _: 1
                                            }))
                                          : _createCommentVNode("", true),
                                        (item.skipverify)
                                          ? (_openBlock(), _createBlock(_component_VChip, {
                                              key: 1,
                                              size: "x-small",
                                              variant: "tonal",
                                              color: "info"
                                            }, {
                                              default: _withCtx(() => [...(_cache[93] || (_cache[93] = [
                                                _createTextVNode("跳过校验", -1)
                                              ]))]),
                                              _: 1
                                            }))
                                          : _createCommentVNode("", true),
                                        (item.autostart)
                                          ? (_openBlock(), _createBlock(_component_VChip, {
                                              key: 2,
                                              size: "x-small",
                                              variant: "tonal",
                                              color: "primary"
                                            }, {
                                              default: _withCtx(() => [...(_cache[94] || (_cache[94] = [
                                                _createTextVNode("自动开始", -1)
                                              ]))]),
                                              _: 1
                                            }))
                                          : _createCommentVNode("", true),
                                        (item.delete_source)
                                          ? (_openBlock(), _createBlock(_component_VChip, {
                                              key: 3,
                                              size: "x-small",
                                              variant: "tonal",
                                              color: "error"
                                            }, {
                                              default: _withCtx(() => [...(_cache[95] || (_cache[95] = [
                                                _createTextVNode("删源种", -1)
                                              ]))]),
                                              _: 1
                                            }))
                                          : _createCommentVNode("", true)
                                      ])
                                    ])
                                  ]))
                                }), 128))
                              ])
                            ]),
                            _: 1
                          })
                        ])),
                    _cache[103] || (_cache[103] = _createElementVNode("div", { class: "dm-section-title mt-4" }, "最近记录", -1)),
                    _createElementVNode("div", {
                      "data-record-state": "transfer",
                      "aria-busy": recordStates.transfer.loading
                    }, [
                      (recordStates.transfer.loading && (recordStates.transfer.loaded || transferRecords.value.length))
                        ? (_openBlock(), _createElementBlock("p", _hoisted_176, "正在刷新记录，保留上次结果"))
                        : _createCommentVNode("", true),
                      _createElementVNode("div", _hoisted_177, [
                        _createVNode(_component_VTable, {
                          density: "compact",
                          class: "dm-table"
                        }, {
                          default: _withCtx(() => [
                            _cache[100] || (_cache[100] = _createElementVNode("thead", null, [
                              _createElementVNode("tr", null, [
                                _createElementVNode("th", { class: "dm-table-head" }, "源 → 目的"),
                                _createElementVNode("th", { class: "dm-table-head" }, "种子"),
                                _createElementVNode("th", { class: "dm-table-head" }, "状态"),
                                _createElementVNode("th", { class: "dm-table-head" }, "更新时间")
                              ])
                            ], -1)),
                            _createElementVNode("tbody", null, [
                              (!transferRecords.value.length || recordStates.transfer.error)
                                ? (_openBlock(), _createElementBlock("tr", _hoisted_178, [
                                    _createElementVNode("td", _hoisted_179, [
                                      _createVNode(TableState, _mergeProps(recordTableState('transfer', transferRecords.value), {
                                        onRetry: _cache[13] || (_cache[13] = $event => (refreshActive()))
                                      }), null, 16)
                                    ])
                                  ]))
                                : _createCommentVNode("", true),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(transferRecords.value, (record) => {
                                return (_openBlock(), _createElementBlock("tr", {
                                  key: `${record.source_downloader}-${record.source_hash}-${record.downloader}`
                                }, [
                                  _createElementVNode("td", _hoisted_180, _toDisplayString(record.source_downloader) + " → " + _toDisplayString(record.downloader), 1),
                                  _createElementVNode("td", {
                                    class: "dm-body-text dm-ellipsis",
                                    title: record.source_hash
                                  }, [
                                    _createTextVNode(_toDisplayString(transferPrimaryText(record)), 1),
                                    _createElementVNode("span", _hoisted_182, " · " + _toDisplayString(transferSecondaryText(record)), 1)
                                  ], 8, _hoisted_181),
                                  _createElementVNode("td", null, [
                                    _createElementVNode("div", _hoisted_183, [
                                      _createVNode(_component_VChip, {
                                        size: "x-small",
                                        variant: "tonal",
                                        color: transferPhaseColor(record.phase)
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(transferPhaseText(record.phase)), 1)
                                        ]),
                                        _: 2
                                      }, 1032, ["color"]),
                                      (record.delete_source)
                                        ? (_openBlock(), _createBlock(_component_VChip, {
                                            key: 0,
                                            size: "x-small",
                                            variant: "tonal",
                                            color: "error"
                                          }, {
                                            default: _withCtx(() => [...(_cache[97] || (_cache[97] = [
                                              _createTextVNode("已删源", -1)
                                            ]))]),
                                            _: 1
                                          }))
                                        : _createCommentVNode("", true),
                                      (record.hr_protected)
                                        ? (_openBlock(), _createBlock(_component_VChip, {
                                            key: 1,
                                            size: "x-small",
                                            variant: "tonal",
                                            color: "info"
                                          }, {
                                            default: _withCtx(() => [...(_cache[98] || (_cache[98] = [
                                              _createTextVNode("H&R 保护", -1)
                                            ]))]),
                                            _: 1
                                          }))
                                        : _createCommentVNode("", true),
                                      (record.fallback)
                                        ? (_openBlock(), _createBlock(_component_VChip, {
                                            key: 2,
                                            size: "x-small",
                                            variant: "tonal",
                                            color: "warning"
                                          }, {
                                            default: _withCtx(() => [...(_cache[99] || (_cache[99] = [
                                              _createTextVNode("兜底", -1)
                                            ]))]),
                                            _: 1
                                          }))
                                        : _createCommentVNode("", true)
                                    ])
                                  ]),
                                  _createElementVNode("td", _hoisted_184, _toDisplayString(formatTimestamp(record.updated_at)), 1)
                                ]))
                              }), 128))
                            ])
                          ]),
                          _: 1
                        })
                      ]),
                      _createElementVNode("div", _hoisted_185, [
                        _createVNode(TableState, _mergeProps(recordTableState('transfer', transferRecords.value), {
                          onRetry: _cache[14] || (_cache[14] = $event => (refreshActive()))
                        }), null, 16),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(transferRecords.value, (record) => {
                          return (_openBlock(), _createElementBlock("article", {
                            key: `m-${record.source_downloader}-${record.source_hash}-${record.downloader}`,
                            class: "dm-record-card"
                          }, [
                            _createElementVNode("div", _hoisted_186, [
                              _createElementVNode("strong", _hoisted_187, _toDisplayString(record.source_downloader) + " → " + _toDisplayString(record.downloader), 1),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                variant: "tonal",
                                color: transferPhaseColor(record.phase)
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(transferPhaseText(record.phase)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("div", _hoisted_188, _toDisplayString(transferPrimaryText(record)) + " · " + _toDisplayString(transferSecondaryText(record)) + " · " + _toDisplayString(formatTimestamp(record.updated_at)), 1)
                          ]))
                        }), 128))
                      ])
                    ], 8, _hoisted_175),
                    (transferRecords.value.length && (transferStatus.value.total_pages || 1) > 1)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_189, [
                          _createVNode(_component_VBtn, {
                            size: "small",
                            "aria-label": "上一页",
                            variant: "text",
                            icon: "mdi-chevron-left",
                            disabled: transferPage.value <= 1,
                            onClick: _cache[15] || (_cache[15] = $event => (changeTransferPage(transferPage.value - 1)))
                          }, null, 8, ["disabled"]),
                          _createElementVNode("span", _hoisted_190, _toDisplayString(transferStatus.value.page || 1) + " / " + _toDisplayString(transferStatus.value.total_pages || 1), 1),
                          _createVNode(_component_VBtn, {
                            size: "small",
                            "aria-label": "下一页",
                            variant: "text",
                            icon: "mdi-chevron-right",
                            disabled: transferPage.value >= (transferStatus.value.total_pages || 1),
                            onClick: _cache[16] || (_cache[16] = $event => (changeTransferPage(transferPage.value + 1)))
                          }, null, 8, ["disabled"])
                        ]))
                      : _createCommentVNode("", true)
                  ]))
                : _createCommentVNode("", true),
              (activeTab.value === 'sitetag')
                ? (_openBlock(), _createElementBlock("div", _hoisted_191, [
                    _cache[110] || (_cache[110] = _createElementVNode("div", { class: "dm-record-block-head" }, [
                      _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "dm-record-block-title" }, "标签清理"),
                        _createElementVNode("div", { class: "dm-hint" }, "扫描所选 qBittorrent 下载器的标签，勾选保留项后清理其余标签。")
                      ])
                    ], -1)),
                    (moduleDetailVisible('tagcleanup'))
                      ? (_openBlock(), _createBlock(ModuleDetailPanel, _mergeProps({
                          key: 0,
                          class: "mt-3",
                          title: "标签清理明细",
                          rows: moduleDetail('tagcleanup').rows
                        }, moduleDetail('tagcleanup')), null, 16, ["rows"]))
                      : _createCommentVNode("", true),
                    _createElementVNode("div", _hoisted_192, [
                      _createVNode(_component_VSelect, {
                        density: "compact",
                        modelValue: cleanupDownloaders.value,
                        "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((cleanupDownloaders).value = $event)),
                        label: "下载器",
                        variant: "outlined",
                        "hide-details": "",
                        items: qbDownloaderItems.value,
                        multiple: "",
                        chips: "",
                        "closable-chips": "",
                        class: "dm-cleanup-select"
                      }, null, 8, ["modelValue", "items"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        color: "primary",
                        variant: "tonal",
                        "prepend-icon": "mdi-radar",
                        loading: cleanupScanning.value,
                        disabled: !cleanupDownloaders.value.length,
                        onClick: scanCleanupTags
                      }, {
                        default: _withCtx(() => [...(_cache[104] || (_cache[104] = [
                          _createTextVNode("扫描标签", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading", "disabled"])
                    ]),
                    (cleanupMessage.value)
                      ? (_openBlock(), _createBlock(_component_VAlert, {
                          key: 1,
                          type: cleanupStatus.value,
                          variant: "tonal",
                          density: "compact",
                          closable: "",
                          class: "mt-3",
                          "onClick:close": _cache[18] || (_cache[18] = $event => (cleanupMessage.value = ''))
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(cleanupMessage.value), 1)
                          ]),
                          _: 1
                        }, 8, ["type"]))
                      : _createCommentVNode("", true),
                    (!cleanupScan.value && !cleanupMessage.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_193, "尚未扫描标签，请选择下载器后点击「扫描标签」"))
                      : _createCommentVNode("", true),
                    (cleanupScan.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_194, [
                          _createElementVNode("div", _hoisted_195, [
                            _createElementVNode("div", null, [
                              _cache[105] || (_cache[105] = _createElementVNode("div", { class: "dm-section-title" }, "扫描结果", -1)),
                              _createElementVNode("div", _hoisted_196, _toDisplayString(cleanupGroups.value.length) + " 个下载器 · 自动清理 " + _toDisplayString(cleanupAutoRemovedCount.value) + " 个临时标签 ", 1)
                            ]),
                            _createElementVNode("div", _hoisted_197, [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "text",
                                "prepend-icon": "mdi-check-all",
                                onClick: _cache[19] || (_cache[19] = $event => (setAllCleanupTags(true)))
                              }, {
                                default: _withCtx(() => [...(_cache[106] || (_cache[106] = [
                                  _createTextVNode("全部保留", -1)
                                ]))]),
                                _: 1
                              }),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "text",
                                color: "warning",
                                "prepend-icon": "mdi-checkbox-blank-outline",
                                onClick: _cache[20] || (_cache[20] = $event => (setAllCleanupTags(false)))
                              }, {
                                default: _withCtx(() => [...(_cache[107] || (_cache[107] = [
                                  _createTextVNode("取消全选", -1)
                                ]))]),
                                _: 1
                              })
                            ])
                          ]),
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupScan.value.errors || [], (item) => {
                            return (_openBlock(), _createBlock(_component_VAlert, {
                              key: `${item.downloader}-${item.message}`,
                              type: "warning",
                              variant: "tonal",
                              density: "compact",
                              class: "mb-2"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(item.downloader) + " · " + _toDisplayString(item.message), 1)
                              ]),
                              _: 2
                            }, 1024))
                          }), 128)),
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupGroups.value, (group) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: group.name,
                              class: "dm-tag-group"
                            }, [
                              _createElementVNode("div", _hoisted_198, [
                                _createElementVNode("div", _hoisted_199, [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-download-network-outline",
                                    size: "19",
                                    color: "primary"
                                  }),
                                  _createElementVNode("strong", _hoisted_200, _toDisplayString(group.name), 1)
                                ]),
                                _createElementVNode("span", _hoisted_201, _toDisplayString(group.task_count) + " 个任务 · " + _toDisplayString(group.tags.length) + " 个标签", 1)
                              ]),
                              (!group.tags.length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_202, [
                                    _createVNode(_component_VIcon, {
                                      icon: "mdi-tag-check-outline",
                                      size: "28",
                                      color: "success"
                                    }),
                                    _cache[108] || (_cache[108] = _createElementVNode("span", null, "没有待选择标签", -1))
                                  ]))
                                : (_openBlock(), _createElementBlock("div", _hoisted_203, [
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.tags, (item) => {
                                      return (_openBlock(), _createElementBlock("label", {
                                        key: `${group.name}-${item.tag}`,
                                        class: "dm-tag-row"
                                      }, [
                                        _createVNode(_component_VCheckboxBtn, {
                                          modelValue: cleanupKeep[tagSelectionKey(group.name, item.tag)],
                                          "onUpdate:modelValue": $event => ((cleanupKeep[tagSelectionKey(group.name, item.tag)]) = $event),
                                          color: "success"
                                        }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                                        _createElementVNode("div", _hoisted_204, [
                                          _createElementVNode("div", _hoisted_205, [
                                            _createElementVNode("span", {
                                              class: "dm-tag-name",
                                              title: item.tag
                                            }, _toDisplayString(item.tag), 9, _hoisted_206),
                                            _createVNode(_component_VChip, {
                                              size: "x-small",
                                              variant: "tonal",
                                              color: cleanupKindMeta(item.kind).color
                                            }, {
                                              default: _withCtx(() => [
                                                _createTextVNode(_toDisplayString(cleanupKindMeta(item.kind).label), 1)
                                              ]),
                                              _: 2
                                            }, 1032, ["color"]),
                                            _createElementVNode("span", _hoisted_207, _toDisplayString(item.count) + " 个任务", 1)
                                          ]),
                                          _createElementVNode("div", {
                                            class: "dm-tag-samples dm-hint",
                                            title: (item.samples || []).join(' · ')
                                          }, _toDisplayString((item.samples || []).join(' · ')), 9, _hoisted_208)
                                        ])
                                      ]))
                                    }), 128))
                                  ]))
                            ]))
                          }), 128)),
                          _createElementVNode("div", _hoisted_209, [
                            _createElementVNode("div", _hoisted_210, " 待清理 " + _toDisplayString(cleanupRemovals.value.length) + " 个标签 · " + _toDisplayString(cleanupRemovalAssociations.value) + " 条任务关联 ", 1),
                            _createVNode(_component_VBtn, {
                              size: "small",
                              color: "warning",
                              variant: "tonal",
                              "prepend-icon": "mdi-eye-outline",
                              disabled: !cleanupRemovals.value.length,
                              onClick: previewCleanupTags
                            }, {
                              default: _withCtx(() => [...(_cache[109] || (_cache[109] = [
                                _createTextVNode("预览标签清理", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled"])
                          ])
                        ]))
                      : _createCommentVNode("", true)
                  ]))
                : _createCommentVNode("", true),
              (activeTab.value === 'diagnostics')
                ? (_openBlock(), _createElementBlock("section", _hoisted_211, [
                    _cache[117] || (_cache[117] = _createElementVNode("div", { class: "dm-section-heading" }, [
                      _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "dm-section-title" }, "运行详情"),
                        _createElementVNode("div", { class: "dm-hint" }, "上传限速运行状态；下载器与站点明细见「上传限速」模块卡的展开详情。")
                      ])
                    ], -1)),
                    _createElementVNode("div", _hoisted_212, [
                      _cache[112] || (_cache[112] = _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "dm-runtime-title" }, "上传限速"),
                        _createElementVNode("div", { class: "dm-hint" }, "MP 或插件离线时，下载器继续保留最后一次已写入的限速。")
                      ], -1)),
                      _createElementVNode("div", _hoisted_213, [
                        _createVNode(_component_VChip, {
                          size: "small",
                          color: uploadLimitStatus.value.color,
                          variant: "tonal"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(uploadLimitStatus.value.label), 1)
                          ]),
                          _: 1
                        }, 8, ["color"]),
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          class: "text-none",
                          onClick: _cache[21] || (_cache[21] = $event => (selectTab('upload')))
                        }, {
                          default: _withCtx(() => [...(_cache[111] || (_cache[111] = [
                            _createTextVNode("查看明细", -1)
                          ]))]),
                          _: 1
                        })
                      ])
                    ]),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(uploadLimit.value.errors || [], (runtimeError) => {
                      return (_openBlock(), _createBlock(_component_VAlert, {
                        key: runtimeError,
                        type: "error",
                        variant: "tonal",
                        density: "compact",
                        class: "mt-3"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(runtimeError), 1)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128)),
                    _createElementVNode("div", _hoisted_214, [
                      _createElementVNode("div", _hoisted_215, [
                        _cache[113] || (_cache[113] = _createElementVNode("span", null, "服务", -1)),
                        _createElementVNode("strong", null, _toDisplayString(uploadLimitStatus.value.label), 1)
                      ]),
                      _createElementVNode("div", _hoisted_216, [
                        _cache[114] || (_cache[114] = _createElementVNode("span", null, "实时速率", -1)),
                        _createElementVNode("strong", null, _toDisplayString(formatUploadRate(uploadLimit.value.upload_rate_bps)), 1)
                      ]),
                      _createElementVNode("div", _hoisted_217, [
                        _cache[115] || (_cache[115] = _createElementVNode("span", null, "受限任务", -1)),
                        _createElementVNode("strong", null, _toDisplayString(uploadLimit.value.managed_torrents || 0), 1)
                      ]),
                      _createElementVNode("div", _hoisted_218, [
                        _cache[116] || (_cache[116] = _createElementVNode("span", null, "宽限任务", -1)),
                        _createElementVNode("strong", null, _toDisplayString(uploadLimit.value.grace_torrents || 0), 1)
                      ])
                    ]),
                    _cache[118] || (_cache[118] = _createElementVNode("div", { class: "dm-hint mt-2" }, "实时速率是下载器当前实际上传流量；站点额度是插件写入单种限速的合计值，两者不是同一指标。", -1))
                  ]))
                : _createCommentVNode("", true),
              (activeTab.value === 'diagnostics')
                ? (_openBlock(), _createElementBlock("section", _hoisted_219, [
                    _cache[130] || (_cache[130] = _createElementVNode("div", { class: "dm-section-heading" }, [
                      _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "dm-section-title" }, "诊断"),
                        _createElementVNode("div", { class: "dm-hint" }, "按运行链路顺序检查下载器、路径、转移、命名、标签和归档状态。")
                      ])
                    ], -1)),
                    (diagnostics.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_220, [
                          _createElementVNode("div", _hoisted_221, [
                            _createElementVNode("div", _hoisted_222, [
                              _cache[119] || (_cache[119] = _createElementVNode("div", { class: "dm-hint" }, "版本", -1)),
                              _createElementVNode("div", _hoisted_223, _toDisplayString(diagnostics.value?.plugin?.version), 1)
                            ]),
                            _createElementVNode("div", _hoisted_224, [
                              _cache[120] || (_cache[120] = _createElementVNode("div", { class: "dm-hint" }, "源下载器", -1)),
                              _createVNode(DownloaderBadge, {
                                class: "dm-section-title",
                                name: diagnostics.value?.downloaders?.from?.name || '未配置',
                                type: diagnostics.value?.downloaders?.from?.type
                              }, null, 8, ["name", "type"]),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: diagnostics.value?.downloaders?.from?.available ? 'success' : 'warning',
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(diagnostics.value?.downloaders?.from?.message), 1)
                                ]),
                                _: 1
                              }, 8, ["color"])
                            ]),
                            _createElementVNode("div", _hoisted_225, [
                              _cache[121] || (_cache[121] = _createElementVNode("div", { class: "dm-hint" }, "目标下载器", -1)),
                              _createVNode(DownloaderBadge, {
                                class: "dm-section-title",
                                name: diagnostics.value?.downloaders?.to?.name || '未配置',
                                type: diagnostics.value?.downloaders?.to?.type
                              }, null, 8, ["name", "type"]),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: diagnostics.value?.downloaders?.to?.available ? 'success' : 'warning',
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(diagnostics.value?.downloaders?.to?.message), 1)
                                ]),
                                _: 1
                              }, 8, ["color"])
                            ]),
                            _createElementVNode("div", _hoisted_226, [
                              _cache[122] || (_cache[122] = _createElementVNode("div", { class: "dm-hint" }, "补刀归档", -1)),
                              _createElementVNode("div", _hoisted_227, _toDisplayString(diagnostics.value?.rename_archive?.archived || 0) + " 条", 1),
                              _createElementVNode("div", _hoisted_228, "连续失败 " + _toDisplayString(diagnostics.value?.rename_archive?.active_failed || 0) + " · 阈值 " + _toDisplayString(diagnostics.value?.rename_archive?.threshold || 3), 1)
                            ])
                          ]),
                          _createElementVNode("div", _hoisted_229, [
                            _createElementVNode("div", _hoisted_230, [
                              _createElementVNode("div", _hoisted_231, [
                                _createElementVNode("span", _hoisted_232, [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-stethoscope",
                                    size: "20"
                                  })
                                ]),
                                _cache[123] || (_cache[123] = _createElementVNode("span", null, "运行诊断", -1))
                              ]),
                              _createElementVNode("div", _hoisted_233, [
                                _createElementVNode("strong", null, _toDisplayString(diagnosticsOkCount.value) + " / " + _toDisplayString(diagnosticsCards.value.length), 1),
                                _cache[124] || (_cache[124] = _createElementVNode("span", null, "正常", -1)),
                                (diagnosticsAttentionCount.value)
                                  ? (_openBlock(), _createElementBlock("span", _hoisted_234, "· " + _toDisplayString(diagnosticsAttentionCount.value) + " 项关注", 1))
                                  : _createCommentVNode("", true)
                              ])
                            ]),
                            _createElementVNode("div", _hoisted_235, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(diagnosticsCards.value, (item) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: item.label,
                                  class: _normalizeClass(["dm-diagnostic-card", `dm-diagnostic-card--${item.status || 'off'}`])
                                }, [
                                  _createElementVNode("div", _hoisted_236, [
                                    _createVNode(_component_VIcon, {
                                      icon: item.icon,
                                      size: "22"
                                    }, null, 8, ["icon"])
                                  ]),
                                  _createElementVNode("div", _hoisted_237, [
                                    _createElementVNode("div", _hoisted_238, _toDisplayString(item.label), 1),
                                    _createElementVNode("div", _hoisted_239, _toDisplayString(item.detail), 1),
                                    _createElementVNode("div", _hoisted_240, _toDisplayString(item.statusText), 1)
                                  ])
                                ], 2))
                              }), 128))
                            ]),
                            _createElementVNode("div", _hoisted_241, [
                              _cache[125] || (_cache[125] = _createElementVNode("span", null, "按运行链路顺序检查下载器、路径、转移、命名、标签和归档状态。", -1)),
                              (diagnosticsAttentionCount.value)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_242, "关注项不阻断运行"))
                                : _createCommentVNode("", true)
                            ])
                          ]),
                          _createElementVNode("div", null, [
                            _cache[127] || (_cache[127] = _createElementVNode("div", { class: "dm-section-title mb-2" }, "最近失败", -1)),
                            (!diagnostics.value?.rename_history?.recent_failures?.length)
                              ? (_openBlock(), _createElementBlock("div", _hoisted_243, "暂无失败记录"))
                              : (_openBlock(), _createElementBlock("div", _hoisted_244, [
                                  _createVNode(_component_VTable, {
                                    density: "compact",
                                    class: "dm-table"
                                  }, {
                                    default: _withCtx(() => [
                                      _cache[126] || (_cache[126] = _createElementVNode("thead", null, [
                                        _createElementVNode("tr", null, [
                                          _createElementVNode("th", { class: "dm-table-head" }, "时间"),
                                          _createElementVNode("th", { class: "dm-table-head" }, "名称"),
                                          _createElementVNode("th", { class: "dm-table-head" }, "原因")
                                        ])
                                      ], -1)),
                                      _createElementVNode("tbody", null, [
                                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(diagnostics.value.rename_history.recent_failures, (item) => {
                                          return (_openBlock(), _createElementBlock("tr", {
                                            key: item.hash
                                          }, [
                                            _createElementVNode("td", _hoisted_245, _toDisplayString(item.time), 1),
                                            _createElementVNode("td", {
                                              class: "dm-body-text dm-ellipsis",
                                              title: item.name
                                            }, _toDisplayString(item.name), 9, _hoisted_246),
                                            _createElementVNode("td", _hoisted_247, _toDisplayString(item.reason), 1)
                                          ]))
                                        }), 128))
                                      ])
                                    ]),
                                    _: 1
                                  })
                                ]))
                          ]),
                          _createElementVNode("div", _hoisted_248, [
                            _cache[128] || (_cache[128] = _createElementVNode("div", { class: "dm-record-block-head" }, [
                              _createElementVNode("div", null, [
                                _createElementVNode("div", { class: "dm-record-block-title" }, "数据清理"),
                                _createElementVNode("div", { class: "dm-hint" }, " 只清理插件自身的历史与统计，不修改下载器任务与文件、H&R 安全状态、活动队列与限速恢复状态。 ")
                              ])
                            ], -1)),
                            _createElementVNode("div", _hoisted_249, [
                              (_openBlock(), _createElementBlock(_Fragment, null, _renderList(CLEANUP_TARGETS, (target, key) => {
                                return _createElementVNode("div", {
                                  key: key,
                                  class: "dm-cleanup-row"
                                }, [
                                  _createElementVNode("div", _hoisted_250, [
                                    _createElementVNode("span", _hoisted_251, _toDisplayString(target.label), 1),
                                    _createElementVNode("span", _hoisted_252, _toDisplayString(target.detail) + " · " + _toDisplayString(cleanupCounts.value[key] || 0) + " 条", 1)
                                  ]),
                                  _createVNode(_component_VBtn, {
                                    size: "small",
                                    variant: "tonal",
                                    color: "warning",
                                    "prepend-icon": "mdi-delete-sweep-outline",
                                    text: `清理`,
                                    disabled: !(cleanupCounts.value[key] > 0),
                                    onClick: $event => (openCleanupDialog(key))
                                  }, null, 8, ["disabled", "onClick"])
                                ])
                              }), 64))
                            ])
                          ])
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_253, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-stethoscope",
                            size: "48",
                            color: "grey-lighten-1",
                            class: "mb-2"
                          }),
                          _cache[129] || (_cache[129] = _createElementVNode("div", null, "点击刷新诊断", -1))
                        ]))
                  ]))
                : _createCommentVNode("", true)
            ], 64))
      ])
    ]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-page",
      modelValue: transferRunDialog.value,
      "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((transferRunDialog).value = $event)),
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
                  default: _withCtx(() => [...(_cache[131] || (_cache[131] = [
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
                    _cache[132] || (_cache[132] = _createTextVNode("按当前配置扫描源下载器并转移种子；若配置了删源，转移完成后会删除源任务。", -1))
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
                  size: "small",
                  variant: "text",
                  disabled: moduleRunning.value === 'transfer-run',
                  onClick: _cache[22] || (_cache[22] = $event => (transferRunDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[133] || (_cache[133] = [
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
                  default: _withCtx(() => [...(_cache[134] || (_cache[134] = [
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
      "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((cleanupConfirmDialog).value = $event)),
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
                _cache[135] || (_cache[135] = _createElementVNode("div", { class: "dm-hint mt-2" }, " 不修改下载器任务与文件，不影响 H&R 安全状态、活动队列与限速恢复状态。 ", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  disabled: cleanupRunning.value,
                  onClick: _cache[24] || (_cache[24] = $event => (cleanupConfirmDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[136] || (_cache[136] = [
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
                  default: _withCtx(() => [...(_cache[137] || (_cache[137] = [
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
      "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((hrClearDialog).value = $event)),
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
                  default: _withCtx(() => [...(_cache[138] || (_cache[138] = [
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
                  size: "small",
                  variant: "text",
                  disabled: hrClearing.value,
                  onClick: _cache[26] || (_cache[26] = $event => (hrClearDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[139] || (_cache[139] = [
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
                  default: _withCtx(() => [...(_cache[140] || (_cache[140] = [
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
      "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((cleanupDialog).value = $event)),
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
                  default: _withCtx(() => [...(_cache[141] || (_cache[141] = [
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
                  size: "small",
                  variant: "text",
                  disabled: cleanupExecuting.value,
                  onClick: _cache[28] || (_cache[28] = $event => (cleanupDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[142] || (_cache[142] = [
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
                  default: _withCtx(() => [...(_cache[143] || (_cache[143] = [
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-ba568582"]]);

export { Page as default };
