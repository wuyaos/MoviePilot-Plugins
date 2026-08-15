import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const _sfc_main = {  };
const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


function _sfc_render(_ctx, _cache) {
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_card = _resolveComponent("v-card");

  return (_openBlock(), _createBlock(_component_v_card, {
    flat: "",
    class: "rounded border"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card_text, null, {
        default: _withCtx(() => [
          _createVNode(_component_v_alert, {
            type: "info",
            variant: "tonal"
          }, {
            default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode(" 农场仪表盘加载中（Phase 3 实现） ", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['render',_sfc_render]]);

export { Dashboard as default };
