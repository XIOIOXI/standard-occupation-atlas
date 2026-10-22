# Skill Inference Eligibility and Budget Analysis

- API calls: **0**
- Population: **{len(rows):,} frozen Job Groups**
- Quality is a deterministic proxy from persisted context/mapping/member fields; it is not a trained classifier.

## Population profile
{
  "groups": 15622,
  "atomic_units": 20964,
  "recruitment_records": 4167,
  "quality": {
    "low": 754,
    "medium": 14194,
    "high": 674
  },
  "mapped": {
    "unmapped": 14706,
    "mapped": 916
  },
  "singleton_multi": {
    "singleton": 13539,
    "multi": 2083
  }
}

## Cross-tab (quality | mapping | singleton/multi)
{
  "low|unmapped|singleton": 702,
  "medium|unmapped|singleton": 12274,
  "medium|unmapped|multi": 1689,
  "high|mapped|singleton": 337,
  "high|mapped|multi": 337,
  "medium|mapped|singleton": 216,
  "low|unmapped|multi": 41,
  "low|mapped|singleton": 10,
  "medium|mapped|multi": 15,
  "low|mapped|multi": 1
}

## Mini pilot abstention (descriptive only)
{
  "status_counts": {
    "completed": 34,
    "insufficient_context": 16
  },
  "by_feature": {
    "context_quality": {
      "high": {
        "completed": 4
      },
      "medium": {
        "completed": 20,
        "insufficient_context": 3
      },
      "low": {
        "completed": 10,
        "insufficient_context": 13
      }
    },
    "mapped": {
      "False": {
        "completed": 34,
        "insufficient_context": 16
      }
    },
    "multi": {
      "True": {
        "completed": 19,
        "insufficient_context": 1
      },
      "False": {
        "insufficient_context": 15,
        "completed": 15
      }
    },
    "title_specific": {
      "True": {
        "completed": 30,
        "insufficient_context": 13
      },
      "False": {
        "completed": 4,
        "insufficient_context": 3
      }
    },
    "major_available": {
      "False": {
        "completed": 8,
        "insufficient_context": 2
      },
      "True": {
        "completed": 26,
        "insufficient_context": 14
      }
    },
    "industry_available": {
      "True": {
        "completed": 34,
        "insufficient_context": 16
      }
    }
  }
}

## Candidate strategies
### A_high_context
{
  "groups": 674,
  "atomic_units": 1734,
  "recruitment_records": 882,
  "quality": {
    "high": 674
  },
  "mapped": {
    "mapped": 674
  },
  "singleton_multi": {
    "singleton": 337,
    "multi": 337
  },
  "selected_pct": 4.31,
  "skipped_groups": 14948,
  "atomic_coverage_pct": 8.27,
  "record_coverage_pct": 21.17
}
### B_high_plus_medium_multi
{
  "groups": 2378,
  "atomic_units": 7672,
  "recruitment_records": 2388,
  "quality": {
    "medium": 1704,
    "high": 674
  },
  "mapped": {
    "unmapped": 1689,
    "mapped": 689
  },
  "singleton_multi": {
    "multi": 2041,
    "singleton": 337
  },
  "selected_pct": 15.22,
  "skipped_groups": 13244,
  "atomic_coverage_pct": 36.6,
  "record_coverage_pct": 57.31
}
### C_high_plus_medium_sufficient_evidence
{
  "groups": 9299,
  "atomic_units": 13592,
  "recruitment_records": 2993,
  "quality": {
    "medium": 8625,
    "high": 674
  },
  "mapped": {
    "unmapped": 8625,
    "mapped": 674
  },
  "singleton_multi": {
    "singleton": 7705,
    "multi": 1594
  },
  "selected_pct": 59.53,
  "skipped_groups": 6323,
  "atomic_coverage_pct": 64.83,
  "record_coverage_pct": 71.83
}
### D_recruitment_weight_prioritized_top_25pct
{
  "groups": 3906,
  "atomic_units": 9248,
  "recruitment_records": 2863,
  "quality": {
    "medium": 3097,
    "high": 674,
    "low": 135
  },
  "mapped": {
    "unmapped": 3177,
    "mapped": 729
  },
  "singleton_multi": {
    "multi": 2083,
    "singleton": 1823
  },
  "selected_pct": 25.0,
  "skipped_groups": 11716,
  "atomic_coverage_pct": 44.11,
  "record_coverage_pct": 68.71
}

## Token and budget planning
- Pilot averages: 1117.28 input, 261.44 output, 1378.72 total tokens/group.
- Illustrative planning rates only (not production pricing): $0.15/M input, $0.60/M output.
{
  "2": {
    "assumption_usd_per_million": {
      "input": 0.15,
      "output": 0.6
    },
    "groups": 6164,
    "input_tokens": 6886914,
    "output_tokens": 1611516,
    "total_tokens": 8498430,
    "atomic_coverage_pct": 54.88,
    "record_coverage_pct": 79.67
  },
  "3": {
    "assumption_usd_per_million": {
      "input": 0.15,
      "output": 0.6
    },
    "groups": 9246,
    "input_tokens": 10330371,
    "output_tokens": 2417274,
    "total_tokens": 12747645,
    "atomic_coverage_pct": 69.59,
    "record_coverage_pct": 88.72
  },
  "4": {
    "assumption_usd_per_million": {
      "input": 0.15,
      "output": 0.6
    },
    "groups": 12328,
    "input_tokens": 13773828,
    "output_tokens": 3223032,
    "total_tokens": 16996860,
    "atomic_coverage_pct": 84.29,
    "record_coverage_pct": 96.11
  }
}

## Conclusion
Recruitment-weight prioritization yields the strongest evidence coverage per selected group; no strategy is auto-approved. Low-evidence groups remain represented and are not deleted.