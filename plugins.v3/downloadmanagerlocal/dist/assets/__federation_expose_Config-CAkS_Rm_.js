import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, M as MODULE_ICONS, D as DownloaderBadge, R as RowActionMenu, g as getPluginApi } from './RowActionMenu-Dk9dO4G3.js';

const {resolveComponent:_resolveComponent$3,openBlock:_openBlock$3,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$1,toDisplayString:_toDisplayString$2,createElementVNode:_createElementVNode$1,createVNode:_createVNode$2,renderSlot:_renderSlot,createElementBlock:_createElementBlock$1} = await importShared('vue');


const _hoisted_1$1 = ["aria-label"];
const _hoisted_2$1 = { class: "dm-form-section-heading" };
const _hoisted_3$1 = { class: "dm-form-section-title" };
const _hoisted_4$1 = {
  key: 1,
  class: "dm-form-section-actions"
};
const _hoisted_5$1 = { class: "dm-form-section-content" };


const _sfc_main$3 = {
  __name: 'FormSection',
  props: {
  title: { type: String, required: true },
  icon: { type: String, default: '' },
},
  setup(__props) {



return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$3("VIcon");
  const _component_VDivider = _resolveComponent$3("VDivider");

  return (_openBlock$3(), _createElementBlock$1("section", {
    class: "dm-form-section",
    "aria-label": __props.title
  }, [
    _createElementVNode$1("header", _hoisted_2$1, [
      (__props.icon)
        ? (_openBlock$3(), _createBlock$3(_component_VIcon, {
            key: 0,
            icon: __props.icon,
            size: "18",
            class: "dm-form-section-icon",
            "aria-hidden": "true"
          }, null, 8, ["icon"]))
        : _createCommentVNode$1("", true),
      _createElementVNode$1("h3", _hoisted_3$1, _toDisplayString$2(__props.title), 1),
      _createVNode$2(_component_VDivider, {
        class: "dm-form-section-line",
        "aria-hidden": "true"
      }),
      (_ctx.$slots.actions)
        ? (_openBlock$3(), _createElementBlock$1("div", _hoisted_4$1, [
            _renderSlot(_ctx.$slots, "actions", {}, undefined, true)
          ]))
        : _createCommentVNode$1("", true)
    ]),
    _createElementVNode$1("div", _hoisted_5$1, [
      _renderSlot(_ctx.$slots, "default", {}, undefined, true)
    ])
  ], 8, _hoisted_1$1))
}
}

};
const FormSection = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-684feeff"]]);

const {toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$2,mergeProps:_mergeProps$1,withCtx:_withCtx$1,createVNode:_createVNode$1,withModifiers:_withModifiers$2,withKeys:_withKeys$2,openBlock:_openBlock$2,createBlock:_createBlock$2} = await importShared('vue');


const {computed: computed$2} = await importShared('vue');


const _sfc_main$2 = {
  __name: 'MultiValueInput',
  props: { modelValue: { type: [String, Array], default: '' }, label: { type: String, required: true } },
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
// Keep the stored comma-separated string untouched until the user edits it.
const values = computed$2(() => Array.isArray(props.modelValue) ? props.modelValue : props.modelValue.split(',').map(value => value.trim()).filter(Boolean));
function update(items) { emit('update:modelValue', Array.isArray(props.modelValue) ? items : items.map(String).join(',')); }
function guardComposition(event) {
  if (event.key === 'Enter' && (event.isComposing || event.keyCode === 229)) event.stopImmediatePropagation();
}

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VCombobox = _resolveComponent$2("VCombobox");

  return (_openBlock$2(), _createBlock$2(_component_VCombobox, {
    "model-value": values.value,
    "onUpdate:modelValue": update,
    label: __props.label,
    delimiters: Array.isArray(__props.modelValue) ? [] : [','],
    multiple: "",
    chips: "",
    "closable-chips": "",
    "return-object": false,
    density: "compact",
    variant: "outlined",
    class: "dm-multi-value-input",
    onKeydownCapture: guardComposition,
    onKeydown: _cache[0] || (_cache[0] = _withKeys$2(_withModifiers$2(() => {}, ["stop"]), ["enter"])),
    "menu-props": { contentClass: 'dm-select-menu' }
  }, {
    chip: _withCtx$1(({ props: chipProps, item }) => [
      _createVNode$1(_component_VChip, _mergeProps$1(chipProps, {
        size: "small",
        title: item.title
      }), {
        default: _withCtx$1(() => [
          _createTextVNode$1(_toDisplayString$1(item.title), 1)
        ]),
        _: 2
      }, 1040, ["title"])
    ]),
    _: 1
  }, 8, ["model-value", "label", "delimiters"]))
}
}

};
const MultiValueInput = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-0c6d0b06"]]);

const {resolveComponent:_resolveComponent$1,withModifiers:_withModifiers$1,withKeys:_withKeys$1,openBlock:_openBlock$1,createBlock:_createBlock$1} = await importShared('vue');


const {computed: computed$1} = await importShared('vue');


const _sfc_main$1 = {
  __name: 'MultiLineInput',
  props: { modelValue: { type: [String, Array], default: '' } },
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
// Render lists as lines without normalizing the stored value until an edit occurs.
const text = computed$1(() => Array.isArray(props.modelValue) ? props.modelValue.join('\n') : props.modelValue);
function update(value) {
  const edited = String(value ?? '');
  emit('update:modelValue', Array.isArray(props.modelValue)
    ? edited.split(/\r?\n/).map(line => line.trim()).filter(Boolean) : edited);
}

return (_ctx, _cache) => {
  const _component_VTextarea = _resolveComponent$1("VTextarea");

  return (_openBlock$1(), _createBlock$1(_component_VTextarea, {
    "model-value": text.value,
    "onUpdate:modelValue": update,
    density: "compact",
    variant: "outlined",
    rows: "3",
    "auto-grow": "",
    class: "dm-multi-line-input",
    onKeydown: _cache[0] || (_cache[0] = _withKeys$1(_withModifiers$1(() => {}, ["stop"]), ["enter"]))
  }, null, 8, ["model-value"]))
}
}

};
const MultiLineInput = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-121a563e"]]);

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,createBlock:_createBlock,createCommentVNode:_createCommentVNode,vShow:_vShow,withDirectives:_withDirectives,unref:_unref,withModifiers:_withModifiers,withKeys:_withKeys,mergeProps:_mergeProps} = await importShared('vue');


const _hoisted_1 = { class: "dm-body" };
const _hoisted_2 = { class: "dm-nav" };
const _hoisted_3 = { class: "dm-content" };
const _hoisted_4 = { class: "dm-subtabs" };
const _hoisted_5 = ["onClick"];
const _hoisted_6 = { class: "dm-window" };
const _hoisted_7 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_8 = { class: "dm-switch-group" };
const _hoisted_9 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_10 = { class: "dm-field-row" };
const _hoisted_11 = { class: "dm-field" };
const _hoisted_12 = { class: "dm-field" };
const _hoisted_13 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_14 = {
  key: 0,
  class: "dm-upload-downloader-list"
};
const _hoisted_15 = { class: "dm-upload-config-name" };
const _hoisted_16 = { class: "min-w-0" };
const _hoisted_17 = { class: "dm-hint" };
const _hoisted_18 = {
  key: 1,
  class: "dm-monitor-empty dm-hint"
};
const _hoisted_19 = { class: "dm-hint mt-3" };
const _hoisted_20 = {
  key: 0,
  class: "dm-upload-site-list mt-4"
};
const _hoisted_21 = { class: "dm-upload-site-name" };
const _hoisted_22 = { class: "min-w-0" };
const _hoisted_23 = { class: "dm-body-text" };
const _hoisted_24 = { class: "dm-hint" };
const _hoisted_25 = {
  key: 1,
  class: "dm-monitor-empty mt-3 dm-hint"
};
const _hoisted_26 = { class: "dm-field-row dm-upload-add-site" };
const _hoisted_27 = { class: "dm-field" };
const _hoisted_28 = {
  key: 2,
  class: "dm-hint text-error",
  role: "alert"
};
const _hoisted_29 = { class: "dm-pane dm-transfer-form dm-compact-form" };
const _hoisted_30 = { class: "dm-switch-group" };
const _hoisted_31 = { class: "dm-field dm-field--toggle" };
const _hoisted_32 = { class: "dm-field dm-field--toggle" };
const _hoisted_33 = { class: "dm-field dm-field--toggle" };
const _hoisted_34 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_35 = { class: "dm-field-row" };
const _hoisted_36 = { class: "dm-field dm-field--number" };
const _hoisted_37 = { class: "dm-field dm-field--number" };
const _hoisted_38 = { class: "dm-switch-group" };
const _hoisted_39 = { class: "dm-field dm-field--toggle" };
const _hoisted_40 = { class: "dm-field dm-field--toggle" };
const _hoisted_41 = { class: "dm-field-row" };
const _hoisted_42 = { class: "dm-field dm-field--number" };
const _hoisted_43 = { class: "dm-switch-group" };
const _hoisted_44 = { class: "dm-field dm-field--toggle" };
const _hoisted_45 = { class: "dm-field dm-field--toggle" };
const _hoisted_46 = { class: "dm-field dm-field--toggle" };
const _hoisted_47 = { class: "dm-field-row" };
const _hoisted_48 = { class: "dm-field dm-field--number" };
const _hoisted_49 = { class: "dm-field dm-field--number" };
const _hoisted_50 = { class: "dm-pane dm-transfer-form dm-compact-form" };
const _hoisted_51 = { class: "dm-task-table mt-3" };
const _hoisted_52 = { class: "dm-task-name" };
const _hoisted_53 = { class: "dm-break-text" };
const _hoisted_54 = { class: "dm-hint" };
const _hoisted_55 = { class: "dm-task-state" };
const _hoisted_56 = { class: "dm-hint" };
const _hoisted_57 = { class: "dm-task-route" };
const _hoisted_58 = { class: "dm-route-item" };
const _hoisted_59 = { class: "dm-route-item" };
const _hoisted_60 = { class: "dm-task-paths" };
const _hoisted_61 = { class: "dm-hint dm-break-text" };
const _hoisted_62 = { class: "dm-hint dm-map-arrow" };
const _hoisted_63 = { class: "dm-task-filters" };
const _hoisted_64 = { class: "dm-task-settings" };
const _hoisted_65 = {
  key: 0,
  class: "dm-hint"
};
const _hoisted_66 = { class: "dm-hint" };
const _hoisted_67 = { class: "dm-hint" };
const _hoisted_68 = { class: "dm-task-actions" };
const _hoisted_69 = {
  key: 0,
  class: "dm-map-empty dm-hint"
};
const _hoisted_70 = { class: "dm-pane dm-hr-form dm-compact-form dm-hr-basic-form" };
const _hoisted_71 = { class: "dm-switch-group" };
const _hoisted_72 = { class: "dm-field dm-field--toggle" };
const _hoisted_73 = { class: "dm-field dm-field--toggle" };
const _hoisted_74 = { class: "dm-field dm-field--toggle" };
const _hoisted_75 = { class: "dm-field dm-field--toggle" };
const _hoisted_76 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_77 = { class: "dm-field-row" };
const _hoisted_78 = { class: "dm-field" };
const _hoisted_79 = { class: "dm-field" };
const _hoisted_80 = { class: "dm-field dm-field--number" };
const _hoisted_81 = { class: "dm-switch-group" };
const _hoisted_82 = { class: "dm-field dm-field--toggle" };
const _hoisted_83 = { class: "dm-field-row" };
const _hoisted_84 = { class: "dm-field" };
const _hoisted_85 = { class: "dm-field" };
const _hoisted_86 = { class: "dm-field" };
const _hoisted_87 = { class: "dm-field-row" };
const _hoisted_88 = { class: "dm-field" };
const _hoisted_89 = { class: "dm-field" };
const _hoisted_90 = { class: "dm-switch-group" };
const _hoisted_91 = { class: "dm-field dm-field--toggle" };
const _hoisted_92 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_93 = { class: "dm-field-row" };
const _hoisted_94 = { class: "dm-field" };
const _hoisted_95 = { class: "dm-field dm-field--number" };
const _hoisted_96 = { class: "dm-pane dm-hr-sites-form dm-compact-form" };
const _hoisted_97 = { class: "dm-switch-group" };
const _hoisted_98 = { class: "dm-field dm-field--toggle" };
const _hoisted_99 = { class: "dm-field dm-field--toggle" };
const _hoisted_100 = { class: "dm-field-row" };
const _hoisted_101 = { class: "dm-field dm-field--number" };
const _hoisted_102 = { class: "dm-field dm-field--number" };
const _hoisted_103 = { class: "dm-field dm-field--number" };
const _hoisted_104 = { class: "dm-field-row" };
const _hoisted_105 = { class: "dm-field dm-field--number" };
const _hoisted_106 = { class: "dm-field dm-field--number" };
const _hoisted_107 = { class: "dm-hr-toolbar" };
const _hoisted_108 = {
  key: 0,
  class: "dm-hint mt-3"
};
const _hoisted_109 = { class: "dm-body-text dm-break-text" };
const _hoisted_110 = {
  key: 0,
  class: "dm-hint"
};
const _hoisted_111 = { class: "dm-hr-values" };
const _hoisted_112 = {
  key: 0,
  class: "dm-hr-inherit-mark"
};
const _hoisted_113 = {
  key: 1,
  class: "dm-hr-values-empty dm-hint"
};
const _hoisted_114 = { class: "dm-hr-rules-overflow" };
const _hoisted_115 = {
  key: 0,
  class: "dm-hr-inherit-mark"
};
const _hoisted_116 = { key: 0 };
const _hoisted_117 = { colspan: "5" };
const _hoisted_118 = { class: "dm-hr-editor" };
const _hoisted_119 = { class: "dm-hr-editor-grid" };
const _hoisted_120 = { class: "dm-hr-editor-grid mt-3" };
const _hoisted_121 = { class: "dm-hr-trackers" };
const _hoisted_122 = { class: "dm-hr-tiers" };
const _hoisted_123 = { class: "dm-hr-tiers-head" };
const _hoisted_124 = {
  key: 0,
  class: "dm-hint"
};
const _hoisted_125 = { key: 0 };
const _hoisted_126 = { class: "mt-3" };
const _hoisted_127 = {
  key: 0,
  class: "dm-field dm-field--full"
};
const _hoisted_128 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_129 = { class: "dm-switch-group" };
const _hoisted_130 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_131 = { class: "dm-field-row" };
const _hoisted_132 = { class: "dm-field" };
const _hoisted_133 = { class: "dm-field" };
const _hoisted_134 = { class: "dm-field" };
const _hoisted_135 = {
  key: 1,
  class: "dm-hint dm-risk"
};
const _hoisted_136 = { class: "dm-field-row" };
const _hoisted_137 = { class: "dm-field" };
const _hoisted_138 = { class: "dm-field" };
const _hoisted_139 = { class: "dm-field" };
const _hoisted_140 = { class: "dm-field" };
const _hoisted_141 = { class: "dm-switch-group" };
const _hoisted_142 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_143 = { class: "dm-field-row" };
const _hoisted_144 = { class: "dm-field" };
const _hoisted_145 = { class: "dm-field" };
const _hoisted_146 = { class: "dm-field dm-field--full" };
const _hoisted_147 = { class: "dm-field" };
const _hoisted_148 = { class: "dm-field" };
const _hoisted_149 = { class: "dm-field" };
const _hoisted_150 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_151 = { class: "dm-switch-group" };
const _hoisted_152 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_153 = {
  key: 1,
  class: "dm-hint dm-risk"
};
const _hoisted_154 = { class: "dm-field-row" };
const _hoisted_155 = { class: "dm-field" };
const _hoisted_156 = { class: "dm-field" };
const _hoisted_157 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_158 = { class: "dm-switch-group" };
const _hoisted_159 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_160 = { class: "dm-field-row" };
const _hoisted_161 = { class: "dm-field" };
const _hoisted_162 = { class: "dm-field" };
const _hoisted_163 = { class: "dm-field" };
const _hoisted_164 = { class: "dm-field-row" };
const _hoisted_165 = { class: "dm-field" };
const _hoisted_166 = { class: "dm-field" };
const _hoisted_167 = { class: "dm-field-row" };
const _hoisted_168 = { class: "dm-field dm-field--full" };
const _hoisted_169 = { class: "dm-field-row" };
const _hoisted_170 = { class: "dm-field dm-field--full" };
const _hoisted_171 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_172 = { class: "dm-field-row" };
const _hoisted_173 = { class: "dm-field dm-field--full" };
const _hoisted_174 = { class: "dm-field-row" };
const _hoisted_175 = { class: "dm-field dm-field--full" };
const _hoisted_176 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_177 = { class: "dm-switch-group" };
const _hoisted_178 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_179 = {
  key: 1,
  class: "dm-hint dm-risk"
};
const _hoisted_180 = { class: "dm-field-row" };
const _hoisted_181 = { class: "dm-field" };
const _hoisted_182 = { class: "dm-field" };
const _hoisted_183 = { class: "dm-field" };
const _hoisted_184 = { class: "dm-pane dm-compact-form dm-unified-form" };
const _hoisted_185 = { class: "dm-field-row" };
const _hoisted_186 = { class: "dm-field" };
const _hoisted_187 = { class: "dm-field" };
const _hoisted_188 = {
  key: 0,
  class: "dm-hint",
  role: "status"
};
const _hoisted_189 = {
  key: 1,
  class: "dm-hint text-error",
  role: "alert"
};
const _hoisted_190 = { class: "dm-hr-table mt-3" };
const _hoisted_191 = { class: "dm-cat-source" };
const _hoisted_192 = { class: "dm-body-text" };
const _hoisted_193 = {
  key: 0,
  class: "dm-hint"
};
const _hoisted_194 = { key: 1 };
const _hoisted_195 = {
  key: 0,
  class: "dm-map-empty dm-hint"
};
const _hoisted_196 = { class: "d-flex justify-end mt-2" };
const _hoisted_197 = { class: "dm-field-row" };
const _hoisted_198 = { class: "dm-field dm-field--full" };
const _hoisted_199 = { class: "dm-hr-table mt-2" };
const _hoisted_200 = { class: "dm-map-site" };
const _hoisted_201 = { class: "dm-map-site" };
const _hoisted_202 = {
  key: 2,
  class: "dm-map-empty-cell"
};
const _hoisted_203 = { class: "dm-map-site" };
const _hoisted_204 = { class: "d-flex justify-end" };
const _hoisted_205 = {
  key: 0,
  class: "dm-map-empty dm-hint"
};
const _hoisted_206 = { class: "d-flex justify-end mt-2" };
const _hoisted_207 = { class: "dm-field-row" };
const _hoisted_208 = { class: "dm-field" };
const _hoisted_209 = { class: "dm-field-row" };
const _hoisted_210 = { class: "dm-field" };
const _hoisted_211 = { class: "dm-field" };
const _hoisted_212 = { class: "dm-field-row" };
const _hoisted_213 = { class: "dm-field dm-field--full" };
const _hoisted_214 = { class: "dm-field dm-field--full" };
const _hoisted_215 = { class: "dm-field-row" };
const _hoisted_216 = { class: "dm-field" };
const _hoisted_217 = { class: "dm-field" };
const _hoisted_218 = { class: "dm-field-row" };
const _hoisted_219 = { class: "dm-field" };
const _hoisted_220 = { class: "dm-switch-group" };
const _hoisted_221 = { class: "dm-field-row" };
const _hoisted_222 = { class: "dm-field dm-field--full" };
const _hoisted_223 = {
  key: 0,
  class: "dm-hint dm-risk mb-2"
};
const _hoisted_224 = { class: "dm-field-row" };
const _hoisted_225 = { class: "dm-field" };
const _hoisted_226 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_227 = { class: "dm-field" };
const _hoisted_228 = {
  key: 0,
  class: "dm-hint dm-risk"
};
const _hoisted_229 = { class: "dm-field-row" };
const _hoisted_230 = { class: "dm-field dm-field--toggle" };
const _hoisted_231 = { class: "dm-field dm-field--toggle" };
const _hoisted_232 = { class: "dm-field-row" };
const _hoisted_233 = { class: "dm-field" };
const _hoisted_234 = { class: "dm-field-row" };
const _hoisted_235 = { class: "dm-field dm-field--full" };
const _hoisted_236 = { class: "dm-field dm-field--full" };
const {reactive,ref,computed,watch,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'DownloadManagerLocal' },
  sourcePluginId: { type: String, default: 'DownloadManagerLocal' },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options);
const form = reactive({});
const saveMessage = ref('');
const saveError = ref(false);
const savePending = ref(false);
const activeMain = ref('transfer');
const activeSub = ref('basic');
const downloaderItems = ref([]);
const transferTasks = ref([]);
const transferExt = ref({});
const transferDialog = ref(false);
const transferEditing = ref(-1);
const transferForm = reactive({});
const transferError = ref('');
const transferDeleteDialog = ref(false);
const transferDeleteIndex = ref(-1);
const transferStatusTasks = ref([]);
const siteItems = ref([]);
const hrPresets = ref([]);
const hrPresetsLoading = ref(false);
const hrPresetsLoaded = ref(false);
const hrPresetsMessage = ref('');
const hrCustomRules = ref([]);
const hrExpandedSites = ref([]);
const hrShowInherited = ref(false);
const hrRawOpen = ref(false);
const hrRawError = ref('');
const hrAddDialog = ref(false);
const hrNewSiteName = ref('');
const hrAddError = ref('');
let hrSyncedSiteConfigText = '';

onMounted(async () => {
  try {
    const [dlResp, siteResp, transferStatusResp] = await Promise.all([
      getApi('downloaders', { feedback: 'silent' }),
      getApi('sites', { feedback: 'silent' }),
      getApi('transfer_status?page=1&page_size=100', { feedback: 'silent' }),
      loadHrPresets(),
      loadTagCategories(),
    ]);
    if (dlResp) {
      downloaderItems.value = dlResp;
    }
    if (siteResp) {
      siteItems.value = siteResp;
    }
    transferStatusTasks.value = Array.isArray(transferStatusResp?.status?.tasks)
      ? transferStatusResp.status.tasks
      : (Array.isArray(transferStatusResp?.tasks) ? transferStatusResp.tasks : []);
  } catch (e) {
    console.error('获取列表失败:', e);
  }
});

const defaults = {
  hr_enabled: false, hr_protection_enabled: true, hr_auto_discover: false,
  hr_enable_site_config: false, hr_downloader: [], hr_sites: [],
  hr_notify: 'always', hr_check_period: 10, hr_hit_and_run_tag: 'H&R',
  hr_auto_cleanup_days: 15, hr_notify_summary_cron: '0 8 * * *',
  hr_exclude_tags: [], hr_exclude_categories: [],
  hr_duration: 48, hr_deadline_days: 14, hr_additional_seed_time: 24,
  hr_ratio: null, hr_upload_multiplier: null, hr_upload_gte_download: null,
  hr_active: false, hr_brush_plugin: 'BrushFlow', hr_site_config_str: '',
  remover_enabled: false, remover_notify: false,
  remover_action: 'pause', remover_downloaders: [], remover_cron: '0 */12 * * *',
  remover_samedata: false, remover_mponly: false, remover_size: '', remover_ratio: '',
  remover_time: '', remover_upspeed: '', remover_labels: '', remover_pathkeywords: '',
  remover_trackerkeywords: '', remover_errorkeywords: '', remover_torrentstates: '',
  remover_torrentcategorys: '',
  migration_observe_only: true,
  failcleanup_enabled: false, failcleanup_notify: true, failcleanup_cron: '0 */2 * * *',
  failcleanup_clean_repeat: true, failcleanup_retain_hours: 6,
  rename_notify: false, rename_cron_enabled: false, rename_on_download_added: true,
  rename_downloaders: [], rename_hash_white_list: '', rename_exclude_tags: '已重命名',
  rename_include_tags: '', rename_cron: '', rename_event_debounce_seconds: 3,
  tag_interval_cron: '5 4 * * *', tag_enable_media_tag: false, tag_enable_tag: true,
  tag_enable_category: false, tag_enable_del_tags: false, tag_downloaders: [],
  tag_all_cat: [], tag_all_cat_rename: [], tag_rename_type: false, tag_path_rename: '',
  tag_catprefix: '',
  enabled: false, transfer_enabled: true, delay_minutes: 25, notify: false,
  transfer_fallback_enabled: true, transfer_fallback_interval_minutes: 60,
  transfer_delete_source_default: false, transfer_delete_duplicate_default: false,
  fromdownloader: '', todownloader: '', frompath: '', topath: '',
  fromtorrentpath: '', nopaths: '', nolabels: '', includelabels: '', includecategory: '',
  transferemptylabel: false, add_torrent_tags: '⏩转种',
  deletesource: false, deleteduplicate: false,
  remainoldcat: false, remainoldtag: false,
  transfer_tasks: '[]', transfer_rename_enabled: false, downloader_ext: '{}',
  rename_enabled: true,
  rename_movie_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}',
  rename_tv_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}',
  rename_exclude_dirs: '',
  tag_enabled: true, tag_siteprefix: '🏠', tag_tracker_mappings_str: '',
  tag_custom_sites_str: '',
  seed_autostart: true, seed_skipverify: false,
  seed_check_interval: 60, seed_max_wait_minutes: 120,
  scan_limit: 500, pause_source: true,
  upload_limit_enabled: false, upload_limit_downloaders: [],
  upload_limit_downloader_limits_kib: {}, upload_limit_site_rules: {},
  upload_limit_grace_minutes: 30,
  // 观察模式（阶段三）：只预览候选、不执行写操作。老配置默认关闭（升级保持升级前行为），
  // 全新安装时由下方 fresh install 补丁打开；按模块前缀自动归入对应页签的「恢复默认」键集。
  transfer_observe_only: false, rename_observe_only: false, tag_observe_only: false,
  hr_observe_only: false, remover_observe_only: false, failcleanup_observe_only: false,
  upload_limit_observe_only: false,
};

// 各设置页签的「恢复默认」键集：transfer 为显式列表（含无前缀共享键），其余按模块前缀从 defaults 提取
const PANE_RESET_KEYS = {
  transfer: ['transfer_enabled', 'delay_minutes', 'notify',
    'transfer_fallback_enabled', 'transfer_fallback_interval_minutes',
    'transfer_delete_source_default', 'transfer_delete_duplicate_default',
    'fromdownloader', 'todownloader', 'frompath', 'topath', 'fromtorrentpath',
    'nopaths', 'nolabels', 'includelabels', 'includecategory', 'transferemptylabel',
    'add_torrent_tags', 'deletesource', 'deleteduplicate', 'remainoldcat', 'remainoldtag',
    'transfer_tasks', 'transfer_rename_enabled', 'downloader_ext',
    'seed_autostart', 'seed_skipverify', 'seed_check_interval', 'seed_max_wait_minutes',
    'scan_limit', 'pause_source', 'transfer_observe_only'],
  hr: Object.keys(defaults).filter(k => k.startsWith('hr_')),
  // remover 观察开关已迁移为 remover_observe_only（带前缀），旧 migration_observe_only 键保留在 defaults 供迁移回填
  remover: Object.keys(defaults).filter(k => k.startsWith('remover_')),
  failclean: Object.keys(defaults).filter(k => k.startsWith('failcleanup_')),
  rename: Object.keys(defaults).filter(k => k.startsWith('rename_')),
  tag: Object.keys(defaults).filter(k => k.startsWith('tag_')),
  upload: Object.keys(defaults).filter(k => k.startsWith('upload_limit_')),
};

// 观察模式键（阶段三）：与后端 utils/config.py 的 OBSERVE_ONLY_KEYS 一一对应；
// 全新安装默认开启，老配置升级保持升级前行为（见下方 watch 中的补丁）。
const OBSERVE_ONLY_KEYS = [
  'transfer_observe_only', 'rename_observe_only', 'tag_observe_only', 'hr_observe_only',
  'remover_observe_only', 'failcleanup_observe_only', 'upload_limit_observe_only',
];
const paneResetDialog = ref(false);
const paneResetTarget = ref('');
const paneResetCount = computed(() => (PANE_RESET_KEYS[paneResetTarget.value] || []).length);
const paneResetTitle = computed(() => mainTabs.find(i => i.key === paneResetTarget.value)?.title || '');

function askPaneReset(key) {
  paneResetTarget.value = key;
  paneResetDialog.value = true;
}

function confirmPaneReset() {
  for (const k of PANE_RESET_KEYS[paneResetTarget.value] || []) {
    form[k] = OBSERVE_ONLY_KEYS.includes(k) ? true : JSON.parse(JSON.stringify(defaults[k]));
  }
  if (paneResetTarget.value === 'transfer') {
    transferTasks.value = parseTransferTasks(form.transfer_tasks);
    transferExt.value = parseDownloaderExt(form.downloader_ext);
  }
  if (paneResetTarget.value === 'tag') {
    tagCatPairs.value = parseCatPairs(form.tag_all_cat, form.tag_all_cat_rename);
    tagTrackerPairs.value = [];
  }
  if (paneResetTarget.value === 'hr') syncHrSiteRulesFromForm();
  paneResetDialog.value = false;
}

const mainTabs = [
  { key: 'transfer', title: '转移做种', icon: MODULE_ICONS.transfer, desc: '监听下载完成事件，延迟后自动转移做种到目标下载器。' },
  { key: 'hr', title: 'H&R 管理', icon: MODULE_ICONS.hr, desc: '按站点规则跟踪 H&R 做种状态，为破坏性操作提供统一保护。' },
  { key: 'remover', title: '自动删种', icon: MODULE_ICONS.autoremove, desc: '按时间、分享率、体积等条件自动暂停或删除种子。' },
  { key: 'failclean', title: '失败清理', icon: MODULE_ICONS.failclean, desc: '整理失败时立即清理源文件与下载历史，并定时清理重复残留。' },
  { key: 'rename', title: '种子重命名', icon: MODULE_ICONS.rename, desc: '转移后自动根据 TMDB 信息命名种子，失败记录进定时补查，也可手动补刀。' },
  { key: 'tag', title: '分类与标签', icon: MODULE_ICONS.tag, desc: '转移后自动根据 tracker 域名打站点标签。' },
  { key: 'upload', title: '上传限速', icon: MODULE_ICONS.upload_limit, desc: '设置下载器全局上传上限，并按需限制指定站点的合计上传速度。' },
];

const subTabs = {
  upload: [
    { key: 'upload_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'upload_rules', title: '限速规则', icon: 'mdi-speedometer' },
  ],
  transfer: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'tasks', title: '任务列表', icon: 'mdi-playlist-check' },
  ],
  hr: [
    { key: 'hr_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'hr_sites', title: '站点规则', icon: 'mdi-home-outline' },
  ],
  remover: [
    { key: 'remover_basic', title: '基础设置', icon: 'mdi-tune-variant' },
  ],
  failclean: [{ key: 'failclean_basic', title: '基础设置', icon: 'mdi-tune-variant' }],
  rename: [
    { key: 'rename_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'rename_format', title: '重命名模板', icon: 'mdi-format-text' },
  ],
  tag: [
    { key: 'tag_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'mapping', title: '映射规则', icon: 'mdi-link-variant' },
  ],
};

// 历史子页跳转仍落在保留内容的新位置。
const legacySubTabs = { seed_basic: 'basic', hr_advanced: 'hr_basic', remover_conditions: 'remover_basic' };
watch(activeSub, key => {
  if (legacySubTabs[key]) activeSub.value = legacySubTabs[key];
}, { flush: 'sync' });

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0]);
const currentSubs = computed(() => subTabs[activeMain.value] || []);
/** 下载器下拉统一展示「名称 (类型)」；value 仍是下载器名，后端只认名字。 */
const downloaderSelectItems = computed(() => downloaderItems.value.map(item => ({
  ...item,
  title: `${item.title} (${item.type})`,
})));
const qbDownloaderItems = computed(() => downloaderItems.value.filter(item => item.type === 'qbittorrent'));
const uploadDownloaderItems = computed(() => downloaderItems.value.filter(item => ['qbittorrent', 'transmission'].includes(item.type)));
const uploadSelectedDownloaders = computed(() => {
  const selected = new Set(form.upload_limit_downloaders || []);
  return uploadDownloaderItems.value.filter(item => selected.has(item.value))
});
const uploadMissingLimits = computed(() => uploadSelectedDownloaders.value.filter(
  item => !uploadDownloaderLimit(item.value),
));
const uploadNewSiteName = ref('');
const uploadAddError = ref('');
function addUploadSiteRule() {
  uploadAddError.value = '';
  const name = String(uploadNewSiteName.value || '').trim();
  if (!name) { uploadAddError.value = '请输入或选择站点名称'; return }
  if (Object.keys(form.upload_limit_site_rules || {}).some(existing => existing.toLocaleLowerCase() === name.toLocaleLowerCase())) {
    uploadAddError.value = '该站点已存在，请编辑原行'; return
  }
  setUploadSiteRule(name, 0);
  uploadNewSiteName.value = '';
}
const uploadSiteRuleRows = computed(() => Object.entries(form.upload_limit_site_rules || {})
  .map(([name, rule]) => ({ name, limit_kib: Number(rule?.limit_kib || 0) || null }))
  .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')));
const hrBrushPluginItems = ['BrushFlow', '不启用'];
const hrNotifyModeItems = [
  { title: '不发送', value: 'none' },
  { title: '仅异常', value: 'on_error' },
  { title: '全部', value: 'always' },
];
// 通知开关仅映射已有三态，关闭后保留本次编辑选择，避免重开丢失“仅异常”。
const hrLastNotifyMode = ref('always');
watch(() => form.hr_notify, mode => {
  if (mode === 'always' || mode === 'on_error') hrLastNotifyMode.value = mode;
}, { immediate: true });
const hrNotificationEnabled = computed({
  get: () => form.hr_notify !== 'none',
  set: enabled => { form.hr_notify = enabled ? hrLastNotifyMode.value : 'none'; },
});
const hrEnabledNotifyModeItems = hrNotifyModeItems.filter(item => item.value !== 'none');
const removerActionItems = [
  { title: '暂停任务', value: 'pause' },
  { title: '删除任务', value: 'delete' },
  { title: '删除任务及文件', value: 'deletefile' },
];
const tagCatPairs = ref([]);
const tagCategoryNames = ref([]);
const tagCategoriesLoading = ref(false);
const tagCategoriesLoaded = ref(false);
const tagCategoriesError = ref('');
// MP 分类仅作为展示候选，载入不回写配置；旧映射完整保留。
const tagCategoryRows = computed(() => {
  const names = new Set(tagCategoryNames.value);
  return [
    ...tagCategoryNames.value.map(from => ({ from, to: tagCatPairs.value.find(pair => pair.from === from)?.to ?? from, legacy: false })),
    ...tagCatPairs.value.filter(pair => !names.has(pair.from)).map(pair => ({ ...pair, legacy: true })),
  ]
});
async function loadTagCategories() {
  if (tagCategoriesLoading.value) return
  tagCategoriesLoading.value = true;
  tagCategoriesError.value = '';
  try {
    if (!props.api?.get) throw new Error('MoviePilot API 未就绪')
    const response = await props.api.get('media/category', { feedback: 'silent' });
    if (response?.success === false) throw new Error(response.message || '获取 MP 分类失败')
    const categories = response?.success === true ? response.data : response;
    if (!categories || Array.isArray(categories) || typeof categories !== 'object'
        || !Object.values(categories).every(list => Array.isArray(list) && list.every(name => typeof name === 'string'))) {
      throw new Error('MP 分类接口返回格式不正确')
    }
    tagCategoryNames.value = [...new Set(Object.values(categories).flat().filter(name => name.trim()))];
    tagCategoriesLoaded.value = true;
  } catch (error) {
    tagCategoriesError.value = error?.message || '获取 MP 分类失败';
  } finally {
    tagCategoriesLoading.value = false;
  }
}
function setTagCategoryTarget(from, value) {
  const pair = tagCatPairs.value.find(item => item.from === from);
  if (pair) pair.to = value ?? '';
  else tagCatPairs.value.push({ from, to: value ?? '' });
}
function removeLegacyCategory(from) {
  tagCatPairs.value = tagCatPairs.value.filter(pair => pair.from !== from);
}
const tagTrackerPairs = ref([]);

function parseCatPairs(cats, renames) {
  const catsList = Array.isArray(cats) ? cats : [];
  const renamesList = Array.isArray(renames) ? renames : [];
  const rows = [];
  for (let i = 0; i < Math.max(catsList.length, renamesList.length); i++) {
    rows.push({ from: catsList[i] || '', to: renamesList[i] || '' });
  }
  return rows
}

function parseTrackerPairs(text) {
  return String(text || '').split('\n').map(line => {
    const [from, ...rest] = line.split('->');
    return { tracker: (from || '').trim(), site: rest.join('->').trim() }
  }).filter(p => p.tracker || p.site)
}

function serializeCatPairs(pairs) {
  return {
    tag_all_cat: pairs.map(p => (p.from || '').trim()).filter(Boolean),
    tag_all_cat_rename: pairs.map(p => (p.to || '').trim()),
  }
}

function serializeTrackerPairs(pairs) {
  return pairs
    .map(p => `${(p.tracker || '').trim()} -> ${(p.site || '').trim()}`)
    .filter(line => !line.startsWith(' -> '))
    .join('\n')
}

function parseCustomSiteLabels(text) {
  const out = {};
  String(text || '').split('\n').forEach(line => {
    const [from, ...rest] = line.split('->');
    const domain = (from || '').trim().toLowerCase();
    const label = rest.join('->').trim();
    if (domain && label) out[domain] = label;
  });
  return out
}

function serializeCustomSiteLabels(pairs) {
  // 未出现在映射编辑器中的旧自定义域名不属于本次行编辑，继续原样保留。
  const editedDomains = new Set([...parseTrackerPairs(form.tag_tracker_mappings_str), ...pairs]
    .map(p => String(p.site || p.tracker || '').trim().toLowerCase()));
  const retained = String(form.tag_custom_sites_str || '').split('\n')
    .filter(line => line.trim() && !editedDomains.has(line.split('->')[0].trim().toLowerCase()));
  const mapped = pairs
    .filter(p => !siteNameByDomain(p.site || p.tracker) && String(p.custom || '').trim())
    .map(p => `${(p.site || p.tracker || '').trim().toLowerCase()} -> ${String(p.custom).trim()}`);
  return [...retained, ...mapped].join('\n')
}

function siteNameByDomain(domain) {
  const clean = String(domain || '').trim().toLowerCase();
  if (!clean) return ''
  const hit = (siteItems.value || []).find(s => String(s.domain || '').toLowerCase() === clean);
  return hit?.title || ''
}


function parseTrackerEditor() {
  const customLabels = parseCustomSiteLabels(form.tag_custom_sites_str);
  return parseTrackerPairs(form.tag_tracker_mappings_str).map(p => ({
    ...p,
    custom: customLabels[String(p.site || p.tracker || '').trim().toLowerCase()] || '',
  }))
}

function addTrackerPair() {
  tagTrackerPairs.value.push({ tracker: '', site: '' });
}

// ═══ 转移做种 · 多任务引擎（transfer_tasks / downloader_ext）═══

/** 任务字段与后端 service/transfer_tasks.py::_TASK_DEFAULTS 一致。 */
const transferTaskDefaults = {
  name: '', enabled: true, from_downloader: '', to_downloader: '',
  include_category: '', include_labels: '', exclude_labels: '', empty_label_ok: true,
  no_paths: '', from_path: '', to_path: '',
  delete_source: 'inherit', delete_duplicate: 'inherit', keep_category: true, keep_tag: true,
  transfer_tag: '已转移',
};

/** 对话框草稿；ext_* 只用于 downloader_ext，不进入任务对象。 */
function blankTransferForm() {
  return { ...transferTaskDefaults, ext_webui_url: '', ext_source_plugin: '' }
}

function normalizeTransferDeleteState(value, legacyDefault) {
  return value === true || value === false || value === 'inherit' ? value : legacyDefault
}

function parseTransferTasks(raw) {
  let parsed;
  try {
    parsed = JSON.parse(String(raw || '[]'));
  } catch (error) {
    console.error('transfer_tasks 解析失败:', error);
    return []
  }
  if (!Array.isArray(parsed)) return []
  return parsed
    .filter(item => item && typeof item === 'object')
    .map(item => ({
      ...transferTaskDefaults,
      ...item,
      delete_source: normalizeTransferDeleteState(item.delete_source, false),
      delete_duplicate: normalizeTransferDeleteState(item.delete_duplicate, true),
      enabled: item.enabled !== false,
    }))
}

function parseDownloaderExt(raw) {
  let parsed;
  try {
    parsed = JSON.parse(String(raw || '{}'));
  } catch (error) {
    console.error('downloader_ext 解析失败:', error);
    return {}
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
  return Object.fromEntries(Object.entries(parsed).map(([name, value]) => [name, {
    ...value,
    webui_url: String(value?.webui_url || ''),
    source_plugin: String(value?.source_plugin || ''),
  }]))
}


function downloaderTypeOf(name) {
  return downloaderItems.value.find(item => item.value === name)?.type || ''
}

function downloaderTitle(name) {
  const hit = downloaderItems.value.find(item => item.value === name);
  return hit ? hit.title : (name || '—')
}

/** 筛选条件摘要：只列实际生效的条件，无条件时明确显示「不限分类」。 */
function taskFilterChips(task) {
  const chips = [];
  const category = String(task.include_category || '').trim();
  chips.push(category ? `分类 ${category}` : '不限分类');
  const labels = String(task.include_labels || '').trim();
  if (labels) chips.push(`标签 ${labels}`);
  const excludeLabels = String(task.exclude_labels || '').trim();
  if (excludeLabels) chips.push(`排除 ${excludeLabels}`);
  if (task.empty_label_ok) chips.push('允许无标签');
  if (task.no_paths) chips.push('不限路径');
  return chips
}

/** 设置列徽标：显示该任务启用了哪些高级设置，未启用任何项时前端显示「默认」。 */
function taskSettingBadges(task) {
  const badges = [];
  if (task.delete_source === true) badges.push({ text: '删源种', color: 'error' });
  if (task.delete_duplicate === true) badges.push({ text: '去重', color: 'warning' });
  if (!task.keep_category) badges.push({ text: '不保留分类', color: 'secondary' });
  if (!task.keep_tag) badges.push({ text: '不保留标签', color: 'secondary' });
  const transferTag = String(task.transfer_tag || '').trim();
  if (transferTag) badges.push({ text: `标签 ${transferTag}`, color: 'primary' });
  const ext = transferExt.value[task.name] || {};
  if (ext.webui_url) badges.push({ text: 'WebUI 覆盖', color: 'info' });
  if (ext.source_plugin) badges.push({ text: 'source 插件', color: 'info' });
  return badges
}

const transferDeleteTriStateItems = [
  { title: '继承全局', value: 'inherit' },
  { title: '开启', value: true },
  { title: '关闭', value: false },
];
const transferDeleteItems = defaultEnabled => transferDeleteTriStateItems.map(item => item.value === 'inherit'
  ? { ...item, title: `默认（${defaultEnabled ? '开启' : '关闭'}）` } : item);
const transferDeleteOriginLabels = {
  task: '任务覆盖',
  global: '继承全局',
  'legacy-default': '升级前默认',
};

function transferStatusForTask(task) {
  return transferStatusTasks.value.find(item => item?.name === task?.name) || null
}

function transferDeleteMeta(task, field) {
  const status = transferStatusForTask(task);
  const origin = status?.[`${field}_origin`];
  const effective = status?.[`${field}_effective`];
  return {
    origin: transferDeleteOriginLabels[origin] || '—',
    effective: effective === true ? '开启' : (effective === false ? '关闭' : '—'),
  }
}

const transferDialogSourceType = computed(() => (
  downloaderItems.value.find(item => item.value === transferForm.from_downloader)?.type || ''
));

const transferDeleteName = computed(() => transferTasks.value[transferDeleteIndex.value]?.name || '');

function loadTransferTaskExt(name) {
  const entry = transferExt.value[name] || {};
  transferForm.ext_webui_url = entry.webui_url || '';
  transferForm.ext_source_plugin = entry.source_plugin || '';
}

// 对话框内改源下载器时同步该下载器的 downloader_ext 草稿
watch(() => transferForm.from_downloader, name => loadTransferTaskExt(name));

function openTransferDialog(index = -1) {
  transferError.value = '';
  transferEditing.value = index;
  const task = index >= 0 ? transferTasks.value[index] : null;
  Object.keys(transferForm).forEach(key => delete transferForm[key]);
  Object.assign(transferForm, blankTransferForm(), task || {});
  loadTransferTaskExt(transferForm.from_downloader);
  transferDialog.value = true;
}

function confirmTransferTask() {
  transferError.value = '';
  const from = String(transferForm.from_downloader || '');
  const to = String(transferForm.to_downloader || '');
  const fromPath = String(transferForm.from_path || '').trim();
  const toPath = String(transferForm.to_path || '').trim();
  if (!from || !to) {
    transferError.value = '请选择源下载器与目的下载器';
    return
  }
  if (from === to) {
    transferError.value = '源下载器与目的下载器不能相同';
    return
  }
  // 路径映射是可选能力：两者都空 = 不做映射（后端 convert_save_path 契约 C1 同样原样返回）。
  // 只有「只填了一个」才是配置错误——那会让映射方向不明。
  if (Boolean(fromPath) !== Boolean(toPath)) {
    transferError.value = '源数据路径与目的数据路径需同时填写或同时留空（都留空＝不做路径映射）';
    return
  }
  const index = transferEditing.value;
  const task = {
    ...transferTaskDefaults,
    ...(index >= 0 ? transferTasks.value[index] : {}),
    name: String(transferForm.name || '').trim() || `任务${index >= 0 ? index + 1 : transferTasks.value.length + 1}`,
    enabled: transferForm.enabled !== false,
    from_downloader: from,
    to_downloader: to,
    include_category: String(transferForm.include_category || '').trim(),
    include_labels: String(transferForm.include_labels || '').trim(),
    exclude_labels: String(transferForm.exclude_labels || '').trim(),
    empty_label_ok: transferForm.empty_label_ok !== false,
    no_paths: String(transferForm.no_paths || ''),
    from_path: fromPath,
    to_path: toPath,
    delete_source: normalizeTransferDeleteState(transferForm.delete_source, 'inherit'),
    delete_duplicate: normalizeTransferDeleteState(transferForm.delete_duplicate, 'inherit'),
    keep_category: transferForm.keep_category !== false,
    keep_tag: transferForm.keep_tag !== false,
    transfer_tag: String(transferForm.transfer_tag ?? '').trim(),
  };
  transferTasks.value = index >= 0
    ? transferTasks.value.map((item, position) => (position === index ? task : item))
    : [...transferTasks.value, task];
  if (transferDialogSourceType.value === 'rtorrent') {
    transferExt.value = {
      ...transferExt.value,
      [from]: {
        ...transferExt.value[from],
        webui_url: String(transferForm.ext_webui_url || '').trim(),
        source_plugin: String(transferForm.ext_source_plugin || '').trim(),
      },
    };
  }
  transferDialog.value = false;
}

function askTransferDelete(index) {
  transferDeleteIndex.value = index;
  transferDeleteDialog.value = true;
}

function confirmTransferDelete() {
  transferTasks.value = transferTasks.value.filter((_, position) => position !== transferDeleteIndex.value);
  transferDeleteDialog.value = false;
}
// H&R 规则键；initialConfig 的 immediate watcher 放在 setup 末尾，
// 确保 YAML 分档解析依赖的 hrTierFields 等声明也已初始化。
const hrSiteRuleKeys = ['hr_duration', 'additional_seed_time', 'hr_deadline_days', 'hr_ratio', 'hr_upload_multiplier', 'hr_upload_gte_download', 'hr_active'];
const hrListRuleKeys = ['trackers'];
const hrTierValueKeys = ['hr_duration', 'hr_deadline_days'];


function switchToData() {
  emit('switch');
}
function buildSavePayload() {
  return {
    ...form,
    transfer_tasks: JSON.stringify(transferTasks.value),
    downloader_ext: JSON.stringify(transferExt.value),
    upload_limit_downloaders: [...(form.upload_limit_downloaders || [])],
    upload_limit_downloader_limits_kib: { ...(form.upload_limit_downloader_limits_kib || {}) },
    upload_limit_site_rules: Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }])),
    hr_downloader: [...(form.hr_downloader || [])],
    hr_sites: [...(form.hr_sites || [])],
    hr_exclude_tags: [...(form.hr_exclude_tags || [])],
    hr_exclude_categories: [...(form.hr_exclude_categories || [])],
    remover_downloaders: [...(form.remover_downloaders || [])],
    rename_downloaders: [...(form.rename_downloaders || [])],
    tag_downloaders: [...(form.tag_downloaders || [])],
    tag_downloaders: [...(form.tag_downloaders || [])],
    // 未编辑的映射保留原串/数组（含未收录旧值），不因保存其他页而重排。
    ...(JSON.stringify(tagCatPairs.value) === JSON.stringify(parseCatPairs(form.tag_all_cat, form.tag_all_cat_rename))
      ? {} : serializeCatPairs(tagCatPairs.value)),
    ...(JSON.stringify(tagTrackerPairs.value) === JSON.stringify(parseTrackerEditor()) ? {} : {
      tag_tracker_mappings_str: serializeTrackerPairs(tagTrackerPairs.value),
      tag_custom_sites_str: serializeCustomSiteLabels(tagTrackerPairs.value),
    }),
  }
}

async function saveConfig() {
  const payload = buildSavePayload();
  saveMessage.value = '';
  saveError.value = false;
  savePending.value = true;
  try {
    if (!props.api?.put) throw new Error('MoviePilot 插件 API 未就绪')
    // 不得改回 emit('save')：宿主 closeOn 含 save，会立即关闭配置窗口（P3 自保存方案的前提）
    const response = await props.api.put(`plugin/${props.pluginId}`, payload);
    if (response?.success === false || response?.data?.success === false) {
      throw new Error(response.message || response.data?.message || '保存配置失败')
    }
    saveMessage.value = '配置已保存，窗口保持打开；如需同步插件列表/侧边导航，请刷新页面。';
  } catch (error) {
    saveError.value = true;
    saveMessage.value = error?.response?.data?.message || error?.data?.message || error?.message || '保存配置失败';
  } finally {
    savePending.value = false;
  }
}
function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key;
  activeSub.value = subTabs[key]?.[0]?.key || '';
}

function uploadDownloaderLimit(downloaderId) {
  const value = Number(form.upload_limit_downloader_limits_kib?.[downloaderId] || 0);
  return value > 0 ? value : null
}

function setUploadDownloaderLimit(downloaderId, value) {
  const mapping = { ...(form.upload_limit_downloader_limits_kib || {}) };
  const normalized = Number(value);
  if (Number.isFinite(normalized) && normalized > 0) mapping[downloaderId] = Math.floor(normalized);
  else delete mapping[downloaderId];
  form.upload_limit_downloader_limits_kib = mapping;
}

function setUploadSiteRule(siteName, value) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]));
  const current = rules[siteName] || { limit_kib: 0 };
  const limit = Number(value);
  current.limit_kib = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 0;
  rules[siteName] = current;
  form.upload_limit_site_rules = rules;
}

function removeUploadSiteRule(siteName) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]));
  delete rules[siteName];
  form.upload_limit_site_rules = rules;
}

// ═══ H&R 站点规则：内置预设 + 自定义 YAML 双层合并视图（v3.6.0）═══

/** 站点规则可编辑字段，键名与后端 HrSiteRule 一致。 */
const hrNumberFields = [
  { key: 'hr_duration', label: '做种时长（小时）' },
  { key: 'additional_seed_time', label: '额外做种时间（小时）' },
  { key: 'hr_deadline_days', label: '考核期（天）' },
  { key: 'hr_ratio', label: '分享率' },
  { key: 'hr_upload_multiplier', label: '上传倍数' },
];
const hrFlagFields = [
  { key: 'hr_upload_gte_download', label: '上传量≥下载量' },
  { key: 'hr_active', label: '强制纳管' },
];
const hrTierFields = [
  { key: 'max_size_gib', label: '上限（GiB）' },
  { key: 'hr_duration', label: '做种时长（小时）' },
  { key: 'hr_deadline_days', label: '考核期（天）' },
];
/** 生效值摘要列；布尔与分档字段单独格式化。 */
const hrSummaryFields = [
  { key: 'hr_duration', label: '做种时长', unit: ' 小时' },
  { key: 'additional_seed_time', label: '额外做种', unit: ' 小时' },
  { key: 'hr_deadline_days', label: '考核期', unit: ' 天' },
  { key: 'hr_ratio', label: '分享率', unit: '' },
  { key: 'hr_upload_multiplier', label: '上传倍数', unit: '' },
  { key: 'hr_upload_gte_download', label: '上传≥下载', unit: '', boolean: true },
  { key: 'hr_active', label: '强制纳管', unit: '', boolean: true },
  { key: 'hr_size_tiers', label: '体积分档', unit: '', tiers: true },
];
const hrTriStateItems = [
  { title: '继承全局', value: 'inherit' },
  { title: '是', value: 'true' },
  { title: '否', value: 'false' },
];

/** 全局规则当前值（config 表单的 hr_* 全局字段），供「继承」显示与 tooltip 使用。 */
const hrGlobalRule = computed(() => ({
  hr_duration: form.hr_duration,
  additional_seed_time: form.hr_additional_seed_time,
  hr_deadline_days: form.hr_deadline_days,
  hr_ratio: form.hr_ratio,
  hr_upload_multiplier: form.hr_upload_multiplier,
  hr_upload_gte_download: form.hr_upload_gte_download,
  hr_active: form.hr_active,
  hr_size_tiers: form.hr_size_tiers,
}));

function hrIsYamlFalse(value) {
  if (value === false) return true
  if (typeof value !== 'string') return false
  return ['false', '0', 'no', 'off'].includes(value.trim().toLowerCase())
}

function hrIsYamlTrue(value) {
  if (value === true) return true
  if (typeof value !== 'string') return false
  return ['true', '1', 'yes', 'on'].includes(value.trim().toLowerCase())
}

function hrFormatSummary(field, value) {
  if (field.tiers) return Array.isArray(value) ? `${value.length} 档` : '已配置'
  if (field.boolean) return hrIsYamlTrue(value) ? '是' : '否'
  const numeric = Number(value);
  return `${Number.isFinite(numeric) ? String(numeric) : String(value)}${field.unit || ''}`
}

function hrGlobalText(key) {
  const field = hrSummaryFields.find(item => item.key === key) || { };
  const value = hrGlobalRule.value[key];
  if (value === undefined || value === null || value === '') return '未设置'
  return hrFormatSummary(field, value)
}

function hrHasRuleValues(rule) {
  if (!rule) return false
  if (Array.isArray(rule.hr_size_tiers)) return true
  if (Array.isArray(rule.trackers) && rule.trackers.length) return true
  return hrSiteRuleKeys.some(key => rule[key] !== undefined && rule[key] !== null)
}

function hrPresetRules() {
  const map = new Map();
  for (const preset of hrPresets.value) {
    const name = String(preset?.site_name || '').trim();
    if (name) map.set(name, preset?.rule || {});
  }
  return map
}

const hrSiteRows = computed(() => {
  const presets = hrPresetRules();
  const customMap = new Map();
  for (const rule of hrCustomRules.value) customMap.set(rule.site_name, rule);
  const extraNames = [...customMap.keys()].filter(name => !presets.has(name)).sort((left, right) => left.localeCompare(right, 'zh-CN'));
  const names = [...presets.keys(), ...extraNames];
  return names.map(name => {
    const preset = presets.get(name) || null;
    const entry = customMap.get(name) || null;
    const blocked = !!entry && hrIsYamlFalse(entry.enabled);
    // enabled 的自定义条目整条覆写预设；内置站的纯影子条目（仅 enabled:false）仍按内置行展示
    const customRow = !!entry && (!preset || !(blocked && !hrHasRuleValues(entry)));
    const sourceRule = blocked ? null : (customRow ? entry : preset);
    const sourceLabel = customRow ? (preset ? '自定义·覆写' : '自定义') : '内置';
    const sourceColor = sourceLabel === '内置' ? 'default' : (sourceLabel === '自定义·覆写' ? 'primary' : 'info');
    const cells = hrSummaryFields.map(field => {
      const value = sourceRule ? sourceRule[field.key] : undefined;
      const inherited = value === undefined || value === null || value === '';
      return {
        key: field.key,
        label: field.label,
        color: `var(--dm-hr-rule-${field.key})`,
        inherited,
        text: inherited ? hrGlobalText(field.key) : hrFormatSummary(field, value),
        tooltip: inherited
          ? `${field.label}：站点未设置，继承全局（${hrGlobalText(field.key)}）`
          : `${field.label}：${hrFormatSummary(field, value)}（${sourceLabel}）`,
      }
    });
    const visibleCells = hrShowInherited.value ? cells : cells.filter(cell => !cell.inherited);
    const summaryCells = visibleCells.slice(0, 3);
    const overflowCells = cells.filter(cell => !summaryCells.includes(cell));
    return {
      name,
      entry,
      preset: !!preset,
      enabled: !blocked,
      blocked,
      custom: customRow,
      expanded: hrExpandedSites.value.includes(name),
      cells,
      visibleCells,
      summaryCells,
      overflowCells,
      inheritedCount: cells.length - visibleCells.length,
      sourceLabel,
      sourceColor,
    }
  })
});

function hrFindCustomRule(name) {
  return hrCustomRules.value.find(rule => rule.site_name === name) || null
}

function hrReplaceCustomRule(name, rule) {
  hrCommitCustomRules(hrCustomRules.value.map(item => (item.site_name === name ? rule : item)));
}

function hrCommitCustomRules(rules) {
  hrCustomRules.value = rules;
  const text = serializeHrSiteConfigYaml(rules);
  hrSyncedSiteConfigText = text;
  hrRawError.value = '';
  form.hr_site_config_str = text;
}

function hrSetSiteEnabled(name, enabled) {
  const entry = hrFindCustomRule(name);
  const nextEnabled = enabled !== false;
  if (!entry) {
    if (!nextEnabled) hrCommitCustomRules([...hrCustomRules.value, { site_name: name, enabled: false }]);
    return
  }
  // 内置站的纯影子条目：开启开关即删除条目，该站回到内置预设
  if (nextEnabled && hrIsYamlFalse(entry.enabled) && !hrHasRuleValues(entry) && hrPresetRules().has(name)) {
    hrRemoveCustomSite(name);
    return
  }
  hrReplaceCustomRule(name, { ...entry, enabled: nextEnabled });
}

function hrRemoveCustomSite(name) {
  hrCommitCustomRules(hrCustomRules.value.filter(rule => rule.site_name !== name));
}

function hrCopyPresetToCustom(name) {
  const preset = hrPresetRules().get(name) || {};
  const entry = hrFindCustomRule(name);
  const rule = { site_name: name, enabled: entry ? !hrIsYamlFalse(entry.enabled) : true };
  for (const field of [...hrNumberFields, ...hrFlagFields]) {
    const value = preset[field.key];
    if (value !== undefined && value !== null) rule[field.key] = value;
  }
  if (Array.isArray(preset.hr_size_tiers)) rule.hr_size_tiers = preset.hr_size_tiers.map(tier => ({ ...tier }));
  hrCommitCustomRules([...hrCustomRules.value.filter(item => item.site_name !== name), rule]);
  if (!hrExpandedSites.value.includes(name)) hrExpandedSites.value = [...hrExpandedSites.value, name];
}

function hrToggleExpanded(name) {
  hrExpandedSites.value = hrExpandedSites.value.includes(name)
    ? hrExpandedSites.value.filter(item => item !== name)
    : [...hrExpandedSites.value, name];
}

function hrRuleNumber(rule, key) {
  const value = rule?.[key];
  return value === undefined || value === null ? '' : value
}

function hrRuleFlag(rule, key) {
  const value = rule?.[key];
  if (value === undefined || value === null) return 'inherit'
  return hrIsYamlTrue(value) ? 'true' : 'false'
}

function hrRuleTrackers(rule) {
  return Array.isArray(rule?.trackers) ? [...rule.trackers] : []
}

function hrNormalizeTrackers(value) {
  const items = Array.isArray(value) ? value : [value];
  const result = [];
  for (const item of items) {
    const text = String(item ?? '').trim();
    if (text && !result.includes(text)) result.push(text);
  }
  return result
}

function hrSetRuleTrackers(name, value) {
  const entry = hrFindCustomRule(name);
  if (!entry) return
  const next = { ...entry };
  const trackers = hrNormalizeTrackers(value);
  if (trackers.length) next.trackers = trackers;
  else delete next.trackers;
  hrReplaceCustomRule(name, next);
}

function hrTierNumber(tier, key) {
  const value = tier?.[key];
  return value === undefined || value === null ? 0 : value
}

function hrSetRuleNumber(name, key, value) {
  const entry = hrFindCustomRule(name);
  if (!entry) return
  const next = { ...entry };
  const text = String(value ?? '').trim();
  if (!text) {
    delete next[key];
  } else {
    const numeric = Number(text);
    if (!Number.isFinite(numeric)) return
    next[key] = numeric;
  }
  hrReplaceCustomRule(name, next);
}

function hrSetRuleFlag(name, key, value) {
  const entry = hrFindCustomRule(name);
  if (!entry) return
  const next = { ...entry };
  if (value === 'inherit') delete next[key];
  else next[key] = value === 'true';
  hrReplaceCustomRule(name, next);
}

function hrAddTier(name) {
  const entry = hrFindCustomRule(name);
  if (!entry) return
  const tiers = (entry.hr_size_tiers || []).map(tier => ({ ...tier }));
  tiers.push({ max_size_gib: 0, hr_duration: 0, hr_deadline_days: 0 });
  hrReplaceCustomRule(name, { ...entry, hr_size_tiers: tiers });
}

function hrRemoveTier(name, index) {
  const entry = hrFindCustomRule(name);
  if (!entry) return
  const tiers = (entry.hr_size_tiers || []).filter((_, position) => position !== index);
  const next = { ...entry };
  if (tiers.length) next.hr_size_tiers = tiers;
  else delete next.hr_size_tiers;
  hrReplaceCustomRule(name, next);
}

function hrSetTierNumber(name, index, key, value) {
  const entry = hrFindCustomRule(name);
  if (!entry) return
  const tiers = (entry.hr_size_tiers || []).map(tier => ({ ...tier }));
  if (!tiers[index]) return
  const text = String(value ?? '').trim();
  const numeric = text ? Number(text) : 0;
  tiers[index] = { ...tiers[index], [key]: Number.isFinite(numeric) ? numeric : 0 };
  hrReplaceCustomRule(name, { ...entry, hr_size_tiers: tiers });
}

function hrOpenAddDialog() {
  hrNewSiteName.value = '';
  hrAddError.value = '';
  hrAddDialog.value = true;
}

function hrConfirmAddSite() {
  hrAddError.value = '';
  const name = hrNewSiteName.value.trim();
  if (!name) {
    hrAddError.value = '请输入站点名';
    return
  }
  if (hrPresetRules().has(name)) {
    hrAddError.value = '该站点是内置预设，请用「复制为自定义」创建覆写';
    return
  }
  if (hrCustomRules.value.some(rule => rule.site_name === name)) {
    hrAddError.value = '该站点已存在自定义条目';
    return
  }
  hrCommitCustomRules([...hrCustomRules.value, { site_name: name, enabled: true }]);
  hrExpandedSites.value = [...hrExpandedSites.value, name];
  hrAddDialog.value = false;
}

async function loadHrPresets(force = false) {
  if (hrPresetsLoading.value || (hrPresetsLoaded.value && !force)) return
  hrPresetsLoading.value = true;
  hrPresetsMessage.value = '';
  try {
    const response = await getApi('hr_presets', { feedback: 'silent' });
    const presets = Array.isArray(response?.presets) ? response.presets : [];
    hrPresets.value = presets.filter(preset => String(preset?.site_name || '').trim());
    hrPresetsLoaded.value = true;
    if (!hrPresets.value.length) hrPresetsMessage.value = '未返回内置预设，可继续使用自定义站点规则';
  } catch (error) {
    hrPresetsMessage.value = error?.message || '内置预设获取失败';
  } finally {
    hrPresetsLoading.value = false;
  }
}

function hrApplySiteConfigText(text) {
  const parsed = parseHrSiteConfigYaml(text);
  if (parsed.error) {
    hrRawError.value = `站点规则 YAML 解析失败：${parsed.error}`;
    hrRawOpen.value = true;
    return
  }
  hrRawError.value = '';
  hrCustomRules.value = parsed.rules;
}

function syncHrSiteRulesFromForm() {
  const text = String(form.hr_site_config_str ?? '');
  hrSyncedSiteConfigText = text;
  hrApplySiteConfigText(text);
}

watch(() => form.hr_site_config_str, raw => {
  const text = String(raw ?? '');
  if (text === hrSyncedSiteConfigText) return
  hrSyncedSiteConfigText = text;
  hrApplySiteConfigText(text);
});

// ── hr_site_config_str 的最小 YAML 列表读写（只覆盖后端接受的字段结构）──

function hrStripComment(line) {
  let quote = '';
  for (let index = 0; index < line.length; index++) {
    const char = line.charAt(index);
    if (quote) {
      if (char === quote) quote = '';
      continue
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue
    }
    if (char === '#') {
      const previous = index === 0 ? '' : line.charAt(index - 1);
      if (index === 0 || previous === ' ' || previous === '\t') return line.slice(0, index)
    }
  }
  return line
}

function hrSplitKeyValue(text) {
  let quote = '';
  for (let index = 0; index < text.length; index++) {
    const char = text.charAt(index);
    if (quote) {
      if (char === quote) quote = '';
      continue
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue
    }
    if (char === ':') {
      const next = index + 1 < text.length ? text.charAt(index + 1) : '';
      if (!next || next === ' ' || next === '\t') {
        const key = text.slice(0, index).trim();
        return key ? { key, valueText: text.slice(index + 1).trim() } : null
      }
    }
  }
  return null
}

function hrParseScalar(text) {
  const trimmed = String(text ?? '').trim();
  if (!trimmed) return { value: null }
  const lower = trimmed.toLowerCase();
  if (trimmed === '~' || lower === 'null') return { value: null }
  if (['true', 'yes', 'on'].includes(lower)) return { value: true }
  if (['false', 'no', 'off'].includes(lower)) return { value: false }
  if (trimmed === '[]') return { value: [] }
  if (trimmed.startsWith('[') || trimmed.startsWith('{')) return { error: `${trimmed} 为行内列表/映射，暂不支持` }
  if (trimmed === '|' || trimmed === '>') return { error: '暂不支持块标量文本' }
  if (trimmed.length > 1 && trimmed.startsWith("'") && trimmed.endsWith("'")) return { value: trimmed.slice(1, -1).replaceAll("''", "'") }
  if (trimmed.length > 1 && trimmed.startsWith('"') && trimmed.endsWith('"')) return { value: trimmed.slice(1, -1).replaceAll('\\"', '"') }
  if (/^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$/.test(trimmed)) return { value: Number(trimmed) }
  return { value: trimmed }
}

function hrSplitFlowItems(text) {
  const items = [];
  let buffer = '';
  let quote = '';
  for (let index = 0; index < text.length; index++) {
    const char = text.charAt(index);
    if (quote) {
      buffer += char;
      if (char === quote) quote = '';
      continue
    }
    if (char === '"' || char === "'") {
      quote = char;
      buffer += char;
      continue
    }
    if (char === ',') {
      items.push(buffer.trim());
      buffer = '';
      continue
    }
    buffer += char;
  }
  items.push(buffer.trim());
  return items.filter(item => item !== '')
}

function hrParseFlowList(valueText) {
  const text = String(valueText ?? '').trim();
  if (!text.endsWith(']')) return { error: `${text} 行内列表未闭合` }
  const inner = text.slice(1, -1).trim();
  if (!inner) return { value: [] }
  const values = [];
  for (const item of hrSplitFlowItems(inner)) {
    const parsed = hrParseScalar(item);
    if (parsed.error) return { error: parsed.error }
    if (Array.isArray(parsed.value)) return { error: `列表项 ${item} 不是标量` }
    if (parsed.value === null || parsed.value === '') continue
    values.push(typeof parsed.value === 'string' ? parsed.value : String(parsed.value));
  }
  return { value: values }
}

function hrAssignScalar(target, key, valueText) {
  const text = String(valueText ?? '').trim();
  if (hrListRuleKeys.includes(key) && text.startsWith('[')) {
    const parsedList = hrParseFlowList(text);
    if (parsedList.error) return `字段 ${key}：${parsedList.error}`
    target[key] = parsedList.value;
    return ''
  }
  const parsed = hrParseScalar(valueText);
  if (parsed.error) return `字段 ${key}：${parsed.error}`
  if (Array.isArray(parsed.value)) {
    if (key !== 'hr_size_tiers') return `字段 ${key} 不接受列表值`
    target.hr_size_tiers = [];
    return ''
  }
  target[key] = parsed.value;
  return ''
}

function parseHrSiteConfigYaml(raw) {
  const lines = String(raw ?? '').replace(/\r\n?/g, '\n').split('\n');
  const items = [];
  let entry = null;
  let tier = null;
  let itemIndent = null;
  let entryIndent = null;
  let tiersIndent = null;
  let tierIndent = null;
  let inTiers = false;
  let inTrackers = false;
  let trackersIndent = null;
  for (let index = 0; index < lines.length; index++) {
    const content = hrStripComment(lines[index]);
    const body = content.trim();
    if (!body || body === '---' || body === '...') continue
    const indent = content.length - content.trimStart().length;
    const second = body.charAt(1);
    const isItem = body.startsWith('-') && (body.length === 1 || second === ' ' || second === '\t');
    const rest = body.length === 1 ? '' : body.slice(2).trim();
    if (isItem) {
      if (inTiers && (tierIndent === null || indent >= tierIndent)) {
        if (tierIndent === null) tierIndent = indent;
        tier = {};
        if (!Array.isArray(entry.hr_size_tiers)) entry.hr_size_tiers = [];
        entry.hr_size_tiers.push(tier);
        if (rest) {
          const pair = hrSplitKeyValue(rest);
          if (!pair) return { error: `第 ${index + 1} 行无法解析「${rest}」` }
          const failure = hrAssignScalar(tier, pair.key, pair.valueText);
          if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
        }
        continue
      }
      if (inTrackers && (trackersIndent === null || indent >= trackersIndent)) {
        if (trackersIndent === null) trackersIndent = indent;
        if (!Array.isArray(entry.trackers)) entry.trackers = [];
        const scalar = hrParseScalar(rest);
        if (scalar.error) return { error: `第 ${index + 1} 行 ${scalar.error}` }
        if (!Array.isArray(scalar.value) && scalar.value !== null && scalar.value !== '') {
          entry.trackers.push(String(scalar.value));
        }
        continue
      }
      inTiers = false;
      inTrackers = false;
      tier = null;
      if (itemIndent === null) itemIndent = indent;
      if (indent !== itemIndent) return { error: `第 ${index + 1} 行列表项缩进与首项不一致` }
      entry = {};
      entryIndent = null;
      tiersIndent = null;
      tierIndent = null;
      trackersIndent = null;
      items.push(entry);
      if (rest) {
        const pair = hrSplitKeyValue(rest);
        if (!pair) return { error: `第 ${index + 1} 行无法解析「${rest}」` }
        const failure = hrAssignScalar(entry, pair.key, pair.valueText);
        if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
      }
      continue
    }
    const pair = hrSplitKeyValue(body);
    if (!pair) return { error: `第 ${index + 1} 行无法解析「${body}」` }
    if (inTiers && tiersIndent !== null && indent <= tiersIndent) {
      inTiers = false;
      tier = null;
    }
    if (inTrackers && trackersIndent !== null && indent <= trackersIndent) inTrackers = false;
    if (inTrackers) return { error: `第 ${index + 1} 行 ${pair.key} 不是列表项（trackers 只接受「- 值」形式）` }
    if (inTiers) {
      if (!tier) return { error: `第 ${index + 1} 行分档字段缺少所属分档项` }
      const failure = hrAssignScalar(tier, pair.key, pair.valueText);
      if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
      continue
    }
    if (!entry) return { error: `第 ${index + 1} 行：顶层必须是列表，每项以「- site_name: 站点名」开头` }
    if (entryIndent === null) entryIndent = indent;
    else if (indent !== entryIndent) return { error: `第 ${index + 1} 行缩进与首字段不一致` }
    if (!pair.valueText) {
      if (pair.key === 'hr_size_tiers') {
        inTiers = true;
        tiersIndent = indent;
        tierIndent = null;
        tier = null;
        entry.hr_size_tiers = [];
        continue
      }
      if (hrListRuleKeys.includes(pair.key)) {
        inTrackers = true;
        trackersIndent = indent;
        entry[pair.key] = [];
        continue
      }
      return { error: `第 ${index + 1} 行 ${pair.key} 缺少值（仅 hr_size_tiers 与 trackers 支持列表）` }
    }
    const failure = hrAssignScalar(entry, pair.key, pair.valueText);
    if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
  }
  const merged = [];
  const positionByName = new Map();
  for (const item of items) {
    const name = String(item.site_name ?? '').trim();
    if (!name) return { error: '存在缺少 site_name 的站点条目' }
    const rule = { site_name: name };
    const extra = {};
    for (const [key, value] of Object.entries(item)) {
      if (key === 'site_name' || key === 'hr_size_tiers') continue
      if (key === 'enabled') {
        rule.enabled = !hrIsYamlFalse(value);
        continue
      }
      if (hrSiteRuleKeys.includes(key)) rule[key] = value;
      else if (hrListRuleKeys.includes(key)) rule[key] = hrNormalizeTrackers(Array.isArray(value) ? value : [value]);
      else extra[key] = value;
    }
    if (Object.keys(extra).length) rule._extra = extra;
    if (rule.enabled === undefined) rule.enabled = true;
    if (Array.isArray(item.hr_size_tiers)) {
      rule.hr_size_tiers = item.hr_size_tiers.map(item => {
        const values = {};
        for (const field of hrTierFields) {
          const numeric = Number(item?.[field.key]);
          if (Number.isFinite(numeric)) values[field.key] = numeric;
        }
        return values
      });
    }
    // 与后端一致：同名后项覆盖前项
    const existing = positionByName.get(name);
    if (existing === undefined) {
      positionByName.set(name, merged.length);
      merged.push(rule);
    } else {
      merged[existing] = rule;
    }
  }
  return { rules: merged }
}

function hrQuoteYaml(value) {
  return `'${String(value).replaceAll("'", "''")}'`
}

function hrYamlScalar(value) {
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  if (value === null || value === undefined) return 'null'
  if (Array.isArray(value)) return '[]'
  if (typeof value === 'object') return hrQuoteYaml(JSON.stringify(value))
  return hrQuoteYaml(value)
}

function serializeHrSiteConfigYaml(rules) {
  const blocks = [];
  for (const rule of rules || []) {
    const name = String(rule?.site_name || '').trim();
    if (!name) continue
    const lines = [`- site_name: ${hrQuoteYaml(name)}`];
    for (const key of hrSiteRuleKeys) {
      const value = rule[key];
      if (value === undefined || value === null) continue
      lines.push(`  ${key}: ${hrYamlScalar(value)}`);
    }
    if (Array.isArray(rule.trackers) && rule.trackers.length) {
      lines.push('  trackers:');
      for (const tracker of rule.trackers) {
        const text = String(tracker ?? '').trim();
        if (text) lines.push(`    - ${hrQuoteYaml(text)}`);
      }
    }
    if (Array.isArray(rule.hr_size_tiers)) {
      if (!rule.hr_size_tiers.length) {
        lines.push('  hr_size_tiers: []');
      } else {
        lines.push('  hr_size_tiers:');
        for (const tier of rule.hr_size_tiers) {
          const limit = Number(tier?.max_size_gib);
          lines.push(`    - max_size_gib: ${Number.isFinite(limit) ? limit : 0}`);
          for (const key of hrTierValueKeys) {
            const numeric = Number(tier?.[key]);
            if (Number.isFinite(numeric)) lines.push(`      ${key}: ${numeric}`);
          }
        }
      }
    }
    for (const [key, value] of Object.entries(rule._extra || {})) {
      lines.push(`  ${key}: ${hrYamlScalar(value)}`);
    }
    lines.push(`  enabled: ${rule.enabled === false ? 'false' : 'true'}`);
    blocks.push(lines.join('\n'));
  }
  return blocks.join('\n\n')
}

watch(() => props.initialConfig, v => {
Object.keys(form).forEach(k => delete form[k]);
  Object.assign(form, defaults, v || {});
  // 决策 A：全新安装（后端没有已保存配置）时观察模式默认开启；老配置升级保持升级前行为。
  if (!v || !Object.keys(v).length) {
    for (const key of OBSERVE_ONLY_KEYS) form[key] = true;
  }
  // 决策 A：自动删种继承旧「仅观察不执行」开关（仅在旧键存在且未保存过新键时生效）
  if (v?.migration_observe_only !== undefined && v?.remover_observe_only === undefined) {
    form.remover_observe_only = !!v.migration_observe_only;
  }
  form.upload_limit_downloaders = [...(v?.upload_limit_downloaders || [])];
  form.upload_limit_downloader_limits_kib = { ...(v?.upload_limit_downloader_limits_kib || {}) };
  form.upload_limit_site_rules = Object.fromEntries(Object.entries(v?.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]));
  form.hr_downloader = [...(v?.hr_downloader || [])];
  form.hr_sites = [...(v?.hr_sites || [])];
  form.hr_exclude_tags = [...(v?.hr_exclude_tags || [])];
  form.hr_exclude_categories = [...(v?.hr_exclude_categories || [])];
  form.remover_downloaders = [...(v?.remover_downloaders || [])];
  form.rename_downloaders = [...(v?.rename_downloaders || [])];
  form.tag_downloaders = [...(v?.tag_downloaders || [])];
  form.tag_all_cat = [...(v?.tag_all_cat || [])];
  form.tag_all_cat_rename = [...(v?.tag_all_cat_rename || [])];
  tagCatPairs.value = parseCatPairs(form.tag_all_cat, form.tag_all_cat_rename);
  tagTrackerPairs.value = parseTrackerEditor();
  syncHrSiteRulesFromForm();
  transferTasks.value = parseTransferTasks(form.transfer_tasks);
  transferExt.value = parseDownloaderExt(form.downloader_ext);
}, { immediate: true, deep: true });

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCombobox = _resolveComponent("VCombobox");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCronField = _resolveComponent("VCronField");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VMenu = _resolveComponent("VMenu");
  const _component_VTable = _resolveComponent("VTable");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VCheckbox = _resolveComponent("VCheckbox");

  return (_openBlock(), _createElementBlock("div", {
    class: _normalizeClass(["dm-config dm-config--compact", { 'dm-config--transfer': activeMain.value === 'transfer' }])
  }, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "dm-card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "dm-header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-download",
                  size: "24"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              density: "compact",
              modelValue: form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
              color: "primary",
              "hide-details": "",
              inset: "",
              label: form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dm-title" }, {
              default: _withCtx(() => [...(_cache[127] || (_cache[127] = [
                _createTextVNode("下载中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, { class: "dm-hint" }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(currentMain.value.desc), 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createElementVNode("div", _hoisted_1, [
          _createElementVNode("nav", _hoisted_2, [
            _createVNode(_component_VList, {
              density: "comfortable",
              nav: "",
              class: "dm-nav-list py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "dm-nav-item",
                    onClick: $event => (selectMain(item.key))
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: item.icon
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.title), 1)
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
          _createElementVNode("section", _hoisted_3, [
            _createElementVNode("div", _hoisted_4, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(currentSubs.value, (sub) => {
                return (_openBlock(), _createElementBlock("button", {
                  key: sub.key,
                  type: "button",
                  class: _normalizeClass(["dm-subtab", { 'dm-subtab--active': activeSub.value === sub.key }]),
                  onClick: $event => (activeSub.value = sub.key)
                }, [
                  _createVNode(_component_VIcon, {
                    icon: sub.icon,
                    size: "18",
                    class: "mr-1"
                  }, null, 8, ["icon"]),
                  _createTextVNode(_toDisplayString(sub.title), 1)
                ], 10, _hoisted_5))
              }), 128)),
              (PANE_RESET_KEYS[activeMain.value])
                ? (_openBlock(), _createBlock(_component_VBtn, {
                    key: 0,
                    size: "small",
                    variant: "text",
                    color: "warning",
                    "prepend-icon": "mdi-restore",
                    class: "ml-auto",
                    onClick: _cache[1] || (_cache[1] = $event => (askPaneReset(activeMain.value)))
                  }, {
                    default: _withCtx(() => [...(_cache[128] || (_cache[128] = [
                      _createTextVNode(" 恢复默认 ", -1)
                    ]))]),
                    _: 1
                  }))
                : _createCommentVNode("", true)
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", _hoisted_6, [
              _withDirectives(_createElementVNode("div", _hoisted_7, [
                _createElementVNode("div", _hoisted_8, [
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.upload_limit_enabled,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.upload_limit_enabled) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "启用"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.upload_limit_observe_only,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.upload_limit_observe_only) = $event)),
                    color: "warning",
                    inset: "",
                    "hide-details": "",
                    label: "观察模式"
                  }, null, 8, ["modelValue"])
                ]),
                (form.upload_limit_observe_only)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_9, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-alert-outline",
                        size: "16"
                      }),
                      _cache[129] || (_cache[129] = _createTextVNode("观察模式：不调整上传限速，也不执行恢复。", -1))
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_10, [
                  _createElementVNode("div", _hoisted_11, [
                    _createVNode(_component_VSelect, {
                      density: "compact",
                      modelValue: form.upload_limit_downloaders,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.upload_limit_downloaders) = $event)),
                      "error-messages": form.upload_limit_enabled && !uploadSelectedDownloaders.value.length ? '请至少选择一个下载器' : '',
                      label: "下载器",
                      variant: "outlined",
                      items: uploadDownloaderItems.value,
                      multiple: "",
                      chips: "",
                      "closable-chips": "",
                      clearable: ""
                    }, null, 8, ["modelValue", "error-messages", "items"])
                  ]),
                  _createElementVNode("div", _hoisted_12, [
                    _createVNode(_component_VTextField, {
                      density: "compact",
                      class: "dm-number-input",
                      modelValue: form.upload_limit_grace_minutes,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.upload_limit_grace_minutes) = $event)),
                      modelModifiers: { number: true },
                      label: "新种宽限（分钟）",
                      type: "number",
                      min: "0",
                      max: "1440",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ]),
                _cache[130] || (_cache[130] = _createElementVNode("div", { class: "dm-hint dm-upload-grace-hint" }, "宽限期间不做站点和单种分配，但仍受对应下载器总上传上限。", -1))
              ], 512), [
                [_vShow, activeSub.value === 'upload_basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_13, [
                _createVNode(FormSection, {
                  title: "下载器总上限",
                  icon: _unref(MODULE_ICONS).upload_limit
                }, {
                  default: _withCtx(() => [
                    (uploadSelectedDownloaders.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_14, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(uploadSelectedDownloaders.value, (item) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: item.value,
                              class: "dm-upload-config-row"
                            }, [
                              _createElementVNode("div", _hoisted_15, [
                                _createVNode(DownloaderBadge, {
                                  name: item.title,
                                  type: item.type,
                                  size: 18
                                }, null, 8, ["name", "type"]),
                                _createElementVNode("div", _hoisted_16, [
                                  _createElementVNode("div", _hoisted_17, _toDisplayString(item.type === 'transmission' ? 'Transmission Session 上传上限' : 'qB 普通与备用上传上限'), 1)
                                ])
                              ]),
                              _createVNode(_component_VTextField, {
                                density: "compact",
                                class: "dm-number-input",
                                "model-value": uploadDownloaderLimit(item.value),
                                "onUpdate:modelValue": $event => (setUploadDownloaderLimit(item.value, $event)),
                                "error-messages": form.upload_limit_enabled && uploadMissingLimits.value.some(missing => missing.value === item.value) ? '请设置正整数总上限' : '',
                                label: "总上限（KiB/s）",
                                type: "number",
                                min: "1",
                                step: "1",
                                variant: "outlined",
                                hint: "必须大于 0；以插件配置为准",
                                "persistent-hint": ""
                              }, null, 8, ["model-value", "onUpdate:modelValue", "error-messages"])
                            ]))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_18, "尚未选择限速下载器"))
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "站点限速",
                  icon: _unref(MODULE_ICONS).upload_limit
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_19, " 支持未收录的自定义站点，可在下方直接输入名称；名称须与种子实际的「" + _toDisplayString(form.tag_siteprefix || '🏠') + "站点名」标签一致（填写时不含前缀），且种子只能有一个有效站点标签。留空或 0 不额外写单种限速，仍受下载器总上限约束。 ", 1),
                    (uploadSiteRuleRows.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_20, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(uploadSiteRuleRows.value, (row) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: row.name,
                              class: "dm-upload-site-row"
                            }, [
                              _createElementVNode("div", _hoisted_21, [
                                _createVNode(_component_VIcon, {
                                  icon: "mdi-home-outline",
                                  size: "19",
                                  color: "primary"
                                }),
                                _createElementVNode("div", _hoisted_22, [
                                  _createElementVNode("strong", _hoisted_23, _toDisplayString(row.name), 1),
                                  _createElementVNode("div", _hoisted_24, _toDisplayString(form.tag_siteprefix || '🏠') + _toDisplayString(row.name), 1)
                                ])
                              ]),
                              _createVNode(_component_VTextField, {
                                density: "compact",
                                class: "dm-number-input",
                                "model-value": row.limit_kib,
                                "onUpdate:modelValue": $event => (setUploadSiteRule(row.name, $event)),
                                label: "合计上限（KiB/s）",
                                type: "number",
                                min: "0",
                                step: "1",
                                clearable: "",
                                variant: "outlined",
                                hint: "留空或 0 不额外写单种上限；仍受下载器全局上限约束",
                                "persistent-hint": ""
                              }, null, 8, ["model-value", "onUpdate:modelValue"]),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                "aria-label": "删除站点",
                                icon: "mdi-delete-outline",
                                color: "primary",
                                variant: "text",
                                title: "删除站点",
                                onClick: $event => (removeUploadSiteRule(row.name))
                              }, null, 8, ["onClick"])
                            ]))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_25, "尚未配置站点上限；没有站点上限时只应用下载器全局上限")),
                    _cache[132] || (_cache[132] = _createElementVNode("div", { class: "dm-hint mt-4" }, " 正数上限限制该站点全部任务的合计上传速度；多个受限站点在下载器全局额度内按实际需求共享可用带宽。 ", -1)),
                    _createElementVNode("div", _hoisted_26, [
                      _createElementVNode("div", _hoisted_27, [
                        _createVNode(_component_VCombobox, {
                          modelValue: uploadNewSiteName.value,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((uploadNewSiteName).value = $event)),
                          items: siteItems.value.map(site => site.title),
                          "return-object": false,
                          density: "compact",
                          variant: "outlined",
                          label: "选择或输入站点名称",
                          "hide-details": "",
                          onKeydown: _withKeys(_withModifiers(addUploadSiteRule, ["stop","prevent"]), ["enter"])
                        }, null, 8, ["modelValue", "items", "onKeydown"])
                      ]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        "prepend-icon": "mdi-plus",
                        onClick: addUploadSiteRule
                      }, {
                        default: _withCtx(() => [...(_cache[131] || (_cache[131] = [
                          _createTextVNode("添加站点", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    (uploadAddError.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_28, _toDisplayString(uploadAddError.value), 1))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                }, 8, ["icon"])
              ], 512), [
                [_vShow, activeSub.value === 'upload_rules']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_29, [
                _createVNode(FormSection, {
                  title: "基础设置",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_30, [
                      _createElementVNode("div", _hoisted_31, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.transfer_enabled,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.transfer_enabled) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "启用"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_32, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.transfer_observe_only,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.transfer_observe_only) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "观察模式"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_33, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.notify,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.notify) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "发送通知"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    (form.transfer_observe_only)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_34, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[133] || (_cache[133] = _createTextVNode("观察模式：转移任务只统计（诊断页可见），不向目标下载器添加种子、不删除源种子。", -1))
                        ]))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "转移策略",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_35, [
                      _createElementVNode("div", _hoisted_36, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.delay_minutes,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.delay_minutes) = $event)),
                          modelModifiers: { number: true },
                          label: "延迟时间（分钟）",
                          type: "number",
                          variant: "outlined",
                          hint: "下载完成后延迟 N 分钟再转移",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_37, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.scan_limit,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.scan_limit) = $event)),
                          modelModifiers: { number: true },
                          label: "源端扫描上限（个）",
                          type: "number",
                          min: "1",
                          variant: "outlined",
                          hint: "每轮最多检查的源种子数量，默认 500",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_38, [
                      _createElementVNode("div", _hoisted_39, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.transfer_fallback_enabled,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.transfer_fallback_enabled) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "兜底扫描"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_40, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.pause_source,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.pause_source) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "暂停源任务"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_41, [
                      _createElementVNode("div", _hoisted_42, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.transfer_fallback_interval_minutes,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.transfer_fallback_interval_minutes) = $event)),
                          modelModifiers: { number: true },
                          label: "兜底间隔（分钟）",
                          type: "number",
                          min: "1",
                          variant: "outlined",
                          disabled: !form.transfer_fallback_enabled,
                          hint: "事件漏触发时按此间隔扫描，默认60分钟",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "disabled"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "转移后操作",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_43, [
                      _createElementVNode("div", _hoisted_44, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.transfer_rename_enabled,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.transfer_rename_enabled) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "转移后重命名"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_45, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.seed_autostart,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.seed_autostart) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "自动开始做种"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_46, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.seed_skipverify,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.seed_skipverify) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "跳过校验"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_47, [
                      _createElementVNode("div", _hoisted_48, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.seed_check_interval,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.seed_check_interval) = $event)),
                          modelModifiers: { number: true },
                          label: "检查间隔（秒）",
                          type: "number",
                          variant: "outlined",
                          hint: "建议 60 秒",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_49, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.seed_max_wait_minutes,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.seed_max_wait_minutes) = $event)),
                          modelModifiers: { number: true },
                          label: "最长等待（分钟）",
                          type: "number",
                          variant: "outlined",
                          hint: "超时后移出队列",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _cache[134] || (_cache[134] = _createElementVNode("div", { class: "dm-hint" }, "重命名仅 qB 目的端生效：修改显示名，不动磁盘文件；Transmission 目的端自动跳过。", -1)),
                    _cache[135] || (_cache[135] = _createElementVNode("div", { class: "dm-hint" }, "做种校验采用按需触发：仅在转移做种或手动补刀添加种子后启动。队列为空后自动停止。", -1))
                  ]),
                  _: 1
                }, 8, ["icon"])
              ], 512), [
                [_vShow, activeSub.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_50, [
                _createVNode(FormSection, {
                  title: "任务列表",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  actions: _withCtx(() => [
                    _createVNode(_component_VBtn, {
                      size: "small",
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-plus",
                      onClick: _cache[20] || (_cache[20] = $event => (openTransferDialog()))
                    }, {
                      default: _withCtx(() => [...(_cache[136] || (_cache[136] = [
                        _createTextVNode("添加任务", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  default: _withCtx(() => [
                    _cache[138] || (_cache[138] = _createElementVNode("div", { class: "dm-hint" }, "每个任务独立配置源/目的下载器、数据可见性映射、筛选条件与高级选项，保存后写回 transfer_tasks。", -1)),
                    _createElementVNode("div", _hoisted_51, [
                      _cache[137] || (_cache[137] = _createElementVNode("div", { class: "dm-task-row dm-task-row--head" }, [
                        _createElementVNode("span", null, "名称"),
                        _createElementVNode("span", null, "状态"),
                        _createElementVNode("span", null, "下载器"),
                        _createElementVNode("span", null, "数据映射"),
                        _createElementVNode("span", null, "筛选条件"),
                        _createElementVNode("span", null, "设置"),
                        _createElementVNode("span", { class: "dm-task-actions" }, "操作")
                      ], -1)),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(transferTasks.value, (task, idx) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: `transfer-task-${idx}`,
                          class: "dm-task-row"
                        }, [
                          _createElementVNode("div", _hoisted_52, [
                            _createElementVNode("strong", _hoisted_53, _toDisplayString(task.name), 1),
                            _createElementVNode("span", _hoisted_54, "转移标签：" + _toDisplayString(task.transfer_tag || '不打标签'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_55, [
                            _createVNode(_component_VSwitch, {
                              density: "compact",
                              modelValue: task.enabled,
                              "onUpdate:modelValue": $event => ((task.enabled) = $event),
                              inset: "",
                              "hide-details": ""
                            }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                            _createElementVNode("span", _hoisted_56, _toDisplayString(task.enabled ? '启用' : '停用'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_57, [
                            _createElementVNode("span", _hoisted_58, [
                              _createVNode(DownloaderBadge, {
                                name: downloaderTitle(task.from_downloader),
                                type: downloaderTypeOf(task.from_downloader),
                                size: 16
                              }, null, 8, ["name", "type"])
                            ]),
                            _createVNode(_component_VIcon, {
                              icon: "mdi-arrow-right",
                              size: "15",
                              class: "dm-map-arrow"
                            }),
                            _createElementVNode("span", _hoisted_59, [
                              _createVNode(DownloaderBadge, {
                                name: downloaderTitle(task.to_downloader),
                                type: downloaderTypeOf(task.to_downloader),
                                size: 16
                              }, null, 8, ["name", "type"])
                            ])
                          ]),
                          _createElementVNode("div", _hoisted_60, [
                            _createElementVNode("span", _hoisted_61, _toDisplayString(task.from_path || '—'), 1),
                            _createElementVNode("div", _hoisted_62, "→ " + _toDisplayString(task.to_path || '—'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_63, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(taskFilterChips(task), (chip) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: chip,
                                size: "x-small",
                                variant: "tonal",
                                color: "secondary"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(chip), 1)
                                ]),
                                _: 2
                              }, 1024))
                            }), 128))
                          ]),
                          _createElementVNode("div", _hoisted_64, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(taskSettingBadges(task), (badge) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: badge.text,
                                size: "x-small",
                                variant: "flat",
                                color: badge.color
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(badge.text), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"]))
                            }), 128)),
                            (!taskSettingBadges(task).length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_65, "默认"))
                              : _createCommentVNode("", true),
                            _createElementVNode("span", _hoisted_66, "删源：来源 " + _toDisplayString(transferDeleteMeta(task, 'delete_source').origin) + "，生效 " + _toDisplayString(transferDeleteMeta(task, 'delete_source').effective), 1),
                            _createElementVNode("span", _hoisted_67, "删重复：来源 " + _toDisplayString(transferDeleteMeta(task, 'delete_duplicate').origin) + "，生效 " + _toDisplayString(transferDeleteMeta(task, 'delete_duplicate').effective), 1)
                          ]),
                          _createElementVNode("div", _hoisted_68, [
                            _createVNode(_component_VBtn, {
                              size: "small",
                              "aria-label": "编辑任务",
                              icon: "mdi-pencil-outline",
                              variant: "text",
                              title: "编辑任务",
                              onClick: $event => (openTransferDialog(idx))
                            }, null, 8, ["onClick"]),
                            _createVNode(_component_VBtn, {
                              size: "small",
                              "aria-label": "删除任务",
                              icon: "mdi-delete-outline",
                              variant: "text",
                              color: "primary",
                              title: "删除任务",
                              onClick: $event => (askTransferDelete(idx))
                            }, null, 8, ["onClick"])
                          ])
                        ]))
                      }), 128)),
                      (!transferTasks.value.length)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_69, "暂无转移任务，点击右上角「添加任务」创建。"))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"])
              ], 512), [
                [_vShow, activeSub.value === 'tasks']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_70, [
                _createVNode(FormSection, {
                  title: "基础设置",
                  icon: _unref(MODULE_ICONS).hr
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_71, [
                      _createElementVNode("div", _hoisted_72, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.hr_enabled,
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.hr_enabled) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "启用"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_73, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: hrNotificationEnabled.value,
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((hrNotificationEnabled).value = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "发送通知"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_74, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.hr_observe_only,
                          "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.hr_observe_only) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "观察模式"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_75, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.hr_auto_discover,
                          "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((form.hr_auto_discover) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "自动发现"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    (form.hr_observe_only)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_76, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[139] || (_cache[139] = _createTextVNode(" 观察模式：检查与统计照常，但不给种子打 H&R 标签、不移除标签", -1))
                        ]))
                      : _createCommentVNode("", true),
                    _createElementVNode("div", _hoisted_77, [
                      _createElementVNode("div", _hoisted_78, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: form.hr_notify,
                          "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.hr_notify) = $event)),
                          label: "通知模式",
                          variant: "outlined",
                          items: _unref(hrEnabledNotifyModeItems),
                          disabled: !hrNotificationEnabled.value,
                          "hide-details": ""
                        }, null, 8, ["modelValue", "items", "disabled"])
                      ]),
                      _createElementVNode("div", _hoisted_79, [
                        _createVNode(_component_VCronField, {
                          density: "compact",
                          modelValue: form.hr_notify_summary_cron,
                          "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((form.hr_notify_summary_cron) = $event)),
                          disabled: form.hr_notify === 'none',
                          label: "汇总计划",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _createElementVNode("div", _hoisted_80, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.hr_check_period,
                          "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((form.hr_check_period) = $event)),
                          modelModifiers: { number: true },
                          label: "检查间隔（分钟）",
                          type: "number",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "跟踪策略",
                  icon: _unref(MODULE_ICONS).hr
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_81, [
                      _createElementVNode("div", _hoisted_82, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.hr_enable_site_config,
                          "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((form.hr_enable_site_config) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "站点独立规则"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_83, [
                      _createElementVNode("div", _hoisted_84, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: form.hr_downloader,
                          "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((form.hr_downloader) = $event)),
                          label: "下载器",
                          variant: "outlined",
                          items: downloaderItems.value,
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          clearable: "",
                          "menu-props": { contentClass: 'dm-select-menu' },
                          "hide-details": ""
                        }, {
                          chip: _withCtx(({ props: chipProps, item }) => [
                            _createVNode(_component_VChip, _mergeProps(chipProps, {
                              size: "small",
                              title: item.title
                            }), {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(item.title), 1)
                              ]),
                              _: 2
                            }, 1040, ["title"])
                          ]),
                          _: 1
                        }, 8, ["modelValue", "items"])
                      ]),
                      _createElementVNode("div", _hoisted_85, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: form.hr_sites,
                          "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((form.hr_sites) = $event)),
                          label: "站点白名单",
                          variant: "outlined",
                          items: siteItems.value,
                          "item-title": "title",
                          "item-value": "title",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          clearable: "",
                          "menu-props": { contentClass: 'dm-select-menu' },
                          "hide-details": "",
                          title: "留空表示全部站点"
                        }, {
                          chip: _withCtx(({ props: chipProps, item }) => [
                            _createVNode(_component_VChip, _mergeProps(chipProps, {
                              size: "small",
                              title: item.title
                            }), {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(item.title), 1)
                              ]),
                              _: 2
                            }, 1040, ["title"])
                          ]),
                          _: 1
                        }, 8, ["modelValue", "items"])
                      ]),
                      _createElementVNode("div", _hoisted_86, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: form.hr_brush_plugin,
                          "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((form.hr_brush_plugin) = $event)),
                          label: "刷流插件",
                          variant: "outlined",
                          items: hrBrushPluginItems,
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_87, [
                      _createElementVNode("div", _hoisted_88, [
                        _createVNode(MultiValueInput, {
                          modelValue: form.hr_exclude_tags,
                          "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((form.hr_exclude_tags) = $event)),
                          label: "排除标签",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_89, [
                        _createVNode(MultiValueInput, {
                          modelValue: form.hr_exclude_categories,
                          "onUpdate:modelValue": _cache[33] || (_cache[33] = $event => ((form.hr_exclude_categories) = $event)),
                          label: "排除分类",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "保护与记录",
                  icon: _unref(MODULE_ICONS).hr
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_90, [
                      _createElementVNode("div", _hoisted_91, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.hr_protection_enabled,
                          "onUpdate:modelValue": _cache[34] || (_cache[34] = $event => ((form.hr_protection_enabled) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "删除保护"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    (!form.hr_protection_enabled)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_92, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[140] || (_cache[140] = _createTextVNode("关闭删除保护后，未达标 H&R 任务可能被删除。", -1))
                        ]))
                      : _createCommentVNode("", true),
                    _createElementVNode("div", _hoisted_93, [
                      _createElementVNode("div", _hoisted_94, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.hr_hit_and_run_tag,
                          "onUpdate:modelValue": _cache[35] || (_cache[35] = $event => ((form.hr_hit_and_run_tag) = $event)),
                          label: "H&R 标签",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_95, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.hr_auto_cleanup_days,
                          "onUpdate:modelValue": _cache[36] || (_cache[36] = $event => ((form.hr_auto_cleanup_days) = $event)),
                          modelModifiers: { number: true },
                          label: "记录保留（天）",
                          type: "number",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"])
              ], 512), [
                [_vShow, activeSub.value === 'hr_basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_96, [
                _createVNode(FormSection, {
                  title: "全局规则",
                  icon: _unref(MODULE_ICONS).hr
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_97, [
                      _createElementVNode("div", _hoisted_98, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.hr_upload_gte_download,
                          "onUpdate:modelValue": _cache[37] || (_cache[37] = $event => ((form.hr_upload_gte_download) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "上传量≥下载量"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_99, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: form.hr_active,
                          "onUpdate:modelValue": _cache[38] || (_cache[38] = $event => ((form.hr_active) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "强制纳管",
                          title: "将适用范围内任务按本规则强制纳管"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_100, [
                      _createElementVNode("div", _hoisted_101, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.hr_duration,
                          "onUpdate:modelValue": _cache[39] || (_cache[39] = $event => ((form.hr_duration) = $event)),
                          modelModifiers: { number: true },
                          label: "做种时长（小时）",
                          type: "number",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_102, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.hr_deadline_days,
                          "onUpdate:modelValue": _cache[40] || (_cache[40] = $event => ((form.hr_deadline_days) = $event)),
                          modelModifiers: { number: true },
                          label: "考核期（天）",
                          type: "number",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_103, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.hr_additional_seed_time,
                          "onUpdate:modelValue": _cache[41] || (_cache[41] = $event => ((form.hr_additional_seed_time) = $event)),
                          modelModifiers: { number: true },
                          label: "额外做种（小时）",
                          type: "number",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_104, [
                      _createElementVNode("div", _hoisted_105, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.hr_ratio,
                          "onUpdate:modelValue": _cache[42] || (_cache[42] = $event => ((form.hr_ratio) = $event)),
                          modelModifiers: { number: true },
                          label: "分享率",
                          type: "number",
                          variant: "outlined",
                          placeholder: "不校验",
                          title: "留空表示不校验分享率",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_106, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          class: "dm-number-input",
                          modelValue: form.hr_upload_multiplier,
                          "onUpdate:modelValue": _cache[43] || (_cache[43] = $event => ((form.hr_upload_multiplier) = $event)),
                          modelModifiers: { number: true },
                          label: "上传倍数",
                          type: "number",
                          variant: "outlined",
                          placeholder: "不校验",
                          title: "留空表示不校验上传倍数",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "站点规则",
                  icon: _unref(MODULE_ICONS).hr
                }, {
                  actions: _withCtx(() => [
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      "prepend-icon": "mdi-refresh",
                      loading: hrPresetsLoading.value,
                      onClick: _cache[44] || (_cache[44] = $event => (loadHrPresets(true)))
                    }, {
                      default: _withCtx(() => [...(_cache[141] || (_cache[141] = [
                        _createTextVNode("重载预设", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_VBtn, {
                      disabled: !form.hr_enable_site_config,
                      size: "small",
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-home-plus-outline",
                      onClick: hrOpenAddDialog
                    }, {
                      default: _withCtx(() => [...(_cache[142] || (_cache[142] = [
                        _createTextVNode("添加站点", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled"])
                  ]),
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_107, [
                      _cache[143] || (_cache[143] = _createElementVNode("span", {
                        class: "dm-hint",
                        title: "站点未设置的字段继承全局；同名自定义规则覆盖预设；停用站点规则后回退全局"
                      }, "灰字为继承全局，停用后回退全局", -1)),
                      _createVNode(_component_VSwitch, {
                        density: "compact",
                        modelValue: hrShowInherited.value,
                        "onUpdate:modelValue": _cache[45] || (_cache[45] = $event => ((hrShowInherited).value = $event)),
                        color: "primary",
                        inset: "",
                        "hide-details": "",
                        label: "显示继承字段"
                      }, null, 8, ["modelValue"])
                    ]),
                    (!form.hr_enable_site_config)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_108, "站点独立规则已关闭，全部站点使用全局规则。"))
                      : _createCommentVNode("", true),
                    (hrPresetsMessage.value)
                      ? (_openBlock(), _createBlock(_component_VAlert, {
                          key: 1,
                          type: "warning",
                          variant: "tonal",
                          density: "compact",
                          closable: "",
                          class: "mt-3",
                          "onClick:close": _cache[46] || (_cache[46] = $event => (hrPresetsMessage.value = ''))
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(hrPresetsMessage.value), 1)
                          ]),
                          _: 1
                        }))
                      : _createCommentVNode("", true),
                    _createVNode(_component_VTable, {
                      density: "compact",
                      class: "dm-hr-site-table mt-3"
                    }, {
                      default: _withCtx(() => [
                        _cache[147] || (_cache[147] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "站点"),
                            _createElementVNode("th", null, "生效规则"),
                            _createElementVNode("th", null, "来源"),
                            _createElementVNode("th", null, "启用"),
                            _createElementVNode("th", null, "操作")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(hrSiteRows.value, (row) => {
                            return (_openBlock(), _createElementBlock(_Fragment, {
                              key: row.name
                            }, [
                              _createElementVNode("tr", {
                                class: _normalizeClass({ 'dm-hr-site-blocked': row.blocked })
                              }, [
                                _createElementVNode("td", null, [
                                  _createElementVNode("strong", _hoisted_109, _toDisplayString(row.name), 1),
                                  (row.blocked)
                                    ? (_openBlock(), _createElementBlock("div", _hoisted_110, "已停用，回退全局"))
                                    : _createCommentVNode("", true)
                                ]),
                                _createElementVNode("td", null, [
                                  _createElementVNode("div", _hoisted_111, [
                                    (row.summaryCells.length)
                                      ? (_openBlock(true), _createElementBlock(_Fragment, { key: 0 }, _renderList(row.summaryCells, (cell) => {
                                          return (_openBlock(), _createElementBlock("span", {
                                            key: cell.key,
                                            class: _normalizeClass(["dm-hr-chip", { 'dm-hr-chip--inherit': cell.inherited }])
                                          }, [
                                            _createVNode(_component_VChip, {
                                              size: "x-small",
                                              variant: cell.inherited ? 'outlined' : 'tonal',
                                              color: cell.color,
                                              "data-rule-key": cell.key,
                                              class: "dm-hr-rule-badge",
                                              title: cell.tooltip
                                            }, {
                                              default: _withCtx(() => [
                                                _createElementVNode("span", null, _toDisplayString(cell.label) + " " + _toDisplayString(cell.text), 1),
                                                (cell.inherited)
                                                  ? (_openBlock(), _createElementBlock("span", _hoisted_112, "· 继承"))
                                                  : _createCommentVNode("", true)
                                              ]),
                                              _: 2
                                            }, 1032, ["variant", "color", "data-rule-key", "title"])
                                          ], 2))
                                        }), 128))
                                      : (!row.overflowCells.length)
                                        ? (_openBlock(), _createElementBlock("span", _hoisted_113, "全部字段继承全局规则"))
                                        : _createCommentVNode("", true),
                                    (row.overflowCells.length)
                                      ? (_openBlock(), _createBlock(_component_VMenu, {
                                          key: 2,
                                          location: "bottom start",
                                          "max-width": "440"
                                        }, {
                                          activator: _withCtx(({ props: menuProps }) => [
                                            _createVNode(_component_VBtn, _mergeProps({ ref_for: true }, menuProps, {
                                              size: "small",
                                              density: "compact",
                                              variant: "text",
                                              class: "dm-hr-rules-more"
                                            }), {
                                              default: _withCtx(() => [
                                                _createTextVNode("+" + _toDisplayString(row.overflowCells.length) + "项", 1)
                                              ]),
                                              _: 2
                                            }, 1040)
                                          ]),
                                          default: _withCtx(() => [
                                            _createElementVNode("div", _hoisted_114, [
                                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(row.overflowCells, (cell) => {
                                                return (_openBlock(), _createBlock(_component_VChip, {
                                                  key: cell.key,
                                                  size: "x-small",
                                                  variant: cell.inherited ? 'outlined' : 'tonal',
                                                  color: cell.color,
                                                  "data-rule-key": cell.key,
                                                  class: "dm-hr-rule-badge",
                                                  title: cell.tooltip
                                                }, {
                                                  default: _withCtx(() => [
                                                    _createElementVNode("span", null, _toDisplayString(cell.label) + " " + _toDisplayString(cell.text), 1),
                                                    (cell.inherited)
                                                      ? (_openBlock(), _createElementBlock("span", _hoisted_115, "· 继承"))
                                                      : _createCommentVNode("", true)
                                                  ]),
                                                  _: 2
                                                }, 1032, ["variant", "color", "data-rule-key", "title"]))
                                              }), 128))
                                            ])
                                          ]),
                                          _: 2
                                        }, 1024))
                                      : _createCommentVNode("", true)
                                  ])
                                ]),
                                _createElementVNode("td", null, [
                                  _createVNode(_component_VChip, {
                                    size: "x-small",
                                    variant: "tonal",
                                    color: row.sourceColor
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(row.sourceLabel), 1)
                                    ]),
                                    _: 2
                                  }, 1032, ["color"])
                                ]),
                                _createElementVNode("td", null, [
                                  _createVNode(_component_VSwitch, {
                                    disabled: !form.hr_enable_site_config,
                                    density: "compact",
                                    "model-value": row.enabled,
                                    color: "primary",
                                    inset: "",
                                    "hide-details": "",
                                    "aria-label": row.name + '规则启用',
                                    title: row.blocked ? '已停用：该站规则不生效，回退全局规则' : '启用中；关闭后该站回退全局规则',
                                    "onUpdate:modelValue": $event => (hrSetSiteEnabled(row.name, $event))
                                  }, null, 8, ["disabled", "model-value", "aria-label", "title", "onUpdate:modelValue"])
                                ]),
                                _createElementVNode("td", null, [
                                  _createVNode(RowActionMenu, {
                                    label: row.name,
                                    actions: row.custom ? [
                          { key: 'edit', label: row.expanded ? '收起' : '编辑', icon: row.expanded ? 'mdi-chevron-up' : 'mdi-pencil-outline' },
                          { key: 'delete', label: row.preset ? '删除覆盖（恢复预设）' : '删除站点', icon: 'mdi-delete-outline', color: 'error', disabled: !form.hr_enable_site_config }
                        ] : [{ key: 'copy', label: '复制规则', icon: 'mdi-content-copy', disabled: !form.hr_enable_site_config }],
                                    onSelect: action => action === 'edit' ? hrToggleExpanded(row.name) : action === 'delete' ? hrRemoveCustomSite(row.name) : hrCopyPresetToCustom(row.name)
                                  }, null, 8, ["label", "actions", "onSelect"])
                                ])
                              ], 2),
                              (row.custom && row.expanded)
                                ? (_openBlock(), _createElementBlock("tr", _hoisted_116, [
                                    _createElementVNode("td", _hoisted_117, [
                                      _createElementVNode("div", _hoisted_118, [
                                        _createElementVNode("div", _hoisted_119, [
                                          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(hrNumberFields, (field) => {
                                            return _createVNode(_component_VTextField, {
                                              disabled: !form.hr_enable_site_config,
                                              density: "compact",
                                              class: "dm-number-input",
                                              key: field.key,
                                              "model-value": hrRuleNumber(row.entry, field.key),
                                              "onUpdate:modelValue": $event => (hrSetRuleNumber(row.name, field.key, $event)),
                                              label: field.label,
                                              type: "number",
                                              variant: "outlined",
                                              placeholder: `继承 ${hrGlobalText(field.key)}`,
                                              title: `留空继承全局（${hrGlobalText(field.key)}）`,
                                              "hide-details": ""
                                            }, null, 8, ["disabled", "model-value", "onUpdate:modelValue", "label", "placeholder", "title"])
                                          }), 64))
                                        ]),
                                        _createElementVNode("div", _hoisted_120, [
                                          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(hrFlagFields, (field) => {
                                            return _createVNode(_component_VSelect, {
                                              disabled: !form.hr_enable_site_config,
                                              density: "compact",
                                              key: field.key,
                                              "model-value": hrRuleFlag(row.entry, field.key),
                                              "onUpdate:modelValue": $event => (hrSetRuleFlag(row.name, field.key, $event)),
                                              items: hrTriStateItems,
                                              label: field.label,
                                              variant: "outlined",
                                              "hide-details": ""
                                            }, null, 8, ["disabled", "model-value", "onUpdate:modelValue", "label"])
                                          }), 64))
                                        ]),
                                        _createElementVNode("div", _hoisted_121, [
                                          _createVNode(MultiLineInput, {
                                            disabled: !form.hr_enable_site_config,
                                            "model-value": hrRuleTrackers(row.entry),
                                            "onUpdate:modelValue": $event => (hrSetRuleTrackers(row.name, $event)),
                                            label: "Tracker 域名",
                                            clearable: "",
                                            "hide-details": "",
                                            placeholder: "tracker.example.com",
                                            title: "站点库识别失败时，按这些域名匹配"
                                          }, null, 8, ["disabled", "model-value", "onUpdate:modelValue"])
                                        ]),
                                        _createElementVNode("div", _hoisted_122, [
                                          _createElementVNode("div", _hoisted_123, [
                                            _cache[145] || (_cache[145] = _createElementVNode("span", { title: "按种子 GiB 匹配；上限为 0 表示不限，需置于末位" }, "体积分档", -1)),
                                            _createVNode(_component_VBtn, {
                                              disabled: !form.hr_enable_site_config,
                                              size: "small",
                                              variant: "tonal",
                                              "prepend-icon": "mdi-plus",
                                              onClick: $event => (hrAddTier(row.name))
                                            }, {
                                              default: _withCtx(() => [...(_cache[144] || (_cache[144] = [
                                                _createTextVNode("添加分档", -1)
                                              ]))]),
                                              _: 1
                                            }, 8, ["disabled", "onClick"])
                                          ]),
                                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(row.entry.hr_size_tiers || [], (tier, tierIndex) => {
                                            return (_openBlock(), _createElementBlock("div", {
                                              key: `${row.name}-${tierIndex}`,
                                              class: "dm-hr-tier-row"
                                            }, [
                                              (_openBlock(), _createElementBlock(_Fragment, null, _renderList(hrTierFields, (field) => {
                                                return _createVNode(_component_VTextField, {
                                                  disabled: !form.hr_enable_site_config,
                                                  density: "compact",
                                                  class: "dm-number-input",
                                                  key: field.key,
                                                  "model-value": hrTierNumber(tier, field.key),
                                                  "onUpdate:modelValue": $event => (hrSetTierNumber(row.name, tierIndex, field.key, $event)),
                                                  label: field.label,
                                                  type: "number",
                                                  variant: "outlined",
                                                  "hide-details": ""
                                                }, null, 8, ["disabled", "model-value", "onUpdate:modelValue", "label"])
                                              }), 64)),
                                              _createVNode(_component_VBtn, {
                                                disabled: !form.hr_enable_site_config,
                                                size: "small",
                                                "aria-label": "删除该分档",
                                                icon: "mdi-delete-outline",
                                                variant: "text",
                                                color: "primary",
                                                title: "删除该分档",
                                                onClick: $event => (hrRemoveTier(row.name, tierIndex))
                                              }, null, 8, ["disabled", "onClick"])
                                            ]))
                                          }), 128)),
                                          (!(row.entry.hr_size_tiers || []).length)
                                            ? (_openBlock(), _createElementBlock("div", _hoisted_124, "未设置分档"))
                                            : _createCommentVNode("", true)
                                        ])
                                      ])
                                    ])
                                  ]))
                                : _createCommentVNode("", true)
                            ], 64))
                          }), 128)),
                          (!hrSiteRows.value.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_125, [...(_cache[146] || (_cache[146] = [
                                _createElementVNode("td", {
                                  colspan: "5",
                                  class: "dm-hint"
                                }, "暂无站点规则", -1)
                              ]))]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _: 1
                    }),
                    _createElementVNode("div", _hoisted_126, [
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "text",
                        "prepend-icon": hrRawOpen.value ? 'mdi-chevron-up' : 'mdi-code-json',
                        onClick: _cache[47] || (_cache[47] = $event => (hrRawOpen.value = !hrRawOpen.value))
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(hrRawOpen.value ? '收起 YAML' : '编辑 YAML'), 1)
                        ]),
                        _: 1
                      }, 8, ["prepend-icon"]),
                      (hrRawOpen.value)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_127, [
                            _createVNode(_component_VTextarea, {
                              disabled: !form.hr_enable_site_config,
                              density: "compact",
                              modelValue: form.hr_site_config_str,
                              "onUpdate:modelValue": _cache[48] || (_cache[48] = $event => ((form.hr_site_config_str) = $event)),
                              "error-messages": hrRawError.value,
                              label: "站点规则",
                              variant: "outlined",
                              rows: "8",
                              class: "mt-1"
                            }, null, 8, ["disabled", "modelValue", "error-messages"])
                          ]))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"])
              ], 512), [
                [_vShow, activeSub.value === 'hr_sites']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_128, [
                _createVNode(FormSection, {
                  title: "基础设置",
                  icon: _unref(MODULE_ICONS).autoremove
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_129, [
                      _createVNode(_component_VSwitch, {
                        density: "compact",
                        modelValue: form.remover_enabled,
                        "onUpdate:modelValue": _cache[49] || (_cache[49] = $event => ((form.remover_enabled) = $event)),
                        color: "primary",
                        inset: "",
                        "hide-details": "",
                        label: "启用"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_VSwitch, {
                        density: "compact",
                        modelValue: form.remover_observe_only,
                        "onUpdate:modelValue": _cache[50] || (_cache[50] = $event => ((form.remover_observe_only) = $event)),
                        color: "warning",
                        inset: "",
                        "hide-details": "",
                        label: "观察模式"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_VSwitch, {
                        density: "compact",
                        modelValue: form.remover_notify,
                        "onUpdate:modelValue": _cache[51] || (_cache[51] = $event => ((form.remover_notify) = $event)),
                        color: "primary",
                        inset: "",
                        "hide-details": "",
                        label: "发送通知"
                      }, null, 8, ["modelValue"])
                    ]),
                    (form.remover_observe_only)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_130, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[148] || (_cache[148] = _createTextVNode("观察模式：只列出候选并通知，不暂停、不删除种子。", -1))
                        ]))
                      : _createCommentVNode("", true),
                    _createElementVNode("div", _hoisted_131, [
                      _createElementVNode("div", _hoisted_132, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: form.remover_action,
                          "onUpdate:modelValue": _cache[52] || (_cache[52] = $event => ((form.remover_action) = $event)),
                          label: "动作",
                          variant: "outlined",
                          items: removerActionItems,
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_133, [
                        _createVNode(_component_VCronField, {
                          density: "compact",
                          modelValue: form.remover_cron,
                          "onUpdate:modelValue": _cache[53] || (_cache[53] = $event => ((form.remover_cron) = $event)),
                          label: "执行计划",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_134, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: form.remover_downloaders,
                          "onUpdate:modelValue": _cache[54] || (_cache[54] = $event => ((form.remover_downloaders) = $event)),
                          label: "下载器",
                          variant: "outlined",
                          items: downloaderItems.value,
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          clearable: "",
                          "hide-details": ""
                        }, null, 8, ["modelValue", "items"])
                      ])
                    ]),
                    (form.remover_action === 'deletefile')
                      ? (_openBlock(), _createElementBlock("div", _hoisted_135, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[149] || (_cache[149] = _createTextVNode("删除任务及文件仍受 H&R 和其他删除保护约束。", -1))
                        ]))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "清理条件",
                  icon: _unref(MODULE_ICONS).autoremove
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_136, [
                      _createElementVNode("div", _hoisted_137, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.remover_time,
                          "onUpdate:modelValue": _cache[55] || (_cache[55] = $event => ((form.remover_time) = $event)),
                          label: "做种时长（小时）",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_138, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.remover_ratio,
                          "onUpdate:modelValue": _cache[56] || (_cache[56] = $event => ((form.remover_ratio) = $event)),
                          label: "分享率",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_139, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.remover_size,
                          "onUpdate:modelValue": _cache[57] || (_cache[57] = $event => ((form.remover_size) = $event)),
                          label: "体积（GB）",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_140, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.remover_upspeed,
                          "onUpdate:modelValue": _cache[58] || (_cache[58] = $event => ((form.remover_upspeed) = $event)),
                          label: "平均上传速度（KB/s）",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _cache[150] || (_cache[150] = _createElementVNode("div", { class: "dm-hint" }, "做种时长、分享率为大于阈值，平均上传速度为小于阈值；体积填写上下限（GB，逗号分隔）。所有条件同时满足才命中。", -1))
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "处理范围",
                  icon: _unref(MODULE_ICONS).autoremove
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_141, [
                      _createVNode(_component_VSwitch, {
                        density: "compact",
                        modelValue: form.remover_mponly,
                        "onUpdate:modelValue": _cache[59] || (_cache[59] = $event => ((form.remover_mponly) = $event)),
                        color: "primary",
                        inset: "",
                        "hide-details": "",
                        label: "仅 MoviePilot 任务"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_VSwitch, {
                        density: "compact",
                        modelValue: form.remover_samedata,
                        "onUpdate:modelValue": _cache[60] || (_cache[60] = $event => ((form.remover_samedata) = $event)),
                        color: "error",
                        inset: "",
                        "hide-details": "",
                        label: "连带同名同大小任务"
                      }, null, 8, ["modelValue"])
                    ]),
                    (form.remover_samedata)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_142, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[151] || (_cache[151] = _createTextVNode("连带处理同名同大小任务，删除动作可能影响文件。", -1))
                        ]))
                      : _createCommentVNode("", true),
                    _createElementVNode("div", _hoisted_143, [
                      _createElementVNode("div", _hoisted_144, [
                        _createVNode(MultiValueInput, {
                          density: "compact",
                          modelValue: form.remover_labels,
                          "onUpdate:modelValue": _cache[61] || (_cache[61] = $event => ((form.remover_labels) = $event)),
                          label: "限定标签",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_145, [
                        _createVNode(MultiValueInput, {
                          density: "compact",
                          modelValue: form.remover_torrentcategorys,
                          "onUpdate:modelValue": _cache[62] || (_cache[62] = $event => ((form.remover_torrentcategorys) = $event)),
                          label: "限定分类",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_146, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.remover_pathkeywords,
                          "onUpdate:modelValue": _cache[63] || (_cache[63] = $event => ((form.remover_pathkeywords) = $event)),
                          label: "路径关键词",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_147, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.remover_trackerkeywords,
                          "onUpdate:modelValue": _cache[64] || (_cache[64] = $event => ((form.remover_trackerkeywords) = $event)),
                          label: "tracker 关键词",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_148, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.remover_errorkeywords,
                          "onUpdate:modelValue": _cache[65] || (_cache[65] = $event => ((form.remover_errorkeywords) = $event)),
                          label: "错误关键词",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_149, [
                        _createVNode(MultiValueInput, {
                          density: "compact",
                          modelValue: form.remover_torrentstates,
                          "onUpdate:modelValue": _cache[66] || (_cache[66] = $event => ((form.remover_torrentstates) = $event)),
                          label: "任务状态",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _cache[152] || (_cache[152] = _createElementVNode("div", { class: "dm-hint" }, "路径、Tracker、错误关键词按原正则表达式匹配，不是逗号分隔列表。", -1))
                  ]),
                  _: 1
                }, 8, ["icon"])
              ], 512), [
                [_vShow, activeSub.value === 'remover_basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_150, [
                _createElementVNode("div", _hoisted_151, [
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.failcleanup_enabled,
                    "onUpdate:modelValue": _cache[67] || (_cache[67] = $event => ((form.failcleanup_enabled) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "启用"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.failcleanup_observe_only,
                    "onUpdate:modelValue": _cache[68] || (_cache[68] = $event => ((form.failcleanup_observe_only) = $event)),
                    color: "warning",
                    inset: "",
                    "hide-details": "",
                    label: "观察模式"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.failcleanup_notify,
                    "onUpdate:modelValue": _cache[69] || (_cache[69] = $event => ((form.failcleanup_notify) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "发送通知"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.failcleanup_clean_repeat,
                    "onUpdate:modelValue": _cache[70] || (_cache[70] = $event => ((form.failcleanup_clean_repeat) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "清理重复残留"
                  }, null, 8, ["modelValue"])
                ]),
                (form.failcleanup_enabled && !form.failcleanup_observe_only)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_152, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-alert-outline",
                        size: "16"
                      }),
                      _cache[153] || (_cache[153] = _createTextVNode("真实模式可能删除源文件及下载历史。", -1))
                    ]))
                  : _createCommentVNode("", true),
                (form.failcleanup_observe_only)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_153, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-alert-outline",
                        size: "16"
                      }),
                      _cache[154] || (_cache[154] = _createTextVNode("观察模式只统计，不删除文件或下载历史。", -1))
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_154, [
                  _createElementVNode("div", _hoisted_155, [
                    _createVNode(_component_VCronField, {
                      density: "compact",
                      modelValue: form.failcleanup_cron,
                      "onUpdate:modelValue": _cache[71] || (_cache[71] = $event => ((form.failcleanup_cron) = $event)),
                      disabled: !form.failcleanup_clean_repeat,
                      label: "巡检计划",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "disabled"])
                  ]),
                  _createElementVNode("div", _hoisted_156, [
                    _createVNode(_component_VTextField, {
                      density: "compact",
                      class: "dm-number-input",
                      modelValue: form.failcleanup_retain_hours,
                      "onUpdate:modelValue": _cache[72] || (_cache[72] = $event => ((form.failcleanup_retain_hours) = $event)),
                      modelModifiers: { number: true },
                      disabled: !form.failcleanup_clean_repeat,
                      label: "残留保留（小时）",
                      type: "number",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "disabled"])
                  ])
                ])
              ], 512), [
                [_vShow, activeSub.value === 'failclean_basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_157, [
                _createElementVNode("div", _hoisted_158, [
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.rename_enabled,
                    "onUpdate:modelValue": _cache[73] || (_cache[73] = $event => ((form.rename_enabled) = $event)),
                    inset: "",
                    "hide-details": "",
                    label: "启用"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.rename_observe_only,
                    "onUpdate:modelValue": _cache[74] || (_cache[74] = $event => ((form.rename_observe_only) = $event)),
                    color: "warning",
                    inset: "",
                    "hide-details": "",
                    label: "观察模式"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.rename_notify,
                    "onUpdate:modelValue": _cache[75] || (_cache[75] = $event => ((form.rename_notify) = $event)),
                    inset: "",
                    "hide-details": "",
                    label: "发送通知"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.rename_on_download_added,
                    "onUpdate:modelValue": _cache[76] || (_cache[76] = $event => ((form.rename_on_download_added) = $event)),
                    inset: "",
                    "hide-details": "",
                    label: "入列触发"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.rename_cron_enabled,
                    "onUpdate:modelValue": _cache[77] || (_cache[77] = $event => ((form.rename_cron_enabled) = $event)),
                    inset: "",
                    "hide-details": "",
                    label: "定时补查"
                  }, null, 8, ["modelValue"])
                ]),
                (form.rename_observe_only)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_159, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-alert-outline",
                        size: "16"
                      }),
                      _cache[155] || (_cache[155] = _createTextVNode("只预览，不执行重命名。", -1))
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_160, [
                  _createElementVNode("div", _hoisted_161, [
                    _createVNode(_component_VTextField, {
                      density: "compact",
                      class: "dm-number-input",
                      modelValue: form.rename_event_debounce_seconds,
                      "onUpdate:modelValue": _cache[78] || (_cache[78] = $event => ((form.rename_event_debounce_seconds) = $event)),
                      modelModifiers: { number: true },
                      label: "事件防抖（秒）",
                      type: "number",
                      min: "1",
                      variant: "outlined",
                      disabled: !form.rename_on_download_added,
                      "hide-details": ""
                    }, null, 8, ["modelValue", "disabled"])
                  ]),
                  _createElementVNode("div", _hoisted_162, [
                    _createVNode(_component_VCronField, {
                      density: "compact",
                      modelValue: form.rename_cron,
                      "onUpdate:modelValue": _cache[79] || (_cache[79] = $event => ((form.rename_cron) = $event)),
                      label: "补查计划",
                      variant: "outlined",
                      "hide-details": "",
                      disabled: !form.rename_cron_enabled
                    }, null, 8, ["modelValue", "disabled"])
                  ]),
                  _createElementVNode("div", _hoisted_163, [
                    _createVNode(_component_VSelect, {
                      density: "compact",
                      modelValue: form.rename_downloaders,
                      "onUpdate:modelValue": _cache[80] || (_cache[80] = $event => ((form.rename_downloaders) = $event)),
                      label: "下载器",
                      variant: "outlined",
                      items: qbDownloaderItems.value,
                      multiple: "",
                      chips: "",
                      "closable-chips": "",
                      clearable: "",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "items"])
                  ])
                ]),
                _createElementVNode("div", _hoisted_164, [
                  _createElementVNode("div", _hoisted_165, [
                    _createVNode(MultiValueInput, {
                      density: "compact",
                      modelValue: form.rename_include_tags,
                      "onUpdate:modelValue": _cache[81] || (_cache[81] = $event => ((form.rename_include_tags) = $event)),
                      label: "包含标签",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _createElementVNode("div", _hoisted_166, [
                    _createVNode(MultiValueInput, {
                      density: "compact",
                      modelValue: form.rename_exclude_tags,
                      "onUpdate:modelValue": _cache[82] || (_cache[82] = $event => ((form.rename_exclude_tags) = $event)),
                      label: "排除标签",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ]),
                _createElementVNode("div", _hoisted_167, [
                  _createElementVNode("div", _hoisted_168, [
                    _createVNode(_component_VTextarea, {
                      density: "compact",
                      modelValue: form.rename_exclude_dirs,
                      "onUpdate:modelValue": _cache[83] || (_cache[83] = $event => ((form.rename_exclude_dirs) = $event)),
                      label: "排除目录",
                      variant: "outlined",
                      rows: "2",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ]),
                _createElementVNode("div", _hoisted_169, [
                  _createElementVNode("div", _hoisted_170, [
                    _createVNode(_component_VTextarea, {
                      density: "compact",
                      modelValue: form.rename_hash_white_list,
                      "onUpdate:modelValue": _cache[84] || (_cache[84] = $event => ((form.rename_hash_white_list) = $event)),
                      label: "Hash 白名单",
                      variant: "outlined",
                      rows: "2",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ])
              ], 512), [
                [_vShow, activeSub.value === 'rename_basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_171, [
                _createElementVNode("div", _hoisted_172, [
                  _createElementVNode("div", _hoisted_173, [
                    _createVNode(_component_VTextarea, {
                      density: "compact",
                      modelValue: form.rename_movie_format,
                      "onUpdate:modelValue": _cache[85] || (_cache[85] = $event => ((form.rename_movie_format) = $event)),
                      label: "电影模板",
                      variant: "outlined",
                      rows: "2",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ]),
                _createElementVNode("div", _hoisted_174, [
                  _createElementVNode("div", _hoisted_175, [
                    _createVNode(_component_VTextarea, {
                      density: "compact",
                      modelValue: form.rename_tv_format,
                      "onUpdate:modelValue": _cache[86] || (_cache[86] = $event => ((form.rename_tv_format) = $event)),
                      label: "电视剧模板",
                      variant: "outlined",
                      rows: "2",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ]),
                _cache[156] || (_cache[156] = _createElementVNode("details", { class: "dm-more mt-4" }, [
                  _createElementVNode("summary", { class: "dm-section-title" }, "可用变量与示例"),
                  _createElementVNode("div", { class: "dm-hint" }, "可用变量：{{ title }}、{{ year }}、{{ season_episode }}、{{ original_name }}；示例：{{ title }} ({{ year }}) - {{ original_name }}")
                ], -1))
              ], 512), [
                [_vShow, activeSub.value === 'rename_format']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_176, [
                _createElementVNode("div", _hoisted_177, [
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.tag_enabled,
                    "onUpdate:modelValue": _cache[87] || (_cache[87] = $event => ((form.tag_enabled) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "启用"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.tag_observe_only,
                    "onUpdate:modelValue": _cache[88] || (_cache[88] = $event => ((form.tag_observe_only) = $event)),
                    color: "warning",
                    inset: "",
                    "hide-details": "",
                    label: "观察模式"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.tag_enable_tag,
                    "onUpdate:modelValue": _cache[89] || (_cache[89] = $event => ((form.tag_enable_tag) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "站点名标签"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.tag_enable_media_tag,
                    "onUpdate:modelValue": _cache[90] || (_cache[90] = $event => ((form.tag_enable_media_tag) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "剧名标签"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.tag_enable_category,
                    "onUpdate:modelValue": _cache[91] || (_cache[91] = $event => ((form.tag_enable_category) = $event)),
                    color: "primary",
                    inset: "",
                    "hide-details": "",
                    label: "下载分类"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    density: "compact",
                    modelValue: form.tag_enable_del_tags,
                    "onUpdate:modelValue": _cache[92] || (_cache[92] = $event => ((form.tag_enable_del_tags) = $event)),
                    color: "error",
                    inset: "",
                    "hide-details": "",
                    label: "允许删除标签"
                  }, null, 8, ["modelValue"])
                ]),
                (form.tag_observe_only)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_178, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-alert-outline",
                        size: "16"
                      }),
                      _cache[157] || (_cache[157] = _createTextVNode("只预览标签和分类，不修改下载器。", -1))
                    ]))
                  : _createCommentVNode("", true),
                (form.tag_enable_del_tags)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_179, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-alert-outline",
                        size: "16"
                      }),
                      _cache[158] || (_cache[158] = _createTextVNode("允许在标签补全时删除下载器标签。", -1))
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_180, [
                  _createElementVNode("div", _hoisted_181, [
                    _createVNode(_component_VTextField, {
                      density: "compact",
                      modelValue: form.tag_siteprefix,
                      "onUpdate:modelValue": _cache[93] || (_cache[93] = $event => ((form.tag_siteprefix) = $event)),
                      label: "站点标签前缀",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _createElementVNode("div", _hoisted_182, [
                    _createVNode(_component_VSelect, {
                      density: "compact",
                      modelValue: form.tag_downloaders,
                      "onUpdate:modelValue": _cache[94] || (_cache[94] = $event => ((form.tag_downloaders) = $event)),
                      label: "下载器",
                      variant: "outlined",
                      items: downloaderItems.value,
                      multiple: "",
                      chips: "",
                      "closable-chips": "",
                      clearable: "",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "items"])
                  ]),
                  _createElementVNode("div", _hoisted_183, [
                    _createVNode(_component_VCronField, {
                      density: "compact",
                      modelValue: form.tag_interval_cron,
                      "onUpdate:modelValue": _cache[95] || (_cache[95] = $event => ((form.tag_interval_cron) = $event)),
                      label: "补全计划",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ])
              ], 512), [
                [_vShow, activeSub.value === 'tag_basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_184, [
                _createVNode(FormSection, {
                  title: "分类规则",
                  icon: _unref(MODULE_ICONS).tag
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_185, [
                      _createElementVNode("div", _hoisted_186, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: form.tag_rename_type,
                          "onUpdate:modelValue": _cache[96] || (_cache[96] = $event => ((form.tag_rename_type) = $event)),
                          items: [{title:'TMDB 识别',value:false},{title:'路径关键词',value:true}],
                          label: "分类方式",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_187, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: form.tag_catprefix,
                          "onUpdate:modelValue": _cache[97] || (_cache[97] = $event => ((form.tag_catprefix) = $event)),
                          label: "分类前缀",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    (!form.tag_rename_type)
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                          (tagCategoriesLoading.value)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_188, "正在读取 MP 分类…"))
                            : _createCommentVNode("", true),
                          (tagCategoriesError.value)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_189, _toDisplayString(tagCategoriesError.value) + "；已有映射保持不变，可重试。", 1))
                            : _createCommentVNode("", true),
                          _createElementVNode("div", _hoisted_190, [
                            _cache[160] || (_cache[160] = _createElementVNode("div", { class: "dm-cat-row dm-cat-row--head" }, [
                              _createElementVNode("span", null, "来源分类（MP 配置）"),
                              _createElementVNode("span"),
                              _createElementVNode("span", null, "写入分类"),
                              _createElementVNode("span")
                            ], -1)),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(tagCategoryRows.value, (pair) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: pair.from,
                                class: "dm-cat-row"
                              }, [
                                _createElementVNode("div", _hoisted_191, [
                                  _createElementVNode("span", _hoisted_192, _toDisplayString(pair.from), 1),
                                  (pair.legacy && tagCategoriesLoaded.value)
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_193, "旧映射"))
                                    : _createCommentVNode("", true)
                                ]),
                                _cache[159] || (_cache[159] = _createElementVNode("span", { class: "dm-map-arrow" }, "→", -1)),
                                _createVNode(_component_VTextField, {
                                  density: "compact",
                                  "model-value": pair.to,
                                  "onUpdate:modelValue": $event => (setTagCategoryTarget(pair.from, $event)),
                                  label: "写入分类",
                                  variant: "outlined",
                                  "hide-details": ""
                                }, null, 8, ["model-value", "onUpdate:modelValue"]),
                                (pair.legacy)
                                  ? (_openBlock(), _createBlock(_component_VBtn, {
                                      key: 0,
                                      size: "small",
                                      "aria-label": "移除旧映射",
                                      icon: "mdi-close",
                                      variant: "text",
                                      color: "primary",
                                      onClick: $event => (removeLegacyCategory(pair.from))
                                    }, null, 8, ["onClick"]))
                                  : (_openBlock(), _createElementBlock("span", _hoisted_194))
                              ]))
                            }), 128)),
                            (!tagCategoryRows.value.length && !tagCategoriesLoading.value && !tagCategoriesError.value)
                              ? (_openBlock(), _createElementBlock("div", _hoisted_195, "MP 暂无分类配置"))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_196, [
                            _createVNode(_component_VBtn, {
                              size: "small",
                              variant: "tonal",
                              "prepend-icon": "mdi-refresh",
                              loading: tagCategoriesLoading.value,
                              disabled: tagCategoriesLoading.value,
                              onClick: loadTagCategories
                            }, {
                              default: _withCtx(() => [...(_cache[161] || (_cache[161] = [
                                _createTextVNode("刷新 MP 分类", -1)
                              ]))]),
                              _: 1
                            }, 8, ["loading", "disabled"])
                          ]),
                          _cache[162] || (_cache[162] = _createElementVNode("div", { class: "dm-hint mt-2" }, " 来源读取 MP 当前分类配置，只需修改写入分类；未设置映射时保持原分类。旧映射保留，不会因刷新消失。切换为路径关键词后此表不生效。 ", -1))
                        ], 64))
                      : _createCommentVNode("", true),
                    (form.tag_rename_type)
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                          _createElementVNode("div", _hoisted_197, [
                            _createElementVNode("div", _hoisted_198, [
                              _createVNode(_component_VTextarea, {
                                density: "compact",
                                modelValue: form.tag_path_rename,
                                "onUpdate:modelValue": _cache[98] || (_cache[98] = $event => ((form.tag_path_rename) = $event)),
                                label: "路径映射",
                                variant: "outlined",
                                rows: "3",
                                hint: "每行一条：关键词#分类",
                                "persistent-hint": ""
                              }, null, 8, ["modelValue"])
                            ])
                          ]),
                          _cache[163] || (_cache[163] = _createElementVNode("div", { class: "dm-hint" }, " 当前模式：按下载保存路径包含的关键词判断分类（如 /anime/#动漫），一行不命中则不设分类；关闭上方开关则改按 TMDB 识别设置分类。 ", -1))
                        ], 64))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "站点规则",
                  icon: _unref(MODULE_ICONS).tag
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_199, [
                      _cache[167] || (_cache[167] = _createElementVNode("div", { class: "dm-map-row dm-map-row--head" }, [
                        _createElementVNode("span", null, "Tracker 域名"),
                        _createElementVNode("span"),
                        _createElementVNode("span", null, "站点库域名"),
                        _createElementVNode("span", null, "匹配站点"),
                        _createElementVNode("span", null, "标签"),
                        _createElementVNode("span", null, "自定义标签"),
                        _createElementVNode("span")
                      ], -1)),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(tagTrackerPairs.value, (pair, idx) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: `tracker-${idx}`,
                          class: "dm-map-row"
                        }, [
                          _createVNode(_component_VTextField, {
                            density: "compact",
                            modelValue: pair.tracker,
                            "onUpdate:modelValue": $event => ((pair.tracker) = $event),
                            label: "Tracker 域名",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                          _cache[166] || (_cache[166] = _createElementVNode("span", { class: "dm-map-arrow" }, "→", -1)),
                          _createVNode(_component_VTextField, {
                            density: "compact",
                            modelValue: pair.site,
                            "onUpdate:modelValue": $event => ((pair.site) = $event),
                            label: "站点库域名",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                          _createElementVNode("div", _hoisted_200, [
                            (siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker))
                              ? (_openBlock(), _createBlock(_component_VChip, {
                                  key: 0,
                                  size: "x-small",
                                  label: "",
                                  color: "primary"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker)), 1)
                                  ]),
                                  _: 2
                                }, 1024))
                              : (pair.site)
                                ? (_openBlock(), _createBlock(_component_VChip, {
                                    key: 1,
                                    size: "x-small",
                                    label: "",
                                    color: "warning"
                                  }, {
                                    default: _withCtx(() => [...(_cache[164] || (_cache[164] = [
                                      _createTextVNode("未收录", -1)
                                    ]))]),
                                    _: 1
                                  }))
                                : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_201, [
                            (siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker))
                              ? (_openBlock(), _createBlock(_component_VChip, {
                                  key: 0,
                                  size: "x-small",
                                  label: "",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(form.tag_siteprefix || '') + _toDisplayString(siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker)), 1)
                                  ]),
                                  _: 2
                                }, 1024))
                              : (String(pair.custom || '').trim())
                                ? (_openBlock(), _createBlock(_component_VChip, {
                                    key: 1,
                                    size: "x-small",
                                    label: "",
                                    variant: "tonal",
                                    color: "primary"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(form.tag_siteprefix || '') + _toDisplayString(String(pair.custom).trim()), 1)
                                    ]),
                                    _: 2
                                  }, 1024))
                                : (_openBlock(), _createElementBlock("span", _hoisted_202, "—"))
                          ]),
                          _createElementVNode("div", _hoisted_203, [
                            (siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker))
                              ? (_openBlock(), _createBlock(_component_VChip, {
                                  key: 0,
                                  size: "x-small",
                                  label: "",
                                  variant: "tonal",
                                  color: "success"
                                }, {
                                  default: _withCtx(() => [...(_cache[165] || (_cache[165] = [
                                    _createTextVNode("已收录", -1)
                                  ]))]),
                                  _: 1
                                }))
                              : (_openBlock(), _createBlock(_component_VTextField, {
                                  key: 1,
                                  density: "compact",
                                  modelValue: pair.custom,
                                  "onUpdate:modelValue": $event => ((pair.custom) = $event),
                                  label: "标签名",
                                  variant: "outlined",
                                  "hide-details": ""
                                }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                          ]),
                          _createElementVNode("div", _hoisted_204, [
                            _createVNode(_component_VBtn, {
                              size: "small",
                              "aria-label": "移除映射",
                              icon: "mdi-close",
                              variant: "text",
                              color: "primary",
                              onClick: $event => (tagTrackerPairs.value.splice(idx, 1))
                            }, null, 8, ["onClick"])
                          ])
                        ]))
                      }), 128)),
                      (!tagTrackerPairs.value.length)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_205, "暂无映射，点击下方按钮添加"))
                        : _createCommentVNode("", true)
                    ]),
                    _createElementVNode("div", _hoisted_206, [
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        "prepend-icon": "mdi-plus",
                        onClick: addTrackerPair
                      }, {
                        default: _withCtx(() => [...(_cache[168] || (_cache[168] = [
                          _createTextVNode("添加映射", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _cache[169] || (_cache[169] = _createElementVNode("div", { class: "dm-hint mt-2" }, " 种子 Tracker 域名按行换算成站点库域名后匹配站点打「站点前缀 + 站点名」标签；站点库未收录的行可填「自定义标签」，按「站点前缀 + 自定义标签」打标，留空则跳过。 ", -1))
                  ]),
                  _: 1
                }, 8, ["icon"])
              ], 512), [
                [_vShow, activeSub.value === 'mapping']
              ])
            ])
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "dm-actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VBtn, {
              size: "small",
              color: "primary",
              variant: "tonal",
              "prepend-icon": "mdi-table-eye",
              onClick: switchToData
            }, {
              default: _withCtx(() => [...(_cache[170] || (_cache[170] = [
                _createTextVNode("查看数据", -1)
              ]))]),
              _: 1
            }),
            (saveMessage.value)
              ? (_openBlock(), _createElementBlock("span", {
                  key: 0,
                  class: _normalizeClass(["dm-hint", { 'text-error': saveError.value }]),
                  role: "status",
                  "aria-live": "polite"
                }, _toDisplayString(saveMessage.value), 3))
              : _createCommentVNode("", true),
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              size: "small",
              color: "primary",
              variant: "tonal",
              onClick: _cache[99] || (_cache[99] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[171] || (_cache[171] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              size: "small",
              color: "primary",
              variant: "tonal",
              "prepend-icon": "mdi-content-save-outline",
              loading: savePending.value,
              disabled: savePending.value,
              onClick: saveConfig
            }, {
              default: _withCtx(() => [...(_cache[172] || (_cache[172] = [
                _createTextVNode("保存配置", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "disabled"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDialog, {
      "content-class": "dm-config",
      modelValue: hrAddDialog.value,
      "onUpdate:modelValue": _cache[102] || (_cache[102] = $event => ((hrAddDialog).value = $event)),
      "max-width": "520"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "dm-form-dialog" }, {
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
                    _createVNode(_component_VIcon, { icon: "mdi-home-plus-outline" })
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "dm-title" }, {
                  default: _withCtx(() => [...(_cache[173] || (_cache[173] = [
                    _createTextVNode("新增自定义站点", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint" }, {
                  default: _withCtx(() => [...(_cache[174] || (_cache[174] = [
                    _createTextVNode("站点名需与站点标签识别出的站点名一致", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(_component_VTextField, {
                  density: "compact",
                  modelValue: hrNewSiteName.value,
                  "onUpdate:modelValue": _cache[100] || (_cache[100] = $event => ((hrNewSiteName).value = $event)),
                  "error-messages": hrAddError.value,
                  label: "站点名",
                  variant: "outlined",
                  hint: "先写入 site_name，字段留空表示继承全局规则",
                  "persistent-hint": "",
                  onKeyup: _withKeys(hrConfirmAddSite, ["enter"])
                }, null, 8, ["modelValue", "error-messages"])
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
                  onClick: _cache[101] || (_cache[101] = $event => (hrAddDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[175] || (_cache[175] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "primary",
                  variant: "flat",
                  "prepend-icon": "mdi-plus",
                  onClick: hrConfirmAddSite
                }, {
                  default: _withCtx(() => [...(_cache[176] || (_cache[176] = [
                    _createTextVNode("添加站点", -1)
                  ]))]),
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
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-config",
      modelValue: transferDialog.value,
      "onUpdate:modelValue": _cache[122] || (_cache[122] = $event => ((transferDialog).value = $event)),
      "max-width": "780",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "dm-form-dialog dm-transfer-form dm-compact-form" }, {
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
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(transferEditing.value >= 0 ? '编辑转移任务' : '添加转移任务'), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint" }, {
                  default: _withCtx(() => [...(_cache[177] || (_cache[177] = [
                    _createTextVNode("源/目的下载器必填且不能相同；数据映射可选（两个都空 = 不映射，只填一个才报错）", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(FormSection, {
                  title: "任务信息",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  actions: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      density: "compact",
                      modelValue: transferForm.enabled,
                      "onUpdate:modelValue": _cache[103] || (_cache[103] = $event => ((transferForm.enabled) = $event)),
                      color: "primary",
                      inset: "",
                      "hide-details": "",
                      label: "启用"
                    }, null, 8, ["modelValue"])
                  ]),
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_207, [
                      _createElementVNode("div", _hoisted_208, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: transferForm.name,
                          "onUpdate:modelValue": _cache[104] || (_cache[104] = $event => ((transferForm.name) = $event)),
                          label: "任务名称",
                          variant: "outlined",
                          hint: "留空自动命名为「任务N」",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_209, [
                      _createElementVNode("div", _hoisted_210, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: transferForm.from_downloader,
                          "onUpdate:modelValue": _cache[105] || (_cache[105] = $event => ((transferForm.from_downloader) = $event)),
                          "error-messages": transferError.value && (!transferForm.from_downloader || !transferForm.to_downloader || transferForm.from_downloader === transferForm.to_downloader) ? transferError.value : '',
                          items: downloaderSelectItems.value,
                          label: "源下载器",
                          variant: "outlined",
                          hint: "从该下载器复制种子",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "error-messages", "items"])
                      ]),
                      _createElementVNode("div", _hoisted_211, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: transferForm.to_downloader,
                          "onUpdate:modelValue": _cache[106] || (_cache[106] = $event => ((transferForm.to_downloader) = $event)),
                          "error-messages": transferError.value && (!transferForm.from_downloader || !transferForm.to_downloader || transferForm.from_downloader === transferForm.to_downloader) ? transferError.value : '',
                          items: downloaderSelectItems.value,
                          label: "目标下载器",
                          variant: "outlined",
                          hint: "转移目标下载器",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "error-messages", "items"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "数据路径",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_212, [
                      _createElementVNode("div", _hoisted_213, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: transferForm.from_path,
                          "onUpdate:modelValue": _cache[107] || (_cache[107] = $event => ((transferForm.from_path) = $event)),
                          "error-messages": transferError.value && (!!transferForm.from_path !== !!transferForm.to_path) ? transferError.value : '',
                          label: "源数据路径",
                          variant: "outlined",
                          hint: "数据可见性映射（可选）：两个都留空 = 不做映射；只填一个视为配置错误",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "error-messages"])
                      ]),
                      _createElementVNode("div", _hoisted_214, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: transferForm.to_path,
                          "onUpdate:modelValue": _cache[108] || (_cache[108] = $event => ((transferForm.to_path) = $event)),
                          "error-messages": transferError.value && (!!transferForm.from_path !== !!transferForm.to_path) ? transferError.value : '',
                          label: "目标数据路径",
                          variant: "outlined",
                          hint: "数据可见性映射（可选）：两个都留空 = 不做映射；只填一个视为配置错误",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "error-messages"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "筛选条件",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_215, [
                      _createElementVNode("div", _hoisted_216, [
                        _createVNode(MultiValueInput, {
                          modelValue: transferForm.include_category,
                          "onUpdate:modelValue": _cache[109] || (_cache[109] = $event => ((transferForm.include_category) = $event)),
                          label: "包含分类",
                          variant: "outlined",
                          hint: "仅转移这些分类的种子，留空不限制",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_217, [
                        _createVNode(MultiValueInput, {
                          modelValue: transferForm.include_labels,
                          "onUpdate:modelValue": _cache[110] || (_cache[110] = $event => ((transferForm.include_labels) = $event)),
                          label: "包含标签",
                          variant: "outlined",
                          hint: "仅转移包含这些标签的种子，留空不限制",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_218, [
                      _createElementVNode("div", _hoisted_219, [
                        _createVNode(MultiValueInput, {
                          modelValue: transferForm.exclude_labels,
                          "onUpdate:modelValue": _cache[111] || (_cache[111] = $event => ((transferForm.exclude_labels) = $event)),
                          label: "排除标签",
                          variant: "outlined",
                          hint: "包含这些标签的种子跳过",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_220, [
                      _createVNode(_component_VCheckbox, {
                        density: "compact",
                        modelValue: transferForm.empty_label_ok,
                        "onUpdate:modelValue": _cache[112] || (_cache[112] = $event => ((transferForm.empty_label_ok) = $event)),
                        color: "info",
                        "hide-details": "",
                        label: "允许无标签种子"
                      }, null, 8, ["modelValue"])
                    ]),
                    _createElementVNode("div", _hoisted_221, [
                      _createElementVNode("div", _hoisted_222, [
                        _createVNode(_component_VTextarea, {
                          density: "compact",
                          modelValue: transferForm.no_paths,
                          "onUpdate:modelValue": _cache[113] || (_cache[113] = $event => ((transferForm.no_paths) = $event)),
                          label: "排除路径",
                          variant: "outlined",
                          rows: "3",
                          hint: "每行一个路径",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                _createVNode(FormSection, {
                  title: "高级设置",
                  icon: _unref(MODULE_ICONS).transfer
                }, {
                  default: _withCtx(() => [
                    (transferForm.delete_source === true)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_223, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-outline",
                            size: "16"
                          }),
                          _cache[178] || (_cache[178] = _createTextVNode(" 「删除源任务」受 H&R 保护约束：源种若已纳入 H&R 管理且未达标，源任务会被保留，并计入数据页「转移做种」卡的「H&R 保护」跳过数。放行办法有三种——等它达标（自动放行）、让种子在进入下载器前就带 H&R 排除标签、或关闭 H&R 保护总开关。注意：", -1)),
                          _cache[179] || (_cache[179] = _createElementVNode("strong", null, "已纳管的种子事后补排除标签无效", -1)),
                          _cache[180] || (_cache[180] = _createTextVNode("（排除只在首次纳管时判定）。 ", -1))
                        ]))
                      : _createCommentVNode("", true),
                    _createElementVNode("div", _hoisted_224, [
                      _createElementVNode("div", _hoisted_225, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: transferForm.delete_source,
                          "onUpdate:modelValue": _cache[114] || (_cache[114] = $event => ((transferForm.delete_source) = $event)),
                          items: transferDeleteItems(form.transfer_delete_source_default),
                          label: "删除源任务",
                          variant: "outlined",
                          hint: "使用默认值，或为此任务单独开启/关闭；实际生效值见任务列表",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"]),
                        (transferForm.delete_source === true)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_226, [
                              _createVNode(_component_VIcon, {
                                icon: "mdi-alert-outline",
                                size: "16"
                              }),
                              _cache[181] || (_cache[181] = _createTextVNode("转移后删除源任务，仍受 H&R 保护约束。", -1))
                            ]))
                          : _createCommentVNode("", true)
                      ]),
                      _createElementVNode("div", _hoisted_227, [
                        _createVNode(_component_VSelect, {
                          density: "compact",
                          modelValue: transferForm.delete_duplicate,
                          "onUpdate:modelValue": _cache[115] || (_cache[115] = $event => ((transferForm.delete_duplicate) = $event)),
                          items: transferDeleteItems(form.transfer_delete_duplicate_default),
                          label: "删除重复任务",
                          variant: "outlined",
                          hint: "使用默认值，或为此任务单独开启/关闭；实际生效值见任务列表",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"]),
                        (transferForm.delete_duplicate === true)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_228, [
                              _createVNode(_component_VIcon, {
                                icon: "mdi-alert-outline",
                                size: "16"
                              }),
                              _cache[182] || (_cache[182] = _createTextVNode("转移时删除重复任务，仍受 H&R 保护约束。", -1))
                            ]))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_229, [
                      _createElementVNode("div", _hoisted_230, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: transferForm.keep_category,
                          "onUpdate:modelValue": _cache[116] || (_cache[116] = $event => ((transferForm.keep_category) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "保留原分类"
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_231, [
                        _createVNode(_component_VSwitch, {
                          density: "compact",
                          modelValue: transferForm.keep_tag,
                          "onUpdate:modelValue": _cache[117] || (_cache[117] = $event => ((transferForm.keep_tag) = $event)),
                          color: "primary",
                          inset: "",
                          "hide-details": "",
                          label: "保留原标签"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_232, [
                      _createElementVNode("div", _hoisted_233, [
                        _createVNode(_component_VTextField, {
                          density: "compact",
                          modelValue: transferForm.transfer_tag,
                          "onUpdate:modelValue": _cache[118] || (_cache[118] = $event => ((transferForm.transfer_tag) = $event)),
                          label: "目标标签",
                          variant: "outlined",
                          hint: "默认「已转移」；留空表示不打标签",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ])
                  ]),
                  _: 1
                }, 8, ["icon"]),
                (transferDialogSourceType.value === 'rtorrent')
                  ? (_openBlock(), _createBlock(FormSection, {
                      key: 0,
                      title: "ruTorrent 网络导出",
                      icon: _unref(MODULE_ICONS).transfer
                    }, {
                      default: _withCtx(() => [
                        _cache[183] || (_cache[183] = _createElementVNode("div", { class: "dm-hint mb-2" }, "源端为 rtorrent 时，必须填写 ruTorrent WebUI 地址与 source 插件路径，否则无法导出种子数据。", -1)),
                        _createElementVNode("div", _hoisted_234, [
                          _createElementVNode("div", _hoisted_235, [
                            _createVNode(_component_VTextField, {
                              density: "compact",
                              modelValue: transferForm.ext_webui_url,
                              "onUpdate:modelValue": _cache[119] || (_cache[119] = $event => ((transferForm.ext_webui_url) = $event)),
                              label: "ruTorrent WebUI 地址",
                              variant: "outlined",
                              hint: "如 http://127.0.0.1:8080/rutorrent，不含末尾斜杠",
                              "persistent-hint": ""
                            }, null, 8, ["modelValue"])
                          ]),
                          _createElementVNode("div", _hoisted_236, [
                            _createVNode(_component_VTextField, {
                              density: "compact",
                              modelValue: transferForm.ext_source_plugin,
                              "onUpdate:modelValue": _cache[120] || (_cache[120] = $event => ((transferForm.ext_source_plugin) = $event)),
                              label: "source 插件路径",
                              variant: "outlined",
                              hint: "相对 WebUI 地址的 source 插件路径，如 plugins/source/action.php",
                              "persistent-hint": ""
                            }, null, 8, ["modelValue"])
                          ])
                        ])
                      ]),
                      _: 1
                    }, 8, ["icon"]))
                  : _createCommentVNode("", true)
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
                  onClick: _cache[121] || (_cache[121] = $event => (transferDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[184] || (_cache[184] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "primary",
                  variant: "flat",
                  "prepend-icon": "mdi-check",
                  onClick: confirmTransferTask
                }, {
                  default: _withCtx(() => [...(_cache[185] || (_cache[185] = [
                    _createTextVNode("应用任务", -1)
                  ]))]),
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
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-config",
      modelValue: transferDeleteDialog.value,
      "onUpdate:modelValue": _cache[124] || (_cache[124] = $event => ((transferDeleteDialog).value = $event)),
      "max-width": "480"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "dm-form-dialog" }, {
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
                  default: _withCtx(() => [...(_cache[186] || (_cache[186] = [
                    _createTextVNode("删除转移任务", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint" }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(transferDeleteName.value || '未命名任务'), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "dm-body-text" }, {
              default: _withCtx(() => [...(_cache[187] || (_cache[187] = [
                _createTextVNode(" 删除后该任务不再参与转移做种；已转移的种子不受影响。改动先作用于表单，点击下方「保存」后才会真正生效。 ", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  onClick: _cache[123] || (_cache[123] = $event => (transferDeleteDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[188] || (_cache[188] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "error",
                  variant: "flat",
                  "prepend-icon": "mdi-delete-outline",
                  onClick: confirmTransferDelete
                }, {
                  default: _withCtx(() => [...(_cache[189] || (_cache[189] = [
                    _createTextVNode("删除任务", -1)
                  ]))]),
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
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      "content-class": "dm-config",
      modelValue: paneResetDialog.value,
      "onUpdate:modelValue": _cache[126] || (_cache[126] = $event => ((paneResetDialog).value = $event)),
      "max-width": "560"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "dm-form-dialog" }, {
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
                    _createVNode(_component_VIcon, { icon: "mdi-restore" })
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "dm-title" }, {
                  default: _withCtx(() => [
                    _createTextVNode("恢复「" + _toDisplayString(paneResetTitle.value) + "」默认设置", 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "dm-hint" }, {
                  default: _withCtx(() => [
                    _createTextVNode("仅重置本页签的 " + _toDisplayString(paneResetCount.value) + " 项，不影响其他页签", 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "dm-body-text" }, {
              default: _withCtx(() => [
                _cache[190] || (_cache[190] = _createTextVNode(" 将把本页签全部设置恢复为插件默认值。改动先作用于表单，点击下方「保存」后才会真正生效。", -1)),
                (paneResetTarget.value === 'hr')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _createTextVNode("H&R 站点独立规则也会一并清空回全局基准。")
                    ], 64))
                  : _createCommentVNode("", true)
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
                  onClick: _cache[125] || (_cache[125] = $event => (paneResetDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[191] || (_cache[191] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  size: "small",
                  color: "warning",
                  variant: "flat",
                  "prepend-icon": "mdi-restore",
                  onClick: confirmPaneReset
                }, {
                  default: _withCtx(() => [...(_cache[192] || (_cache[192] = [
                    _createTextVNode("恢复默认", -1)
                  ]))]),
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
  ], 2))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-65e5d0c0"]]);

export { Config as default };
