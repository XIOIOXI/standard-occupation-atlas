import { useEffect, useState } from 'react';

const SNO_DATA = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/';
let evidencePromise;

export function updateAtomicUnits(catalogue) {
  const units = {};
  for (const batch of catalogue.batches || []) {
    if (!['completed', 'completed_with_failures'].includes(batch.status)) continue;
    for (const item of batch.items || []) {
      const sources = item.source_records?.length ? item.source_records : [item];
      sources.forEach(source => {
        const atomicId = sources.length > 1 ? `UPDATE:${batch.batch_id}:${item.atomic_key}:${source.source_record_id}` : `UPDATE:${batch.batch_id}:${item.atomic_key}`;
        units[atomicId] = {
          source_record_id: `UPDATE_RECORD:${batch.batch_id}:${source.source_record_id}`,
          raw_job_title: source.raw_job_title || item.raw_job_title,
          company_name: source.company_name || item.company_name,
          company_type: source.company_type || item.company_type,
          location: source.location || item.location,
          recruitment_url: source.recruitment_url || item.recruitment_url,
          announcement_url: source.announcement_url || item.announcement_url,
          job_title_unit: item.title_unit,
          job_group_id: `UPDATE:${batch.batch_id}`,
        };
      });
    }
  }
  return units;
}

export function readSnoEvidence() {
  if (!evidencePromise) evidencePromise = Promise.all([
    fetch(`${SNO_DATA}sno_atomic_evidence_index_v1.json`).then(response => response.ok ? response.json() : Promise.reject(new Error(`原子岗位来源索引读取失败：${response.status}`))),
    fetch(`${SNO_DATA}update_batches.json`).then(response => response.ok ? response.json() : { batches: [] }),
  ]).then(([index, updates]) => ({ ...index, atomic_units: { ...(index.atomic_units || {}), ...updateAtomicUnits(updates) } }));
  return evidencePromise;
}

export function aggregateSnoEvidence(atomicUnits, atomicIds, allowedSourceIds = []) {
  const sourceIds = new Set(allowedSourceIds);
  const records = new Map();
  atomicIds.forEach(atomicId => {
    const item = atomicUnits[atomicId];
    if (!item || (sourceIds.size && !sourceIds.has(item.source_record_id))) return;
    const record = records.get(item.source_record_id) || {
      source_record_id: item.source_record_id, raw_job_title: item.raw_job_title,
      company_name: item.company_name, location: item.location, company_type: item.company_type,
      recruitment_url: item.recruitment_url, announcement_url: item.announcement_url,
      job_title_units: [], atomic_unit_ids: [], job_group_ids: [],
    };
    record.job_title_units.push(item.job_title_unit);
    record.atomic_unit_ids.push(atomicId);
    record.job_group_ids.push(item.job_group_id);
    records.set(item.source_record_id, record);
  });
  return [...records.values()].map(record => ({
    ...record,
    job_title_units: [...new Set(record.job_title_units)],
    atomic_unit_ids: [...new Set(record.atomic_unit_ids)],
    job_group_ids: [...new Set(record.job_group_ids)],
  }));
}

export function useSnoEvidence(key, atomicIds, sourceRecordIds = []) {
  const [state, setState] = useState({ key: null, records: [], loading: true, error: null });
  const atomicKey = atomicIds.join('|');
  const sourceKey = sourceRecordIds.join('|');
  useEffect(() => {
    let active = true;
    readSnoEvidence()
      .then(index => active && setState({ key, records: aggregateSnoEvidence(index.atomic_units || {}, atomicIds, sourceRecordIds), loading: false, error: null }))
      .catch(error => active && setState({ key, records: [], loading: false, error }));
    return () => { active = false; };
  }, [key, atomicKey, sourceKey]);
  return state.key === key ? state : { key, records: [], loading: true, error: null };
}
