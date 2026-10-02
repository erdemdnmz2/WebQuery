import assert from 'node:assert/strict';
import writeXlsxFile from 'write-excel-file/node';

const rows = [
  { customer_id: 7, email: 'ada@example.test', active: true },
  { customer_id: 9, email: 'lin@example.test', active: false },
];
const columns = Object.keys(rows[0]);

const output = await writeXlsxFile([
  columns,
  ...rows.map((row) => columns.map((column) => row[column])),
]).toBuffer();

assert.ok(output.length > 100, 'The exported workbook must contain workbook data.');
assert.deepEqual(output.subarray(0, 4), Buffer.from('PK\x03\x04'));
assert.ok(output.includes(Buffer.from('xl/worksheets/sheet1.xml')));
