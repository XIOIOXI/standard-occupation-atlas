# Skill Inference v2 Pilot

- Groups: 50
- API attempts / successful responses: 50 / 50
- Statuses: {'completed': 34, 'insufficient_context': 16}
- Tokens (input / output / total): 55864 / 13072 / 68936
- Estimated cost: unavailable (no project pricing configuration).

## Skills

- Hard / soft: 112 / 70
- Raw / normalized unique: 159 / 159
- Confidence: {'high': 63, 'medium': 119}
- Scope: {'occupation_core': 90, 'domain_specific': 92}
- Evidence: {'inferred_medium': 182}
- Most frequent normalized skills: [('问题解决能力', 5), ('团队协作', 4), ('沟通协调能力', 3), ('机械设计', 3), ('质量管理', 2), ('跨部门协调', 2), ('Communication Skills', 2), ('新能源行业知识', 2), ('自动化技术', 2), ('跨学科协作', 2), ('数据分析能力', 2), ('跨部门沟通', 2), ('Logistics Management', 2), ('采购管理', 2), ('供应链协调', 2)]

## Quality flags

{
  "normalization_collisions": [],
  "suspected_semantic_duplicates": [],
  "generic_soft_skill_repetition": [],
  "suspicious_over_specific_skills": [],
  "possible_hallucination_cases": [],
  "empty_or_near_empty_results": [
    "JG2-2f37ab1a822123d1",
    "JG2-89b3b587d0520680",
    "JG2-b816577c2aad2710",
    "JG2-266515d56025eef4",
    "JG2-63beb2ef264e989b",
    "JG2-d9ec6fd9f1d6804e",
    "JG2-43cc79243a5cbcec",
    "JG2-6d6cc8f929428218",
    "JG2-cba6874589677dbc",
    "JG2-06e1743148844d38",
    "JG2-34bfc783d7396564",
    "JG2-5950f082bce30a8f",
    "JG2-3d910b4049293f6e",
    "JG2-9838888c857dece1",
    "JG2-9dbc31aefff0f190",
    "JG2-b9bd848a90b19b21"
  ]
}

## 财务专员跨行业

[
  {
    "job_group_id": "JG2-da655eb19ae09450",
    "representative_title": "财务专员",
    "cache_hit": true,
    "inference_status": "completed",
    "hard_skills": [
      {
        "raw_skill_name": "财务管理",
        "normalized_skill_name": "财务管理",
        "skill_type": "hard",
        "confidence": "high",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "As a 财务专员 (Financial Specialist), core responsibilities likely involve financial management tasks within the新能源与能源产业 domain."
      },
      {
        "raw_skill_name": "会计核算",
        "normalized_skill_name": "会计核算",
        "skill_type": "hard",
        "confidence": "high",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Financial specialists typically perform accounting and bookkeeping duties to ensure accurate financial records."
      },
      {
        "raw_skill_name": "报表编制与分析",
        "normalized_skill_name": "报表编制与分析",
        "skill_type": "hard",
        "confidence": "medium",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Preparing and analyzing financial reports is a standard role for financial positions."
      },
      {
        "raw_skill_name": "新能源行业知识",
        "normalized_skill_name": "新能源行业知识",
        "skill_type": "hard",
        "confidence": "medium",
        "skill_scope": "domain_specific",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Job is within the新能源与能源产业, requiring familiarity with the new energy industry context."
      }
    ],
    "soft_skills": [
      {
        "raw_skill_name": "沟通协调能力",
        "normalized_skill_name": "沟通协调能力",
        "skill_type": "soft",
        "confidence": "medium",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Financial specialists generally need to communicate with multiple departments and external stakeholders."
      },
      {
        "raw_skill_name": "细致严谨",
        "normalized_skill_name": "细致严谨",
        "skill_type": "soft",
        "confidence": "high",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Attention to detail is crucial for financial record accuracy and compliance."
      },
      {
        "raw_skill_name": "数据分析思维",
        "normalized_skill_name": "数据分析思维",
        "skill_type": "soft",
        "confidence": "medium",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Analytical thinking supports interpretation of financial data and decision-making."
      }
    ],
    "model": "gpt-4.1-mini",
    "input_fingerprint": "f23efe376c55b5ceabde97f996db318d6e8319e5c6c8e3040bc58bb1b42844a5",
    "usage": {
      "input_tokens": 2377,
      "output_tokens": 453,
      "total_tokens": 2830,
      "estimated_cost": null
    },
    "versions": {
      "grouping": "job-grouping-v2-occupation-safe",
      "inference": "skill-inference-v2",
      "prompt": "job-group-skill-inference-prompt-v6",
      "context": "job-group-context-v2",
      "normalization": "skill-normalization-v1"
    },
    "context_quality": "high",
    "mapped": true,
    "member_count": 5,
    "industry_domain_context": "l1:新能源与能源产业"
  },
  {
    "job_group_id": "JG2-eaaf26c7f00b94c3",
    "representative_title": "财务专员",
    "cache_hit": true,
    "inference_status": "completed",
    "hard_skills": [
      {
        "raw_skill_name": "财务核算",
        "normalized_skill_name": "财务核算",
        "skill_type": "hard",
        "confidence": "high",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Essential core accounting tasks expected for a finance specialist role."
      },
      {
        "raw_skill_name": "财务报表编制",
        "normalized_skill_name": "财务报表编制",
        "skill_type": "hard",
        "confidence": "high",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Preparation of financial statements is a fundamental finance duty."
      },
      {
        "raw_skill_name": "预算管理",
        "normalized_skill_name": "预算管理",
        "skill_type": "hard",
        "confidence": "medium",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Budget management is commonly required in finance specialist positions."
      },
      {
        "raw_skill_name": "数据分析能力",
        "normalized_skill_name": "数据分析能力",
        "skill_type": "hard",
        "confidence": "medium",
        "skill_scope": "domain_specific",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Finance roles in electronic and semiconductor industries usually require data analysis."
      },
      {
        "raw_skill_name": "电子信息产业知识",
        "normalized_skill_name": "电子信息产业知识",
        "skill_type": "hard",
        "confidence": "medium",
        "skill_scope": "domain_specific",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Industry domain context indicates value for domain-specific finance knowledge."
      }
    ],
    "soft_skills": [
      {
        "raw_skill_name": "细致且有条理的工作习惯",
        "normalized_skill_name": "细致且有条理的工作习惯",
        "skill_type": "soft",
        "confidence": "high",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Finance specialists need attention to detail and organization to manage financial data."
      },
      {
        "raw_skill_name": "沟通协调能力",
        "normalized_skill_name": "沟通协调能力",
        "skill_type": "soft",
        "confidence": "medium",
        "skill_scope": "occupation_core",
        "source_type": "llm_inference",
        "evidence_level": "inferred_medium",
        "reasoning_summary": "Interacting with multiple departments in finance roles requires communication skills."
      }
    ],
    "model": "gpt-4.1-mini",
    "input_fingerprint": "42d6fee3693be36b9fe876889aba8b7b116540a49018bd98d887457751bedbde",
    "usage": {
      "input_tokens": 1075,
      "output_tokens": 452,
      "total_tokens": 1527,
      "estimated_cost": null
    },
    "versions": {
      "grouping": "job-grouping-v2-occupation-safe",
      "inference": "skill-inference-v2",
      "prompt": "job-group-skill-inference-prompt-v6",
      "context": "job-group-context-v2",
      "normalization": "skill-normalization-v1"
    },
    "context_quality": "medium",
    "mapped": true,
    "member_count": 2,
    "industry_domain_context": "l1:电子信息与通信产业"
  }
]
