# Start here

Six steps. Everything that could be done for you is done — these are the ones
that need your accounts and your passwords, which I can't touch.

---

## Step 1 — Make a practice trading account

Go to **alpaca.markets** and sign up. It's free. Ask for **paper trading**
keys — "paper" means fake money. You'll get two long codes: an **API Key ID**
and a **Secret Key**.

> Alpaca is where the fake money lives. TradingView is the screen where you
> watch it. You need both.

---

## Step 2 — Tell your computer the two codes

Open the Terminal app and run these two lines, pasting your own codes where it
says `paste_your_...`:

```bash
echo 'export APCA_API_KEY_ID=paste_your_key_id_here' >> ~/.zprofile
```

```bash
echo 'export APCA_API_SECRET_KEY=paste_your_secret_here' >> ~/.zprofile
```

**Now close Terminal and open a new one.** (It only reads those codes when it
starts up.)

Check it worked:

```bash
cd ~/Desktop/market\ bot && ./.venv/bin/event-aware-trader account
```

You should see your account and a balance. If it says `not_connected`, the
codes didn't save — try Step 2 again.

---

## Step 3 — Practice run (nothing is bought or sold)

```bash
cd ~/Desktop/market\ bot && bash scripts/install-session.sh --months 2
```

This makes the bot think through real decisions every 15 minutes, but it does
not place any orders. Let it go for one day.

Look at what it did:

```bash
cd ~/Desktop/market\ bot && tail -30 data/session.log
```

---

## Step 4 — Turn it on for real (still fake money)

```bash
cd ~/Desktop/market\ bot && bash scripts/install-session.sh --months 2 --live
```

That's it. It now runs by itself, every 15 minutes, while the US market is
open (06:30–13:00 your time), Monday to Friday. **It stops on its own after
two months** and writes a final report.

---

## Step 5 — Connect it to TradingView so you can watch

1. Open **tradingview.com** and open any chart.
2. At the bottom, click the **Trading Panel**.
3. Find **Alpaca** in the broker list and click **Connect**.
4. Sign in and pick your **paper** account.

Now every trade the bot makes shows up on your TradingView chart, because
TradingView and the bot are both looking at the same Alpaca account.

> TradingView doesn't do the buying. It's the window, not the hands.

---

## Step 6 — See the bot's thinking on the chart (optional)

1. In TradingView, click **Pine Editor** at the bottom.
2. Open the file `tradingview/PASTE-INTO-TRADINGVIEW.pine`, select all, copy.
3. Paste it into the Pine Editor, click **Save**, then **Add to chart**.

You'll see the moving averages and the trailing stop line the bot uses.

---

## Checking on it any time

```bash
cd ~/Desktop/market\ bot && ./.venv/bin/event-aware-trader record
```

Look for `status`:

| What it says | What it means |
|---|---|
| `NO_TRADES_YET` | Normal. Some weeks it buys nothing. |
| `INSUFFICIENT_EVIDENCE` | Too few trades to tell yet. Keep waiting. |
| `NOT_DISTINGUISHABLE_FROM_LUCK` | Enough trades now, and the result could easily be chance. |
| `POSITIVE_AND_MEASURABLE` | Enough trades, and the result is real. |

The weekly report lands in `data/WEEKLY-RECORD.json`, and the final one in
`data/FINAL-RECORD.json`.

---

## To stop it early

```bash
launchctl unload ~/Library/LaunchAgents/com.eventawaretrader.session.plist
```

---

## What to expect (please read this part)

**It will probably lose a little money.** When I tested these rules on ten
years of real market history, they lost money in most years. Every intraday
week I tested lost money. I could not find a version that reliably makes a
profit, and I'm not going to pretend otherwise.

**So why run it?** Because two months of real trades will tell you whether it
works — and right now nobody knows, including me. Fake money is exactly the
right way to find that out. If the answer is "this doesn't work," you'll have
learned it in two months for $0 instead of five years and real savings.

**Never put real money in this.** Not after two good weeks, not after two good
months. Two months isn't enough trades to prove anything, and the honest
report will keep telling you that until it is.
