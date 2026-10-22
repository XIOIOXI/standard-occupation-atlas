import test from 'node:test';
import assert from 'node:assert/strict';
import { scopeRecordTitles } from '../src/lib/scopedRoleTitles.js';

test('extracts only source-backed titles linked to the current category and atomic unit', () => {
  const raw = '光学设计集成调试软件开发固件开发测校开发技术支持光学测试 算法开发光机结构设计测校软件开发应付会计';
  const records = [{ raw_job_title:raw, job_title_units:[raw], atomic_unit_ids:['a'] }];
  const result = scopeRecordTitles(records, [
    { label:'测校开发', sourceAtomicIds:['a'] },
    { label:'测试开发工程师', sourceAtomicIds:['a'] },
    { label:'应付会计', sourceAtomicIds:['other'] },
  ]);
  assert.deepEqual(result[0].display_job_titles, ['测校开发']);
  assert.equal(result[0].raw_job_title, raw);
  assert.equal(records[0].display_job_titles, undefined);
  assert.deepEqual(scopeRecordTitles(records, [{ label:'固件开发', sourceAtomicIds:['a'] }])[0].display_job_titles, ['固件开发']);
});

test('does not invent a source title when a category label has no literal evidence', () => {
  assert.deepEqual(scopeRecordTitles([{ raw_job_title:'综合岗位', atomic_unit_ids:['a'] }], [{ label:'软件开发', sourceAtomicIds:['a'] }])[0].display_job_titles, []);
});
