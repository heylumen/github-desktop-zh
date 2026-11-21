// Usage: node scripts/verify_translation.mjs ORIGINAL TRANSLATED ACORN_MODULE
// Acorn 8.15.0 can be installed under .work with npm; see docs/3.6.10.md.
//
// Security stance (default deny):
// A string literal / template text may change ONLY when its ancestor chain
// ends in a reviewed display sink (UI property or reviewed display call).
// Variable declarations, assignments, returns, comparisons, object keys,
// enums, imports and all other contexts are protected.
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

// Only these UI properties may receive translated text.
const DISPLAY_PROPS = new Set([
  'label', 'title', 'placeholder', 'aria-label', 'ariaLabel', 'subtitle',
  'description', 'confirmationTitle', 'dialogTitle', 'tooltip', 'header',
  'heading', 'text', 'message', 'name', 'children', 'defaultMessage',
  'caption', 'alt', 'confirmButtonText', 'cancelButtonText',
]);

// Reviewed display / logging callees in the pinned bundle.
const DISPLAY_CALLS = new Set([
  'createElement', 'renderMenuBackedAction', 'renderFeatureModelPicker',
  'renderButtonGroupButton', 'p_',
]);

// Wrappers that do not change the meaning of an eventual display sink.
const TRANSPARENT = new Set([
  'ConditionalExpression', 'LogicalExpression', 'ParenthesizedExpression',
  'SequenceExpression', 'ArrayExpression', 'TemplateLiteral',
]);

function propertyName(node) {
  if (!node || node.type !== 'Property') return null;
  if (node.key.type === 'Identifier') return node.key.name;
  if (node.key.type === 'Literal') return String(node.key.value);
  return null;
}

function callName(node) {
  if (!node || node.type !== 'CallExpression') return null;
  if (node.callee.type === 'Identifier') return node.callee.name;
  if (node.callee.type === 'MemberExpression'
      && node.callee.property.type === 'Identifier') return node.callee.property.name;
  return null;
}

function isAllowedTextChange(ancestors) {
  if (!ancestors.length) return false;
  let elementIndex = null;
  for (let index = ancestors.length - 1; index >= 0; index -= 1) {
    const [parent, key] = ancestors[index];
    if (parent.type === 'Property' && key === 'value') {
      return DISPLAY_PROPS.has(propertyName(parent) || '');
    }
    if (parent.type === 'CallExpression' && key === 'arguments') {
      const name = callName(parent);
      if (!name) return false;
      if (name === 'createElement' && elementIndex === 0) return false;
      if (DISPLAY_CALLS.has(name)) return true;
      if (parent.callee.type === 'MemberExpression'
          && parent.callee.object.type === 'Identifier'
          && parent.callee.object.name === 'log'
          && ['error', 'warn', 'info'].includes(name)) return true;
      return false;
    }
    if (Array.isArray(parent) && typeof key === 'number') {
      elementIndex = key;
      continue;
    }
    if (TRANSPARENT.has(parent.type)) continue;
    return false;
  }
  return false;
}

function compare(a, b, parent, key, ancestors) {
  if (a === null || typeof a !== 'object') {
    assert.equal(b, a, `Non-text value changed: ${key}`);
    return;
  }
  assert.equal(typeof b, 'object');
  if (Array.isArray(a)) {
    assert.ok(Array.isArray(b));
    assert.equal(b.length, a.length, 'AST array length changed');
    a.forEach((value, index) => compare(
      value, b[index], a, index, ancestors.concat([[a, index]])));
    return;
  }
  if (a.type === 'Literal' && typeof a.value === 'string') {
    assert.equal(b.type, a.type);
    assert.equal(typeof b.value, 'string');
    if (b.value !== a.value) {
      assert.ok(isAllowedTextChange(ancestors),
        `String literal changed outside reviewed display context: ${a.value}`);
      assert.match(b.value, /[\u3400-\u9fff]/u,
        `Replacement is not Chinese text: ${a.value}`);
      changedLiterals++;
    }
  }
  if (a.type === 'TemplateElement' && a.value.raw !== b.value.raw) {
    assert.ok(isAllowedTextChange(ancestors),
      `Template text changed outside reviewed display context: ${a.value.raw}`);
    assert.ok(/[\u3400-\u9fff]/u.test(b.value.raw)
      || /^[\s\p{P}\p{S}]*$/u.test(b.value.raw),
      `Template replacement is not Chinese text: ${b.value.raw}`);
    changedTemplateParts++;
  }
  const keys = Object.keys(a).filter(k => !['start', 'end', 'raw'].includes(k));
  assert.deepEqual(Object.keys(b).filter(k => !['start', 'end', 'raw'].includes(k)), keys);
  for (const name of keys) {
    if (a.type === 'Literal' && typeof a.value === 'string' && name === 'value') continue;
    if (a.type === 'TemplateElement' && name === 'value') continue;
    compare(a[name], b[name], a, name, ancestors.concat([[a, name]]));
  }
}

compare(before, after, null, null, []);
for (const marker of ['3.6.10', 'ucrt64', 'credential-desktop',
  'startBackgroundFetching', 'stopBackgroundFetching']) {
  assert.equal(translated.split(marker).length, original.split(marker).length,
    `Critical marker changed: ${marker}`);
}
assert.ok(changedLiterals + changedTemplateParts > 0, 'No translations applied');
console.log(JSON.stringify({
  file: path.basename(translatedPath), changedLiterals, changedTemplateParts,
  structureUnchanged: true, protectedConstantsUnchanged: true,
  displayContextEnforced: true,
}));
