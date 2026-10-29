// 结构一致性审计：对一个或多个 dom-audit.js 产出的 dump JSON，
// 按 role 分组比较「同一层级」的文字/控件样式签名，输出可直接对照的 Markdown。
//
// 用法：node tests/dom-audit-roles.mjs .ralph/dom-baseline/config-before.json .ralph/dom-baseline/page-before.json
// 说明：签名只取规范第 2 节关心的属性；几何差异（x/y、对齐）需 dump 扩展后才有，见文件末尾提示。

import { readFileSync } from 'node:fs';

// 形状属性：同级应当统一，用于判定「不统一」
const SHAPE = ['fontSize', 'fontWeight', 'lineHeight', 'height', 'borderRadius'];
// 语义属性：允许按状态不同（危险按钮红、观察橙等），只记录不判错
const SEMANTIC = ['color', 'paddingLeft', 'letterSpacing'];
const PROPS = [...SHAPE, ...SEMANTIC];

const ROLE_ORDER = [
  'title', 'section', 'label', 'field', 'switch', 'help',
  'table-head', 'table-cell', 'badge', 'tab', 'card', 'button', 'other',
];

const files = process.argv.slice(2);
if (!files.length) {
  console.error('用法: node tests/dom-audit-roles.mjs <dump.json> [dump2.json ...]');
  process.exit(2);
}

const shapeSig = (node) => SHAPE.map((p) => node.styles?.[p] ?? '-').join(' | ');
const semanticSig = (node) => SEMANTIC.map((p) => node.styles?.[p] ?? '-').join(' | ');
const brief = (node) => {
  const text = String(node.text ?? '').replace(/\s+/g, ' ').trim();
  const label = text ? `「${text.slice(0, 26)}」` : '(无文字)';
  const { w = 0, h = 0 } = node.rect ?? {};
  return `${label} ${Math.round(w)}×${Math.round(h)}`;
};
const load = (file) => {
  const dump = JSON.parse(readFileSync(file, 'utf8'));
  return {
    file,
    counts: dump.counts ?? {},
    capturedAt: dump.capturedAt ?? '',
    nodes: Array.isArray(dump.nodes) ? dump.nodes : [],
  };
};

const dumps = files.map(load);
const byRole = (nodes) => {
  const groups = new Map();
  for (const node of nodes) {
    const role = node.role ?? 'other';
    if (!groups.has(role)) groups.set(role, new Map());
    const inner = groups.get(role);
    const key = shapeSig(node);
    if (!inner.has(key)) inner.set(key, []);
    inner.get(key).push(node);
  }
  return groups;
};

const out = [];
const say = (line = '') => out.push(line);

say('# 结构一致性审计（同一 role 内的样式签名对比）');
say();
say(`生成时间：${new Date().toISOString()}`);
say();
say('> 数据来源：`tests/dom-audit.js` 的真实浏览器计算样式 dump。只有图上事实，无观感判断。');
say('> 判据：同一 `role` 出现多个签名 = 该层级不统一，需要收敛到规范值。');
say();

dumps.forEach((dump, index) => {
  const groups = byRole(dump.nodes);
  say(`## 文件 ${index + 1}：\`${dump.file}\``);
  say();
  say(`- 采集时间：${dump.capturedAt}`);
  say(`- 节点数：${dump.counts.nodes ?? dump.nodes.length}，角色分布：${[...groups.entries()]
    .map(([role, m]) => `${role}=${[...m.values()].reduce((a, v) => a + v.length, 0)}`)
    .join(' / ')}`);
  say();
  for (const role of ROLE_ORDER) {
    const inner = groups.get(role);
    if (!inner) continue;
    const total = [...inner.values()].reduce((a, v) => a + v.length, 0);
    const signatures = [...inner.entries()]
      .map(([key, nodes]) => [key, nodes, [...new Set(nodes.map(semanticSig))]])
      .sort((a, b) => b[1].length - a[1].length);
    const flag = signatures.length > 1 ? `**不统一：${signatures.length} 种签名**` : '统一：1 种签名';
    say(`### ${role}（${total} 个节点）—— ${flag}`);
    say();
    signatures.forEach(([key, nodes, semanticSets], i) => {
      const props = SHAPE.map((p, j) => `${p}=${key.split(' | ')[j]}`).join('，');
      say(`- 签名 ${i + 1}（${nodes.length} 个）：${props}`);
      const samples = nodes.slice(0, 3).map(brief).join('；');
      say(`  - 例：${samples}`);
      if (semanticSets.length) {
        say(`  - 语义属性（允许不同）：${semanticSets.join(' / ')}`);
      }
      if (nodes.length > 3) say(`  - 其余 ${nodes.length - 3} 个同类节点略`);
    });
    say();
  }
});

if (dumps.length > 1) {
  say('## 跨文件对比（同一 role 在两页是否一致）');
  say();
  const maps = dumps.map((d) => byRole(d.nodes));
  const roles = new Set(maps.flatMap((m) => [...m.keys()]));
  say('| role | 各文件签名数 | 结论 |');
  say('| --- | --- | --- |');
  for (const role of ROLE_ORDER.filter((r) => roles.has(r))) {
    const per = maps.map((m) => (m.has(role) ? m.get(role).size : 0));
    const present = per.filter((n) => n > 0);
    const verdict = present.length < 2 ? '单文件出现，无法比对'
      : present.every((n) => n === 1)
        ? (maps.every((m) => !m.has(role) || new Set([...m.get(role).keys()]).size === 1)
          && new Set(maps.flatMap((m) => (m.has(role) ? [...m.get(role).keys()] : []))).size === 1
          ? '一致'
          : '**不一致**')
        : '**各自内部即不统一**';
    say(`| ${role} | ${per.join(' / ')} | ${verdict} |`);
  }
  say();
  const shared = new Set(
    maps[0] && maps[1] ? [...maps[0].keys()].filter((r) => maps[1].has(r)) : [],
  );
  if (shared.size) {
    say('### 共有 role 的签名明细');
    say();
    for (const role of ROLE_ORDER.filter((r) => shared.has(r))) {
      const sets = maps.map((m) => [...m.get(role).keys()]);
      const union = new Set(sets.flat());
      if (union.size <= 1) continue;
      say(`- **${role}**：`);
      sets.forEach((keys, i) => {
        for (const key of keys) {
          say(`  - 文件 ${i + 1}：${key}`);
        }
      });
    }
    say();
  }
}

say('## 控件宽度分布（同一 role 的 rect.w / rect.h）');
say();
for (const dump of dumps) {
  const counted = new Map();
  for (const node of dump.nodes) {
    for (const role of ['field', 'switch', 'button']) {
      if (node.role !== role) continue;
      const { w = 0, h = 0 } = node.rect ?? {};
      const key = `${role} | ${Math.round(w)}×${Math.round(h)}`;
      counted.set(key, (counted.get(key) ?? 0) + 1);
    }
  }
  say(`### \`${dump.file}\``);
  say();
  const rows = [...counted.entries()].sort((a, b) => b[1] - a[1]);
  if (!rows.length) say('- 无 field/switch/button 节点');
  for (const [key, count] of rows) say(`- ${key} → ${count} 个`);
  say();
}
say('## 本次未覆盖（需扩展 dump 才能量化）');
say();
say('- 元素之间的对齐（标签与输入框垂直中心差）、同级控件起点 x 是否对齐、内容区右侧/下方空白占比：');
say('  当前 `rect` 只有 `w`/`h`，没有 `x`/`y`。需要给 `tests/dom-audit.js` 补 `x`/`y` 后重新采集才能出数值，');
say('  在此之前由视觉模型给出的像素差值一律只作线索、不作判据。');

const text = `${out.join('\n')}\n`;
process.stdout.write(text);
