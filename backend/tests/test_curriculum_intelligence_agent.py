import json
import tempfile
import unittest
from pathlib import Path
from app.agent.curriculum_intelligence import AgentRunError, AgentState, CurriculumIntelligenceAgent, FrozenArtifacts


class CurriculumIntelligenceAgentTests(unittest.TestCase):
    def test_offline_workflow_returns_complete_result(self):
        result = CurriculumIntelligenceAgent().run_offline()
        self.assertEqual(result["run_metadata"]["state"], "completed")
        self.assertEqual(result["run_metadata"]["api_calls"], 0)
        self.assertTrue(result["priority_gaps"])
        self.assertTrue(result["recommendations"])

    def test_state_transitions_are_fixed(self):
        agent = CurriculumIntelligenceAgent(); agent.run_offline()
        self.assertEqual(agent.state_history, [state.value for state in (AgentState.PENDING, AgentState.ANALYZING_CURRICULUM, AgentState.MAPPING_MARKET, AgentState.IDENTIFYING_GAPS, AgentState.GENERATING_RECOMMENDATIONS, AgentState.COMPLETED)])

    def test_evidence_references_are_preserved(self):
        result = CurriculumIntelligenceAgent().run_offline()
        self.assertIn("gaps", result["evidence"])
        self.assertTrue(result["recommendations"][0]["gap_ids"])
        self.assertTrue(result["recommendations"][0]["market_evidence"])

    def test_missing_artifact_fails_with_state(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            artifacts = FrozenArtifacts(market_profile=missing)
            agent = CurriculumIntelligenceAgent(artifacts)
            with self.assertRaises(AgentRunError) as caught: agent.run_offline()
            self.assertEqual(caught.exception.state_history[-1], "failed")

    def test_result_is_json_serializable(self):
        result = CurriculumIntelligenceAgent().run_offline()
        self.assertIsInstance(json.dumps(result, ensure_ascii=False), str)
