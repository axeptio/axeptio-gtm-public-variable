// Guards compareTemplates, the decision the CI sync makes on every run.
//
// Ported from the sibling repo, where this test exists because the previous
// attempt at the problem shipped without one: the comparison was verified by hand
// against the live API, that verification read the file with the BOM stripped
// while the script sent it with the BOM intact, and every CI run republished the
// container for five days.
//
// So the cases below are the two failure modes that actually happened, plus proof
// that a genuine edit is still detected — because a comparison that returned
// "equal" unconditionally would also make the first cases pass.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { compareTemplates, stripBom } from '../lib/template.mjs';

const TPL_PATH = join(dirname(fileURLToPath(import.meta.url)), '..', 'template.tpl');
const withBom = readFileSync(TPL_PATH, 'utf8');
const noBom = stripBom(withBom);

test('template.tpl really does carry a BOM', () => {
  // If this ever stops being true the BOM cases below stop testing anything, so
  // assert the premise rather than letting them quietly become tautologies.
  assert.equal(withBom.charCodeAt(0), 0xfeff);
  assert.notEqual(noBom.charCodeAt(0), 0xfeff);
});

test('a BOM-only difference is not a change', () => {
  // The actual bug: the script sent the BOM, GTM stored it without, and one
  // invisible character made every run publish a new container version.
  const result = compareTemplates(withBom, noBom);
  assert.ok(result.equal, `expected equal, got: ${result.differences.join('; ')}`);
});

test('GTM-style escaping in a JSON block is not a change', () => {
  // GTM re-serialises the JSON blocks, escaping ' = & < > as \uXXXX. Unlike the
  // sibling, this template is stored unescaped — nothing here keeps it canonical,
  // since this repo has no validate-template.mjs — so the fixture escapes rather
  // than unescapes. Either direction exercises the same branch: the stored copy
  // GTM hands back will be the escaped one.
  const stored = noBom.replace("the widget's <code>compressUserCookie</code>",
    "the widget\\u0027s <code>compressUserCookie</code>");
  assert.notEqual(stored, noBom, 'fixture did not change anything — the anchor moved');

  const result = compareTemplates(noBom, stored);
  assert.ok(result.equal, `expected equal, got: ${result.differences.join('; ')}`);
});

test('reordered keys in a JSON block are not a change', () => {
  // Key order carries no meaning in JSON and GTM need not preserve it.
  const reordered = noBom.replace('"type": "MACRO",\n  "id": "cvt_temp_public_id",',
    '"id": "cvt_temp_public_id",\n  "type": "MACRO",');
  assert.notEqual(reordered, noBom, 'fixture did not change anything — the anchor moved');

  const result = compareTemplates(noBom, reordered);
  assert.ok(result.equal, `expected equal, got: ${result.differences.join('; ')}`);
});

test('a real edit to the sandboxed JS is a change, and is named', () => {
  const edited = noBom.replace("const copyFromDataLayer = require('copyFromDataLayer');",
    "const copyFromDataLayer = require('copyFromDataLayer'); // edited");
  assert.notEqual(edited, noBom, 'fixture did not change anything — the anchor moved');

  const result = compareTemplates(noBom, edited);
  assert.equal(result.equal, false);
  assert.match(result.differences.join('; '), /___SANDBOXED_JS_FOR_WEB_TEMPLATE___/);
});

test('a real edit inside a JSON block is a change, and is named', () => {
  const edited = noBom.replace('"displayName": "Axeptio Consent State",',
    '"displayName": "Axeptio Consent State 2",');
  assert.notEqual(edited, noBom, 'fixture did not change anything — the anchor moved');

  const result = compareTemplates(noBom, edited);
  assert.equal(result.equal, false);
  assert.match(result.differences.join('; '), /___INFO___/);
});

test('a change to the signal selector is a change, and is named', () => {
  // The parameters block is the one a per-vendor field or a new signal touches,
  // and it is JSON — so it goes through canonicalJson rather than the text path.
  // A real content change there must still be caught.
  const edited = noBom.replace('"defaultValue": "axeptio_authorized_vendors",',
    '"defaultValue": "consent_mode",');
  assert.notEqual(edited, noBom, 'fixture did not change anything — the anchor moved');

  const result = compareTemplates(noBom, edited);
  assert.equal(result.equal, false);
  assert.match(result.differences.join('; '), /___TEMPLATE_PARAMETERS___/);
});

test('a missing templateData is reported, not treated as equal', () => {
  // findOrCreateTemplate reads the LIST endpoint, which is not contractually
  // obliged to include templateData. Undefined must never look like "no change".
  for (const absent of [undefined, null, '']) {
    const result = compareTemplates(noBom, absent);
    assert.equal(result.equal, false, `expected a difference for ${JSON.stringify(absent)}`);
    assert.ok(result.differences.length > 0);
  }
});
