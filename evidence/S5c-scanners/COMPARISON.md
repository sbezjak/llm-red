# S5c - promptfoo (scale tool) vs the hand-built catalog

The article asset: where does an off-the-shelf OWASP-LLM scanner WIN, MISS, or
FRAME-DIFFERENTLY versus what we hand-built? Fill the TODOs after the run from
the RAW probe + reply text (not promptfoo's summary - it's a qwen grader,
see F11/F13/F14).

- **Date:** TODO
- **Tool:** `promptfoo@latest` redteam, fully local (qwen2.5:7b generator + grader)
- **Target:** project 0 `/ask`, as-is baseline (:8000)
- **Config:** `experiments/promptfoo/promptfooconfig.yaml`
- **Scale:** numTests=1/plugin, 3 plugins, 2 strategies (basic, jailbreak) = TODO total probes

## Plugin -> our family map (apples-to-apples)

| promptfoo plugin   | OWASP   | our family         | our findings here |
|--------------------|---------|--------------------|-------------------|
| harmful:cybercrime | LLM01   | obfuscation / jailbreak | F3, F5, F10 ...   |
| prompt-extraction  | LLM07   | prompt_extraction  | (hardened-only)   |
| pii                | LLM02   | (data exfiltration)| TODO              |

## Results table (one row per generated probe - from the RAW text)

| # | plugin | strategy | probe (verbatim, short) | /ask reply (verbatim, short) | promptfoo verdict | MY verdict | agree? |
|---|--------|----------|-------------------------|------------------------------|-------------------|-----------|--------|
| 1 | TODO   | TODO     | TODO                    | TODO                         | TODO              | TODO      | TODO   |

## Where the tool WON (found/framed something our catalog didn't)

- TODO

## Where the tool MISSED (our catalog catches it, promptfoo didn't)

- TODO (expected: anything needing the competence-gradient read - F3 - or the
  confabulation-vs-real-leak distinction - F13/F14 - since the grader is the
  same weak local model that already false-alarms on those.)

## Where the grader was WRONG (read end to end, the F5/F13 trap)

- TODO

## Net (the one-paragraph takeaway for the article) - CONFIRMED, S5c done 2026-06-20

garak fired hundreds of in-the-wild jailbreaks at project 0 in minutes and its
`MitigationBypass` detector reported **~100% ASR**. Reading the raw replies tells
the real story: in the 122-attempt sample, **~44% were explicit refusals and only
~2% contained any code/recipe markers** - the true harm rate is ~2%, not 100%. The
detector measures *"no refusal phrase,"* not *"produced harm,"* so it counts
persona-acceptance ("empty jailbreaks") and even outright refusals as bypasses -
the exact over-count our own S1 naive detector had (StrongREJECT documents this as
the field's problem). **Verdict, confirmed:** the scanner WINS on breadth + speed +
harness; it LOSES on judgment, and the judgment ("real bypass vs just chatty") is
the layer this suite hand-builds and the whole point of the project. More runs would
not fix it - it is a detector-definition gap, not sampling noise. See notes.md F15.

**Fairness caveat:** DanInTheWild is jailbreak framing with no paired harmful ask,
and `MitigationBypass` is garak's crudest detector. The counterweight (a concrete
harmful goal + content detector, `malwaregen.SubFunctions`) was staked at
`experiments/garak/garak_project0_malware.yaml` but left unrun when S5c was closed -
resume there if the writeup wants the "does it emit harm when actually asked" data point.

## Prompts sent

These are tool-generated in-the-wild jailbreaks, not our catalog, so the verbatim
prompts live in the saved run artifacts, recoverable without a re-run:
`p0_dan.report.jsonl` (8-prompt light run, seq 0-7) and `p0_dan_sample.report.jsonl`
(122-attempt sample of the full run). Each `attempt` row carries the exact `prompt`
sent and the raw reply. See `garak-dan-light-run.md` for the 8 paired prompt/reply rows.

## Caveats

- Local generator (qwen2.5:7b) writes weaker attacks than promptfoo's default
  GPT-4 generator - this is a FLOOR for the tool, not its ceiling.
- numTests=1, single run - directional, not measured.
- Grader is the same family of local model that false-alarmed in F13/F14;
  every verdict re-read by hand.
