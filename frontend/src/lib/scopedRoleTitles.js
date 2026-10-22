// Display-only extraction: existing category links plus literal source evidence.
export function scopeRecordTitles(records, occupations) {
  const labelsByAtomicId = new Map();
  for (const occupation of occupations) {
    for (const id of occupation.sourceAtomicIds || []) {
      const labels = labelsByAtomicId.get(id) || new Set();
      if (occupation.label?.trim()) labels.add(occupation.label.trim());
      labelsByAtomicId.set(id, labels);
    }
  }
  return records.map(record => {
    const sourceTitles = [record.raw_job_title, ...(record.job_title_units || [])].filter(Boolean);
    const labels = [...new Set((record.atomic_unit_ids || []).flatMap(id => [...(labelsByAtomicId.get(id) || [])]))];
    const matched = labels.filter(label => sourceTitles.some(title => title.includes(label)));
    return { ...record, display_job_titles: matched };
  });
}
