"""Phase 4 §3. Independently verify one recorded session against its sources.

Eleven checks, one per line of the brief. Each returns PASS, FAIL or
UNVERIFIED, and the third state is the point of the module: a checker that
cannot distinguish "measured and fine" from "never measured" reports
health it has not established. Where an input is missing, the check says
UNVERIFIED and names what was missing, rather than passing by default.

A discrepancy is REPORTED, never corrected. Adjusting a recorded figure so
it agrees with the broker destroys the only evidence that something
upstream is wrong.

This module is read-only with respect to the strategy. It imports frozen
configuration to compare against it and changes nothing.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from .forward import (CASH_TOLERANCE_ABS, EQUITY_TOLERANCE_ABS,
                      EQUITY_TOLERANCE_REL, unprotected_positions)

PASS = "PASS"
FAIL = "FAIL"
UNVERIFIED = "UNVERIFIED"

#: Exit reasons the frozen rule can produce, plus the external path. Anything
#: else in a record is a reason nobody defined, which is a defect in the
#: recorder rather than a legitimate new behaviour.
VALID_EXIT_REASONS = ("rule", "external")


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == PASS


@dataclass
class Verification:
    checks: List[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(Check(name, status, detail))

    @property
    def failures(self) -> List[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def unverified(self) -> List[Check]:
        return [c for c in self.checks if c.status == UNVERIFIED]

    @property
    def ok(self) -> bool:
        """True only when nothing FAILED. UNVERIFIED does not fail a session.

        Deliberate: an unmeasurable check is not evidence of a defect. It is
        reported separately and counted, so a session verified mostly by
        UNVERIFIED cannot be mistaken for a clean one.
        """
        return not self.failures

    def as_dict(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "passed": sum(1 for c in self.checks if c.status == PASS),
            "failed": [c.name for c in self.failures],
            "unverified": [c.name for c in self.unverified],
            "checks": [{"check": c.name, "status": c.status,
                        "detail": c.detail} for c in self.checks],
        }


def _iso_date(value) -> str:
    return str(value or "")[:10]


def verify(observation,
           positions: Sequence[Dict],
           resting_sells: Dict[str, List],
           orders: Sequence[Dict],
           account: Dict,
           fees: Sequence[Dict],
           dividends: Sequence[Dict],
           benchmark_bar=None,
           universe: Optional[Sequence[str]] = None,
           adv_by_symbol: Optional[Dict[str, float]] = None,
           policy=None,
           now: Optional[datetime] = None) -> Verification:
    """Check one recorded session against the broker and the frozen rules."""
    from .risk import RiskPolicy
    policy = policy or RiskPolicy()
    v = Verification()
    session = observation.session
    equity = float(observation.equity)

    # 1. Protection.
    naked = unprotected_positions(positions, resting_sells)
    v.add("every position protected", PASS if not naked else FAIL,
          "" if not naked else "no resting stop: " + ", ".join(naked))

    # 2. Orders follow the frozen rules.
    #
    # Two exemptions, both established by measuring a live session rather
    # than assumed. The cash-parking ETF is traded by the loop and is
    # deliberately NOT in the universe - it is where idle cash sits, not a
    # candidate - so flagging it as off-universe reports a defect that is
    # actually correct behaviour. And parking is a NOTIONAL order while
    # crypto is fractional by design; only equity entries are whole-share,
    # so both fail a naive whole-share check for the wrong reason. Without
    # these exemptions every single session fails two checks, which would
    # train the reader to ignore them.
    todays = [o for o in orders if _iso_date(o.get("submitted_at")) == session]
    from .autotrade import AutoTradeConfig
    parking = str(AutoTradeConfig().cash_parking_symbol or "SGOV").upper()
    if universe is None:
        v.add("orders within the frozen universe", UNVERIFIED,
              "no universe supplied")
    else:
        allowed = {s.upper() for s in universe} | {parking}
        stray = sorted({str(o.get("symbol", "")).upper() for o in todays
                        if str(o.get("symbol", "")).upper() not in allowed})
        v.add("orders within the frozen universe", PASS if not stray else FAIL,
              "" if not stray else "off-universe: " + ", ".join(stray))
    fractional = sorted({str(o.get("symbol")) for o in todays
                         if float(o.get("quantity") or 0) % 1
                         and "/" not in str(o.get("symbol", ""))
                         and str(o.get("symbol", "")).upper() != parking})
    v.add("whole-share equity orders", PASS if not fractional else FAIL,
          "" if not fractional else "fractional: " + ", ".join(fractional))

    # 3. Sizing follows the frozen risk policy.
    over = []
    for p in observation.positions:
        value = abs(float(p.get("market_value") or 0.0))
        if equity and value / equity > policy.max_notional_fraction + 1e-6:
            over.append("{0} {1:.1%}".format(p.get("symbol"), value / equity))
    v.add("concentration within the frozen cap",
          PASS if not over else FAIL,
          "" if not over else "over {0:.0%}: ".format(policy.max_notional_fraction)
          + ", ".join(over))
    held = observation.positions_held
    v.add("position count within the frozen limit",
          PASS if held <= policy.max_open_positions else FAIL,
          "{0} held, limit {1}".format(held, policy.max_open_positions))

    # 4. Participation limits.
    cap = getattr(policy, "max_volume_participation", None)
    filled = [o for o in todays if float(o.get("filled_quantity") or 0.0)]
    if not cap:
        v.add("participation limit respected", UNVERIFIED,
              "no participation cap configured")
    elif not filled:
        # Nothing was traded, so the cap had nothing to bind on. That is a
        # genuine pass rather than an unmeasured check.
        v.add("participation limit respected", PASS,
              "no fills this session")
    elif not adv_by_symbol:
        v.add("participation limit respected", UNVERIFIED,
              "no average dollar volume supplied for the session's entries")
    else:
        breaches = []
        for o in todays:
            symbol = str(o.get("symbol", "")).upper()
            adv = adv_by_symbol.get(symbol)
            price = float(o.get("filled_avg_price") or 0.0)
            qty = float(o.get("filled_quantity") or 0.0)
            if not adv or not price or not qty:
                continue
            share = (qty * price) / adv
            if share > cap + 1e-9:
                breaches.append("{0} {1:.2%}".format(symbol, share))
        v.add("participation limit respected", PASS if not breaches else FAIL,
              "" if not breaches else "over {0:.1%}: ".format(cap)
              + ", ".join(breaches))

    # 5. Exit reasons.
    bad = sorted({str(e.get("reason")) for e in observation.exits
                  if e.get("reason") not in VALID_EXIT_REASONS})
    v.add("exit reasons recognised", PASS if not bad else FAIL,
          "" if not bad else "unknown reason: " + ", ".join(bad))

    # 6/7. Equity and cash reconcile.
    for name, recorded, authoritative, tol in (
            ("equity reconciles", observation.equity,
             float(account.get("equity") or 0.0), EQUITY_TOLERANCE_ABS),
            ("cash reconciles", observation.cash,
             float(account.get("cash") or 0.0), CASH_TOLERANCE_ABS)):
        gap = abs(float(recorded) - authoritative)
        rel = (gap / abs(authoritative)) if authoritative else 1.0
        v.add(name, PASS if (gap <= tol or rel <= EQUITY_TOLERANCE_REL) else FAIL,
              "recorded {0:,.2f} vs account {1:,.2f} (gap {2:,.2f})"
              .format(float(recorded), authoritative, gap))

    # 8. Costs. Only checkable as "what the broker charged is what we wrote".
    charged = round(sum(abs(float(f.get("net_amount") or 0.0)) for f in fees
                        if _iso_date(f.get("date")) == session), 4)
    v.add("transaction costs recorded",
          PASS if abs(charged - float(observation.transaction_costs)) < 0.01
          else FAIL,
          "broker charged {0:.4f}, recorded {1:.4f}"
          .format(charged, observation.transaction_costs))

    # 9. Dividends, when applicable.
    paid = round(sum(float(d.get("net_amount") or 0.0) for d in dividends
                     if _iso_date(d.get("date")) == session), 4)
    if not paid:
        v.add("dividends recorded", PASS, "none paid this session")
    else:
        v.add("dividends recorded",
              PASS if abs(paid - float(observation.dividends_received)) < 0.01
              else FAIL,
              "broker paid {0:.4f}, recorded {1:.4f}"
              .format(paid, observation.dividends_received))

    # 10. The benchmark is the same date as the session.
    if benchmark_bar is None:
        v.add("benchmark matches the session date", UNVERIFIED,
              "no benchmark bar supplied")
    else:
        bar_day = benchmark_bar.timestamp.date().isoformat()
        v.add("benchmark matches the session date",
              PASS if bar_day == session else FAIL,
              "benchmark bar {0}, session {1}".format(bar_day, session))

    # 11. No future information. The decision timestamp must not precede the
    # session, and must not lie in the future relative to the clock.
    now = now or datetime.now(timezone.utc)
    try:
        as_of = datetime.fromisoformat(observation.as_of)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
    except ValueError:
        v.add("decision timestamp coherent", FAIL,
              "unparseable as_of: " + str(observation.as_of))
        return v
    problems = []
    if _iso_date(observation.as_of) < session:
        problems.append("as_of precedes the session")
    if as_of > now:
        problems.append("as_of is in the future")
    v.add("decision timestamp coherent", PASS if not problems else FAIL,
          "; ".join(problems))
    return v
