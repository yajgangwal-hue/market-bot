# Datasheet: futures-proxies-yahoo-2006-2026-20

*Acquired 2026-10-05 UTC (2026-10-04 Pacific) by `scripts/h0039_acquire.py`
for H-0039, before H-0039 was registered. Identity: SHA-256
`dc1d1049c62f4cf0f86b2e31eb359b1f1f9c73f7be1727aa886f8ea473958042`, 20 files.
Load it only through `research_gate.verify_dataset`.*

## What it is

One raw Yahoo Finance chart payload per symbol: daily bars from 2006-01-03 (or
the fund's first day) to 2026-10-02, with the close and the split- and
dividend-adjusted close. The bytes are exactly as received; nothing was
edited.

| File | Fund | Stands for (futures market) | Asset class | First day |
|---|---|---|---|---|
| SPY.json | SPDR S&P 500 | S&P 500 index futures (Micro E-mini) | equity | 2006-01-03 |
| QQQ.json | Invesco QQQ | Nasdaq-100 index futures (Micro E-mini) | equity | 2006-01-03 |
| IWM.json | iShares Russell 2000 | Russell 2000 index futures (Micro E-mini) | equity | 2006-01-03 |
| DIA.json | SPDR Dow Jones | Dow index futures (Micro E-mini) | equity | 2006-01-03 |
| SHY.json | iShares 1-3 Year Treasury | 2-year Treasury note futures | rates | 2006-01-03 |
| IEF.json | iShares 7-10 Year Treasury | 10-year Treasury note futures | rates | 2006-01-03 |
| TLT.json | iShares 20+ Year Treasury | Treasury bond futures | rates | 2006-01-03 |
| GLD.json | SPDR Gold Shares | gold futures (micro) | metals | 2006-01-03 |
| SLV.json | iShares Silver | silver futures (micro) | metals | 2006-04-28 |
| DBB.json | Invesco DB Base Metals | copper futures (micro) | metals | 2007-01-05 |
| USO.json | United States Oil Fund | WTI crude oil futures (micro) | energy | 2006-04-10 |
| UNG.json | United States Natural Gas Fund | Henry Hub natural gas futures | energy | 2007-04-18 |
| DBA.json | Invesco DB Agriculture | grain futures | agriculture | 2007-01-05 |
| FXE.json | Invesco CurrencyShares Euro | euro futures (micro) | currency | 2006-01-03 |
| FXY.json | Invesco CurrencyShares Yen | yen futures (micro) | currency | 2007-02-13 |
| FXB.json | Invesco CurrencyShares Pound | pound futures (micro) | currency | 2006-06-26 |
| FXA.json | Invesco CurrencyShares Australian Dollar | Australian dollar futures (micro) | currency | 2006-06-26 |
| FXC.json | Invesco CurrencyShares Canadian Dollar | Canadian dollar futures (micro) | currency | 2006-06-26 |
| FXF.json | Invesco CurrencyShares Swiss Franc | Swiss franc futures (micro) | currency | 2006-06-26 |
| IRX.json | ^IRX, 13-week Treasury bill yield | the cash return | cash | 2006-01-03 |

The "first day" column is the first bar with an adjusted close in the payload.

## Why funds, and what that costs in accuracy

Free futures history comes as front-month prices spliced at each roll. The
splice jumps at every roll, and those jumps are not returns. Funds have
clean, dividend-adjusted total returns, and a fund's total return minus the
Treasury-bill return approximates the matching futures position's return.

The approximation has known gaps:

- **Fees.** Each fund's expense ratio is already deducted from its returns
  (about 0.1%-0.9% a year), which futures do not charge. This makes the funds
  look slightly worse than the futures they stand for.
- **Commodity funds hold futures themselves.** USO, UNG, DBA and DBB roll
  futures contracts, so their returns include roll costs and contango. That
  is realistic. USO changed how it rolls in April-May 2020, during the
  negative-oil-price episode.
- **Currency funds** hold foreign-currency deposits, so their returns include
  the foreign deposit rate. That is close to what a currency future earns
  over cash, less the fund's fee.
- **Bond funds** do not match a futures contract's duration exactly.
- **DBB** is a basket of aluminium, zinc and copper standing in for copper,
  and **DBA** is a basket of farm goods standing in for grains.
- **Yahoo's adjusted close** is recomputed backwards from each later dividend
  and split. The ratio between consecutive days is the total return.

## Information boundary

- The bars run through 2026-10-02.
- This is a new strategy family, so no Clean OOS record exists for it.
- Nothing here touches the stock strategy's forward record.
- Evidence class: `historical_in_sample`. These data can reject a futures
  strategy but cannot, by themselves, accept one.

## Provenance

- **Request:** `query1.finance.yahoo.com/v8/finance/chart/<symbol>`, interval
  1d, from 2006-01-01 to 2026-10-03 UTC, events `div,split`, adjusted close
  included. No credential.
- **Each file's details** are in the manifest: URL, HTTP status, size,
  SHA-256 and point count.
- **Two fetches minutes apart returned slightly different byte counts** for
  some symbols. The payload's metadata block changes between requests, so
  this copy is identified by its own hashes, not by re-fetching.
