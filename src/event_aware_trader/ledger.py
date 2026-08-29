"""A persistent equity balance that carries across runs.

Every test so far started at a fresh $1,000, which makes runs incomparable:
a run that made $35 and a run that lost $35 both reported "$1,000 start", and
nothing accumulated.  This keeps one balance on disk, so a run that ends at
$1,035 is the run that the next one begins with, and the sequence of runs is
itself a record.

Compounding is the point and also the risk: position sizing is a percentage
of equity, so a run that grows the balance also grows the next run's absolute
risk.  That is correct behaviour, and it means a bad sequence compounds too.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class LedgerRun:
    label: str
    started_at: str
    opening_equity: float
    closing_equity: float
    trades: int
    wins: int
    note: str = ""

    @property
    def pnl(self) -> float:
        return self.closing_equity - self.opening_equity

    @property
    def return_fraction(self) -> float:
        return (self.closing_equity / self.opening_equity - 1.0) if self.opening_equity else 0.0


@dataclass
class Ledger:
    starting_equity: float = 1_000.0
    current_equity: float = 1_000.0
    runs: List[LedgerRun] = field(default_factory=list)

    @property
    def total_pnl(self) -> float:
        return self.current_equity - self.starting_equity

    @property
    def total_return(self) -> float:
        return (self.current_equity / self.starting_equity - 1.0) if self.starting_equity else 0.0

    def record(
        self,
        label: str,
        closing_equity: float,
        trades: int,
        wins: int,
        note: str = "",
    ) -> LedgerRun:
        """Append a run and roll the balance forward to where it ended."""
        if closing_equity < 0:
            raise ValueError("closing_equity cannot be negative")
        run = LedgerRun(
            label=label,
            started_at=datetime.now(timezone.utc).isoformat(),
            opening_equity=self.current_equity,
            closing_equity=closing_equity,
            trades=trades,
            wins=wins,
            note=note,
        )
        self.runs.append(run)
        self.current_equity = closing_equity
        return run

    def as_dict(self) -> Dict[str, object]:
        return {
            "starting_equity": round(self.starting_equity, 2),
            "current_equity": round(self.current_equity, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_return_pct": round(100 * self.total_return, 3),
            "run_count": len(self.runs),
            "runs": [
                {
                    **asdict(run),
                    "pnl": round(run.pnl, 2),
                    "return_pct": round(100 * run.return_fraction, 3),
                }
                for run in self.runs
            ],
        }


def load_ledger(path: Path, starting_equity: float = 1_000.0) -> Ledger:
    """Load the balance, or open a fresh one at ``starting_equity``."""
    if not path.exists():
        return Ledger(starting_equity=starting_equity, current_equity=starting_equity)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Ledger(
        starting_equity=float(raw.get("starting_equity", starting_equity)),
        current_equity=float(raw.get("current_equity", starting_equity)),
        runs=[
            LedgerRun(
                label=str(item["label"]),
                started_at=str(item["started_at"]),
                opening_equity=float(item["opening_equity"]),
                closing_equity=float(item["closing_equity"]),
                trades=int(item.get("trades", 0)),
                wins=int(item.get("wins", 0)),
                note=str(item.get("note", "")),
            )
            for item in raw.get("runs", [])
        ],
    )


def save_ledger(path: Path, ledger: Ledger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(ledger.as_dict())
    payload["note"] = "Simulated balance carried between runs. Not a brokerage statement."
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def reset_ledger(path: Path, starting_equity: float = 1_000.0) -> Ledger:
    ledger = Ledger(starting_equity=starting_equity, current_equity=starting_equity)
    save_ledger(path, ledger)
    return ledger
