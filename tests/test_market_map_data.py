"""Acceptance checks against frozen source artifacts, without any API access."""
import hashlib
import importlib.util
import json
import random
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('market_builder', ROOT / 'scripts/build_market_map_data.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class MarketMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {key: builder.load(path) for key, path in builder.INPUTS.items()}
        cls.groups = {g['job_group_id']: g for g in cls.inputs['groups']}
        cls.results = {r['job_group_id']: r for r in cls.inputs['results']}
        cls.summary = builder.load(builder.OUT / 'market_map_summary.json')
        cls.catalog = builder.load(builder.OUT / 'market_occupations.json')['occupations']
        cls.details = {}
        for file in sorted((builder.OUT / 'occupation_details').glob('*.json')):
            cls.details.update(builder.load(file)['occupations'])

    def test_all_groups_accounted_for_once(self):
        ids = [gid for o in self.catalog for gid in o['source_references']['job_group_ids']]
        self.assertEqual(len(ids), 15622)
        self.assertEqual(set(ids), set(self.groups))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.summary['total_occupations'], len(self.catalog))

    def test_distinct_lineage_at_every_level(self):
        self.assertEqual(self.summary['demand_metric'], 'distinct_recruitment_record_count')
        all_records = {m['source_record_id'] for m in self.inputs['members']}
        self.assertEqual(self.summary['total_recruitment_evidence'], len(all_records))
        for oid, detail in self.details.items():
            occ = detail['occupation']
            ids = occ['source_references']['job_group_ids']
            records = {r for gid in ids for r in self.groups[gid]['source_recruitment_record_ids']}
            atomic = {r for gid in ids for r in self.groups[gid]['source_atomic_unit_ids']}
            self.assertEqual(occ['recruitment_evidence_count'], len(records), oid)
            self.assertEqual(occ['atomic_unit_count'], len(atomic), oid)
            self.assertEqual({r['source_record_id'] for r in detail['recruitment_evidence']}, records)
            for context in detail['contexts']:
                ids = context['source_job_group_ids']
                records = {r for gid in ids for r in self.groups[gid]['source_recruitment_record_ids']}
                self.assertEqual(context['recruitment_evidence_count'], len(records))
                self.assertEqual(set(context['source_recruitment_record_ids']), records)
                by_skill = {s['skill_id']: s for s in context['skills']}
                covered = set()
                for community in context['skill_communities']:
                    covered.update(community['skill_ids'])
                    support = {rid for sid in community['skill_ids'] for rid in by_skill[sid]['evidence_references']['source_recruitment_record_ids']}
                    self.assertEqual(community['recruitment_evidence_count'], len(support))
                self.assertEqual(covered, set(by_skill))

    def test_coverage_and_skills_come_only_from_completed_results(self):
        selected_ids = {g['job_group_id'] for g in self.inputs['selected']}
        normalized = {(n['job_group_id'], n['raw_skill_name']): n['v2_normalized_skill'] for n in self.inputs['normalization']}
        completed_total = 0
        for detail in self.details.values():
            completed_total += detail['occupation']['completed_inference_group_count']
            levels = [(detail['occupation'], detail['occupation']['source_references']['job_group_ids'], detail['skills'])]
            levels += [(c, c['source_job_group_ids'], c['skills']) for c in detail['contexts']]
            for item, gids, skills in levels:
                status = Counter(self.results[g]['inference_status'] for g in gids if g in self.results)
                self.assertEqual(item['skill_intelligence']['status_counts'], dict(status))
                self.assertEqual(item['total_inference_group_count'], len(set(gids) & selected_ids))
                names = {normalized[g, s['raw_skill_name']] for g in gids if self.results.get(g, {}).get('inference_status') == 'completed'
                         for s in self.results[g]['hard_skills'] + self.results[g]['soft_skills']}
                self.assertEqual({s['display_name'] for s in skills}, names)
                self.assertEqual(item['skill_intelligence_available'], bool(names) and status['completed'] > 0)
                for skill in skills:
                    self.assertEqual(skill['source_type'], 'llm_inference')
                    self.assertTrue(set(skill['evidence_levels']) <= {'inferred_medium', 'inferred_low'})
                    self.assertEqual(skill['inference_version'], 'skill-inference-v2')
        self.assertEqual(completed_total, 985)

    def test_uncovered_occupations_remain_in_market(self):
        uncovered = [o for o in self.catalog if not o['skill_intelligence_available']]
        self.assertEqual(len(uncovered), self.summary['market_only_occupations'])
        self.assertTrue(any(o['total_inference_group_count'] == 0 for o in uncovered))
        for occ in uncovered:
            self.assertGreater(occ['recruitment_evidence_count'], 0)
            self.assertEqual(self.details[occ['occupation_id']]['skills'], [])

    def test_product_manager_full_market_and_frozen_subset(self):
        detail = self.details['OCC0289']
        old = self.inputs['product_details']['occupations']['OCC0289']['occupation']
        actual = detail['occupation']
        self.assertEqual((actual['job_group_count'], actual['context_count'], actual['recruitment_evidence_count']), (28, 28, 80))
        subset = detail['selective_subset']
        self.assertEqual((subset['job_group_count'], subset['context_count'], subset['recruitment_evidence_count'], subset['completed_inference_group_count'], subset['skill_count']), (13, 13, 65, 13, 34))
        self.assertEqual(subset['job_group_count'], old['job_group_count'])
        self.assertEqual(subset['recruitment_evidence_count'], old['recruitment_evidence_count'])
        self.assertEqual(subset['skill_count'], old['unique_skill_count'])
        self.assertTrue(any(c['skill_intelligence_available'] for c in detail['contexts']))
        self.assertTrue(any(not c['skill_intelligence_available'] for c in detail['contexts']))
        ai = next(o for o in self.catalog if o['display_name'] == 'AI产品经理')
        self.assertNotEqual(ai['occupation_id'], actual['occupation_id'])

    def test_deterministic_aggregation_with_shuffled_inputs(self):
        inputs = self.inputs.copy()
        rng = random.Random(2026)
        for key in ('groups', 'members', 'selected', 'results', 'normalization', 'identity_families'):
            inputs[key] = list(inputs[key])
            rng.shuffle(inputs[key])
        summary, catalog, details = builder.build(inputs['groups'], inputs['members'], inputs['selected'], inputs['results'],
            inputs['normalization'], inputs['product_manifest'], inputs['product_details'], inputs['skill_catalog'], inputs['snapshots'], inputs['identity_families'], inputs['group_summary'], inputs['inference_summary'])
        self.assertEqual(catalog, self.catalog)
        self.assertEqual(details, self.details)
        for key, value in summary.items():
            self.assertEqual(value, self.summary[key])

    def test_duplicates_do_not_inflate_demand(self):
        # An artificial duplicate source-ID inside a frozen group's list must not
        # inflate distinct-record demand; production source files stay untouched.
        groups = [dict(g) for g in self.inputs['groups']]
        for group in groups[:10]:
            group['source_recruitment_record_ids'] = group['source_recruitment_record_ids'] * 2
        values = self.inputs
        summary, catalog, _ = builder.build(groups, values['members'], values['selected'], values['results'],
            values['normalization'], values['product_manifest'], values['product_details'], values['skill_catalog'], values['snapshots'], values['identity_families'], values['group_summary'], values['inference_summary'])
        self.assertEqual(catalog, self.catalog)
        self.assertEqual(summary['total_recruitment_evidence'], self.summary['total_recruitment_evidence'])

    def test_frozen_sources_unchanged(self):
        manifest = builder.load(builder.OUT / 'market_map_manifest.json')
        for source in manifest['frozen_upstream_inputs']:
            self.assertEqual(hashlib.sha256((ROOT / source['path']).read_bytes()).hexdigest(), source['sha256'])


if __name__ == '__main__':
    unittest.main()
