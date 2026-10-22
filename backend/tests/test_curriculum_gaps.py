import unittest
from app.domain.curriculum.gaps import relevance, priority

class CurriculumGapRulesTests(unittest.TestCase):
 def test_it_skill_is_program_relevant(self):
  self.assertEqual(relevance('网络安全与隐私保护','hard',[])[0],'high')
 def test_unrelated_skill_stays_low_relevance(self):
  self.assertEqual(relevance('园艺管理','hard',['raw:农业'])[0],'low')
 def test_short_it_tokens_do_not_match_inside_words(self):
  self.assertNotEqual(relevance('Attention to Detail','soft',[])[0],'high')
 def test_high_requires_relevance_missing_and_weight(self):
  self.assertEqual(priority('high','not_observed',50,5)[0],'high')
  self.assertEqual(priority('medium','not_observed',50,5)[0],'medium')
