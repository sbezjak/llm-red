# llm-redteam

A pytest-based red team test suite for an LLM-backed API. It fires a
catalog of adversarial inputs at an existing FastAPI + LLM service
(project 0, https://github.com/sbezjak/llm-api-testing) and decides, per
response, whether a guardrail was actually bypassed.

> **Theme:** which adversarial inputs slip past an LLM API's guardrails, and
> how do you tell a genuine bypass from the model just being chatty? The
> detector (bypass vs safe) is where the real work is - that is what makes
> this a testing project, not a hacking demo.

Project 3 of a 5-project AI/QA learning portfolio. A learning project,
written up for anyone trying to get into AI testing.

## Rules of engagement

This suite only attacks systems we own and run locally (project 0, and
later our own RAG / agent projects). It is a defensive testing kit - know
your guardrails before someone else finds the gaps. Do not point it at any
service you are not authorized to test.

## What it tests

Filled in session by session as attack families and detectors land. The
locked families (see `PLAN.md`): direct injection, system-prompt
extraction, jailbreak / role-play, encoded / obfuscated, multilingual, and
data exfiltration. Findings are categorized by a 3-tier severity model
mapped to the OWASP LLM Top 10.

## If you already do automation QA

This is the same test / assert / regress loop you already run. Only one thing
changes: the assertion goes from boolean to statistical, because the system
under test is non-deterministic - the same attack might slip past 9 times out
of 10, so a finding is reported as a success *rate*, not a single pass/fail.

| Regular automation QA | This red-team suite |
|---|---|
| Test case | Attack payload |
| Expected result | What a "safe" response looks like |
| Assertion | The detector (did a guardrail actually get bypassed?) |
| Boolean assertion | Statistical assertion - success rate over N trials |
| Regression test | A strict `xfail` that fails loudly if a known bypass ever stops working |
| Severity / bug triage | A 3-tier severity model, each finding tagged with its OWASP LLM Top 10 and MITRE ATLAS id |

If you can read a bug report with a severity and a repro, you can read this
suite's output.

## How to run

The `mocked` tests need nothing external. The `live` tests fire at the real
target, so first **clone and start project 0 on `:8000`** (in a separate
terminal), with Ollama running:

```sh
git clone https://github.com/sbezjak/llm-api-testing
cd llm-api-testing
ollama serve &                # the LLM backend (separate tab is fine)
ollama pull llama3.2          # the model project 0 calls
uvicorn app.main:app          # the target API on :8000
curl localhost:8000/health    # -> {"status":"ok"}
```

The jailbreak and extraction `live` tests fire at project 0's **hardened**
mode (the three-layer defense it grows under `HARDENED=1`), which the suite
expects on `:8001` - separate from the plain target on `:8000`, so both run
side by side. In another terminal:

```sh
HARDENED=1 uvicorn app.main:app --port 8001   # the hardened target on :8001
curl localhost:8001/health                    # -> {"status":"ok"}
```

Override the port with `LLMRED_HARDENED_URL`. See project 0's own README
("Hardened mode") for what each layer does. Once it answers on `:8000`
(plain) and `:8001` (hardened), the `live` tests below have something to hit.

```sh
uv sync                      # install deps (incl. dev group)
uv run pytest                # all tests; writes reports/report.html
uv run pytest -m mocked      # fast, no live target needed (the default)
uv run pytest -m live        # requires the live target API running
uv run pytest -m "not live"  # skip live tests
uv run ruff check .          # lint
```

## Reports

Two self-contained HTML reports are published (captured model prompts and
responses at INFO level), hosted on GitHub Pages:

- **[Findings report](https://sbezjak.github.io/llm-red/reports/report-findings.html)**
  (`reports/report-findings.html`) - deterministic and network-free: it replays the
  real captured transcript behind every finding (F1-F17) through the real detectors,
  so each finding is visible the same way on every run. Built from `data/findings.yaml`
  by `tests/test_findings_showcase.py`. This is the one to read first.
- **[Full suite run](https://sbezjak.github.io/llm-red/reports/report-full-live-2026-06-28.html)**
  (`reports/report-full-live-<date>.html`) - the whole suite executed against the
  live targets (plain `:8000` + hardened `:8001`): the real adversarial run, including
  the non-deterministic live tests.

Reports are saved under stable/dated names and **never overwritten** - findings here
are non-deterministic, so a run that surfaced one must stay linkable. The auto
`reports/report.html` is only the transient "latest" of whatever you last ran
(gitignored); the hosted reports above are committed deliberately.

**Reproducing findings (and what's in this repo).** The suite ships the
attack *prompts*, the *detectors*, and the captured *evidence* behind each
finding (raw transcripts and write-ups under `evidence/`). The mocked tests
inject placeholder responses, so a default run produces no live model output;
the live findings are generated on *your own* machine when you run the `live`
tests against your own Ollama, the same as asking that model the question
directly. The auto-generated `reports/report.html` reflects whatever your last
run did, so it is gitignored and regenerated each run; the curated report
published with the writeup is committed deliberately. Nothing is redacted: the
only verified reproductions are conceptual (naming that a hazard exists, not a
usable procedure), so there is nothing actionable to withhold.

## How this was built

Built session by session with Claude Code (Anthropic's CLI) as a
pair-programming assistant, working against a written scope plan so the
project stayed disciplined rather than sprawling. The workflow ran in both
directions: I drove the model, but the model also kept a queue of tasks for
*me* - the calls only a person should make (deciding whether a borderline
reply really counts as a guardrail bypass, grading refusals, supplying real
target URLs). The squishy ground-truth judgments stayed with me; the
scaffolding and detector code was paired.

`CLAUDE.md`, committed alongside this README, is the standing instruction set
the assistant works from: the seams to preserve, the working style, what
counts as evidence. The rest of the process ran through working notes kept out
of the repo (personal), named here so the method is on the record:

- `PLAN.md` - the scope document: families locked in or out, the session arc,
  the stopping rule. The discipline that kept this a focused suite, not a
  sprawl.
- `notes.md` - a findings-first record of each bypass: what it was, why it
  works, and the detector reasoning behind calling it a bypass vs safe.
- `human-tasks.md` - the model's queue of human-only tasks. The interesting
  half of the division of labor: the assistant handed *back* the judgment
  calls instead of guessing them.

## Further reading

If this made you want to learn LLM red teaming, these are the resources I
found most useful - hands-on first, then the standards the report speaks:

- [Gandalf](https://gandalf.lakera.ai) - a prompt-injection game; the same
  idea as the system-prompt-extraction attacks here, as 7 levels.
- [PortSwigger Web Security Academy - Web LLM attacks](https://portswigger.net/web-security/llm-attacks)
  - free, graded labs on direct and indirect injection.
- [Learn Prompting - Prompt Hacking](https://learnprompting.org/docs/category/prompt-hacking)
  - a free course built from the largest public injection competition.
- [Embrace the Red](https://embracethered.com/blog/) (Johann Rehberger) - the
  densest worked examples of real injection attacks, with actual payloads and
  screenshots; a good source of concrete seeds for the attack catalog.
- [Inject My PDF](https://kai-greshake.de/posts/inject-my-pdf/) (Kai Greshake) -
  a vivid hands-on demo of indirect injection hidden in an ingested document.
- [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)
  - the standard this suite's severity tiers map to (LLM01 injection, LLM02
  sensitive-info disclosure, LLM07 prompt leakage).
- [OWASP GenAI Red Teaming Guide](https://genai.owasp.org/resource/genai-red-teaming-guide/)
  - process and lifecycle for running a red-team engagement (roles, scope,
  method), the companion to the taxonomy above.
- [MITRE ATLAS](https://atlas.mitre.org) - an ATT&CK-style threat matrix for
  adversarial machine learning.
- [garak](https://github.com/NVIDIA/garak),
  [PyRIT](https://github.com/Azure/PyRIT), and
  [promptfoo](https://www.promptfoo.dev/docs/red-team/) - the production
  red-team tools this project deliberately hand-builds the small version of.
  promptfoo is the config-driven, CI-friendly one whose attack plugins map
  straight onto the OWASP LLM Top 10.
- [Microsoft - Lessons from red teaming 100 generative AI products](https://www.microsoft.com/en-us/security/blog/2025/01/13/3-takeaways-from-red-teaming-100-generative-ai-products/).
- Video: DEF CON AI Village talks; Andrej Karpathy's "Intro to Large Language
  Models" (the security section); Simon Willison's
  [prompt injection](https://simonwillison.net/tags/prompt-injection/) writing.
