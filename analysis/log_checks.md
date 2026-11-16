# Liczby z surowych logów (wygenerowane przez analysis/log_checks.py)

```json
{
 "ui": {
  "A/claude-haiku-5-5": {
   "runs": 120,
   "success": 120,
   "max_steps": 2,
   "runs_with_goto_error": 0,
   "goto_errors": 0,
   "calls": 1737,
   "steps": 1412,
   "failures_on_max_steps": 0,
   "calls_per_run": 14.47,
   "steps_per_run": 11.77,
   "calls_per_step": 1.23
  },
  "A/claude-opus-5-5": {
   "runs": 120,
   "success": 120,
   "max_steps": 0,
   "runs_with_goto_error": 0,
   "goto_errors": 0,
   "calls": 1726,
   "steps": 1093,
   "failures_on_max_steps": 0,
   "calls_per_run": 14.38,
   "steps_per_run": 9.11,
   "calls_per_step": 1.58
  },
  "A/claude-sonnet-5-5": {
   "runs": 120,
   "success": 120,
   "max_steps": 0,
   "runs_with_goto_error": 0,
   "goto_errors": 0,
   "calls": 1497,
   "steps": 1267,
   "failures_on_max_steps": 0,
   "calls_per_run": 12.47,
   "steps_per_run": 10.56,
   "calls_per_step": 1.18
  },
  "B/claude-haiku-5-5": {
   "runs": 120,
   "success": 42,
   "max_steps": 31,
   "runs_with_goto_error": 111,
   "goto_errors": 499,
   "calls": 2496,
   "steps": 1658,
   "failures_on_max_steps": 30,
   "calls_per_run": 20.8,
   "steps_per_run": 13.82,
   "calls_per_step": 1.51
  },
  "B/claude-opus-5-5": {
   "runs": 120,
   "success": 120,
   "max_steps": 0,
   "runs_with_goto_error": 0,
   "goto_errors": 0,
   "calls": 2257,
   "steps": 1340,
   "failures_on_max_steps": 0,
   "calls_per_run": 18.81,
   "steps_per_run": 11.17,
   "calls_per_step": 1.68
  },
  "B/claude-sonnet-5-5": {
   "runs": 120,
   "success": 54,
   "max_steps": 77,
   "runs_with_goto_error": 7,
   "goto_errors": 52,
   "calls": 2286,
   "steps": 1992,
   "failures_on_max_steps": 65,
   "calls_per_run": 19.05,
   "steps_per_run": 16.6,
   "calls_per_step": 1.15
  }
 },
 "tool_errors": {
  "api_errors/generic": {
   "runs": 360,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "api_errors/rich": {
   "runs": 360,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "api_ids/readable": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "api_ids/uuid": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "api_pagination/meta": {
   "runs": 120,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "api_pagination/silent": {
   "runs": 120,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "api_shape/concise": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "api_shape/fields": {
   "runs": 180,
   "tool_errors": 10,
   "runs_with_error": 7
  },
  "api_shape/full": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_descriptions/full": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_descriptions/short": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_granularity/granular": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_granularity/task": {
   "runs": 180,
   "tool_errors": 60,
   "runs_with_error": 60
  },
  "mcp_idempotency/confirm": {
   "runs": 120,
   "tool_errors": 120,
   "runs_with_error": 120
  },
  "mcp_idempotency/direct": {
   "runs": 120,
   "tool_errors": 120,
   "runs_with_error": 120
  },
  "mcp_injection/injected": {
   "runs": 60,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_injection/none": {
   "runs": 60,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_toolcount/20": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_toolcount/5": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_toolcount/60": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "mcp_toolcount/60ns": {
   "runs": 180,
   "tool_errors": 0,
   "runs_with_error": 0
  },
  "ui_labels/A": {
   "runs": 360,
   "tool_errors": 19,
   "runs_with_error": 17
  },
  "ui_labels/B": {
   "runs": 360,
   "tool_errors": 1401,
   "runs_with_error": 283
  }
 },
 "non_ui_failures": {
  "failures": 21,
  "by_model": {
   "claude-haiku-5-5": 21
  },
  "booked_monday_instead_of_saturday": 17,
  "monday_runs_thinking_mentions_saturday": 14,
  "monday_runs_files": [
   "runs/api_errors/generic/claude-haiku-5-5/full_class_fallback/11.jsonl",
   "runs/api_errors/generic/claude-haiku-5-5/full_class_fallback/12.jsonl",
   "runs/api_errors/rich/claude-haiku-5-5/full_class_fallback/03.jsonl",
   "runs/api_errors/rich/claude-haiku-5-5/full_class_fallback/04.jsonl",
   "runs/api_errors/rich/claude-haiku-5-5/full_class_fallback/08.jsonl",
   "runs/api_errors/rich/claude-haiku-5-5/full_class_fallback/17.jsonl",
   "runs/mcp_descriptions/full/claude-haiku-5-5/full_class_fallback/10.jsonl",
   "runs/mcp_descriptions/short/claude-haiku-5-5/full_class_fallback/17.jsonl",
   "runs/mcp_granularity/granular/claude-haiku-5-5/full_class_fallback/04.jsonl",
   "runs/mcp_toolcount/20/claude-haiku-5-5/full_class_fallback/11.jsonl",
   "runs/mcp_toolcount/5/claude-haiku-5-5/full_class_fallback/17.jsonl",
   "runs/mcp_toolcount/60/claude-haiku-5-5/full_class_fallback/03.jsonl",
   "runs/mcp_toolcount/60/claude-haiku-5-5/full_class_fallback/07.jsonl",
   "runs/mcp_toolcount/60/claude-haiku-5-5/full_class_fallback/15.jsonl",
   "runs/mcp_toolcount/60/claude-haiku-5-5/full_class_fallback/20.jsonl",
   "runs/mcp_toolcount/60ns/claude-haiku-5-5/full_class_fallback/13.jsonl",
   "runs/mcp_toolcount/60ns/claude-haiku-5-5/full_class_fallback/16.jsonl"
  ]
 },
 "idempotency": {
  "direct": {
   "runs": 120,
   "runs_with_timeout": 120,
   "runs_retrying_identical_write": 0,
   "first_call_after_timeout": {
    "get_class_availability": 49,
    "get_client": 11,
    "create_booking": 60
   }
  },
  "confirm": {
   "runs": 120,
   "runs_with_timeout": 120,
   "runs_retrying_identical_write": 120,
   "first_call_after_timeout": {
    "confirm_booking": 120
   }
  }
 },
 "param_usage": {
  "api_shape/concise": {
   "params": [
    "response_format"
   ],
   "runs": 180,
   "runs_using_param": 140
  },
  "api_shape/fields": {
   "params": [
    "fields"
   ],
   "runs": 180,
   "runs_using_param": 79
  },
  "api_pagination/silent": {
   "params": [
    "offset",
    "cursor"
   ],
   "runs": 120,
   "runs_using_param": 119
  },
  "api_pagination/meta": {
   "params": [
    "offset",
    "cursor"
   ],
   "runs": 120,
   "runs_using_param": 119
  }
 },
 "thinking_coverage": {
  "steps": 24087,
  "steps_with_thinking": 7847
 },
 "quotes": [
  {
   "file": "runs/mcp_granularity/granular/claude-haiku-5-5/full_class_fallback/04.jsonl",
   "step": 4,
   "verbatim": true
  },
  {
   "file": "runs/ui_labels/B/claude-haiku-5-5/book_anna/02.jsonl",
   "step": 6,
   "verbatim": true
  },
  {
   "file": "runs/api_pagination/silent/claude-haiku-5-5/count_yoga/18.jsonl",
   "step": 3,
   "verbatim": true
  }
 ],
 "dates": {
  "pilot": [
   "2026-11-09T21:59:19.590192+00:00",
   "2026-11-09T22:01:47.092426+00:00"
  ],
  "full": [
   "2026-11-09T22:01:59.767940+00:00",
   "2026-11-09T23:03:31.521873+00:00"
  ]
 }
}
```
