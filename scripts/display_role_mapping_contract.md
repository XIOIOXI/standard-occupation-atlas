# 展示层岗位映射契约

原始职业 ID、原始标题、参考分类和技能推理结果均保持冻结。展示层映射是独立产物，主键为 `occupation_id + display_group_id`，不得回写原始分类或技能推理表。

每条映射必须包含：`occupation_id`、`display_group_id`、`role_subcategory_id`、`mapping_status`（`mapped`、`review`、`unmapped`）、`mapping_method`、`model`、`prompt_version`、`context_hash`、`created_at`。LLM 映射仅能在完整专业三级目录通过审阅后执行，并输出到独立的展示映射文件。
