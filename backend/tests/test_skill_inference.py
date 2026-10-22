from __future__ import annotations
import json
import unittest
import importlib.util
import io
import urllib.error
from dataclasses import replace
from pathlib import Path
from app.domain.skills.inference import InferredSkill, JobGroupSkillInferenceInput, JobGroupSkillInferenceResult, normalize_skill
from app.domain.skills.normalization_v2 import normalize_skill_v2, SKILL_NORMALIZATION_VERSION
_spec=importlib.util.spec_from_file_location('pilot_runner', 'scripts/run_skill_inference_v2_pilot.py')
_runner=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_runner)

class SkillInferenceTests(unittest.TestCase):
 def input(self,title='软件工程师'):
  return JobGroupSkillInferenceInput('JG-1',title,None,None,'raw:tech',(title,),1,1,1,(),(),{}, {},'job-grouping-v1','mvp-taxonomy-v4.1-frozen','low')
 def test_fingerprint_is_deterministic_and_changes_with_evidence(self):
  self.assertEqual(self.input().fingerprint(),self.input().fingerprint());self.assertNotEqual(self.input().fingerprint(),self.input('测试工程师').fingerprint())
 def test_result_allows_zero_skills_for_insufficient_context(self):
  r=JobGroupSkillInferenceResult('JG-1',self.input().fingerprint(),'insufficient_context');self.assertEqual(r.hard_skills,())
 def test_management_trainee_can_be_skipped_without_skills(self):
  r=JobGroupSkillInferenceResult('JG-management-trainee','context-fingerprint','skipped_generic');self.assertEqual(r.hard_skills,());self.assertEqual(r.soft_skills,())
 def test_context_payload_is_bounded(self):
  with self.assertRaises(ValueError):replace(self.input(),representative_source_contexts=tuple({'source_record_id':str(i)} for i in range(6)))
 def test_inferred_skill_cannot_claim_observed_high(self):
  with self.assertRaises(ValueError): InferredSkill('Python','Python','hard','low',evidence_level='observed_high')
 def test_skill_limits_and_normalization(self):
  s=InferredSkill('Python 编程','Python','hard','medium')
  with self.assertRaises(ValueError): JobGroupSkillInferenceResult('JG-1','f','completed',(s,)*6,())
  self.assertEqual(normalize_skill(' Python programming '),'Python')
 def test_pilot_has_required_shape(self):
  rows=[json.loads(x) for x in Path('data/processed/skill_inference/skill_inference_pilot_50.jsonl').read_text(encoding='utf-8').splitlines() if x]
  self.assertEqual(len(rows),50);self.assertEqual(len({x['job_group_id'] for x in rows}),50)
  self.assertTrue(any(x['mapped'] for x in rows));self.assertTrue(any(not x['mapped'] for x in rows));self.assertEqual({x['context_quality'] for x in rows},{'high','medium','low'})
 def test_api_error_categories(self):
  e=urllib.error.HTTPError('u',401,'x',{},io.BytesIO(b'{"error":{"code":"invalid_api_key"}}'))
  self.assertEqual(_runner.classify_exception(e)['error_category'],'api_authentication_error')
  e=urllib.error.HTTPError('u',403,'x',{},io.BytesIO(b'{"error":{"code":"model_not_found"}}'))
  self.assertEqual(_runner.classify_exception(e)['error_category'],'api_model_access_error')
  e=urllib.error.HTTPError('u',429,'x',{},io.BytesIO(b'{"error":{"code":"rate_limit_exceeded"}}'))
  d=_runner.classify_exception(e); self.assertEqual(d['error_category'],'api_rate_limit_error'); self.assertTrue(d['retryable'])
 def test_http_error_body_fields_are_extracted_safely(self):
  e=urllib.error.HTTPError('u',400,'x',{},io.BytesIO(b'{"error":{"type":"invalid_request_error","code":"bad_param","param":"text.format","message":"invalid structured output"}}'))
  d=_runner.classify_exception(e)
  self.assertEqual(d['api_error_type'],'invalid_request_error'); self.assertEqual(d['api_error_code'],'bad_param'); self.assertEqual(d['api_error_param'],'text.format'); self.assertEqual(d['api_error_message'],'invalid structured output')
 def test_malformed_http_error_body_falls_back_safely(self):
  e=urllib.error.HTTPError('u',400,'x',{},io.BytesIO(b'not-json'))
  d=_runner.classify_exception(e); self.assertEqual(d['error_category'],'api_request_error'); self.assertIsNone(d['api_error_code'])
 def test_network_output_and_schema_categories(self):
  self.assertEqual(_runner.classify_exception(urllib.error.URLError('offline'))['error_category'],'api_network_error')
  self.assertEqual(_runner.classify_exception(_runner.StructuredOutputError('bad output'))['error_category'],'structured_output_error')
  self.assertEqual(_runner.classify_exception(_runner.SchemaValidationError('bad schema'))['error_category'],'schema_validation_error')
 def test_secret_never_in_diagnostic_message(self):
  import os
  old=os.environ.get('OPENAI_API_KEY'); os.environ['OPENAI_API_KEY']='secret-value'
  try: self.assertNotIn('secret-value',_runner.classify_exception(Exception('Authorization: Bearer secret-value'))['message'])
  finally:
   if old is None: os.environ.pop('OPENAI_API_KEY',None)
   else: os.environ['OPENAI_API_KEY']=old
 def test_single_group_mode_limits_selection(self):
  rows=[{'job_group_id':'a'},{'job_group_id':'a'},{'job_group_id':'b'}]
  with self.assertRaises(ValueError): _runner.select_rows(rows,'a')
  selected,mode=_runner.select_rows(rows[:1],'a'); self.assertTrue(mode); self.assertEqual(len(selected),1)
 def test_request_preflight_accepts_json_object_contract(self):
  body=_runner.build_request({'title':'test'})
  self.assertEqual(_runner.validate_request_contract(body,group_count=1,single_group=True),[])
 def test_request_preflight_blocks_missing_json(self):
  body={'model':'gpt-4.1-mini','instructions':'contains json','input':'context','text':{'format':{'type':'json_object'}}}
  self.assertTrue(_runner.validate_request_contract(body,group_count=1,single_group=True))
 def test_request_preflight_requires_lowercase_json_in_actual_input(self):
  base={'model':'gpt-4.1-mini','instructions':'json','text':{'format':{'type':'json_object'}}}
  self.assertTrue(_runner.validate_request_contract({**base,'input':'context'},group_count=1,single_group=True))
  self.assertTrue(_runner.validate_request_contract({**base,'input':'JSON object'},group_count=1,single_group=True))
  self.assertEqual(_runner.validate_request_contract({**base,'input':'return json object'},group_count=1,single_group=True),[])
 def test_preflight_and_http_body_share_actual_input(self):
  body=_runner.build_request({'title':'x'}); self.assertIn('json',body['input']); self.assertEqual(_runner.validate_request_contract(body,group_count=1,single_group=True),[])
 def test_valid_llm_fixture_parses_and_normalizes(self):
  raw={'status':'completed','skills':[{'raw_skill_name':'Python 编程','skill_type':'hard','confidence':'medium','skill_scope':'occupation_core','reasoning_summary':'title supports programming'}]}
  parsed=_runner.parse_and_validate_response({'output_text':json.dumps(raw,ensure_ascii=False)})
  self.assertEqual(parsed[1],'completed'); self.assertEqual(parsed[2][0]['normalized_skill_name'],'Python')
 def test_invalid_status_fixture_is_rejected(self):
  with self.assertRaises(_runner.SchemaValidationError): _runner.parse_and_validate_response({'output_text':'{"status":"done","skills":[]}'})
 def test_responses_api_output_content_extraction(self):
  payload={'output':[{'type':'message','content':[{'type':'output_text','text':'{"status":"insufficient_context","skills":[]}'}]}]}
  self.assertIn('insufficient_context',_runner.extract_response_text(payload))
 def test_missing_output_is_structured_error_not_empty_object(self):
  with self.assertRaisesRegex(_runner.StructuredOutputError,'missing_response_output_text'): _runner.extract_response_text({'output':[]})
 def test_malformed_json_is_structured_error(self):
  with self.assertRaises(_runner.StructuredOutputError):
   _runner.parse_and_validate_response({'output_text':'not-json'})
 def test_normalization_v2_confirmed_aliases_converge(self):
  self.assertEqual(normalize_skill_v2('Team collaboration')[0],'团队协作'); self.assertEqual(normalize_skill_v2('问题解决能力')[0],'问题解决')
 def test_normalization_v2_protected_boundaries_remain_distinct(self):
  self.assertNotEqual(normalize_skill_v2('质量管理')[0],normalize_skill_v2('Quality Engineering')[0]); self.assertNotEqual(normalize_skill_v2('Java')[0],normalize_skill_v2('JavaScript')[0])
 def test_normalization_v2_is_deterministic_and_versioned(self):
  self.assertEqual(normalize_skill_v2('Collaboration'),normalize_skill_v2('Collaboration')); self.assertEqual(SKILL_NORMALIZATION_VERSION,'skill-normalization-v2'); self.assertEqual(normalize_skill('Python programming'),'Python')
 def test_request_preflight_blocks_multi_group_diagnostic(self):
  body=_runner.build_request({'title':'test'})
  self.assertTrue(_runner.validate_request_contract(body,group_count=2,single_group=True))
