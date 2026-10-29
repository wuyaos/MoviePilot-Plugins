import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { compileScript, compileStyle, parse } from '@vue/compiler-sfc'
import { createRenderer, createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'

const root = fileURLToPath(new URL('../../', import.meta.url))
// Resolve bare imports from existing project dependencies, just like the existing harness.
// Only CSS imports are removed for Node; styles are parsed separately and built by Vite.
export async function loadSfc(name, { transformSource = source => source } = {}) {
  const dir = fs.mkdtempSync(path.join(root, 'node_modules', '.dml-sfc-'))
  const compiled = new Set()
  function compile(file) {
    const filename = path.join(root, 'src/components', file)
    const output = path.join(dir, file.replace('.vue', '.mjs'))
    if (compiled.has(file)) return output
    compiled.add(file)
    const source = transformSource(fs.readFileSync(filename, 'utf8'), filename)
    const { descriptor, errors } = parse(source, { filename })
    assert.deepEqual(errors, [])
    const id = 'dml-' + file.replace('.vue', '').toLowerCase()
    for (const style of descriptor.styles) {
      assert.deepEqual(compileStyle({ source: style.content, filename, id, scoped: style.scoped }).errors, [])
    }
    let content = compileScript(descriptor, { id, inlineTemplate: true }).content
    content = content.replace(/^import ['"][^'"\n]+\.css['"];?$/gm, '')
    content = content.replace(/from ['"](\.\/[^'"]+\.vue)['"]/g, (_, imported) => {
      const dependency = path.basename(imported)
      compile(dependency)
      return 'from ' + JSON.stringify('./' + dependency.replace('.vue', '.mjs'))
    })
    // Preserve real local JS modules (including extensionless ./api imports).
    content = content.replace(/from ['"](\.\/[^'"]+)['"]/g, (statement, imported) => {
      if (imported.endsWith('.mjs')) return statement
      const dependency = path.resolve(path.dirname(filename), imported)
      const resolved = path.extname(dependency) ? dependency : dependency + '.js'
      return 'from ' + JSON.stringify(pathToFileURL(resolved).href)
    })
    fs.writeFileSync(output, content)
    return output
  }
  try { return (await import(pathToFileURL(compile(name)).href)).default }
  finally { fs.rmSync(dir, { recursive: true, force: true }) }
}

export const render = (component, props = {}, slots = {}) =>
  renderToString(createSSRApp({ render: () => h(component, props, slots) }))

// Vue's real renderer with an in-memory host, not a fake component/setup implementation.
// Event handlers and reactive row expansion can be exercised without DOM dependencies.
export function mount(component, props = {}, slots = {}, { components = {} } = {}) {
  const node = (type, text = '') => ({ type, text, props: {}, style: {}, children: [], parent: null })
  const renderer = createRenderer({
    createElement: type => node(type),
    createText: text => node('#text', text),
    createComment: text => node('#comment', text),
    setText: (el, text) => { el.text = text },
    setElementText: (el, text) => { el.text = text; el.children = [] },
    patchProp: (el, key, prev, next) => { el.props[key] = next },
    insert(el, parent, anchor = null) {
      if (el.parent) el.parent.children.splice(el.parent.children.indexOf(el), 1)
      const index = anchor ? parent.children.indexOf(anchor) : -1
      parent.children.splice(index < 0 ? parent.children.length : index, 0, el)
      el.parent = parent
    },
    remove(el) { if (el.parent) el.parent.children.splice(el.parent.children.indexOf(el), 1); el.parent = null },
    parentNode: el => el.parent,
    nextSibling: el => el.parent?.children[el.parent.children.indexOf(el) + 1] || null,
  })
  const root = node('root')
  const app = renderer.createApp({ render: () => h(component, props, slots) })
  for (const [name, stub] of Object.entries(components)) app.component(name, stub)
  app.mount(root)
  const findAll = predicate => {
    const found = []
    function visit(el) { if (predicate(el)) found.push(el); el.children.forEach(visit) }
    visit(root)
    return found
  }
  return { root, findAll, unmount: () => app.unmount() }
}
