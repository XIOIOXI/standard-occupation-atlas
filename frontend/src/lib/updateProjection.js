// Overlay persisted update batches onto the immutable SNO display projection.
// The base projection is never mutated: this keeps existing counts and lineage
// stable while allowing a later batch to be loaded into the same directory.
function cloneBuckets(buckets = {}) {
  return Object.fromEntries(Object.entries(buckets).map(([id, bucket]) => [id, { ...bucket, occupations: [...(bucket.occupations || [])] }]));
}

function updateOccupation(batch, item) {
  const prefix = `UPDATE:${batch.batch_id}:`;
  const failed = item.result_status === 'failed';
  const sources = item.source_records?.length ? item.source_records : [{ source_record_id: item.source_record_id }];
  const atomicIds = sources.map(source => sources.length > 1
    ? `${prefix}${item.atomic_key}:${source.source_record_id}` : `${prefix}${item.atomic_key}`);
  return {
    standard_occupation_id: failed ? `ABNORMAL:${prefix}${item.atomic_key}` : `${prefix}${item.atomic_key}`,
    label: item.title_unit,
    source_atomic_unit_ids: atomicIds,
    source_record_ids: sources.map(source => `UPDATE_RECORD:${batch.batch_id}:${source.source_record_id}`),
    source_record_role_ids: [],
    original_group_ids: [],
    status: failed ? 'abnormal' : item.result_status === 'classified' ? 'mapped' : 'review',
    reason: item.reason || (failed ? 'update_mapping_failure' : 'update_mapping_review_required'),
    candidate_category_ids: [],
    item_kind: 'update_atomic_role',
    update_batch_id: batch.batch_id,
  };
}

function categoryFor(item) {
  return {
    category_id: item.category_id,
    level_1: item.level_1,
    level_2: item.level_2,
    level_3: item.level_3 || null,
    target_level: item.level_3 ? 'level_3' : 'level_2',
  };
}

export function overlayUpdateBatches(projection, updateCatalogue = {}) {
  const categoryBubbles = cloneBuckets(projection.category_bubbles);
  const level2Buckets = cloneBuckets(projection.level2_direct_buckets);
  const unplaced = [...(projection.unplaced || [])];
  const seenAtomicKeys = new Set();

  for (const batch of updateCatalogue.batches || []) {
    if (!['completed', 'completed_with_failures'].includes(batch.status)) continue;
    for (const item of batch.items || []) {
      if (!item.atomic_key || seenAtomicKeys.has(item.atomic_key)) continue;
      seenAtomicKeys.add(item.atomic_key);
      const occupation = updateOccupation(batch, item);
      if (item.result_status !== 'classified' || !item.category_id || !item.level_1 || !item.level_2) {
        unplaced.push(occupation);
        continue;
      }
      const category = categoryFor(item);
      if (category.target_level === 'level_2') {
        const bucketId = `direct:${category.category_id}`;
        const bucket = level2Buckets[bucketId] || { bucket_id: bucketId, category, occupations: [] };
        bucket.occupations.push(occupation);
        level2Buckets[bucketId] = bucket;
      } else {
        const bucket = categoryBubbles[category.category_id] || { category, occupations: [] };
        bucket.occupations.push(occupation);
        categoryBubbles[category.category_id] = bucket;
      }
    }
  }
  return { ...projection, category_bubbles: categoryBubbles, level2_direct_buckets: level2Buckets, unplaced };
}
