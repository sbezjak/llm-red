import datetime
import logging

import pytest

logging.getLogger("llm_red").setLevel(logging.INFO)
# Test-support components (the fake target provider) log prompt/response too, so
# their I/O shows up in the report alongside the real provider's.
logging.getLogger("tests").setLevel(logging.INFO)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Structural no-overwrite guarantee for the HTML report.

    Findings here are non-deterministic, so a run that surfaced a real bypass must
    never be clobbered by the next run. pyproject's `addopts` points `--html` at the
    fixed `reports/report.html`, which the next run would overwrite. So before
    pytest-html reads the path, we rewrite the DEFAULT path to a unique
    `reports/report-<UTC timestamp>.html`. tryfirst, so this runs before pytest-html's
    own configure captures the path.

    A run whose report should be COMMITTED passes its own descriptive `--html`
    (e.g. `--html=reports/report-findings.html`); that is not the default, so we leave
    it untouched. The auto-timestamped files are gitignored (see .gitignore); the
    descriptively-named ones are committed. See CLAUDE.md / PLAN.md (report-archiving
    rule) and the save-reproduced-transcripts discipline.
    """
    htmlpath = getattr(config.option, "htmlpath", None)
    if htmlpath in (None, "reports/report.html"):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        config.option.htmlpath = f"reports/report-{stamp}.html"
