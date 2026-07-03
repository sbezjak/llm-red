"""Findings showcase - the deterministic, network-free view of every documented
finding (F1-F19), rendered into the committed pytest-html report.

Why this exists: the live suite (`-m live`) hits a non-deterministic model, so no
single live run ever contains every finding, and a run that surfaced one can be
lost to the next report overwrite. This module instead replays the REAL captured
target replies (publishable; the actionable F3 variant stays in private evidence/)
through the real deterministic detectors, asserting the documented verdict so the
detector behaviour is locked. Judge / Llama Guard / garak findings carry a
`recorded` verdict - those need a live model/tool, so they are displayed, not
recomputed. Every prompt+reply is logged at INFO, so the report's "Captured log"
shows the actual model words. Result: ONE report shows every finding, the same way
every run. Source of truth: data/findings.yaml (also the S6 findings.json seed).
"""

import logging
from pathlib import Path

import pytest
import yaml

from llm_red.dataset import Attack
from llm_red.detectors import (
    canary_leaked,
    guard_evaded,
    injected_output_present,
    refused,
)
from llm_red.detectors.deterministic import indirect_injection_obeyed
from llm_red.findings import (
    ATLAS_TITLES,
    OWASP_TITLES,
    taxonomy_coverage,
    write_findings_json,
)

logger = logging.getLogger("tests")

FINDINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "findings.yaml"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# Detectors that take (attack, response). `refused` takes (response) and is handled
# separately below.
_DETECTORS = {
    "injected_output_present": injected_output_present,
    "indirect_injection_obeyed": indirect_injection_obeyed,
    "canary_leaked": canary_leaked,
    "guard_evaded": guard_evaded,
}


def _load_findings() -> list[dict]:
    return yaml.safe_load(FINDINGS_FILE.read_text())["findings"]


FINDINGS = _load_findings()


@pytest.mark.mocked
def test_campaign_overview():
    """Render the campaign header into the report (targets, models, dates, scope)."""
    families = sorted({f.get("family", "") for f in FINDINGS if f.get("family")})
    logger.info(
        "\n=== RED-TEAM CAMPAIGN OVERVIEW ===\n"
        "findings shown: %d (F1-F19, some grouped)\n"
        "targets: project-0 plain :8000 and hardened :8001 (HARDENED=1, canary + L1/L2/L3)\n"
        "models: llama3.2 (target), llama3.1:8b (swap), qwen2.5:7b (LLM-judge), "
        "llama-guard3:1b (classifier)\n"
        "families: %s\n"
        "live campaign: 2026-06-10 .. 2026-06-28, multiple live runs. Findings are "
        "non-deterministic, so this report REPLAYS captured transcripts "
        "deterministically; live reproduction is the `-m live` suite.\n"
        "detectors: deterministic (refused / marker / canary / guard) + LLM-judge "
        "(qwen2.5) + Llama Guard (llama-guard3).",
        len(FINDINGS),
        ", ".join(families),
    )


@pytest.mark.mocked
def test_taxonomy_coverage():
    """Render the OWASP/ATLAS coverage rollup into the report (technique -> findings).

    The per-finding log answers "what is F6 tagged?"; this answers the inverse the
    pentest reader actually asks - "which findings exercise AML.T0056?". Same data,
    rolled up, so a reviewer sees the standard-taxonomy footprint at a glance.
    """
    coverage = taxonomy_coverage(FINDINGS)
    lines = ["\n=== TAXONOMY COVERAGE (which findings hit each id) ==="]
    for axis, titles in (("owasp", OWASP_TITLES), ("atlas", ATLAS_TITLES)):
        lines.append(f"\n-- {axis.upper()} --")
        for tag in sorted(coverage[axis]):
            ids = ", ".join(coverage[axis][tag])
            lines.append(f"{tag} ({titles.get(tag, '?')}): {ids}")
    untagged = [f["id"] for f in FINDINGS if not coverage_has(coverage, f["id"])]
    lines.append(f"\nno technique (detector-quality / scanner findings): {', '.join(untagged)}")
    logger.info("\n".join(lines))

    # The named ids the project commits to in PLAN.md must all appear - a renamed or
    # dropped tag is a regression, not a silent gap.
    for expected in ("LLM01", "LLM07", "LLM02"):
        assert expected in coverage["owasp"], f"OWASP {expected} no longer covered"
    for expected in ("AML.T0051", "AML.T0051.000", "AML.T0051.001", "AML.T0054", "AML.T0056"):
        assert expected in coverage["atlas"], f"ATLAS {expected} no longer covered"


def coverage_has(coverage: dict, finding_id: str) -> bool:
    """True if `finding_id` appears under any OWASP or ATLAS id."""
    return any(finding_id in ids for axis in coverage.values() for ids in axis.values())


@pytest.mark.mocked
def test_findings_json_artifact():
    """Emit reports/findings.json deterministically from the catalog and lock its shape.

    Regenerated every run (it's a golden artifact, not a lucky-run capture), so the
    committed JSON always matches the YAML. Asserts every finding round-trips with the
    pentest-shape keys PLAN.md specifies.
    """
    data = write_findings_json(REPORTS_DIR / "findings.json", FINDINGS)
    assert data["count"] == len(FINDINGS)
    ids_in = {f["id"] for f in FINDINGS}
    ids_out = {e["id"] for e in data["findings"]}
    assert ids_out == ids_in, f"findings.json dropped/added ids: {ids_in ^ ids_out}"
    required = {"id", "title", "family", "severity", "owasp", "atlas", "realized_harm", "asr"}
    for entry in data["findings"]:
        missing = required - entry.keys()
        assert not missing, f"{entry['id']}: findings.json entry missing {missing}"
    logger.info("findings.json: %d findings, coverage=%s", data["count"], data["coverage"])


@pytest.mark.mocked
@pytest.mark.parametrize("finding", FINDINGS, ids=lambda f: f["id"])
def test_finding_showcase(finding):
    """Replay one finding's real captured reply; render it and lock detector behaviour.

    Deterministic detectors are CALLED and asserted (a detector regression fails
    here). `recorded` findings (judge/Guard/garak) are displayed only - they need a
    live model/tool and are graded in their own live tests.
    """
    markers = tuple(finding.get("success_markers") or ())
    attack = Attack(
        id=finding["id"],
        family=finding.get("family", ""),
        payload=finding.get("attack", ""),
        bypass_when="",
        safe_when="",
        success_markers=markers,
    )
    verdict = finding.get("expect", finding.get("recorded_verdict"))
    logger.info(
        "\n=== %s  %s ===\n"
        "family=%s  severity=%s  OWASP=%s  ATLAS=%s  realized_harm=%s\n"
        "detector=%s  verdict=%s  (captured %s)\n"
        "--- attack sent ---\n%s\n"
        "--- target reply (real, captured) ---\n%s\n"
        "--- reading ---\n%s\n"
        "evidence: %s",
        finding["id"],
        finding["title"],
        finding.get("family"),
        finding.get("severity"),
        finding.get("owasp"),
        finding.get("atlas"),
        finding.get("realized_harm"),
        finding["detector"],
        verdict,
        finding.get("captured"),
        finding.get("attack"),
        finding.get("reply"),
        finding.get("note"),
        finding.get("evidence"),
    )

    detector_name = finding["detector"]
    if detector_name == "recorded":
        # Judge / Llama Guard / garak finding - displayed above, graded in its own
        # live test. Nothing to recompute here without a live model/tool.
        assert "recorded_verdict" in finding, f"{finding['id']}: recorded finding needs a verdict"
        return

    reply = finding["reply"]
    if detector_name == "refused":
        result = refused(reply)
    else:
        detector = _DETECTORS.get(detector_name)
        assert detector is not None, f"{finding['id']}: unknown detector {detector_name!r}"
        result = detector(attack, reply)

    expected = finding["expect"]
    assert result == expected, (
        f"{finding['id']}: detector {detector_name} returned {result}, expected "
        f"{expected} on the captured reply - DETECTOR REGRESSION (the saved reply did "
        f"not change, so the detector did)."
    )
