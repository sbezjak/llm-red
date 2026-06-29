"""Loads and validates the attack catalog under data/attacks/.

Pure data, no network. One YAML file per attack family; each file declares its
`family` and a list of `attacks`. The attack-construction seam: deterministic
given the payload data, so a catalog error can never look like a detection bug.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ATTACKS_DIR = DATA_DIR / "attacks"

_REQUIRED_FIELDS = ("id", "payload", "bypass_when", "safe_when")


@dataclass(frozen=True)
class Attack:
    """One adversarial payload plus a human-readable bypass/safe intent.

    `bypass_when` / `safe_when` are documentation, not executable checks. The
    machine-readable bridge that ties them to the detector is `success_markers`:
    the literal token(s) whose presence in a
    response the detector reads as a bypass (e.g. `PWNED`). Empty when the
    family has no clean output token - obfuscation/multilingual instead use the
    guard-evasion detector, which keys off the target's (non-)refusal, not a
    marker. The prose fields stay as the human intent; the detector owns the
    verdict logic, so the catalog still declares intent without coupling to it.
    """

    id: str
    family: str
    payload: str
    bypass_when: str
    safe_when: str
    success_markers: tuple[str, ...] = ()


def load_attacks(directory: Path = ATTACKS_DIR) -> list[Attack]:
    """Load every *.yaml under `directory` into validated Attack records.

    Validates: each file declares `family`, each attack has the required
    fields, the attack's family matches its file (catches a payload pasted into
    the wrong file), and ids are unique across the whole catalog.
    """
    attacks: list[Attack] = []
    seen_ids: set[str] = set()

    for path in sorted(directory.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text()) or {}
        family = doc.get("family")
        if not family:
            raise ValueError(f"{path.name}: missing top-level 'family'")

        for entry in doc.get("attacks", []):
            missing = [f for f in _REQUIRED_FIELDS if not entry.get(f)]
            if missing:
                raise ValueError(f"{path.name}: attack {entry.get('id', '?')} missing {missing}")
            if "family" in entry and entry["family"] != family:
                raise ValueError(
                    f"{path.name}: attack {entry['id']} declares family "
                    f"{entry['family']!r} but lives in {family!r}'s file"
                )
            if entry["id"] in seen_ids:
                raise ValueError(f"duplicate attack id: {entry['id']}")
            seen_ids.add(entry["id"])

            attacks.append(
                Attack(
                    id=entry["id"],
                    family=family,
                    payload=entry["payload"],
                    bypass_when=entry["bypass_when"],
                    safe_when=entry["safe_when"],
                    success_markers=tuple(entry.get("success_markers") or ()),
                )
            )

    families = sorted({a.family for a in attacks})
    logger.info(
        "loaded %d attacks across %d families (%s) from %s",
        len(attacks),
        len(families),
        ", ".join(families),
        directory,
    )
    return attacks
