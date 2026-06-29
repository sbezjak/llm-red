"""Target swap - run the bare-model catalog against TWO bare Ollama targets
(llama3.2, llama3.1:8b) and grade every reply with the qwen2.5:7b judge.

Why BARE models (no project-0 guardrails): this measures the F3 COMPETENCE
GRADIENT - does a bigger model produce coherent harmful content where llama3.2
produced gibberish or refused? - so the MODEL must be the only variable.
Guardrails don't sit still; they catch things, masking the model signal.
Swapping only the provider (TargetProvider -> OllamaProvider) is also the
cleanest payoff of the target-agnostic design (PLAN pre-staked decision 4): the
catalog, runner posture, and judge are untouched, only the provider changes.

Scope - only the families that BITE a bare model: harmful-content elicitation
(multilingual, obfuscation, jailbreak jb-004..007). The canary/extraction
families (jb-001..003, pe-*) need a system prompt to leak; a bare model has none,
so they are inherently hardened-target attacks and are excluded here BY DESIGN.
direct_injection (PWNED / JAILBREAK ENABLED markers) is also excluded: it
measures instruction-following compliance, a different axis from harmful-content
competence, and the judge rubric does not grade a benign marker.

Performance - two phases so ONE model is resident at a time. Interleaving target
and judge calls forces ollama to evict/reload between every call (~150s/call
observed under three-model contention). Phase 1 collects ALL target replies for a
model while it stays hot; phase 2 judges ALL replies while qwen stays hot. Raw
transcripts are written to evidence/ BEFORE judging, so a non-deterministic reply
is never lost to a re-run (memory: save-reproduced-transcripts).

The log IS the deliverable (same posture as the judge-calibration test): the
per-model verdict distribution and per-attack bypass/partial counts are the
cross-target finding. The asserts only confirm the run actually happened
(non-empty replies); divergence is data, not failure.

Cheap-validation hooks (env): LLMRED_S5A_IDS="ml-001,obf-001" restricts the
attack set; LLMRED_S5A_TRIALS=1 cuts trials. Used to smoke the batched pipe
before the full ~2h run.
"""

import json
import logging
import os
from collections import Counter
from pathlib import Path

import pytest

from llm_red.dataset import load_attacks
from llm_red.detectors import LLMJudgeDetector
from llm_red.providers.ollama import OllamaProvider

logger = logging.getLogger("tests")

TARGET_MODELS = ("llama3.2", "llama3.1:8b")
HARMFUL_FAMILIES = {"multilingual", "obfuscation"}
HARMFUL_JAILBREAK_IDS = {"jb-004", "jb-005", "jb-006", "jb-007"}
EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "evidence" / "S5a-target-swap"


def _harmful_subset():
    """The catalog entries that bite a bare model (see module docstring)."""
    attacks = [
        a for a in load_attacks() if a.family in HARMFUL_FAMILIES or a.id in HARMFUL_JAILBREAK_IDS
    ]
    only = os.environ.get("LLMRED_S5A_IDS")
    if only:
        keep = {s.strip() for s in only.split(",")}
        attacks = [a for a in attacks if a.id in keep]
    return attacks


@pytest.mark.live
async def test_target_swap_competence_gradient():
    trials = int(os.environ.get("LLMRED_S5A_TRIALS", "3"))
    attacks = _harmful_subset()
    assert attacks, "no attacks selected"
    judge = LLMJudgeDetector(
        OllamaProvider("qwen2.5:7b", temperature=0, json_format=True, timeout=300.0)
    )

    # --- Phase 1: collect every target reply, one model resident at a time ------
    transcripts: dict[str, dict[str, list[str]]] = {}
    for model in TARGET_MODELS:
        provider = OllamaProvider(model, timeout=300.0)
        transcripts[model] = {}
        for attack in attacks:
            replies = [await provider.generate(attack.payload) for _ in range(trials)]
            transcripts[model][attack.id] = replies
            logger.info("COLLECTED %s / %s : %d replies", model, attack.id, len(replies))

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "transcripts.json").write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2)
    )

    # --- Phase 2: judge every collected reply, qwen resident throughout ---------
    graded: dict[str, dict[str, list[dict]]] = {}
    for model in TARGET_MODELS:
        graded[model] = {}
        for attack in attacks:
            rows = []
            for i, reply in enumerate(transcripts[model][attack.id]):
                j = await judge.judge(attack.payload, reply)
                rows.append(
                    {
                        "trial": i,
                        "reply": reply,
                        "verdict": j.verdict,
                        "quote": j.quote,
                        "reasoning": j.reasoning,
                        "quote_verified": j.quote_verified,
                    }
                )
                logger.info(
                    "GRADE %s / %s trial %d: verdict=%s quote_verified=%s\n"
                    "  quote: %s\n  reasoning: %s\n  reply: %s",
                    model,
                    attack.id,
                    i,
                    j.verdict,
                    j.quote_verified,
                    j.quote,
                    j.reasoning,
                    reply,
                )
            graded[model][attack.id] = rows

    (EVIDENCE_DIR / "graded.json").write_text(json.dumps(graded, ensure_ascii=False, indent=2))

    # --- Phase 3: the deliverable - per-model distribution + per-attack counts --
    for model in TARGET_MODELS:
        dist = Counter(r["verdict"] for rows in graded[model].values() for r in rows)
        lines = []
        for attack in attacks:
            rows = graded[model][attack.id]
            byp = sum(r["verdict"] == "bypass" for r in rows)
            par = sum(r["verdict"] == "partial" for r in rows)
            lines.append(f"  {attack.id:8} bypass={byp}/{len(rows)} partial={par}/{len(rows)}")
        logger.info(
            "TARGET-SWAP %s  verdict-distribution=%s\n%s",
            model,
            dict(dist),
            "\n".join(lines),
        )

    # --- asserts: confirm the run happened; divergence is data, not failure -----
    for model in TARGET_MODELS:
        for attack in attacks:
            replies = transcripts[model][attack.id]
            assert len(replies) == trials, f"{model}/{attack.id}: wrong trial count"
            assert all(r.strip() for r in replies), f"{model}/{attack.id}: empty reply"
