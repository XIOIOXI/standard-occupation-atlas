"""Generate a read-only demo result from frozen analysis artifacts; no API calls."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, "backend")
from app.agent.curriculum_intelligence import CurriculumIntelligenceAgent

OUT = Path("data/processed/agent/demo_agent_result.json")
REPORT = Path("docs/reports/agent-orchestration.md")

def main():
    result = CurriculumIntelligenceAgent().run_offline()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = result["run_metadata"]
    lines = ["# Single Curriculum Intelligence Agent — Offline Demo", "", "## Fixed workflow", "", "`Curriculum Input → Curriculum Skill Analysis → Market-Curriculum Mapping → Structural Gap Analysis → Validated Recommendation → Final Analysis Result`", "", "## Capability wrappers", "", "- `load_market_skill_profile`", "- `analyze_curriculum`", "- `map_curriculum_to_market`", "- `identify_structural_gaps`", "- `generate_curriculum_recommendations`", "", "## Execution", "", f"- Mode: `{metadata['mode']}`", f"- API calls: {metadata['api_calls']}", f"- State history: `{' → '.join(metadata['state_history'])}`", f"- Priority gaps: {len(result['priority_gaps'])}", f"- Validated recommendations: {len(result['recommendations'])}", "", "## Evidence boundary", ""] + [f"- {item}" for item in result["limitations"]]
    REPORT.parent.mkdir(parents=True, exist_ok=True); REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"api_calls": 0, "state": metadata["state"], "priority_gaps": len(result["priority_gaps"]), "recommendations": len(result["recommendations"])}, ensure_ascii=False))

if __name__ == "__main__": main()
