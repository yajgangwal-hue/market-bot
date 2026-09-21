"""Is the terminal 'available value' real price, or the 0.652% haircut?
Compares the cap bar's OPEN against its RAW close (no haircut) and
against the booked exit (close x (1-0.652%)). Descriptive only.
"""
import sys
from statistics import fmean, median
sys.path.insert(0, "C:/market-bot/src"); sys.path.insert(0, "C:/market-bot/scripts")
from event_aware_trader.mean_reversion import MeanReversionConfig, conviction as sc
from event_aware_trader.phase5.metrics import measure
from event_aware_trader.research import production_report, PRODUCTION_CANDIDATE
from forensics_regime import load
_c = {}
def conviction(sym, h):
    k=(sym,len(h),h[0].timestamp if h else None)
    v=_c.get(k)
    if v is None: v=_c[k]=sc(h[-40:])
    return v
print("haircut in the production candidate:",
      PRODUCTION_CANDIDATE.get("rule_exit_timing_haircut"))
series = load()
rep = production_report(series, conviction=conviction, dataset="decade",
                        purpose="rejection_test", mr_config=MeanReversionConfig())
m = measure(rep,"B").as_dict()
assert abs(m["total_return"]-0.585889)<5e-7 and m["trades"]==698
idx={s:{b.timestamp.date():i for i,b in enumerate(bs)} for s,bs in series.items()}
o_vs_rawclose, o_vs_booked, booked_vs_raw = [], [], []
usd_raw = usd_booked = 0.0
n=0
for t in rep.trades:
    if t.exit_reason!="time_exit": continue
    bs=series[t.symbol]; i1=idx[t.symbol].get(t.exit_time.date())
    if i1 is None: continue
    cap_open, cap_close = bs[i1].open, bs[i1].close
    if cap_open<=0 or cap_close<=0: continue
    o_vs_rawclose.append(cap_open/cap_close-1.0)
    o_vs_booked.append(cap_open/t.exit_price-1.0)
    booked_vs_raw.append(t.exit_price/cap_close-1.0)
    usd_raw += max(0.0,cap_open-cap_close)*t.quantity
    usd_booked += max(0.0,cap_open-t.exit_price)*t.quantity
    n+=1
print("cap-bar trades:",n)
print("\n  booked exit vs RAW close      mean {0:+.4%}  (this is the haircut)".format(fmean(booked_vs_raw)))
print("  cap OPEN vs BOOKED exit       mean {0:+.4%}  median {1:+.4%}   $ {2:,.0f}".format(
    fmean(o_vs_booked), median(o_vs_booked), usd_booked))
print("  cap OPEN vs RAW close         mean {0:+.4%}  median {1:+.4%}   $ {2:,.0f}".format(
    fmean(o_vs_rawclose), median(o_vs_rawclose), usd_raw))
share = 1.0 - fmean(o_vs_rawclose)/fmean(o_vs_booked)
print("\n  -> share of the terminal 'gain' that is purely the haircut: {0:.1%}".format(share))
