"""Read frozen artifacts; build deterministic market projections. No network/inference.

Run from any directory: python scripts/build_market_map_data.py
Only data/processed/job_market_intelligence/market_map is written.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed'
OUT = DATA / 'job_market_intelligence/market_map'
VERSION = 'job-market-map-v1'
METRIC = 'distinct_recruitment_record_count'
INPUTS = {
    'groups': DATA / 'job_groups_v2/job_groups.jsonl',
    'members': DATA / 'job_groups_v2/job_group_members.jsonl',
    'group_summary': DATA / 'job_groups_v2/job_group_v2_summary.json',
    'identity_families': DATA / 'occupation_identity/occupation_candidate_families.jsonl',
    'selected': DATA / 'skill_inference_v2/selective_mini_1000/selected_inputs.jsonl',
    'results': DATA / 'skill_inference_v2/selective_mini_1000/results.jsonl',
    'inference_summary': DATA / 'skill_inference_v2/selective_mini_1000/final_summary.json',
    'normalization': DATA / 'skill_inference_v2/selective_mini_1000/normalization_v2_comparison.jsonl',
    'product_manifest': DATA / 'job_market_intelligence/product/manifest.json',
    'product_details': DATA / 'job_market_intelligence/product/occupation_details.json',
    'skill_catalog': DATA / 'job_market_intelligence/product/skill_catalog.json',
    'snapshots': DATA / 'recruitment_snapshots.sqlite',
}


def load(path):
    if path.suffix == '.sqlite':
        connection = sqlite3.connect(path)
        try:
            rows = connection.execute('''SELECT r.snapshot_id, r.record_id, r.education_requirement,
                r.recruitment_url, r.announcement_url
                FROM recruitment_records r JOIN dataset_snapshots s ON s.snapshot_id = r.snapshot_id
                ORDER BY s.imported_at DESC''').fetchall()
        finally:
            connection.close()
        output = defaultdict(dict)
        for snapshot_id, record_id, education, recruitment_url, announcement_url in rows:
            output[snapshot_id].setdefault(record_id, {
                'education_requirement': education,
                'recruitment_url': recruitment_url,
                'announcement_url': announcement_url,
            })
        return output
    with path.open(encoding='utf-8') as stream:
        if path.suffix == '.jsonl':
            return [json.loads(line) for line in stream if line.strip()]
        return json.load(stream)


def stable(prefix, value):
    # Existing Product V1 keys, deliberately no semantic matching/new taxonomy.
    return prefix + hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]


def identity(group):
    cid = group.get('canonical_occupation_id')
    title = group['representative_title'].strip()
    return (cid, group.get('canonical_occupation_title') or title, 'mapped') if cid else (
        stable('candidate-', title.casefold()), title, 'unmapped')


def references():
    return [{'path': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in INPUTS.values()]


def build(groups, members, selected, results, normalization, product_manifest, product_details, skill_catalog, snapshots, families, group_summary, inference_summary):
    by_id = {g['job_group_id']: g for g in groups}
    snapshot_records = snapshots.get(group_summary['snapshot_id'], {})
    assert len(by_id) == len(groups) == group_summary['job_group_count']
    selected_by_id = {g['job_group_id']: g for g in selected}
    result_by_id = {r['job_group_id']: r for r in results}
    assert len(selected_by_id) == len(selected) and len(result_by_id) == len(results)
    assert set(result_by_id) <= set(selected_by_id) <= set(by_id)
    member_groups = defaultdict(list)
    atomic_owners = {}
    for member in members:
        gid = member['job_group_id']
        assert gid in by_id
        aid = member['source_atomic_unit_id']
        assert aid not in atomic_owners, f'Duplicate atomic lineage: {aid}'
        atomic_owners[aid] = gid
        member_groups[gid].append(member)
    family_ids = {f['candidate_family_id'] for f in families}
    for gid, group in by_id.items():
        assert group['grouping_version'] == 'job-grouping-v2-occupation-safe'
        rows = member_groups[gid]
        assert rows and all(m['source_record_id'] for m in rows)
        assert {m['source_record_id'] for m in rows} == set(group['source_recruitment_record_ids'])
        assert {m['source_atomic_unit_id'] for m in rows} == set(group['source_atomic_unit_ids'])
        assert not group.get('occupation_identity_family_id') or group['occupation_identity_family_id'] in family_ids
        if gid in selected_by_id:
            prepared = selected_by_id[gid]['prepared_inference_input']
            assert prepared.get('canonical_occupation_id') == group.get('canonical_occupation_id')
            assert prepared['industry_domain_context'] == group['industry_domain_context']
            assert selected_by_id[gid]['representative_title'] == group['representative_title']

    norm = {(n['job_group_id'], n['raw_skill_name']): n['v2_normalized_skill'] for n in normalization}
    skill_meta = {s['display_name']: s for s in skill_catalog['skills']}
    versions = product_manifest['source_versions']
    assert versions['inference'] == inference_summary['inference_version']

    def record_ids(ids):
        return sorted({rid for gid in ids for rid in by_id[gid]['source_recruitment_record_ids']})

    def skills_for(ids):
        aggregate = {}
        for gid in sorted(ids):
            result = result_by_id.get(gid, {})
            if result.get('inference_status') != 'completed':
                continue
            for skill in result.get('hard_skills', []) + result.get('soft_skills', []):
                name = norm.get((gid, skill['raw_skill_name']))
                assert name, f'Missing frozen normalization: {gid}/{skill["raw_skill_name"]}'
                item = aggregate.setdefault(name, {'groups': set(), 'types': set(), 'scopes': set(), 'levels': set(), 'confidence': set(), 'models': set()})
                assert skill['source_type'] == 'llm_inference'
                assert skill['evidence_level'] in ('inferred_medium', 'inferred_low')
                item['groups'].add(gid)
                item['types'].add(skill['skill_type'])
                item['scopes'].add(skill['skill_scope'])
                item['levels'].add(skill['evidence_level'])
                item['confidence'].add(skill['confidence'])
                item['models'].add(result['model'])
        output = []
        for name, item in sorted(aggregate.items()):
            meta = skill_meta.get(name, {})
            gids = sorted(item['groups'])
            output.append({
                'skill_id': meta.get('skill_id', stable('skill-', name.casefold())), 'display_name': name,
                'skill_type': sorted(item['types']), 'scope': sorted(item['scopes']),
                'supporting_group_count': len(gids), 'recruitment_evidence_count': len(record_ids(gids)),
                'community_ids': meta.get('community_ids', []),
                'global_pmi_relationships': meta.get('global_pmi_relationships', []),
                'source_type': 'llm_inference', 'evidence_levels': sorted(item['levels']),
                'evidence_label': 'candidate skills inferred from role context',
                'inference_version': versions['inference'], 'confidence': sorted(item['confidence']),
                'prompt_version': inference_summary['prompt_version'], 'inference_timestamp': None,
                'models': sorted(item['models']),
                'evidence_references': {'job_group_ids': gids, 'source_recruitment_record_ids': record_ids(gids),
                    'source': INPUTS['results'].relative_to(ROOT).as_posix(), 'normalization_version': versions['normalization']},
            })
        return output

    def communities_for(skills):
        grouped = defaultdict(list)
        for skill in skills:
            for cid in skill['community_ids'] or ['unclustered']:
                grouped[cid].append(skill)
        return [{'community_id': cid, 'display_name': '未归入能力群的技能' if cid == 'unclustered' else f'能力群 {cid.split("-")[-1]}',
            'skill_ids': sorted(s['skill_id'] for s in items),
            'recruitment_evidence_count': len({rid for s in items for rid in s['evidence_references']['source_recruitment_record_ids']}),
            'semantics': 'frozen_global_cooccurrence_membership_not_prerequisite'} for cid, items in sorted(grouped.items())]

    def metrics(ids, skills):
        ids = sorted(ids)
        status = Counter(result_by_id[g]['inference_status'] for g in ids if g in result_by_id)
        selected_count = sum(g in selected_by_id for g in ids)
        completed = status['completed']
        available = completed > 0 and bool(skills)
        return {
            'job_group_count': len(ids), 'recruitment_evidence_count': len(record_ids(ids)),
            'atomic_unit_count': len({aid for gid in ids for aid in by_id[gid]['source_atomic_unit_ids']}),
            'skill_intelligence_available': available, 'completed_inference_group_count': completed,
            'total_inference_group_count': selected_count, 'skill_count': len(skills),
            'skill_intelligence': {'available': available, 'coverage_level': 'none' if not available else ('complete' if completed == len(ids) else 'partial'),
                'total_groups': len(ids), 'selected_groups': selected_count, 'result_groups': sum(status.values()),
                'completed_groups': completed, 'insufficient_context_groups': status['insufficient_context'],
                'failed_groups': sum(v for k, v in status.items() if k.startswith('failed')),
                'unselected_groups': len(ids) - selected_count, 'selected_without_result_groups': selected_count - sum(status.values()),
                'status_counts': dict(sorted(status.items())), 'skill_count': len(skills),
                'completed_fraction': completed / len(ids), 'eligible_groups': None,
                'eligibility_note': 'Eligibility of unselected groups is not inferred.',
                'inference_version': versions['inference']},
        }

    buckets = defaultdict(list)
    for group in groups:
        buckets[identity(group)[0]].append(group)
    occupations, details = [], {}
    for oid, bucket in sorted(buckets.items()):
        bucket.sort(key=lambda g: g['job_group_id'])
        _, label, identity_type = identity(bucket[0])
        gids = [g['job_group_id'] for g in bucket]
        skills = skills_for(gids)
        contexts = defaultdict(list)
        for group in bucket:
            contexts[group.get('industry_domain_context') or 'unknown'].append(group['job_group_id'])
        shard = hashlib.sha1(oid.encode()).hexdigest()[:2]
        # 16 shards keep requests small without thousands of tiny artifacts.
        detail_file = f'occupation_details/{shard[0]}.json'
        occupation = {'occupation_id': oid, 'display_name': label, 'identity_type': identity_type,
            'canonical_id': oid if identity_type == 'mapped' else None,
            **metrics(gids, skills), 'context_count': len(contexts), 'demand_metric': METRIC,
            'searchable_aliases': sorted({g['representative_title'] for g in bucket}),
            'identity_basis': 'frozen_canonical_id' if identity_type == 'mapped' else 'existing_product_exact_title_casefold',
            'identity_uncertainty': None if identity_type == 'mapped' else 'Candidate label; not a confirmed canonical occupation.',
            'detail_file': detail_file,
            'source_references': {'artifact': INPUTS['groups'].relative_to(ROOT).as_posix(), 'job_group_ids': gids,
                'frozen_family_ids': sorted({g['occupation_identity_family_id'] for g in bucket if g.get('occupation_identity_family_id')})},
        }
        context_rows = []
        for context, ids in sorted(contexts.items()):
            cskills = skills_for(ids)
            context_rows.append({'context_id': stable('context-', oid + '|' + context), 'context_name': context,
                'industry_domain_label': context.split(':', 1)[-1],
                'context_classification': 'taxonomy_domain' if context.startswith('l1:') else 'raw_source_context',
                **metrics(ids, cskills), 'demand_metric': METRIC,
                'source_job_group_ids': sorted(ids), 'source_recruitment_record_ids': record_ids(ids),
                'normalized_skills': [s['display_name'] for s in cskills], 'skills': cskills,
                'skill_communities': communities_for(cskills)})
        evidence = {}
        for gid in gids:
            for member in member_groups[gid]:
                rid = member['source_record_id']
                entry = evidence.setdefault(rid, {key: member.get(key) for key in ('source_record_id', 'raw_job_title', 'company_name', 'location', 'industry_category', 'recruitment_session', 'recruitment_batch', 'education_requirement')})
                source = snapshot_records.get(rid, {})
                entry['education_requirement'] = entry.get('education_requirement') or source.get('education_requirement')
                entry['recruitment_url'] = source.get('recruitment_url')
                entry['announcement_url'] = source.get('announcement_url')
                entry.setdefault('job_group_ids', set()).add(gid)
                entry.setdefault('atomic_unit_ids', set()).add(member['source_atomic_unit_id'])
                entry.setdefault('job_title_units', set()).add(member['job_title_unit'])
        for item in evidence.values():
            for key in ('job_group_ids', 'atomic_unit_ids', 'job_title_units'):
                item[key] = sorted(item[key])
        subset_ids = [g for g in gids if g in selected_by_id]
        detail = {'occupation': occupation, 'contexts': context_rows,
            'recruitment_evidence': [evidence[rid] for rid in sorted(evidence)],
            'skills': skills, 'hierarchy': 'occupation_context_skills', 'supported_subtype_relationships': [],
            'selective_subset': {**(metrics(subset_ids, skills) if subset_ids else {}),
                'context_count': len({by_id[g]['industry_domain_context'] for g in subset_ids})}}
        if oid in product_details['occupations']:
            old = product_details['occupations'][oid]
            assert {s['display_name'] for s in skills} == {s['display_name'] for s in old['skills']}, f'Skill mismatch: {oid}'
        occupations.append(occupation)
        details[oid] = detail
    occupations.sort(key=lambda o: (-o['recruitment_evidence_count'], o['occupation_id']))
    all_ids = sorted(by_id)
    summary = {'schema_version': VERSION, 'demand_metric': METRIC, 'total_job_groups': len(groups),
        'total_occupations': len(occupations), 'total_recruitment_evidence': len(record_ids(all_ids)),
        'total_atomic_units': len(atomic_owners), 'total_contexts': sum(o['context_count'] for o in occupations),
        'distinct_context_labels': len({g['industry_domain_context'] for g in groups}),
        'skill_intelligence_covered_occupations': sum(o['skill_intelligence_available'] for o in occupations),
        'market_only_occupations': sum(not o['skill_intelligence_available'] for o in occupations),
        'inference_status_counts': dict(sorted(Counter(r['inference_status'] for r in results).items())),
        'selected_inference_groups': len(selected), 'mapped_occupations': sum(o['identity_type'] == 'mapped' for o in occupations),
        'occupation_evidence_sum': sum(o['recruitment_evidence_count'] for o in occupations),
        'demand_note': 'Distinct source record IDs, not vacancies or Job Group count. A record can support several occupations; bubbles are not additive.',
        'hero_occupation_id': 'OCC0289'}
    return summary, occupations, details


def main():
    before = references()
    values = {key: load(path) for key, path in INPUTS.items()}
    summary, occupations, details = build(values['groups'], values['members'], values['selected'], values['results'],
        values['normalization'], values['product_manifest'], values['product_details'], values['skill_catalog'], values['snapshots'], values['identity_families'], values['group_summary'], values['inference_summary'])
    generated = datetime.now(timezone.utc).isoformat()
    summary.update(generated_at=generated, source_artifact_references=before)
    outputs = {'market_map_summary.json': summary, 'market_occupations.json': {'schema_version': VERSION, 'demand_metric': METRIC, 'occupations': occupations}}
    for shard in '0123456789abcdef':
        outputs[f'occupation_details/{shard}.json'] = {'occupations': {oid: d for oid, d in details.items() if d['occupation']['detail_file'] == f'occupation_details/{shard}.json'}}
    manifest = {'schema_version': VERSION, 'generated_at': generated, 'demand_metric': METRIC,
        'frozen_upstream_inputs': before, 'source_versions': values['product_manifest']['source_versions'],
        'snapshot_id': values['group_summary']['snapshot_id'], 'generated_files': sorted([*outputs, 'market_map_manifest.json']),
        'coverage_rule': 'available iff completed_groups > 0 and normalized skill_count > 0; complete iff all market groups completed; otherwise partial/none',
        'identity_rule': 'Reuse Product V1 canonical ID or exact representative-title casefold candidate key. No fuzzy merge, taxonomy changes or subtype inference.',
        'limitations': [summary['demand_note'], 'Raw context labels can describe company type; they are not newly inferred industry classes.',
            'Candidate occupation labels are uncertain; frozen family links remain provenance, not new cross-title merges.',
            'Only frozen completed selective-1000 results contribute skills; these are candidate skills inferred from role context.',
            'Global PMI and communities describe co-occurrence, not prerequisites.',
            'Per-run timestamps are unavailable in frozen result rows; inference_timestamp is null. Prompt version comes from frozen final_summary.json.'],
        'api_calls': 0, 'llm_calls': 0}
    outputs['market_map_manifest.json'] = manifest
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, content in outputs.items():
        path = OUT / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    assert before == references(), 'Frozen inputs changed during generation'
    print(json.dumps({k: v for k, v in summary.items() if k != 'source_artifact_references'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
