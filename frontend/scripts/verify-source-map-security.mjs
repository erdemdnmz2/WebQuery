// SPEC-0034 AC-02. Constructor checks only: do not flatten hostile maps.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { SourceMapConsumer } = require('source-map-js');
const flat = {
  version: 3,
  sources: ['input.js'],
  sourcesContent: ['const answer = 42;'],
  names: [],
  mappings: 'AAAA',
};
const indexed = (line, map = flat) => ({
  version: 3,
  sections: [{ offset: { line, column: 0 }, map }],
});

assert.throws(
  () => new SourceMapConsumer(indexed(10_000_001)),
  /Section offset line must not exceed/,
  'Oversized indexed source-map offsets must be rejected.',
);
assert.throws(
  () => new SourceMapConsumer(indexed(5_000_000, indexed(6_000_000))),
  /including offsets of nested sections/,
  'Nested indexed offsets must be bounded cumulatively.',
);
assert.deepEqual(
  new SourceMapConsumer(flat).originalPositionFor({ line: 1, column: 0 }),
  { source: 'input.js', line: 1, column: 0, name: null },
);
console.log('PASS: oversized/nested source-map offsets rejected; valid map preserved.');
