import test from 'node:test';
import assert from 'node:assert/strict';
import { buildDisplayOccupationNodes, countDisplayOccupationNodes, findDisplayGroup } from '../src/lib/displayOccupationGroups.js';

const occupations = [
  { node_id: 'a', label: '管理培训生', recruitment_evidence_count: 8 },
  { node_id: 'b', label: '管培生', recruitment_evidence_count: 6 },
  { node_id: 'c', label: '柜员', recruitment_evidence_count: 12 },
  { node_id: 'd', label: '营销岗', recruitment_evidence_count: 4 },
];
const groups = [{
  display_group_id: 'group-trainee', label: '管理培训方向', member_occupation_ids: ['a', 'b'], member_count: 2,
  distinct_recruitment_record_count: 11,
}];

test('the bubble field contains only display directions, never raw one-child occupations', () => {
  const result = buildDisplayOccupationNodes({ occupations, displayGroups: groups, primary: [occupations[0], occupations[2]], bubbledLongTail: [] });
  assert.deepEqual(result.bubbleNodes.map(item => item.node_id), ['group:group-trainee']);
  assert.deepEqual(result.indexedNodes.map(item => item.node_id).sort(), ['c', 'd']);
  assert.equal(result.bubbleNodes.find(item => item.display_kind === 'group').recruitment_evidence_count, 11);
  assert.equal(result.bubbleNodes.find(item => item.display_kind === 'group').child_count, 2);
});

test('a parent metric counts display directions instead of recruitment records', () => {
  assert.equal(countDisplayOccupationNodes({ occupations, displayGroups: groups }), 1);
});

test('a display group stays available even when none of its leaves were previously primary', () => {
  const result = buildDisplayOccupationNodes({ occupations, displayGroups: groups, primary: [occupations[2]], bubbledLongTail: [] });
  assert.deepEqual(result.bubbleNodes.map(item => item.node_id), ['group:group-trainee']);
  assert.deepEqual(result.indexedNodes.map(item => item.node_id).sort(), ['c', 'd']);
  assert.equal(findDisplayGroup(groups, 'b')?.display_group_id, 'group-trainee');
});
