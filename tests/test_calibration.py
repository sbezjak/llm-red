"""Well-formedness of the detector calibration specimens (data/calibration/).

These are hand-verified Gandalf transcripts (prompt + real response + a
bypass/safe label) used to calibrate the detector. This test guards the
ground-truth data itself; the detector-grades-them-correctly test lands with
the detector. Pure data, no network.
"""

from pathlib import Path

import yaml

CALIBRATION_DIR = Path(__file__).resolve().parent.parent / "data" / "calibration"

# The locked attack families - a calibration specimen must map to one of them,
# so a typo'd family is caught here rather than silently never matching a detector.
FAMILIES = {
    "direct_injection",
    "injection_indirect",
    "prompt_extraction",
    "jailbreak",
    "obfuscation",
}
REQUIRED = ("id", "level", "family", "prompt", "response", "verdict")


def test_gandalf_calibration_is_well_formed():
    doc = yaml.safe_load((CALIBRATION_DIR / "gandalf.yaml").read_text())
    specimens = doc["specimens"]
    assert specimens, "expected at least one calibration specimen"

    seen = set()
    for s in specimens:
        missing = [f for f in REQUIRED if not s.get(f)]
        assert not missing, f"{s.get('id', '?')} missing {missing}"
        assert s["verdict"] in ("bypass", "safe"), f"{s['id']}: bad verdict {s['verdict']!r}"
        assert s["family"] in FAMILIES, f"{s['id']}: unknown family {s['family']!r}"
        assert s["id"] not in seen, f"duplicate specimen id: {s['id']}"
        seen.add(s["id"])
