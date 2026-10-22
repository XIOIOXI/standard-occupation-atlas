import unittest

from app.agent.recruitment_update_agent import RestrictedRecruitmentUpdateAgent, SimulatedPlanner


class RecruitmentUpdateAgentTests(unittest.TestCase):
    def test_agent_reads_split_tool_result_then_requests_classification(self):
        calls = []
        def split(_):
            calls.append("split")
            return {"terminal": False, "outcome": "split_checked", "accepted_units": ["甲", "乙"]}
        def classify(_):
            calls.append("classify")
            return {"terminal": True, "outcome": "classified", "mapping": {"status": "mapped"}}
        def hold(_): return {"terminal": True, "outcome": "held", "mapping": None}
        agent = RestrictedRecruitmentUpdateAgent(SimulatedPlanner(), {"request_split": split, "classify": classify, "hold": hold, "reuse": hold, "repair": classify})
        result, trace = agent.run_item({"model_enabled": True, "split_review_needed": True, "has_reusable_mapping": False})
        self.assertEqual(calls, ["split", "classify"])
        self.assertEqual(result["mapping"]["status"], "mapped")
        self.assertEqual([entry["action"] for entry in trace], ["request_split", "classify"])

    def test_out_of_contract_decision_is_held_without_running_unapproved_tool(self):
        class UnsafePlanner:
            def choose(self, item, history, allowed): return {"action": "shell", "reason": "no"}
        agent = RestrictedRecruitmentUpdateAgent(UnsafePlanner(), {"hold": lambda _: {"terminal": True, "outcome": "held"}})
        result, trace = agent.run_item({})
        self.assertEqual(result["outcome"], "held")
        self.assertEqual(trace[0]["action"], "hold")

    def test_agent_can_choose_one_repair_after_a_validation_result(self):
        class RepairPlanner:
            def choose(self, item, history, allowed):
                return {"action": "classify" if not history else "repair", "reason": "test"}
        calls = []
        def classify(_): calls.append("classify"); return {"terminal": False, "outcome": "validation_failed"}
        def repair(_): calls.append("repair"); return {"terminal": True, "outcome": "classified", "mapping": {"status": "mapped"}}
        agent = RestrictedRecruitmentUpdateAgent(RepairPlanner(), {"classify": classify, "repair": repair, "hold": lambda _: {"terminal": True, "outcome": "held"}})
        result, trace = agent.run_item({})
        self.assertEqual(calls, ["classify", "repair"])
        self.assertEqual(result["outcome"], "classified")
        self.assertEqual([step["action"] for step in trace], ["classify", "repair"])


if __name__ == "__main__":
    unittest.main()
