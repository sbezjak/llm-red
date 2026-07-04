# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Pytest-based **red team test suite** for an LLM-backed API. Targets the
existing **FastAPI + LLM project** (project 0,
https://github.com/sbezjak/llm-api-testing) as the system under test, not
a fresh app - the point is to try to break something that already exists.
Python 3.11+, managed with `uv`.

**One focused theme:** which adversarial inputs slip past an LLM API's
guardrails, and how do you tell a genuine bypass from the model just being
chatty? The detector (bypass vs safe) is where the real work is - that is
what makes this a testing project, not a hacking demo. See `PLAN.md` for
full scope discipline.

Package layout under `llm_red/` (pinned in `pyproject.toml`
`packages = ["llm_red"]` for the wheel build):

These are the intended seams, built session by session (see `PLAN.md`
session arc). Only `providers/` and `dataset.py` exist as of S0:

- `providers/`, adapters that talk to the target API / LLM backend. The
  only place that issues HTTP calls; tests mock at this boundary with
  `respx`. Shape ported from the eval harness / RAG projects. (S0 ships the
  `OllamaProvider` seam; the project-0 target provider lands in S1.)
- `attacks/`, the adversarial payload catalog, grouped by attack family
  (direct injection, indirect injection, system-prompt extraction,
  jailbreak/role-play, encoded/obfuscated, multilingual). Pure data +
  light construction, no network calls. (S1+)
- `probes/` or `runners/`, send an attack at the target and capture the raw
  response. Deterministic given (attack, target response). (S1+)
- `detectors/`, decide whether a response indicates a *bypass* (leaked
  system prompt, followed the injected instruction, produced disallowed
  content). This is the red-team analog of the RAG scorers and is where
  most of the judgment lives - keep it I/O-free except for any LLM-judge
  detector, which calls a provider. (S2+)
- `severity.py`, map a detected bypass to a severity tier. (S2+)
- `dataset.py`, loads + validates the attack datasets under `data/`.

Datasets live at `data/` (populated S1+):

- `attacks/`, the payloads, one file per attack family.
- `expected.yaml`, per attack: what a *safe* response looks like vs a
  *bypass*, so pass/fail is checkable.

## Commands

Use `uv` for all environment and execution tasks:

- Install / sync deps (including dev group): `uv sync`
- Run all tests: `uv run pytest`
- Run a single test: `uv run pytest tests/path/to/test_file.py::test_name`
- Run only fast (mocked) tests: `uv run pytest -m mocked`
- Run only tests that hit the live target API: `uv run pytest -m live`
- Skip live tests: `uv run pytest -m "not live"`
- Rebuild the committed findings report: `uv run pytest -m finding
  --html=reports/report-findings.html` - the `finding` marker (on
  `tests/test_findings_showcase.py`) selects exactly the finding rows, so the
  hosted report is findings-only, never the whole hermetic suite.
- HTML report: every `uv run pytest` writes a UNIQUE `reports/report-<UTC
  timestamp>.html` - the default `reports/report.html` is auto-rewritten to a
  timestamp by `tests/conftest.py` (`pytest_configure`, tryfirst), so **no run can
  ever overwrite another**. This is the structural guarantee, NOT a rule to
  remember (a written "don't overwrite" rule was broken within 20 min; enforcement
  has to be mechanical - see working_with_ai.md). Auto-timestamped files are
  gitignored; a report to COMMIT/host is generated with an explicit descriptive
  name (`uv run pytest -m finding --html=reports/report-findings.html` for the
  findings report; `-m "not live"` or a live run for a full-suite report), which
  conftest leaves untouched. Self-contained, captured logs at INFO+.
- Findings are non-deterministic, so the committed/hosted report is built
  DETERMINISTICALLY from saved real transcripts via fixture-injected /
  `xfail`-as-contract tests (`tests/test_findings_showcase.py` replays
  `data/findings.yaml`; the calibration + detector tests do the same), so ONE
  report shows every documented finding every run - never rely on a lucky live run.
  Snapshot real transcripts to `evidence/` too (see save-reproduced-transcripts).
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`

Project-specific scripts (added incrementally across sessions): none yet (S0).

## Test conventions (configured in pyproject.toml)

- `asyncio_mode = "auto"`, async tests do not need `@pytest.mark.asyncio`.
- Custom markers gate environment-dependent tests:
  - `@pytest.mark.live`, slow, requires the live target API running.
  - `@pytest.mark.mocked`, uses `respx` to mock the target HTTP API;
    should be the default for unit tests.
- `testpaths = ["tests"]`; `ruff` line length is 100, target `py311`.

Test categories mirror the locked attack families in `tests/` subfolders,
created as each family lands (S1+). Keeping families separate is how a
single broad bypass doesn't get mistaken for a category-wide failure:

- `tests/injection_direct/`, "ignore previous instructions" style.
- `tests/injection_indirect/`, hostile instructions hidden in content the
  system ingests.
- `tests/prompt_extraction/`, attempts to leak the system prompt.
- `tests/jailbreak/`, role-play / persona attacks.
- `tests/obfuscation/`, encoded / Unicode-trick / multilingual attacks.

Use the `xfail(strict=True)`-as-contract pattern (ported from projects 1-2)
to lock in *known* bypasses: a strict xfail that fails loudly if a bypass
ever stops working, forcing acknowledgment instead of silent drift.

## Architecture intent

Preserve these seams when adding code:

- HTTP calls only inside `providers/`. Tests mock here with `respx`.
- Attack construction has no network calls - deterministic given the
  payload data.
- Detection depends on the target's response but tests inject known
  responses as fixtures, so attack-construction and detection failures
  don't contaminate each other.
- Detectors stay I/O-free (an LLM-judge detector is the exception, it
  calls a provider).

## Working style with this user

- **`human-tasks.md` is the channel for anything only the user can do.**
  Whenever the next step needs the user (post an update, paste a real URL,
  decide a squishy ground-truth call, run an interactive login), append a
  checkbox item to `human-tasks.md` instead of only mentioning it in chat -
  chat scrolls, the file persists. Read it when picking up work. Named
  `human-tasks`, not `tasks`, so it isn't confused with a generic task tool.
- **Prepare drafts/templates for any task the user has to do by hand.**
  When the next step is something only the user can do (write an attack
  payload, decide whether a given response counts as a bypass, grade a
  refusal), prepare a fill-in-the-blanks file with the structure pre-built.
  Don't make the user start from a blank page. Examples: a YAML scaffold
  with TODOs, a markdown table with rows pre-filled, a notes template with
  section headings. Reduce the user's task to filling in the squishy parts.
- **Capture explanations to `notes.md` when teaching.** When the user asks
  "explain this to me" and the answer is non-trivial (why an attack family
  works, how a detector decides, OWASP LLM Top 10 mechanics), mirror it
  (lightly cleaned up) into `notes.md` as reference material. The chat
  scrolls; the article stays.
- **Two writing registers, no duplicate copies.** `notes.md` is the dense,
  finding-first record. The teaching / front-door artifacts (the narrated
  walkthrough, `docs/` explainers, README) use the plain, layered voice the
  user likes (plain words, an analogy or two, structured so a reader can
  stop as soon as they have it). Same explanation in two registers drifts
  out of sync, so the registers serve different artifacts, never two copies
  of one thing. Do not add a standalone concepts/glossary file; notes.md
  plus the walkthrough cover both lookup and teaching.
- **Ground each front-door artifact in the previous projects' versions
  before drafting.** The article, walkthrough, and LinkedIn post all come
  out measurably better when the model first reads the *same* artifact from
  the earlier projects (A/B confirmed: cold start < partial context <
  pointed at all prior writings - do the last one). Links live in
  `PORTFOLIO.md` (single source of truth, don't copy them here), but read
  the LOCAL copies - they are faster and the LinkedIn URLs are auth-walled:
  the sibling repos at `../llm-eval-harness/`, `../llm-rag/`,
  `../llm-api-testing/` hold the prior `article.md` / `docs/*article*.md`.
  For a LinkedIn post specifically, match the shipped voice: curiosity /
  first-person hook, one finding told as a story, an easy-case-vs-hard-case
  contrast, no arrows / hashtags / stacked numbers, closing line exactly
  `Automation engineer learning AI testing. Project N of 5. More from the
  series: <link>`.
- **Default to production / best-practice solutions; take the pragmatic
  shortcut only when the trade-off is justified for this project's scope,
  and call the trade-off out explicitly.** Don't silently pick the easy
  path. Name what the production-grade pattern would be, name why we're not
  doing it here (scope, runtime context, learning focus), and write the
  trade-off into `notes.md` so the writeup shows it was a deliberate choice,
  not an oversight.
- **Validate a new integration cheaply before any long or expensive run.**
  Before launching a long run (especially one exercising a new external
  tool that has never run end to end here), prove it works on the smallest
  possible input first (1-2 items, fabricated inputs are fine) and confirm
  the output parses / scores. ALWAYS arm a monitor on the log for any run
  that is not near-instant - grepping for success AND failure signatures
  (`500|Internal Server Error|Traceback|Error|Exception|Killed|OOM|NaN|Timeout|Failed`)
  so a mid-run failure surfaces at the failing job. Smoke test first,
  monitor second, both every time. When a run does fail, fix the root cause
  and re-validate cheaply before re-running full.
- **Always make model prompts and responses visible in test reports.**
  Every component that calls a model (providers, LLM-judge detectors) must
  log the prompt going in and the response coming out at `INFO` level via
  the stdlib `logging` module, not truncated. The always-on pytest-html
  report captures these, so any failing test's "Captured log" section shows
  exactly what the model saw and said. For a red-team project this is how
  you tell a real bypass from the model just being verbose.
- **Read the report/logs thoroughly - the raw model output is the only ground
  truth, never conclude from a summary boolean, a count, or a keyword/length
  heuristic when the actual response text is available.** In S2 a detector
  boolean, and then an in-language keyword heuristic, both mislabelled a German
  reply that refused in its first sentence and then gave numbered
  bomb-construction steps ("refuse-then-comply"). A reply can also have the
  *form* of a recipe but gibberish content, or look like a bypass while being a
  decode-failure ramble - only reading the whole thing tells them apart. Open the
  response and read it end to end, that reading IS the work, not an optional
  check.
- **Prefer the smallest solution that solves the problem; after writing,
  re-read and cut machinery the task didn't ask for.** Asked to "add
  validation", don't reach for a configurable framework with custom
  exception classes when a few lines of `if` are the real answer. Treat the
  re-read as a step: "is half of this scaffolding I invented but nobody
  asked for?" If yes, rewrite it small.
- In all prose (docs, comments, commit messages, PR descriptions), join
  clauses with a single hyphen `-`, a comma, a period, or parentheses. The
  only dash character in written text is a single `-`.
- End commit messages at the body. The user is the sole author.
