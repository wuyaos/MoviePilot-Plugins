#!/usr/bin/env node
// DML 样式审计对比：把 dom-audit.js 的两次 dump（改前/改后）做机器化对比。
// 用法：
//   node tests/dom-audit-diff.mjs <baseline.json> [after.json] [--md out.md]
// 只给 baseline 时：输出「当前同角色不一致清单」（P1 的输入）。
// 给两个文件时：输出不一致项的变化（新增 / 消失）。
import fs from 'node:fs';
import path from 'node:path';

const STYLE_KEYS = ['fontSize', 'fontWeight', 'lineHeight', 'color', 'backgroundColor', 'borderRadius', 'paddingTop', 'paddingLeft', 'marginTop', 'marginBottom', 'height'];
const UNIFY_ROLES = new Set(['title', 'section', 'label', 'help', 'button', 'badge', 'table-head', 'table-cell', 'field', 'switch']);
const IGNORE_CLASSES = /(v-tab|dm-side-item|v-overlay|v-ripple|v-btn__overlay|v-field__outline|v-progress|dm-chart)/;

function loadDump(file) {
  const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
  const payload = raw && raw.result && raw.result.js_return ? JSON.parse(raw.result.js_return) : raw;
  if (!payload || payload.ok !== true) throw new Error(`${file}: dump ok!==true (${payload && payload.reason})`);
  return payload;
}

function roleIndex(dump) {
  const groups = new Map();
  for (const node of dump.nodes) {
    if (!UNIFY_ROLES.has(node.role)) continue;
    if (IGNORE_CLASSES.test(node.sig)) continue;
    const key = `${node.role} :: ${node.sig || '(no-class)'}`;
    if (!groups.has(key)) groups.set(key, { key, role: node.role, sig: node.sig, seen: 0, texts: [], styles: new Map(), issues: new Set() });
    const group = groups.get(key);
    group.seen += 1;
    if (node.text && group.texts.length < 3) group.texts.push(node.text.slice(0, 40));
    const tuple = STYLE_KEYS.map(k => node.styles[k]).join('|');
    if (!group.styles.has(tuple)) group.styles.set(tuple, { tuple, count: 0, sample: node.styles });
    group.styles.get(tuple).count += 1;
    for (const issue of node.issues || []) group.issues.add(issue);
  }
  return groups;
}

function styleDelta(a, b) {
  const diffs = [];
  for (const k of STYLE_KEYS) {
    if (a[k] !== b[k]) diffs.push(`${k}: ${a[k]} -> ${b[k]}`);
  }
  return diffs;
}

function compare(baseline, after) {
  const baseGroups = roleIndex(baseline);
  const afterGroups = roleIndex(after);
  const lines = [];
  const push = s => lines.push(s);
  push(`# DML 样式审计对比`);
  push('');
  push(`- baseline: ${baseline.context} @ ${baseline.capturedAt} (${baseline.nodes.length} nodes, v=${path.basename(baseline.version.split('?')[1] || baseline.version)})`);
  push(`- after:    ${after.context} @ ${after.capturedAt} (${after.nodes.length} nodes, v=${path.basename(after.version.split('?')[1] || after.version)})`);
  push('');

  const resolved = [];
  const changed = [];
  let remaining = 0;
  for (const [key, group] of baseGroups) {
    const afterGroup = afterGroups.get(key);
    const baseVariants = group.styles.size;
    if (baseVariants < 2) continue;
    const afterVariants = afterGroup ? afterGroup.styles.size : 0;
    if (afterGroup && afterVariants === 1) {
      const sample = [...afterGroup.styles.values()][0].sample;
      const baseSamples = [...group.styles.values()].map(v => v.sample);
      const deltas = baseSamples.map(s => styleDelta(s, sample).join(', ')).filter(Boolean);
      resolved.push(`- ${key}（${baseVariants} → 1）统一为 ${sample.fontSize}/${sample.fontWeight}/${sample.lineHeight}｜差异: ${deltas.slice(0, 3).join(' ;; ')}`);
    } else {
      remaining += 1;
      changed.push(`- ${key}：${baseVariants} → ${afterVariants || '缺失'} 种`);
    }
  }
  push(`## 已统一（P1 目标达成）`);
  push(resolved.length ? resolved.join('\n') : '- 无');
  push('');
  push(`## 仍未统一`);
  push(changed.length ? changed.join('\n') : '- 无');
  push('');

  const newGroups = [...afterGroups.keys()].filter(k => !baseGroups.has(k));
  push(`## 新出现的元素组`);
  push(newGroups.length ? newGroups.map(k => `- ${k}`).join('\n') : '- 无');
  push('');

  const baseIssues = collectIssues(baseline);
  const afterIssues = collectIssues(after);
  push(`## 几何异常`);
  push(`- baseline: ${fmtIssues(baseIssues)}`);
  push(`- after:    ${fmtIssues(afterIssues)}`);
  push('');
  push(`**结论**：仍未统一 ${remaining} 组，几何异常 ${afterIssues.size} 类。`);
  return lines.join('\n');
}

function collectIssues(dump) {
  const map = new Map();
  for (const node of dump.nodes) {
    for (const issue of node.issues || []) {
      const key = `${issue} :: ${node.role} :: ${node.sig || '(no-class)'}`;
      if (!map.has(key)) map.set(key, { issue, count: 0, text: node.text.slice(0, 30) });
      map.get(key).count += 1;
    }
  }
  return map;
}

function fmtIssues(map) {
  if (!map.size) return '无';
  return [...map.values()].map(v => `${v.issue}×${v.count}(${v.text})`).join(' | ');
}

function currentInconsistencies(dump) {
  const groups = roleIndex(dump);
  const lines = [];
  lines.push(`# 当前同角色样式不一致清单（P1 输入）`);
  lines.push('');
  lines.push(`- context: ${dump.context} @ ${dump.capturedAt}，${dump.nodes.length} 个元素`);
  lines.push(`- 计数：buttons=${dump.counts.buttons} fields=${dump.counts.fields} switches=${dump.counts.switches} tables=${dump.counts.tables}`);
  lines.push('');
  const inconsistent = [...groups.values()].filter(g => g.styles.size > 1).sort((a, b) => b.styles.size - a.styles.size);
  lines.push(`## 同角色不一致（${inconsistent.length} 组）`);
  for (const g of inconsistent) {
    lines.push('');
    lines.push(`### ${g.key}  —— ${g.seen} 个元素 / ${g.styles.size} 种样式`);
    for (const v of g.styles.values()) {
      const s = v.sample;
      lines.push(`- ${v.count}×  font=${s.fontSize}/${s.fontWeight}/${s.lineHeight} color=${s.color} radius=${s.borderRadius} h=${s.height}`);
    }
    if (g.texts.length) lines.push(`- 样例文本：${g.texts.map(t => `「${t}」`).join(' ')}`);
    if (g.issues.size) lines.push(`- 几何异常：${[...g.issues].join(', ')}`);
  }
  const issues = collectIssues(dump);
  lines.push('');
  lines.push(`## 几何异常（${issues.size} 类）`);
  lines.push(issues.size ? [...issues.values()].map(v => `- ${v.issue}×${v.count} ${v.key || ''} ${v.text ? `「${v.text}」` : ''}`).join('\n') : '- 无');
  return lines.join('\n');
}

const [baseFile, afterFile] = process.argv.slice(2).filter(a => !a.startsWith('--'));
const mdIndex = process.argv.indexOf('--md');
const mdOut = mdIndex > -1 ? process.argv[mdIndex + 1] : null;
if (!baseFile) {
  console.error('usage: node tests/dom-audit-diff.mjs <baseline.json> [after.json] [--md out.md]');
  process.exit(2);
}
const baseline = loadDump(baseFile);
const report = afterFile ? compare(baseline, loadDump(afterFile)) : currentInconsistencies(baseline);
if (mdOut) {
  fs.writeFileSync(mdOut, report + '\n', 'utf8');
  console.log(`written ${mdOut}`);
} else {
  console.log(report);
}
