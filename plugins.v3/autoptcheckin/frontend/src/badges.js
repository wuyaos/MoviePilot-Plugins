export const sourceBadge = source => ({'MP 站点':'badge-mp', '插件适配':'badge-adapter', '自定义站点':'badge-custom'}[source] || 'badge-unknown')
export function credentialBadge(source = '') {
  if (/jwt|api/i.test(source)) return 'badge-api_key'
  if (/cookie/i.test(source)) return 'badge-cookie'
  if (/password|密码/.test(source)) return 'badge-password'
  return 'badge-unknown'
}
