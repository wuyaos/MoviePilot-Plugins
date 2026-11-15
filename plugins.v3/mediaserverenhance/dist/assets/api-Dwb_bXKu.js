function isStandardEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response).sort();
  return keys.length === 3
    && keys[0] === 'data'
    && keys[1] === 'message'
    && keys[2] === 'success'
    && typeof response.success === 'boolean'
}

function pluginPath(pluginId, path = '') {
  const normalizedId = String(pluginId || '').trim();
  if (!normalizedId) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '');
  return suffix ? `plugin/${normalizedId}/${suffix}` : `plugin/${normalizedId}`
}

function unwrapResponse(response) {
  if (!isStandardEnvelope(response)) return response
  if (!response.success) {
    const error = new Error(response.message || '请求失败');
    error.code = response.data?.code;
    throw error
  }
  return response.data
}

async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(pluginPath(pluginId, path), options);
  return unwrapResponse(response)
}

async function postPluginJsonApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(pluginPath(pluginId, path), payload, options);
  return unwrapResponse(response)
}

function errorText(error) {
  return error?.response?.data?.message || error?.response?.data?.detail
    || error?.data?.message || error?.data?.detail || error?.message || '请求失败'
}

export { errorText as e, getPluginApi as g, postPluginJsonApi as p };
