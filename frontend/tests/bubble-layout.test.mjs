import test from 'node:test';
import assert from 'node:assert/strict';
import { bubbleLayout } from '../src/lib/bubbleLayout.js';

const items = Array.from({ length: 80 }, (_, i) => ({ id: `occupation-${i}`, value: i + 1, available: i % 2 === 0 }));

test('bubble area is proportional to demand, independently of skill availability', () => {
  const { nodes } = bubbleLayout(items);
  const ratio = nodes[0].r ** 2 / nodes[0].value;
  for (const node of nodes) assert.ok(Math.abs(node.r ** 2 / node.value - ratio) < 1e-9);
  const alternate = bubbleLayout(items.map(item => ({ ...item, available: !item.available })));
  assert.deepEqual(alternate.nodes.map(n => n.r), nodes.map(n => n.r));
});

test('all occupations stay distinct, finite, non-overlapping and inside fit bounds', () => {
  const { nodes, extent } = bubbleLayout(items);
  assert.equal(new Set(nodes.map(n => n.id)).size, items.length);
  for (const [i, node] of nodes.entries()) {
    assert.ok(Number.isFinite(node.x) && Number.isFinite(node.y));
    assert.ok(Math.abs(node.x) + node.r <= extent && Math.abs(node.y) + node.r <= extent);
    for (const other of nodes.slice(i + 1)) assert.ok(Math.hypot(node.x - other.x, node.y - other.y) >= node.r + other.r);
  }
});

test('layout is stable under input reordering and does not modify market objects', () => {
  const before = structuredClone(items);
  assert.deepEqual(bubbleLayout(items), bubbleLayout([...items].reverse()));
  assert.deepEqual(items, before);
});
