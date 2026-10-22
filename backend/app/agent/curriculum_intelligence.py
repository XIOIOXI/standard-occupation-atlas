"""Read-only single-agent orchestration over frozen Curriculum Intelligence artifacts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AgentState(str, Enum):
    PENDING = "pending"
    ANALYZING_CURRICULUM = "analyzing_curriculum"
    MAPPING_MARKET = "mapping_market"
    IDENTIFYING_GAPS = "identifying_gaps"
    GENERATING_RECOMMENDATIONS = "generating_recommendations"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRunError(RuntimeError):
    def __init__(self, message: str, state_history: list[str]):
        super().__init__(message)
        self.state_history = state_history


@dataclass(frozen=True)
class FrozenArtifacts:
    market_profile: Path = Path("data/processed/skill_demand_profile/skill_demand_profile.json")
    program: Path = Path("data/demo/curriculum/demo_program.json")
    curriculum_profile: Path = Path("data/processed/curriculum/curriculum_skill_profile.json")
    mapping: Path = Path("data/processed/curriculum/market_curriculum_mapping.json")
    gaps: Path = Path("data/processed/curriculum/curriculum_gap_analysis.json")
    recommendations: Path = Path("data/processed/recommendations/recommendation_result.json")


class CurriculumIntelligenceAgent:
    """Fixed-order, API-ready orchestration; tools never recalculate frozen analyses."""
    def __init__(self, artifacts: FrozenArtifacts = FrozenArtifacts()):
        self.artifacts = artifacts
        self.state = AgentState.PENDING
        self.state_history = [self.state.value]

    def _transition(self, target: AgentState) -> None:
        allowed = {
            AgentState.PENDING: {AgentState.ANALYZING_CURRICULUM, AgentState.FAILED},
            AgentState.ANALYZING_CURRICULUM: {AgentState.MAPPING_MARKET, AgentState.FAILED},
            AgentState.MAPPING_MARKET: {AgentState.IDENTIFYING_GAPS, AgentState.FAILED},
            AgentState.IDENTIFYING_GAPS: {AgentState.GENERATING_RECOMMENDATIONS, AgentState.FAILED},
            AgentState.GENERATING_RECOMMENDATIONS: {AgentState.COMPLETED, AgentState.FAILED},
        }
        if target not in allowed.get(self.state, set()):
            raise RuntimeError(f"invalid agent transition: {self.state.value} -> {target.value}")
        self.state = target; self.state_history.append(target.value)

    def _read(self, path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"required frozen artifact is missing: {path.as_posix()}")
        return json.loads(path.read_text(encoding="utf-8"))

    # Capability interfaces. These are intentional wrappers, not duplicate analytics.
    def load_market_skill_profile(self) -> dict:
        profile = self._read(self.artifacts.market_profile)
        frequency = profile.get("overall_frequency", {})
        return {"provenance": profile.get("provenance", {}), "top_skills": (frequency.get("all") or [])[:10], "profile_artifact": self.artifacts.market_profile.as_posix()}

    def analyze_curriculum(self) -> dict:
        program = self._read(self.artifacts.program); profile = self._read(self.artifacts.curriculum_profile)
        return {"program": {"program_id": program["program_id"], "program_name": program["program_name"], "description": program["description"], "provenance": program["provenance"], "courses": [{"course_id": course["course_id"], "course_name": course["course_name"], "learning_outcomes": course["learning_outcomes"], "assessments": course.get("assessments", [])} for course in program["courses"]]}, "covered_skills": [{"normalized_skill": item["normalized_skill"], "evidence_count": item["evidence_count"], "supporting_course_ids": item["supporting_course_ids"], "supporting_learning_outcomes": item["supporting_learning_outcomes"][:2]} for item in profile.get("covered_skills", [])], "profile_artifact": self.artifacts.curriculum_profile.as_posix()}

    def map_curriculum_to_market(self) -> dict:
        mapping = self._read(self.artifacts.mapping)
        return {"input_mapping_entries": len(mapping.get("mapping", [])), "coverage_status_counts": mapping.get("status_counts", {}), "provenance": mapping.get("provenance", {}), "mapping_artifact": self.artifacts.mapping.as_posix()}

    def identify_structural_gaps(self) -> dict:
        gaps = self._read(self.artifacts.gaps)
        return {"priority_gaps": gaps.get("final_actionable_candidates", []), "priority_counts": gaps.get("priority_counts", {}), "candidate_count_before_cap": gaps.get("relevance_tested_candidate_count_before_final_cap"), "provenance": gaps.get("provenance", {}), "gap_artifact": self.artifacts.gaps.as_posix()}

    def generate_curriculum_recommendations(self) -> dict:
        result = self._read(self.artifacts.recommendations)
        metadata = result.get("metadata", {})
        if metadata.get("validation_status") != "passed":
            raise ValueError("frozen recommendation artifact is not validated")
        output = result.get("recommendation_output", {})
        return {"recommendations": output.get("recommendations", []), "overall_summary": output.get("overall_summary"), "limitations": output.get("limitations", []), "metadata": {key: metadata.get(key) for key in ("model", "prompt_version", "input_fingerprint", "validation_status", "token_usage")}, "recommendation_artifact": self.artifacts.recommendations.as_posix()}

    def run_offline(self) -> dict:
        """Execute the approved fixed workflow from frozen outputs; API calls are always zero."""
        try:
            market = self.load_market_skill_profile()
            self._transition(AgentState.ANALYZING_CURRICULUM)
            curriculum = self.analyze_curriculum()
            self._transition(AgentState.MAPPING_MARKET)
            coverage = self.map_curriculum_to_market()
            self._transition(AgentState.IDENTIFYING_GAPS)
            gaps = self.identify_structural_gaps()
            self._transition(AgentState.GENERATING_RECOMMENDATIONS)
            recommendations = self.generate_curriculum_recommendations()
            self._transition(AgentState.COMPLETED)
        except Exception as error:
            if self.state != AgentState.FAILED:
                self._transition(AgentState.FAILED)
            raise AgentRunError(str(error), self.state_history) from error
        limitations = [
            "Recruitment skills are inferred candidate skills based on job-group context, not stated recruitment requirements.",
            "Curriculum data is MVP demo/sample content, not an official syllabus.",
            "not_observed means no frozen curriculum-text evidence was observed; it does not confirm absence from teaching.",
            "Recommendations are decision-support suggestions, not authoritative curriculum decisions.",
            "Market evidence comes from selective skill inference rather than all job groups.",
        ] + recommendations["limitations"]
        return {"program": curriculum["program"], "market_summary": market, "curriculum_summary": {"covered_skills": curriculum["covered_skills"], "profile_artifact": curriculum["profile_artifact"]}, "coverage_summary": coverage, "priority_gaps": gaps["priority_gaps"], "recommendations": recommendations["recommendations"], "evidence": {"market_profile": market["profile_artifact"], "curriculum_profile": curriculum["profile_artifact"], "mapping": coverage["mapping_artifact"], "gaps": gaps["gap_artifact"], "recommendations": recommendations["recommendation_artifact"], "recommendation_metadata": recommendations["metadata"]}, "limitations": limitations, "run_metadata": {"mode": "offline_frozen_artifacts", "api_calls": 0, "state": self.state.value, "state_history": self.state_history}}
