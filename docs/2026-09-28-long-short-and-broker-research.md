# Shorting and a second broker: researched, nothing built

*2026-09-28. Research only. No code was changed, nothing was backtested, no
broker was called, and nothing was committed. The owner asked:*

> "no research if the bot should be able to short and long and for optimal
> trading and also if i need to impliment a new broker so that it can paper
> trade futuers and also crypto and the normal market make no mistakes"

## The answers

| Question | Answer | In one line |
|---|---|---|
| Should the bot short as well as buy? | **No, not now** | All four of this project's registered shorting tests were rejected. The bot trails SPY because it holds too little stock, and shorts lower its market exposure further. |
| Does it need a new broker for stocks? | **No** | Alpaca paper already runs the stock strategy. |
| Does it need a new broker for crypto? | **No**, for buying and selling crypto | Alpaca paper already runs the 5% BTC sleeve. Shorting crypto is the exception: Alpaca can't do it, so it would need crypto futures. |
| Does it need a new broker for futures? | **Yes, but not yet** | Alpaca has no futures. There is also no tested futures strategy yet, so a broker would have nothing to run. |

## 1. Shorting

### What this project has already measured

Each row is a registered experiment in `docs/experiments.jsonl` with its own
write-up in `docs/`.

| | What was shorted | Result | Write-up |
|---|---|---|---|
| EXP-0011 | The mirror of the buy rule: RSI ≥ 70 below the 200-day average, cover at RSI ≤ 40, stop 2.5 ATR above | **+1.200% a trade** (1,217 signals, 1996–2026, net of 6 bps a side and 0.5%/yr borrow). As an account it lost: **−0.88% a year** over the decade and **−0.19% a year** over thirty years. | `2026-09-10-short-book-rejected.md` |
| EXP-0012 | The bot's own buy signals, turned into shorts | **−0.501% a trade** over 25,643 signals, 34% winners. The same trades as longs earned +0.903%. | `2026-09-10-shorting-the-signal-rejected.md` |
| EXP-0013 | Stocks after a violent open | Negative in all five buckets over 154,131 sessions. The most violent opens *rose* the most: +0.0997% to the close, so shorting them netted −0.2197%. | `2026-09-10-volatile-opens-rejected.md` |
| EXP-0026 | Violent opening gaps down; also gaps up held long, and both together; run as accounts over thirty years | **−49.8% to −64.2% a year** and a −100% drawdown in every variant | `2026-09-11-owner-ideas-priced.md` |

Two of them lost money on the average trade. The other two lost money once
they ran as whole accounts, one of them despite earning +1.2% a trade.

There is one older result, which is not a registered experiment. It was
measured on an earlier model-ranked version of the bot over 2021–2026 and is
recorded in the docstring of `src/event_aware_trader/regime_shorts.py`:

| Version | Six-year return |
|---|---:|
| Long only | +58.90% |
| With shorts all the time | −0.74% |
| Shorting only while SPY was below its 200-day average | +55.98% |

The bear-market version earned +17.57% in 2022, when long-only made +3.81%.
It gave back 12 points in 2023. It works as insurance that costs money in
ordinary years. It is off by default and not connected to the live bot.

### Why shorting fails here: structural reasons, not a setting

- **The bot's gap to SPY is exposure.** Over the decade, on average only
  44.3% of the account was invested, measured on 2026-09-16:
  - the strategy made +58.6%;
  - SPY held at the same 44.3% exposure made +88.8%;
  - SPY itself made +283% (price only).

  A short book lowers net market exposure further. In a rising market that
  widens the gap to SPY, whatever the short book earns on its own.
- **The market's drift runs against a short.** In the older measurement, 56%
  of all 10-day windows were positive. A short pays that drift for every day
  it is held, and it also pays the dividends.
- **The sizing gives the best shorts the least money.** Position size is the
  risk budget divided by the stop distance. The violent run-ups behind
  EXP-0011's best years were high-ATR stocks, so they got the smallest
  positions. The book was also mostly idle: about eleven trades a year, with
  less than one position open on average out of twelve slots.
- **The risks are lopsided, and the rules add friction.**
  - A long can lose at most what was paid for it; a short's loss has no
    ceiling.
  - Borrowed shares can be recalled.
  - A short squeeze hurts most when the short is most wrong.
  - Before any short sale, the broker must have "reasonable grounds to believe
    that the security can be borrowed". This is the Regulation SHO locate
    requirement (SEC).
  - After "a price decline of at least 10 percent in one day", SEC Rule 201
    restricts short sales in that stock. The restriction lasts for the rest of
    that day and the next, and short sales may only execute above the national
    best bid. That is the kind of day a mean-reversion short would want to
    act on.
- **The live code cannot hold a short safely.** Every cycle places a standing
  GTC *sell* stop under each position (`docs/WINDOWS-SETUP.md`). On a short, a
  sell stop adds to the position instead of closing it, which doubles it.
  `broker.py` only places sell-side protective stops.
- **Paper trading would make shorts look better than they are.** Alpaca's
  paper account allows short selling, but:
  - it charges no borrow fees (its documentation lists them as "Coming Soon");
  - it does not simulate dividends, which a real short has to pay.
- **The evaluation would restart again.** Adding shorts changes the frozen
  stock strategy, so the fingerprint changes and the forward evaluation starts
  over. EXP-0055 already restarted it once, moving the first clean session to
  2026-10-27. Shorts would be a second restart.

### The broker is not what stands in the way

This is from Alpaca's own documentation, read today:

- Short selling needs "$2,000 or more account equity". The paper account holds
  about $100,000.
- "Alpaca offers 5,000+ ETB (Easy-to-Borrow) securities that are approved for
  locates with zero fees".
- Trading API users pay "$0 locate and borrow fees on all ETB shares".
- Hard-to-borrow stocks need "an approved locate before a short-sale order can
  be submitted", plus a daily borrow fee.
- The paper account lists "Short Selling ✅".

So the stock broker can already short. What is missing is a strategy that
makes money doing it, and code that handles shorts safely.

### What would change the answer

Changing a parameter on the current rule would not. The short-book write-up
names what would be needed:

- a separate short sleeve with its own capital;
- positions sized by volatility, or equally, rather than by stop distance;
- a live reconciler that places *buy* stops above short positions.

That is a new strategy. It would need a preregistered test on the thirty-year
data and on the ETF-only control set, where survivorship bias can't inflate
the result. Research can run at any time. Nothing reaches the live bot while
the frozen evaluation is running.

The strongest published record for trading both long and short comes from
another kind of strategy altogether: trend-following across many futures
markets, going long or short in each market according to its own recent
trend.

- **Moskowitz, Ooi and Pedersen (2012)** found it in "each of the 58 liquid
  instruments" they studied: equity index, currency, commodity and bond
  futures. A diversified portfolio "performs best during extreme markets".
- **Hurst, Ooi and Pedersen (2017)** found positive average returns "in each
  decade since 1880". It also performed well in 8 of the 10 largest crises for
  a 60/40 stock/bond portfolio.

That is a futures strategy, which is where the broker question comes in. Its
return comes from diversifying across many markets, not from shorting
individual stocks. It has never been tested here on futures.

## 2. Brokers

### What each kind of trading needs

| | Alpaca paper, today | Needs another broker? |
|---|---|---|
| Stocks and ETFs, buying | ✅ running | No |
| Stocks, shorting | ✅ available: easy-to-borrow stocks at no fee; hard-to-borrow with a locate and a daily fee | No. The bot's own code is what is missing. |
| Crypto, buying and selling | ✅ running (the 5% BTC sleeve) | No |
| Crypto, shorting | ❌ Alpaca: "Margin Trading for Crypto is not applicable". On 2026-09-08 all 73 of Alpaca's crypto assets were marked not shortable (`docs/2026-09-08-crypto-rejected.md`). | Yes: crypto futures at a futures broker |
| Futures | ❌ not offered. Alpaca describes itself as an API "for Stock, Options, Crypto Trading". | Yes |

### Candidates for futures

| Broker | Paper trading for an API bot | Futures | Spot crypto | Verdict |
|---|---|---|---|---|
| **Interactive Brokers** | ✅ A real simulator: fills are simulated from the top of the order book | ✅ | ✅ through Paxos and Zero Hash. Crypto *in the paper account*: **not confirmed** | Broadest, but the heaviest to run |
| **TradeStation** | ✅ A "SIM" API, "identical to the Live API in all ways except it uses fake trading accounts seeded with fake money", with instant simulated fills (`sim-api.tradestation.com/v3`) | ✅ | ❌ Left US spot crypto on 22 February 2024. The SEC also charged TradeStation Crypto over a crypto lending product, and it paid a $1.5 million penalty. Whether it has returned was not checked. | Simplest fit for a futures-only second account |
| **Tradovate** (owned by NinjaTrader) | ✅ A demo API environment | ✅ futures only | ❌ | The API needs a funded live account |
| **NinjaTrader** | ✅ A simulation account inside its desktop platform | ✅ | not assessed | Doesn't fit a Python bot |
| **tastytrade** | ❌ **Not a real simulator.** The sandbox resets daily and fakes its fills | ✅ | ✅ | Unusable for paper trading this bot |
| **Schwab** | ❌ Third-party guides report that the Trader API has no paper mode | ❌ Third-party guides report no futures orders through the API | ❌ Not through the API (third-party guides) | Unusable |

Notes on each:

- **Interactive Brokers.**
  - IBKR's Client Portal guide: "All new clients automatically receive a paper
    trading account with 1,000,000 USD of paper trading Equity with Loan
    Value".
  - Its API documentation says the paper account is opened "if your regular
    trading account has been approved and funded". Either way, a real IBKR
    account comes first.
  - The drawbacks:
    - The API runs through TWS or IB Gateway, a desktop program that has to
      stay logged in on this PC.
    - Real-time data needs a funded account ($500 minimum, from IBKR's pages
      checked earlier today) plus paid data subscriptions.
    - The API does not serve expired futures contracts older than about two
      years.
    - Two searches did not settle whether crypto can be traded in the paper
      account.
- **TradeStation.** A plain web API with a proper simulator, covering stocks,
  options and futures. Its account minimum for API access was not checked.
- **Tradovate.**
  - Text from Tradovate's API site, quoted on its forum: "You need a LIVE
    account with more than $1000 in equity" and "You need a subscription to
    API Access".
  - Third-party guides put the subscription at $25 a month.
  - It is a futures-only broker.
- **NinjaTrader.**
  - Its own automation is NinjaScript: C# strategies running inside the
    NinjaTrader 8 desktop program. Driving that from Python needs a
    third-party bridge.
  - NinjaTrader's developer site hosts the Tradovate API, which is the
    web-API route.
- **tastytrade.** Its own sandbox page, read today, says:
  - "The environment resets every 24 hours, clearing trades, transactions and
    positions";
  - "Market data is not served";
  - "Market order: Always fills, at a price of $1";
  - "Limit order priced $3 or above: Goes Live and never fills".

  That is a harness for testing connections, not a paper-trading account. It
  could not hold a position for the up to 20 sessions this bot does, or price
  one honestly.
- **Schwab.** Its paperMoney simulator inside thinkorswim covers futures, but a
  bot cannot drive it.

**No single broker checked here offers stocks, futures and crypto with a
usable paper account for all three.**

- IBKR comes closest; only its paper crypto is unconfirmed.
- tastytrade offers all three with real money, but its sandbox is not a
  simulator.

This is one more reason to keep crypto on Alpaca and add futures separately.

### Recommendation

1. **Don't add a broker now.** Nothing the bot does today needs one. Stocks
   and crypto stay on Alpaca paper, which is already integrated and tested.
2. **Start futures with a strategy, not a broker.** Research a futures
   strategy on historical data first, and connect a broker only if it passes
   a preregistered test. Finding the data is its own problem, because IBKR's
   API won't serve old expired contracts.
3. **Add futures beside Alpaca, not in place of it.** Run two accounts: Alpaca
   for stocks and crypto, and a futures broker for futures. Moving the working
   stock bot to a new broker would:
   - restart its evaluation;
   - reopen every safety check written for Alpaca: the paper-only endpoint
     guard, stop reconciliation, and outside-close detection.
4. **Choose among IBKR, TradeStation and Tradovate when the strategy exists.**
   The facts that decide it haven't all been checked yet:
   - account minimums (Tradovate's is known: more than $1,000);
   - data costs;
   - whether each API can run unattended on this PC.

   TradeStation or Tradovate is simpler if crypto stays on Alpaca. IBKR is
   broader, but needs a desktop gateway kept logged in. tastytrade and Schwab
   are out: neither offers paper trading a bot can use.
5. **The owner acts first.** Opening a brokerage account is something only the
   owner can do. Under the standing credential rule, no new vendor connection
   gets wired while the exposed Alpaca key remains unrotated. A second broker
   would bring a second set of keys, which must be handled through the same
   secure setup process.

## What is still not confirmed

These are flagged rather than stated as fact:

- whether IBKR paper accounts can trade crypto (two searches did not settle
  it);
- TradeStation's account minimum for API access, and whether it has offered
  spot crypto again since February 2024;
- Schwab: the facts come from third-party guides, because Schwab's developer
  documentation sits behind a login;
- the $25 a month price of Tradovate's API subscription, which comes from
  third-party guides.

None of these changes either answer. The shorting verdict rests on this
project's own four experiments. The broker verdict rests on Alpaca's own
documentation and on what the bot already runs.

## Sources

**Project:** the four write-ups named in the table above,
`docs/experiments.jsonl`, `docs/2026-09-08-crypto-rejected.md`,
`docs/WINDOWS-SETUP.md`, `src/event_aware_trader/regime_shorts.py`,
`src/event_aware_trader/broker.py` and `src/event_aware_trader/forward.py`.

**External, read 2026-09-28:**

- Alpaca:
  - [Margin and Short Selling](https://docs.alpaca.markets/docs/margin-and-short-selling)
  - [Paper Trading](https://docs.alpaca.markets/docs/paper-trading)
  - [alpaca.markets](https://alpaca.markets/)
- TradeStation:
  - [SIM vs. LIVE](https://api.tradestation.com/docs/fundamentals/sim-vs-live/)
  - [Trading API](https://developer.tradestation.com/trading-api/)
  - [SEC press release 2024-16 on TradeStation Crypto](https://www.sec.gov/newsroom/press-releases/2024-16)
  - [Benzinga on TradeStation Crypto leaving spot crypto](https://www.benzinga.com/markets/cryptocurrency/24/01/36679407/tradestation-crypto-bows-out-of-spot-cryptocurrency-trading-what-investors-need-to-know)
- Interactive Brokers:
  - [Client Portal paper trading account](https://www.ibkrguides.com/clientportal/papertradingaccount.htm)
  - [TWS API paper-trading limitations](https://www.interactivebrokers.com/docs/tws-api/doc/notes-limitations/limitations/paper-trading)
  - [cryptocurrencies](https://www.interactivebrokers.com/en/trading/products-cryptocurrencies.php)
  - [unavailable historical data](https://www.interactivebrokers.com/docs/web-api/v1/endpoints/market-data/unavailable-historical-data)
- tastytrade:
  - [sandbox](https://developer.tastytrade.com/docs/sandbox/)
  - [developer docs](https://developer.tastytrade.com/)
- Tradovate and NinjaTrader:
  - [Tradovate forum, API access requirements](https://community.tradovate.com/t/api-access-requirements/7769)
  - [NinjaTrader developer site, Tradovate API](https://developer.ninjatrader.com/docs/api)
  - [CrossTrade, a third-party Python bridge for NinjaTrader 8](https://crosstrade.io/blog/how-to-build-a-python-trading-bot-for-ninjatrader-8)
- Schwab:
  - [paperMoney](https://www.schwab.com/trading/thinkorswim/paper-trading)
  - [TradersPost guide on Schwab paper trading](https://blog.traderspost.io/article/does-schwab-have-paper-trading)
- Rules:
  - [SEC, Key Points about Regulation SHO](https://www.sec.gov/investor/pubs/regsho.htm)
  - [Buchanan Ingersoll & Rooney, SEC Approves Alternative Uptick Rule](https://www.bipc.com/sec-approves-alternative-uptick-rule)
- Research:
  - Moskowitz, Ooi and Pedersen, "Time series momentum", *Journal of Financial Economics* 104(2), 228–250, 2012. [Author's copy](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf)
  - Hurst, Ooi and Pedersen, "A Century of Evidence on Trend-Following Investing", *Journal of Portfolio Management* 44(1), 15–29, 2017. [Abstract](https://jpm.pm-research.com/content/44/1/15.abstract)

Not built.
