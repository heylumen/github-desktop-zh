// Usage: node scripts/verify_translation.mjs ORIGINAL TRANSLATED ACORN_MODULE
// Acorn 8.15.0 can be installed under .work with npm; see docs/3.6.10.md.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const [originalPath, translatedPath, acornPath] = process.argv.slice(2);
if (!originalPath || !translatedPath || !acornPath) {
  throw new Error('Expected ORIGINAL TRANSLATED ACORN_MODULE');
}
const {parse, version} = await import(pathToFileURL(path.resolve(acornPath)).href);
assert.equal(version, '8.15.0', 'Use Acorn 8.15.0 for reproducible verification');
const original = fs.readFileSync(originalPath, 'utf8');
const translated = fs.readFileSync(translatedPath, 'utf8');
const before = parse(original, {ecmaVersion: 'latest'});
const after = parse(translated, {ecmaVersion: 'latest'});
let changedLiterals = 0;
let changedTemplateParts = 0;

function isProtected(node, parent, key) {
  if (!parent) return false;
  if (parent.type === 'Property' && key === 'key') return true;
  if (parent.type === 'MemberExpression' && key === 'property') return true;
  if (parent.type === 'SwitchCase' && key === 'test') return true;
  if (parent.type === 'BinaryExpression' && parent.operator !== '+') return true;
  if (parent.type === 'ImportExpression') return true;
  if (parent.type === 'CallExpression') {
    const name = parent.callee.type === 'MemberExpression'
      ? parent.callee.property.name : parent.callee.name;
    // These display/logging call sites were reviewed against the pinned 3.6.10 bundle.
    const displayCalls = new Set(['createElement', 'renderMenuBackedAction',
      'renderFeatureModelPicker', 'renderButtonGroupButton', 'p_']);
    const logMessage = parent.callee.type === 'MemberExpression'
      && parent.callee.object.name === 'log' && name === 'error';
    if (!displayCalls.has(name) && !logMessage) return true;
    if (name === 'createElement' && parent.arguments[0] === node) return true;
  }
  // TypeScript enum reverse mapping: e[e.Notifications = 5] = "Notifications".
  if (parent.type === 'AssignmentExpression' && key === 'right'
      && parent.left.type === 'MemberExpression'
      && parent.left.property.type === 'AssignmentExpression') return true;
  return false;
}

function compare(a, b, parent, key) {
  if (a === null || typeof a !== 'object') {
    assert.equal(b, a, `Non-text value changed: ${key}`);
    return;
  }
  assert.equal(typeof b, 'object');
  if (Array.isArray(a)) {
    assert.ok(Array.isArray(b));
    assert.equal(b.length, a.length, 'AST array length changed');
    a.forEach((v, i) => compare(v, b[i], parent, key));
    return;
  }
  if (a.type === 'Literal' && typeof a.value === 'string') {
    assert.equal(b.type, a.type);
    assert.equal(typeof b.value, 'string');
    if (b.value !== a.value) {
      assert.ok(!isProtected(a, parent, key), `Protocol/key/enum literal changed: ${a.value}`);
      assert.match(b.value, /[\u3400-\u9fff]/u, `Replacement is not Chinese text: ${a.value}`);
      changedLiterals++;
    }
  }
  if (a.type === 'TemplateElement' && a.value.raw !== b.value.raw) {
    assert.ok(/[\u3400-\u9fff]/u.test(b.value.raw) || /^[\s\p{P}\p{S}]*$/u.test(b.value.raw),
      `Template replacement is not Chinese text: ${b.value.raw}`);
    changedTemplateParts++;
  }
  const keys = Object.keys(a).filter(k => !['start', 'end', 'raw'].includes(k));
  assert.deepEqual(Object.keys(b).filter(k => !['start', 'end', 'raw'].includes(k)), keys);
  for (const k of keys) {
    if (a.type === 'Literal' && typeof a.value === 'string' && k === 'value') continue;
    if (a.type === 'TemplateElement' && k === 'value') continue;
    compare(a[k], b[k], a, k);
  }
}

compare(before, after, null, null);
for (const marker of ['3.6.10', 'ucrt64', 'credential-desktop', 'startBackgroundFetching', 'stopBackgroundFetching']) {
  assert.equal(translated.split(marker).length, original.split(marker).length, `Critical marker changed: ${marker}`);
}
assert.ok(changedLiterals + changedTemplateParts > 0, 'No translations applied');
console.log(JSON.stringify({file: path.basename(translatedPath), changedLiterals, changedTemplateParts, structureUnchanged: true, protectedConstantsUnchanged: true}));
