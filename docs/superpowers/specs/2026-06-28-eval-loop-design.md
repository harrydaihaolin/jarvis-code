# Eval Loop Design Spec

**Date:** 2026-06-28
**Status:** Approved

---

## What It Is

A standalone async eval script that runs one sanity-check scenario through Jarvis Code's real Anthropic API and records traces and scores in a self-hosted Langfuse instance.

---

## Stack

| Layer | Choice |
|---|---|
| Runner | `python evals/run.py` — standalone, not pytest |
| Tracing + scoring | `langfuse` Python SDK, self-hosted at `http://localhost:3000` |
| LLM | Real Anthropic API (`ANTHROPIC_API_KEY` from env) |
| Reuses | `jarvis.query.run_turn`, `jarvis.config.load_config`, `jarvis.history.History` |

---

## File

```
evals/
└── run.py    # ~80 lines, self-contained async script
```

---

## Scenario

**Name:** `read_file sanity check`

| Step | Detail |
|---|---|
| Setup | Write `/tmp/jarvis_eval.txt` with content `"jarvis-eval-42"` |
| Prompt | `"Read /tmp/jarvis_eval.txt and tell me what's in it"` |
| Check 1 — `tool_called` | A `tool_use` block with `name == "read_file"` exists in `history.messages` |
| Check 2 — `content_present` | Final assistant text block contains `"jarvis-eval-42"` |
| Score | Each check scored 0.0 (fail) or 1.0 (pass) on the Langfuse trace |

---

## Flow

```
asyncio.run(main())
  │
  ├── Init Langfuse(host="http://localhost:3000", keys from env)
  ├── Upsert dataset "jarvis-sanity"
  ├── Upsert dataset item { input: prompt, expected_output: "jarvis-eval-42" }
  │
  └── For the single dataset item:
        ├── Write /tmp/jarvis_eval.txt
        ├── history = History(); history.append_user(prompt)
        ├── trace = langfuse.trace(name="read_file-sanity", input=prompt)
        ├── generation = trace.generation(name="run_turn", model=config.model, input=history.messages)
        ├── await run_turn(history, config)
        ├── generation.end(output=<final assistant text>)
        ├── Extract tool_called and content_present from history.messages
        ├── langfuse.score(trace_id, "tool_called", 0.0 or 1.0)
        ├── langfuse.score(trace_id, "content_present", 0.0 or 1.0)
        ├── langfuse.create_dataset_run_item(run_name=..., item_id=..., observation_id=trace.id)
        └── Print PASS/FAIL + trace URL
  │
  └── langfuse.flush()
```

---

## Env Vars

| Var | Source |
|---|---|
| `ANTHROPIC_API_KEY` | `~/.zshrc` |
| `LANGFUSE_PUBLIC_KEY` | `~/.zshrc` |
| `LANGFUSE_SECRET_KEY` | `~/.zshrc` |
| `LANGFUSE_HOST` | Hardcoded default `http://localhost:3000` in script |

---

## Output

```
=== Jarvis Code Eval ===
Dataset: jarvis-sanity | Run: 2026-06-28T...

[1/1] read_file sanity check
  ✓ tool_called    (read_file)
  ✓ content_present (jarvis-eval-42 in response)
  PASS  (2.4s)

1/1 passed
Trace: http://localhost:3000/trace/<id>
```

---

## Out of Scope

- Multiple scenarios
- Pytest integration
- Langfuse cloud
- LLM-as-judge scoring
