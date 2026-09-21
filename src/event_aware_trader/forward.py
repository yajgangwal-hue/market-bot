"""Phase 3. The clean out-of-sample record, isolated from research.

This module exists to make the forward evidence trustworthy BEFORE anyone
sees what it says. Everything here is about preventing three failures:

  FREEZE DRIFT     the configuration quietly changes mid-experiment, so the
                   record measures a moving target. Guarded by a fingerprint
                   over every frozen parameter (G15).

  BACKWARD FLOW    a clean observation reaches a research or optimisation
                   routine and silently becomes part of parameter selection,
                   which would spend the only uncontaminated data there is.
                   Guarded by a distinct type that research refuses (G16).

  RETROSPECTIVE EDIT   a recorded session is altered after the fact - the
                   most damaging failure, because nothing downstream can
                   detect it. Guarded by a hash chain: every record carries
                   the digest of the one before, so any edit anywhere breaks
                   every link after it (G16).

The hash chain is the part worth explaining. Append-only "by convention"
means append-only until somebody edits the file. Chaining each record to
its predecessor makes tampering detectable rather than merely discouraged -
`verify_chain` recomputes every link and reports the first break. It does
not make tampering impossible; nothing in a local file can. It makes it
impossible to tamper SILENTLY, which is the property that matters.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# The clean record. Deliberately NOT under docs/ with the experiment
# registry, and never written by research code.
FORWARD_LOG = Path("data/forward-evaluation.jsonl")

# The genesis link. A chain has to start somewhere, and a fixed value means
# the first record's digest is reproducible.
GENESIS = "0" * 64

# Sessions below which no verdict may be issued (G18). Sixty is about a
# quarter. Even that cannot resolve profitability - at ~6-9% annual
# volatility the standard error over 60 sessions exceeds the entire annual
# edge - so this is a floor on when the question may be ASKED, not a
# threshold at which the answer becomes reliable.
MINIMUM_SESSIONS_FOR_ANY_VERDICT = 60


class ForwardDataLeak(RuntimeError):
    """Raised when clean out-of-sample data reaches research code."""


class FrozenConfigChanged(RuntimeError):
    """Raised when the evaluation's configuration is not the frozen one."""


@dataclass(frozen=True)
class CleanObservation:
    """One clean forward session.

    A distinct type, not a dict, precisely so that research functions can
    refuse it by type rather than by inspecting its contents. A dict would
    flow anywhere.

    Every field is what the strategy actually knew or did at the time.
    Nothing here may be backfilled: `as_of` is the decision timestamp and a
    value that was not available then does not belong in the record.
    """
    session: str                      # ISO date of the trading session
    as_of: str                        # decision timestamp, UTC ISO
    config_fingerprint: str           # which frozen config produced this
    universe_size: int
    signals: int
    orders: int
    fills: int
    positions_held: int
    exposure: float                   # invested / equity
    cash: float
    equity: float
    transaction_costs: float
    dividends_received: float
    # THE COMBINED ACCOUNT's session return. Named before the account held
    # anything but the equity book; it is NOT the frozen candidate's return
    # and must never be reported as one. The account also carries a BTC
    # sleeve and parked cash, so use `equity_sleeve_return` for the
    # candidate. Kept under its original name rather than silently
    # repurposed, because quietly changing what a recorded field means is
    # the failure this evaluation exists to prevent.
    strategy_return: Optional[float]  # session return, None on the first day
    benchmark_return: Optional[float]
    # Per-name sizes, not merely a count. "Position sizing follows the frozen
    # risk policy" is one of the things each clean session must be checkable
    # against, and a count cannot be checked against a sizing rule.
    positions: List[Dict] = field(default_factory=list)
    exits: List[Dict] = field(default_factory=list)
    execution_discrepancies: List[str] = field(default_factory=list)
    data_quality_issues: List[str] = field(default_factory=list)

    # ---- sleeve accounting -------------------------------------------
    # One account, three books. The frozen candidate is the EQUITY sleeve
    # only; the BTC sleeve and parked cash are separately identifiable so
    # that no figure has to be reconstructed by subtracting one from the
    # other after the fact.
    #
    #   equity_sleeve_equity = account equity - crypto market value
    #     SGOV stays inside the equity sleeve: `reserved_fraction` is
    #     withheld from the equity book BEFORE the parking sweep, so
    #     parked cash is the equity book's own idle capital.
    #
    # `equity_sleeve_return` is the HEADLINE candidate metric and is net
    # of any external cash movement, so a deposit can never read as
    # performance.
    crypto_market_value: float = 0.0
    parking_market_value: float = 0.0
    reserved_fraction: float = 0.0
    cash_movements: float = 0.0          # deposits/withdrawals/journals
    equity_sleeve_equity: float = 0.0
    equity_sleeve_return: Optional[float] = None
    # The two closes the benchmark return was computed from, stored
    # because an adjusted series is RESTATED by the vendor on every new
    # distribution: a later fetch can legitimately return different
    # numbers for the same dates, and then the stored return would be
    # unreproducible. The split-adjusted pair is kept beside it so the
    # dividend component is auditable.
    benchmark_close: Optional[float] = None
    benchmark_prev_close: Optional[float] = None
    benchmark_close_split: Optional[float] = None
    benchmark_prev_close_split: Optional[float] = None
    benchmark_basis: str = "total_return_adjustment_all"

    def payload(self) -> Dict[str, object]:
        return asdict(self)


def _digest(payload: Dict[str, object], previous: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((previous + body).encode("utf-8")).hexdigest()


def config_digest(mr=None, policy=None, costs=None, live=None,
                  candidate=None) -> str:
    """The digest body. ONE definition, two callers.

    Called with no arguments it describes the DECLARED frozen
    configuration - the source defaults. Called with the objects a cycle
    actually ran on it describes THAT run.

    The distinction is the whole point. Until 2026-09-21 the fingerprint
    was only ever recomputed from defaults, on both sides of every check,
    so it could detect a change to the source and never a divergence
    between the source and the process that was trading. The runner was
    passing `--interval 15m` while the recorder stamped the digest of
    `interval="1d"`, and nothing could see it. See
    docs/2026-09-21-pre-oos-governance-audit.md.
    """
    from .autotrade import AutoTradeConfig
    from .mean_reversion import MeanReversionConfig
    from .research import PRODUCTION_CANDIDATE
    from .risk import CostModel, RiskPolicy

    mr = MeanReversionConfig() if mr is None else mr
    policy = RiskPolicy() if policy is None else policy
    costs = CostModel() if costs is None else costs
    live = AutoTradeConfig() if live is None else live
    candidate = PRODUCTION_CANDIDATE if candidate is None else candidate
    frozen = {
        "rule": {k: getattr(mr, k) for k in sorted(vars(mr))},
        "risk": {k: getattr(policy, k) for k in sorted(vars(policy))},
        "costs": {"half_spread_bps": costs.half_spread_bps,
                  "slippage_bps": costs.slippage_bps,
                  "commission_per_share": costs.commission_per_share},
        "live": {k: getattr(live, k, None) for k in
                 ("entry_rule", "entry_window_minutes", "max_orders_per_run",
                  "cash_parking_symbol", "cash_parking_floor",
                  "reserved_fraction", "live_model_floor", "interval")},
        "candidate": dict(sorted(candidate.items())),
        "embargo_sessions": _embargo(),
        "benchmark": {"risk_free": 0.0230,
                      "basis_pre_2016": "price_vs_price",
                      "basis_post_2016": "total_vs_total",
                      "dividends": "cash_not_reinvested",
                      "annualisation_days": 365.25},
    }
    body = json.dumps(frozen, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def frozen_fingerprint() -> str:
    """The DECLARED frozen configuration's digest.

    If any of these move, the fingerprint moves, and every session
    recorded afterwards is visibly from a different configuration. That
    is what makes G15 checkable rather than promised.

    This is the REFERENCE. What a run actually did is `config_digest`
    called with that run's own objects, and `append_session` refuses any
    observation whose stamp does not equal this value.
    """
    return config_digest()


def _embargo() -> int:
    from .purge import embargo_sessions
    return embargo_sessions()


def last_digest(path: Path = FORWARD_LOG) -> str:
    rows = _raw(path)
    return rows[-1]["digest"] if rows else GENESIS


def _raw(path: Path) -> List[Dict]:
    if not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def append_session(observation: CleanObservation,
                   path: Path = FORWARD_LOG,
                   expected_fingerprint: Optional[str] = None) -> Dict:
    """Append one clean session. Refuses to overwrite, refuses on drift.

    Two refusals, both deliberate:
      - a session already recorded cannot be recorded again, so a re-run
        cannot quietly replace an inconvenient day;
      - the observation's fingerprint must match the current frozen config,
        so a session cannot be filed under a configuration that has since
        moved.
    """
    path = Path(path)
    current = expected_fingerprint or frozen_fingerprint()
    if observation.config_fingerprint != current:
        raise FrozenConfigChanged(
            "observation was produced under fingerprint {0} but the current "
            "frozen configuration is {1}. The freeze has moved; the "
            "evaluation must be stopped and restarted, not continued."
            .format(observation.config_fingerprint[:12], current[:12]))

    existing = _raw(path)
    if any(r["payload"]["session"] == observation.session for r in existing):
        raise ForwardDataLeak(
            "session {0} is already recorded. The clean record is "
            "append-only; a result may not be revised after the fact."
            .format(observation.session))

    previous = existing[-1]["digest"] if existing else GENESIS
    payload = observation.payload()
    row = {"payload": payload, "previous": previous,
           "digest": _digest(payload, previous),
           "recorded_at": datetime.now(timezone.utc).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def verify_chain(path: Path = FORWARD_LOG) -> Dict[str, object]:
    """Recompute every link. Reports the FIRST break, not merely that one exists."""
    rows = _raw(path)
    previous = GENESIS
    for i, row in enumerate(rows):
        if row.get("previous") != previous:
            return {"intact": False, "sessions": len(rows), "broken_at": i,
                    "reason": "link {0} does not follow its predecessor".format(i)}
        expected = _digest(row["payload"], previous)
        if row.get("digest") != expected:
            return {"intact": False, "sessions": len(rows), "broken_at": i,
                    "reason": "record {0} was edited after it was written".format(i)}
        previous = row["digest"]
    return {"intact": True, "sessions": len(rows), "broken_at": None,
            "reason": "every link recomputes"}


def load_sessions(path: Path = FORWARD_LOG) -> List[CleanObservation]:
    """Read the clean record. Raises if the chain is broken.

    Refusing to return data from a tampered file is the point: a caller that
    gets rows back has, by construction, rows nobody edited.
    """
    check = verify_chain(path)
    if not check["intact"]:
        raise ForwardDataLeak(
            "the clean record is not intact: {0}. It cannot be used as "
            "evidence.".format(check["reason"]))
    return [CleanObservation(**r["payload"]) for r in _raw(path)]


# How deep to look for a smuggled observation. Research inputs are shallow
# structures - a dict of symbol -> bars, a config dict, a list of periods -
# so four levels reaches every realistic nesting without walking a large
# price series to no purpose.
_MAX_SCAN_DEPTH = 4


def reject_forward_data(*values, _depth: int = 0) -> None:
    """Guard for research entry points. Raises if handed clean observations.

    Called by research routines so the refusal is by TYPE: a
    CleanObservation cannot be mistaken for a dict of bars, and a list of
    them cannot be quietly averaged into a parameter sweep.

    It recurses, because the first version only checked the top level and a
    list's items. An observation nested one level deeper - inside a config
    dict, say - walked straight past it and failed later with a JSON
    serialisation error, which is a failure but not a refusal, and would
    have been no protection at all had the object been serialisable.
    """
    if _depth > _MAX_SCAN_DEPTH:
        return
    for value in values:
        if isinstance(value, CleanObservation):
            raise ForwardDataLeak(
                "a clean forward observation was passed to research code. "
                "Out-of-sample data may not influence parameter selection.")
        if isinstance(value, dict):
            reject_forward_data(*value.values(), _depth=_depth + 1)
        elif isinstance(value, (list, tuple, set)):
            reject_forward_data(*value, _depth=_depth + 1)


# ---------------------------------------------------------------------------
# G18. The system must refuse to reach a conclusion it cannot support.
# ---------------------------------------------------------------------------

VERDICTS = ("INSUFFICIENT_EVIDENCE", "MEASURED_NO_CONCLUSION")


@dataclass
class ForwardVerdict:
    """What the clean record supports, and explicitly what it does not.

    There is deliberately no "profitable" or "beats_benchmark" member. The
    type cannot express those conclusions, so no amount of favourable data
    can cause the code to emit one - the refusal is structural rather than a
    threshold somebody can lower.
    """
    verdict: str
    sessions: int
    required: int
    measured: Dict[str, object]
    uncertain: List[str]
    not_testable_yet: List[str]

    @property
    def may_conclude(self) -> bool:
        return False        # never, from this type

    def as_dict(self) -> Dict[str, object]:
        return {"verdict": self.verdict, "sessions": self.sessions,
                "required": self.required, "measured": self.measured,
                "uncertain": self.uncertain,
                "not_testable_yet": self.not_testable_yet,
                "note": ("This type cannot express profitability or "
                         "benchmark superiority. Sixty sessions is a floor "
                         "on asking, not a threshold at which the answer "
                         "becomes reliable.")}


def evaluate_forward(sessions: Sequence[CleanObservation],
                     minimum: int = MINIMUM_SESSIONS_FOR_ANY_VERDICT
                     ) -> ForwardVerdict:
    """Summarise the clean record without ever concluding from it."""
    n = len(sessions)
    rets = [s.strategy_return for s in sessions if s.strategy_return is not None]
    bench = [s.benchmark_return for s in sessions if s.benchmark_return is not None]

    measured: Dict[str, object] = {"clean_sessions": n}
    if rets:
        cum = 1.0
        for r in rets:
            cum *= 1 + r
        measured["cumulative_return"] = round(cum - 1, 6)
        measured["sessions_positive"] = sum(1 for r in rets if r > 0)
        measured["share_positive"] = round(
            sum(1 for r in rets if r > 0) / len(rets), 4)
        measured["mean_exposure"] = round(
            sum(s.exposure for s in sessions) / n, 4)
    if bench:
        cb = 1.0
        for r in bench:
            cb *= 1 + r
        measured["benchmark_cumulative_return"] = round(cb - 1, 6)

    uncertain = [
        "annualised statistics: not computed below {0} sessions - a CAGR "
        "from a handful of days is arithmetic, not evidence".format(minimum),
        "volatility, Sharpe and Sortino: too few observations to estimate",
        "the 0.652% exit-timing haircut remains a frozen BOUND, not a "
        "measurement, until ~30 eligible live rule exits have accrued",
    ]
    not_testable = [
        "whether the strategy is profitable",
        "whether it outperforms the S&P 500 on any basis",
        "whether the in-sample drawdown advantage persists",
        "whether the parameters chosen in-sample are correct",
    ]
    verdict = ("INSUFFICIENT_EVIDENCE" if n < minimum
               else "MEASURED_NO_CONCLUSION")
    return ForwardVerdict(verdict, n, minimum, measured, uncertain, not_testable)


# ---------------------------------------------------------------------------
# Phase 4. Eligibility, and reconciliation against the authoritative account.
# ---------------------------------------------------------------------------

# G20 tolerances, documented rather than implicit. Equity and cash are
# compared in dollars AND in relative terms; either passing is enough,
# because a $1 gap on $100,000 and a $1 gap on $10 are different claims.
EQUITY_TOLERANCE_ABS = 1.00
EQUITY_TOLERANCE_REL = 0.0001        # 1 basis point
CASH_TOLERANCE_ABS = 1.00
# Counts must match exactly. There is no sensible tolerance on "how many
# positions do we hold".
EXACT_FIELDS = ("positions_held",)


def first_clean_session(sessions: Sequence[date], registry_rows) -> Optional[date]:
    """The first session admissible as clean evidence, from the real calendar.

    Derived, never hard-coded: the freeze comes from the registry and the
    embargo from the strategy's own holding cap, so this answer moves only
    if the trading calendar moves or a genuine config change resets it.
    """
    from .purge import evaluation_window
    return evaluation_window(registry_rows, sessions).clean_from


def is_eligible(session: date, sessions: Sequence[date], registry_rows) -> bool:
    start = first_clean_session(sessions, registry_rows)
    return start is not None and session >= start


@dataclass
class Reconciliation:
    """G20. Recorded state against the authoritative account record."""
    checks: List[Dict[str, object]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.checks)

    @property
    def failures(self) -> List[Dict[str, object]]:
        return [c for c in self.checks if not c["ok"]]

    def add(self, name: str, recorded, authoritative, ok: bool,
            tolerance: str) -> None:
        self.checks.append({"check": name, "recorded": recorded,
                            "authoritative": authoritative, "ok": ok,
                            "tolerance": tolerance})

    def as_dict(self) -> Dict[str, object]:
        return {"ok": self.ok, "checks": self.checks,
                "failures": [c["check"] for c in self.failures]}


def reconcile(recorded: Dict[str, object],
              authoritative: Dict[str, object]) -> Reconciliation:
    """Compare a recorded session against the broker's own numbers.

    A discrepancy is returned, never corrected. Silently adjusting a
    recorded figure to match the broker would destroy the only signal that
    something upstream is wrong.
    """
    r = Reconciliation()
    for field_name in ("equity", "cash"):
        a = float(recorded.get(field_name, 0.0))
        b = float(authoritative.get(field_name, 0.0))
        gap = abs(a - b)
        abs_tol = EQUITY_TOLERANCE_ABS if field_name == "equity" else CASH_TOLERANCE_ABS
        rel_ok = (gap / abs(b) <= EQUITY_TOLERANCE_REL) if b else False
        r.add(field_name, a, b, gap <= abs_tol or rel_ok,
              "<= ${0:.2f} or {1:.2%}".format(abs_tol, EQUITY_TOLERANCE_REL))
    for field_name in EXACT_FIELDS:
        a, b = recorded.get(field_name), authoritative.get(field_name)
        r.add(field_name, a, b, a == b, "exact")
    return r


def is_protective(order: Dict) -> bool:
    """True only for an order that actually limits a loss.

    `open_sell_orders` returns EVERY resting sell, because Alpaca reserves
    the shares against any of them. That is the right question to ask
    before submitting an order and the wrong one to ask about safety: a
    bracket's take-profit LIMIT leg reserves the shares just as firmly as
    its stop leg and protects nothing on the way down. Counting it as
    protection is how a naked position reads as covered.
    """
    kind = str(order.get("type", "")).lower()
    return "stop" in kind or order.get("stop_price") is not None


def unprotected_positions(positions: Sequence[Dict],
                          resting_sells: Dict[str, List],
                          parking_symbol: str = "SGOV") -> List[str]:
    """Positions carrying no resting stop. Crypto and the parking ETF exempt.

    This is the check that found MDY naked overnight, so it runs on every
    clean session rather than when somebody thinks to look. Crypto is
    exempt because the sleeve is managed by its own worker rather than by
    resting broker stops; SGOV is exempt because it is parked cash.
    """
    out = []
    for p in positions:
        symbol = str(p.get("symbol", "")).upper()
        if "/" in symbol or symbol == parking_symbol.upper():
            continue
        if not any(is_protective(o) for o in resting_sells.get(symbol, ())):
            out.append(symbol)
    return sorted(out)


def eligible_sessions(calendar: Sequence[date], registry_rows) -> List[date]:
    """Every session admissible as clean evidence, from the real calendar."""
    start = first_clean_session(calendar, registry_rows)
    if start is None:
        return []
    return [d for d in sorted(calendar) if d >= start]


def continuity(recorded: Sequence[CleanObservation],
               calendar: Sequence[date], registry_rows) -> Dict[str, object]:
    """G22. Eligible sessions against recorded ones, with the gaps named.

    A missing session is reported, never filled. The whole value of the
    clean record is that it cannot be reconstructed after the fact, so a
    day the recorder did not capture stays a hole - visible, counted, and
    part of the evidence about how the experiment ran.
    """
    eligible = eligible_sessions(calendar, registry_rows)
    have = {o.session for o in recorded}
    missing = [d for d in eligible if d.isoformat() not in have]
    early = sorted(s for s in have
                   if not eligible or s < eligible[0].isoformat())
    return {
        "eligible": len(eligible),
        "recorded": len(have),
        "missing": [d.isoformat() for d in missing],
        "recorded_before_eligibility": early,
        "first_eligible": eligible[0].isoformat() if eligible else None,
        "complete": not missing and not early,
    }
