import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { F as FarmWorkbench } from './FarmWorkbench-DkuW1n3n.js';

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: Object, default: () => ({}) },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

return (_ctx, _cache) => {
  return (_openBlock(), _createBlock(FarmWorkbench, {
    api: props.api,
    "plugin-id": "FarmAuto",
    "show-close": "",
    "show-switch": "",
    compact: "",
    onAction: _cache[0] || (_cache[0] = $event => (emit('action', $event))),
    onSwitch: _cache[1] || (_cache[1] = $event => (emit('switch'))),
    onClose: _cache[2] || (_cache[2] = $event => (emit('close')))
  }, null, 8, ["api"]))
}
}

};

export { _sfc_main as default };
