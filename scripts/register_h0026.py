"""Register H-0026: seal it BEFORE any outcome is computed.

Refuses unless:
- the registration chain is intact;
- the dataset gate accepts the registration;
- the trial count in the spec equals what the ledgers hold now, plus one;
- every H-0026 code file is committed and unchanged, so the recorded
  code_commit is the code that will run.

prereg.register() refuses a second H-0026 by itself.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                  # noqa: E402
from event_aware_trader.research import search_size             # noqa: E402

import h0026_spec as spec                                        # noqa: E402
import research_gate                                             # noqa: E402


def main():
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    hypothesis = spec.hypothesis()
    problems = research_gate.check_registration(hypothesis)
    if problems:
        print("REFUSED: " + "; ".join(problems))
        return 2
    counted = search_size() + prereg.declared_trials() + 1
    if counted != spec.DSR_TRIALS:
        print("REFUSED: the spec says N = {0} but the ledgers give {1}.".format(
            spec.DSR_TRIALS, counted))
        return 2
    dirty = subprocess.run(["git", "status", "--porcelain", "--"] + spec.CODE_FILES,
                           capture_output=True, text=True, cwd=REPO).stdout.strip()
    if dirty:
        print("REFUSED: commit the H-0026 code first:\n" + dirty)
        return 2
    row = prereg.register(hypothesis)
    payload = row["payload"]
    print("registered {0}".format(payload["hypothesis_id"]))
    print("  seal        {0}".format(payload["seal"]))
    print("  code commit {0}".format(payload["code_commit"]))
    print("  at          {0}".format(payload["registered_at"]))
    print("  digest      {0}".format(row["digest"]))
    print("  chain       {0}".format(prereg.verify_chain()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
