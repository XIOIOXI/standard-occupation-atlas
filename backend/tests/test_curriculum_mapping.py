import unittest
from app.domain.curriculum.mapping import coverage_status, extract_curriculum_skills

class CurriculumMappingTests(unittest.TestCase):
 def test_exact_match_retains_evidence(self):
  program={'program_id':'p','courses':[{'course_id':'c','description':'Practice data analysis.','learning_outcomes':[],'assessments':[]}]}
  found=extract_curriculum_skills(program,{'data analysis','team collaboration'})
  self.assertEqual(found[0]['normalized_skill'],'data analysis')
  self.assertEqual(found[0]['source_field'],'course_description')
 def test_v2_alias_is_conservative(self):
  program={'program_id':'p','courses':[{'course_id':'c','description':'Team collaboration is assessed.','learning_outcomes':[],'assessments':[]}]}
  found=extract_curriculum_skills(program,{'团队协作'})
  self.assertEqual(found[0]['normalized_skill'],'团队协作')
  self.assertEqual(found[0]['match_method'],'approved_v2_alias_match')
 def test_coverage_status(self):
  self.assertEqual(coverage_status([]),'not_observed')
  self.assertEqual(coverage_status([{'course_id':'c'}]),'partially_covered')
  self.assertEqual(coverage_status([{'course_id':'a'},{'course_id':'b'}]),'covered')
