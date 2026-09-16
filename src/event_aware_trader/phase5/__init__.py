"""Track B. Quarantined profitability research.

Phase 5 runs two tracks that must never touch. Track A is the frozen
forward evaluation from Phase 4: one configuration, one fingerprint, one
append-only record, and no verdict until years of clean sessions exist.
Track B - this package - is where the search for a materially more
profitable strategy happens, and it is allowed to fail loudly and often.

The separation is enforced in three places rather than promised:

  SEPARATE LEDGER    Phase 5 experiments are written to their own file.
                     The frozen evaluation derives its freeze date from
                     the production registry, so a Phase 5 row landing
                     there could silently reset Track A's embargo clock
                     and invalidate the clean record. `ledger.py` writes
                     somewhere else and a test proves the freeze cannot
                     move.

  SEPARATE PURPOSE   every historical window is CONTAMINATED for the
                     current candidate. Phase 5 may therefore only use
                     them to reject or to diagnose. A good result on the
                     decade is a hypothesis, never an acceptance.

  NO PRODUCTION WRITE  nothing in this package imports into the live loop
                     and nothing here changes a frozen parameter. A
                     promotion is a future phase's decision, with a new
                     fingerprint and a restarted evaluation.
"""
