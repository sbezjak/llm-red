"""Findings catalog -> taxonomy coverage rollup + machine-readable findings.json.

I/O-free except `write_findings_json`, which is the one explicit emitter. The
catalog (`data/findings.yaml`) tags every finding with an OWASP LLM Top 10 id and a
MITRE ATLAS technique id; this module rolls those up (technique -> which findings hit
it) and renders the pentest-report shape PLAN.md asks for. Deterministic given the
YAML, so `reports/findings.json` is a golden artifact, not a lucky-run capture.
"""

import json
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FINDINGS_FILE = DATA_DIR / "findings.yaml"

# Technique/risk id -> human title, so the rollup names what each id MEANS instead of
# leaving a bare code. Kept here (not in the YAML) so the catalog stays terse and the
# titles can't drift per-finding.
ATLAS_TITLES = {
    "AML.T0051": "LLM Prompt Injection",
    "AML.T0051.000": "LLM Prompt Injection: Direct",
    "AML.T0051.001": "LLM Prompt Injection: Indirect",
    "AML.T0054": "LLM Jailbreak",
    "AML.T0056": "LLM Meta Prompt Extraction",
}
OWASP_TITLES = {
    "LLM01": "Prompt Injection",
    "LLM02": "Sensitive Information Disclosure",
    "LLM07": "System Prompt Leakage",
}


def load_findings(path: Path = FINDINGS_FILE) -> list[dict]:
    """Load the raw finding records from the catalog YAML."""
    return yaml.safe_load(path.read_text())["findings"]


def _tags(value) -> list[str]:
    """Normalise an owasp/atlas field to a list of ids, dropping the "-" sentinel.

    A finding may carry one id ("LLM01"), several ("LLM07, LLM02"), or "-" for the
    detector-quality/scanner findings that map to no technique.
    """
    if not value or value == "-":
        return []
    return [t.strip() for t in str(value).split(",") if t.strip() and t.strip() != "-"]


def taxonomy_coverage(findings: list[dict]) -> dict[str, dict[str, list[str]]]:
    """Roll findings up by taxonomy: {"owasp"|"atlas": {id: [finding ids]}}.

    The inverse of the per-finding tags - answers "which findings exercise AML.T0056?"
    rather than "what is F6 tagged?". This is the coverage view the per-finding log
    can't show.
    """
    coverage: dict[str, dict[str, list[str]]] = {"owasp": {}, "atlas": {}}
    for finding in findings:
        for axis, field in (("owasp", "owasp"), ("atlas", "atlas")):
            for tag in _tags(finding.get(field)):
                coverage[axis].setdefault(tag, []).append(finding["id"])
    return coverage


def build_findings_json(findings: list[dict]) -> dict:
    """Render the catalog into the pentest-report shape (PLAN.md S6 artifact).

    Per finding: id, title, family, severity, owasp/atlas (as id lists), realized_harm,
    asr (the detector's success rate - null until a human fills it), detector + verdict,
    repro pointers. Plus the taxonomy coverage rollup and a small header.
    """
    entries = []
    for f in findings:
        entries.append(
            {
                "id": f["id"],
                "title": f.get("title", ""),
                "family": f.get("family", ""),
                "severity": f.get("severity", ""),
                "owasp": _tags(f.get("owasp")),
                "atlas": _tags(f.get("atlas")),
                "realized_harm": f.get("realized_harm"),
                "asr": f.get("asr"),  # detector success rate; the over-counting number
                "detector": f.get("detector"),
                "verdict": f.get("expect", f.get("recorded_verdict")),
                "captured": f.get("captured"),
                "evidence": f.get("evidence"),
                "tag_rationale": f.get("tag_rationale"),
            }
        )
    return {
        "schema": "llm-red/findings@1",
        "note": (
            "asr is the detector-reported attack-success rate (over-counts); "
            "realized_harm is what a human read confirms. The gap is the thesis."
        ),
        "count": len(entries),
        "coverage": taxonomy_coverage(findings),
        "titles": {"owasp": OWASP_TITLES, "atlas": ATLAS_TITLES},
        "findings": entries,
    }


def write_findings_json(path: Path, findings: list[dict] | None = None) -> dict:
    """Build and write reports/findings.json; return the rendered structure."""
    data = build_findings_json(findings if findings is not None else load_findings())
    # `captured:` parses out of YAML as a date; render it (and any stray date) as ISO.
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")
    logger.info("wrote %d findings to %s", data["count"], path)
    return data
