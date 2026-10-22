import test from 'node:test';
import assert from 'node:assert/strict';
import { overlayUpdateBatches } from '../src/lib/updateProjection.js';
import { aggregateSnoEvidence, updateAtomicUnits } from '../src/lib/snoEvidence.js';
import { getLocationDistribution } from '../src/lib/locationDistribution.js';

const base = {
  category_bubbles: { L1: { category: { category_id: 'L1', level_1: '研发', level_2: '开发', level_3: '前端', target_level: 'level_3' }, occupations: [{ standard_occupation_id: 'base', label: '既有岗位', source_atomic_unit_ids: ['base-atomic'], source_record_ids: ['base-record'], status: 'mapped' }] } },
  level2_direct_buckets: {}, unplaced: [],
};
const updates = { batches: [{ batch_id: 'UPD-1', status: 'completed', items: [
  { atomic_key: 'new-1', source_record_id: 'record-1', title_unit: '新增前端工程师', result_status: 'classified', category_id: 'L1', level_1: '研发', level_2: '开发', level_3: '前端', company_name: '示例公司' },
  { atomic_key: 'review-1', source_record_id: 'record-2', title_unit: '待确认岗位', result_status: 'pending' },
  { atomic_key: 'failed-1', source_record_id: 'record-3', title_unit: '失败岗位', result_status: 'failed' },
] }, { batch_id: 'UPD-2', status: 'completed', items: [
  { atomic_key: 'new-1', source_record_id: 'record-1', title_unit: '新增前端工程师', result_status: 'classified', category_id: 'L1', level_1: '研发', level_2: '开发', level_3: '前端' },
] }] };

test('overlays classified updates into their SNO node without mutating or double-counting the base projection', () => {
  const merged = overlayUpdateBatches(base, updates);
  assert.equal(base.category_bubbles.L1.occupations.length, 1);
  assert.equal(merged.category_bubbles.L1.occupations.length, 2);
  assert.equal(merged.category_bubbles.L1.occupations[1].source_atomic_unit_ids[0], 'UPDATE:UPD-1:new-1');
});

test('keeps pending and failed updates in their existing review and abnormal display paths', () => {
  const merged = overlayUpdateBatches(base, updates);
  assert.equal(merged.unplaced.length, 2);
  assert.equal(merged.unplaced[0].status, 'review');
  assert.match(merged.unplaced[1].standard_occupation_id, /^ABNORMAL:/);
});

test('builds source detail and location evidence for a mapped update without changing base evidence', () => {
  const units = updateAtomicUnits(updates);
  const atomicId = 'UPDATE:UPD-1:new-1';
  const records = aggregateSnoEvidence(units, [atomicId], ['UPDATE_RECORD:UPD-1:record-1']);
  assert.equal(records.length, 1);
  assert.equal(records[0].company_name, '示例公司');
  assert.deepEqual(records[0].job_title_units, ['新增前端工程师']);
  const distribution = getLocationDistribution([{ ...records[0], location: '上海' }]);
  assert.equal(distribution.identifiableRecords, 1);
  assert.equal(distribution.provinces.find(item => item.name === '上海').value, 1);
});
