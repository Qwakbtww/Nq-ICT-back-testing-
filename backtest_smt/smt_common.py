"""Shared helpers: freeze verification (spec, clarifications, calendar) for every SMT script."""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _check(sha_file):
    for line in open(os.path.join(HERE, sha_file)).read().strip().splitlines():
        want, name = line.split()
        got = hashlib.sha256(open(os.path.join(HERE, os.path.basename(name)), "rb").read()).hexdigest()
        if got != want:
            sys.exit(f"{name} changed since the freeze ({got} != {want}); refusing to run.")


def verify_freeze():
    """Refuse to run if SPEC_v1.md, SPEC_v1_CLARIFICATIONS.md or calendar_skip_days.csv changed."""
    _check("SPEC.sha256")
    _check("CALENDAR.sha256")
