function syncTheme() {
  const root = document.documentElement
  const host = document.querySelector('.v-application') || root
  const style = getComputedStyle(host)
  const channels = style.getPropertyValue('--v-theme-surface').match(/[\d.]+/g)?.map(Number)
  let dark
  if (host.classList.contains('v-theme--dark') || root.classList.contains('v-theme--dark')) dark = true
  else if (host.classList.contains('v-theme--light') || root.classList.contains('v-theme--light')) dark = false
  else if (channels?.length === 3) dark = channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722 < 128
  else dark = matchMedia('(prefers-color-scheme: dark)').matches
  const theme = dark ? 'dark' : 'light'
  const glass = String(host.classList.contains('v-theme--glass') || root.classList.contains('v-theme--glass'))
  if (root.dataset.ptcTheme !== theme) root.dataset.ptcTheme = theme
  if (root.dataset.ptcGlass !== glass) root.dataset.ptcGlass = glass
}

export function watchHostTheme() {
  if (typeof document === 'undefined') return () => {}
  syncTheme()
  const observer = new MutationObserver(syncTheme)
  observer.observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['class', 'style'] })
  const media = matchMedia('(prefers-color-scheme: dark)')
  media.addEventListener('change', syncTheme)
  return () => { observer.disconnect(); media.removeEventListener('change', syncTheme) }
}
