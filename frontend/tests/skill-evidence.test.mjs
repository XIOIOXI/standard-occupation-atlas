import test from 'node:test';
import assert from 'node:assert/strict';
import { matchingSkillEvidence, recruitmentRecordIds } from '../src/lib/skillEvidence.js';

test('matches record IDs supplied as a Product Data array', () => {
  const records = [{ source_record_id: 'record-a' }, { source_record_id: 'record-b' }, { source_record_id: 'record-c' }];
  const matched = matchingSkillEvidence(records, { source_recruitment_record_ids: ['record-a', 'record-c'] });
  assert.deepEqual(matched.map(record => record.source_record_id), ['record-a', 'record-c']);
});

test('keeps compatibility with comma- or whitespace-separated legacy strings', () => {
  assert.deepEqual(recruitmentRecordIds('record-a, record-b record-c'), ['record-a', 'record-b', 'record-c']);
});
