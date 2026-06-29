# promptfoo spike - runbook (S5c)

A light, local, free run of promptfoo's red-team scanner against project 0, so
we can compare what an off-the-shelf "scale mode" tool auto-finds to our
hand-built catalog. Standalone Node, outside the uv stack.

## Prereqs (all present as of 2026-06-19)

- Node + npx (have: v26).
- Ollama running with `qwen2.5:7b` (the local generator/grader) and `llama3.2`
  (project 0's backend model).
- project 0 checked out at `/Users/sara/StudioProjects/llm-api-testing`.

## 1. Start the target (project 0, as-is baseline on :8000)

```bash
cd /Users/sara/StudioProjects/llm-api-testing
uv run uvicorn app.main:app --port 8000        # as-is; no HARDENED env
# sanity:  curl -s localhost:8000/health  -> {"status":"ok"}
```

(The hardened variant, for a later before/after pass: `HARDENED=1 uv run uvicorn app.main:app --port 8001`.)

## 2. Run the spike

```bash
cd /Users/sara/StudioProjects/llm-red/experiments/promptfoo
npx promptfoo@latest redteam run            # generates probes, fires them, grades
npx promptfoo@latest redteam report         # opens the HTML report in a browser
```

`redteam run` does three things in order: (1) the local generator writes a
handful of adversarial probes per plugin, (2) fires them at `/ask`, (3) the
local grader labels each reply pass/fail. Output lands in
`experiments/promptfoo/` (`redteam.yaml` = generated probes, `*.json` = results).

## 3. Read it like we read everything (CLAUDE.md: raw output is ground truth)

Do NOT trust promptfoo's pass/fail summary on its own - it is an LLM grader
(qwen) and we already know (F11, F13, F14) local graders false-alarm on
recipe-FORM and confabulated "tokens". Open the actual probe text and the
actual `/ask` reply for every flagged row, read end to end, and decide
yourself. That reading IS the finding. Then fill in COMPARISON.md.

## Notes / gotchas

- **OpenAI by default.** Without the two `provider:` overrides in
  `promptfooconfig.yaml`, promptfoo's generator AND grader call OpenAI and need
  `OPENAI_API_KEY` + money. Keeping both local is the whole reason this is free.
- **Local generator is weaker.** qwen2.5:7b writes blunter jailbreaks than
  GPT-4 would, so promptfoo's auto-attacks here are a floor, not its ceiling -
  note that in the writeup so we don't undersell the tool.
- **Read-only alternative** (no live attack traffic to project 0) is sketched
  in `notes.md` -> "promptfoo source map", if we ever want the comparison
  without firing real requests.
