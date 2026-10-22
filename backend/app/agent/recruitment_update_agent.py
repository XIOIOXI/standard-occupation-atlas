"""Bounded decision loop for a recruitment-update run.

The agent cannot execute code, query historical files, or write records.  It
only selects from the supplied tool names, sees tool result summaries, and
emits a short user-visible rationale.  The host retains all validation and
persistence authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

ALLOWED_ACTIONS = frozenset({"reuse", "request_split", "classify", "repair", "hold", "finish"})


class Planner(Protocol):
    def choose(self, item: dict[str, Any], history: list[dict[str, Any]], allowed: set[str]) -> dict[str, str]: ...


class SimulatedPlanner:
    """Offline planner used by tests and no-key runs; never calls an LLM."""
    def choose(self, item: dict[str, Any], history: list[dict[str, Any]], allowed: set[str]) -> dict[str, str]:
        last = history[-1]["action"] if history else None
        if last is None and item.get("has_reusable_mapping") and "reuse" in allowed:
            return {"action": "reuse", "reason": "已验证的具体岗位分类可复用。"}
        if last is None and item.get("split_review_needed") and "request_split" in allowed:
            return {"action": "request_split", "reason": "原始岗位文本包含多个岗位线索，先读取程序拆分结果。"}
        if last in {None, "request_split"} and item.get("model_enabled") and "classify" in allowed:
            return {"action": "classify", "reason": "没有可安全复用的分类，申请受限目录分类工具。"}
        return {"action": "hold", "reason": "缺少可验证依据或模型工具不可用，保留待确认。"}


@dataclass
class RestrictedRecruitmentUpdateAgent:
    planner: Planner
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]
    max_calls_per_item: int = 6
    max_repairs_per_item: int = 1

    def run_item(self, item: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        trace: list[dict[str, Any]] = []
        repairs = 0
        for _ in range(self.max_calls_per_item):
            proposed = self.planner.choose(item, trace, set(ALLOWED_ACTIONS))
            action = proposed.get("action")
            if action not in ALLOWED_ACTIONS:
                action, proposed = "hold", {"reason": "决策不在允许工具范围内，程序转入待确认。"}
            if action == "finish":
                break
            if action == "repair":
                if repairs >= self.max_repairs_per_item:
                    action = "hold"; proposed = {"reason": "已达到单岗位修正上限，转入待确认。"}
                repairs += 1
            tool = self.tools.get(action)
            if tool is None:
                action, tool, proposed = "hold", self.tools["hold"], {"reason": "该操作当前不可用，转入待确认。"}
            result = tool(item)
            trace.append({"action": action, "reason": proposed.get("reason", ""), "result": result})
            if result.get("terminal"):
                return result, trace
            # Tool results are carried forward, but never treated as authority
            # to bypass the host's final contract validation.
            item = {**item, "last_tool_result": result}
        result = self.tools["hold"](item)
        trace.append({"action": "hold", "reason": "达到单岗位工具调用上限。", "result": result})
        return result, trace
