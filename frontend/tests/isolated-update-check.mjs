import fs from 'node:fs';
import assert from 'node:assert/strict';
import { overlayUpdateBatches } from '../src/lib/updateProjection.js';
import { updateAtomicUnits } from '../src/lib/snoEvidence.js';

const root = process.argv[2];
const batches = JSON.parse(fs.readFileSync(`${root}/display/update_batches.json`, 'utf8'));
const daily = JSON.parse(fs.readFileSync(`${root}/display/daily_jobs_v1.json`, 'utf8'));
const merged = overlayUpdateBatches({ category_bubbles: {}, level2_direct_buckets: {}, unplaced: [] }, batches);
const mapped = [...Object.values(merged.category_bubbles), ...Object.values(merged.level2_direct_buckets)].flatMap(bucket => bucket.occupations);
const sources = updateAtomicUnits(batches);
const items = batches.batches.flatMap(batch => batch.items);
assert.equal(mapped.length, items.filter(item => item.result_status === 'classified').length);
assert.equal(daily.items.length, items.filter(item => ['classified', 'pending'].includes(item.result_status)).length);
assert.equal(Object.keys(sources).length, items.length);
assert.equal(new Set(daily.items.map(item => item.daily_item_id)).size, daily.items.length);
console.log(JSON.stringify({ mapped: mapped.length, daily: daily.items.length, source_units: Object.keys(sources).length }));
