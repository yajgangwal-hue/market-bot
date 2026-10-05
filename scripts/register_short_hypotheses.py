"""Register H-0027..H-0030: seal them BEFORE any outcome is computed.

Refuses unless the registration chain is intact, every hypothesis passes the
dataset gate's registration check, and none of the four IDs exists yet.

The owner has not authorised commits, so `code_commit` is the pre-existing
HEAD and the code is bound by the SHA-256 of every file in spec.CODE_FILES,
which the seal covers. run_short_hypotheses.py recomputes those hashes and
refuses to run if any file has changed since this registration.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                  # noqa: E402
from event_aware_trader.research import search_size             # noqa: E402

import research_gate                                             # noqa: E402
import short_hypotheses_spec as spec                             # noqa: E402


def main():
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    existing = {p["hypothesis_id"] for p in prereg.load()}
    hypotheses = spec.hypotheses()
    for h in hypotheses:
        if h.hypothesis_id in existing:
            print("REFUSED: {0} is already registered.".format(h.hypothesis_id))
            return 2
        problems = research_gate.check_registration(h)
        if problems:
            print("REFUSED {0}: {1}".format(h.hypothesis_id, "; ".join(problems)))
            return 2
    print("trials already counted (experiments + registrations): {0}".format(
        search_size() + prereg.declared_trials()))
    for h in hypotheses:
        row = prereg.register(h)
        p = row["payload"]
        print("registered {0}  seal {1}  at {2}".format(p["hypothesis_id"], p["seal"], p["registered_at"]))
    print("code sha256: {0}".format(spec.code_hashes()))
    print("chain: {0}".format(prereg.verify_chain()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
