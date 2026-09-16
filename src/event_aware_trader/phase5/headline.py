"""A deliberately small, auditable headline matcher for single stocks.

WHY THIS EXISTS RATHER THAN REUSING events.classify_headline. That
classifier is a MACRO one: its stances are hawkish, dovish, risk_on and
risk_off, and its categories are inflation, central_bank, energy,
geopolitics. Asked about "Apple beats earnings estimates" it correctly
returns stance `neutral`, because a company beating estimates is not a
hawkish or dovish event. Using it as a stock-direction signal would
silently return neutral for every headline and the resulting feature
would be a column of zeros that looks like evidence of "no effect" when
it is really evidence of the wrong instrument.

WHAT THIS IS. A keyword matcher over the headline only. It does not read
the article, does not handle negation ("not raising guidance" matches
`raises guidance` on the bullish list only by the words present), does
not know sarcasm, and does not know whether the market already priced the
story. It is reported as a keyword matcher everywhere it is used, and it
is allowed to find nothing.

WHAT IT IS NOT. It is not sentiment analysis, and a score from it is not
evidence of predictive value. The brief is explicit that adding a
positive/negative score and declaring it useful is the failure mode to
avoid. This exists so that a specific question - does adverse news before
an oversold entry predict a worse outcome - can be ASKED. The answer is
whatever the measurement says.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

BEARISH: Tuple[str, ...] = (
    "downgrade", "downgraded", "cuts guidance", "cut guidance",
    "lowers guidance", "lowered guidance", "misses", "missed estimates",
    "profit warning", "warns", "warning", "plunge", "plunges", "plummet",
    "tumbles", "slumps", "sinks", "slides", "falls short", "disappointing",
    "recall", "lawsuit", "sued", "investigation", "probe", "subpoena",
    "sec charges", "fraud", "layoffs", "job cuts", "restructuring",
    "bankruptcy", "chapter 11", "default", "delisting", "halted",
    "resigns", "steps down", "ousted", "short seller", "fda rejects",
    "complete response letter", "trial failure", "discontinues",
    "loses contract", "antitrust", "fined", "penalty", "data breach",
)

BULLISH: Tuple[str, ...] = (
    "upgrade", "upgraded", "raises guidance", "raised guidance",
    "boosts guidance", "beats", "beat estimates", "tops estimates",
    "record revenue", "record profit", "surges", "soars", "jumps",
    "rallies", "buyback", "share repurchase", "dividend increase",
    "raises dividend", "acquisition", "to acquire", "merger", "takeover",
    "fda approval", "approved", "wins contract", "awarded", "partnership",
    "expands", "new product", "price target raised", "initiated at buy",
    "outperform", "strong demand",
)

#: Words that flip a match. Crude, and declared as crude: this catches
#: "not approved" and "fails to beat", not every construction English has.
NEGATORS: Tuple[str, ...] = ("not ", "no ", "fails to ", "failed to ",
                             "without ", "denies ", "denied ")


@dataclass
class HeadlineLabel:
    direction: str            # "adverse", "favourable", "mixed", "none"
    bearish_hits: List[str]
    bullish_hits: List[str]
    conflicted: bool

    @property
    def adverse(self) -> bool:
        return self.direction == "adverse"

    @property
    def favourable(self) -> bool:
        return self.direction == "favourable"


def _hits(text: str, terms: Sequence[str]) -> List[str]:
    found = []
    for term in terms:
        index = text.find(term)
        if index < 0:
            continue
        preceding = text[max(0, index - 14):index]
        if any(preceding.endswith(n) for n in NEGATORS):
            continue
        found.append(term)
    return found


def label(headline: str) -> HeadlineLabel:
    text = " " + re.sub(r"\s+", " ", (headline or "").lower()).strip() + " "
    bear, bull = _hits(text, BEARISH), _hits(text, BULLISH)
    if bear and bull:
        direction, conflicted = "mixed", True
    elif bear:
        direction, conflicted = "adverse", False
    elif bull:
        direction, conflicted = "favourable", False
    else:
        direction, conflicted = "none", False
    return HeadlineLabel(direction, bear, bull, conflicted)


def summarise(headlines: Sequence[str]) -> Dict[str, int]:
    """Counts by direction over a set of headlines, plus the net."""
    out = {"adverse": 0, "favourable": 0, "mixed": 0, "none": 0}
    for text in headlines:
        out[label(text).direction] += 1
    out["net"] = out["favourable"] - out["adverse"]
    out["matched"] = out["adverse"] + out["favourable"] + out["mixed"]
    return out
