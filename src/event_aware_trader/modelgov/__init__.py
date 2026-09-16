"""Research-side machinery for deciding whether a learned model can be trusted.

NOT IN THE MONEY PATH. Nothing here is imported by the live loop, and
nothing here writes a model the live loop reads. It exists to answer one
question honestly - does this model have out-of-sample predictive value -
and the answer is allowed to be no.

Three modules, in the order they are used:

  walkforward   the only admissible evaluation. Train strictly before
                test, purge the examples whose outcome window straddles
                the boundary, embargo the horizon after it, and score the
                EXACT model that would have been deployed at that moment.

  trust         the gate. Train/test gap, calibration, stability across
                folds and regimes, and a shuffled-label control that must
                fail. A model that cannot beat its own shuffled control is
                not measuring anything.

  lineage       the record. Every trained model gets an id, its intervals,
                its data and code versions, its information cutoff and its
                trust status, so "what did the model know when it made
                this decision" always has an answer.
"""
