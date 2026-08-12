#!/usr/bin/env python3
"""Unattended overnight scanner for profitable Polymarket wallets.

Seeds a work queue from the public leaderboard API (`lb-api.polymarket.com`,
which returns the raw `proxyWallet` address alongside the pseudonym, so no
frontend HTML is ever parsed), then pulls each wallet's trade and position
history from the public data API and classifies it:

  * human alpha  - directional, low frequency, round-number sizing. Recorded
                   with the metrics a copy-trader needs (category mix, win
                   rate, average position size, holding period).
  * bot          - high frequency, fractional sizing, micro-holds, extreme
                   price sweeps. Recorded with the operational parameters a
                   reverse-engineer needs (grid spacing, size, cadence, the
                   markets it targets).

One dataset is maintained incrementally on disk (`scanned_wallets.json` under
app/data/) so a run that is killed mid-scan keeps everything it had already
learned. Each record carries its own classification; the two files this
replaces could disagree about the same wallet.

Every record also carries the figures the 100-point audit scores from - the
per-market settled results, the traded volume, and a replay of what copying the
wallet would have returned under the Copy Execution Profile. They are computed
here because this is the only moment the raw feeds exist (ADR 0012).

Usage:
    python overnight_scanner.py                 # loop until stopped
    python overnight_scanner.py --once          # a single pass
    python overnight_scanner.py --max-wallets 25

Alert settings, read from the environment or from a `.env` file beside this
script (re-read on every alert, so one can be added mid-run):
    POLYCOP_DISCORD_WEBHOOK   Discord webhook URL for high-signal alerts.
    POLYCOP_TELEGRAM_TOKEN    Telegram bot token (with POLYCOP_TELEGRAM_CHAT).
    POLYCOP_TELEGRAM_CHAT     Telegram chat id.
Alerts are logged and not sent when neither is configured.
"""
import argparse
import json
import logging
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict, deque

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "src"))

from paths import DATA_DIR, SCANNED_WALLETS_FILE  # noqa: E402
from execution.copy_execution_profile import CURRENT_PROFILE  # noqa: E402
from screener.first_party_copy_replay import replay_copy  # noqa: E402
from screener.first_party_metrics import hedged_rate  # noqa: E402
from screener.score_wallets import RECENT_FORM_WINDOW_TRADES  # noqa: E402

LEADERBOARD_API = "https://lb-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

# One record per wallet, carrying its classification. Two files let one wallet
# hold two contradictory verdicts, and a rescan that flipped the verdict had to
# remember to clear the losing file - a rule enforced by hand in one place and
# forgotten everywhere else.
SCANNED_FILE = os.path.join(DATA_DIR, SCANNED_WALLETS_FILE)
# The datasets this replaces. Kept only so a first run under the new schema can
# migrate them, then left alone.
LEGACY_HUMAN_FILE = os.path.join(DATA_DIR, "human_alpha.json")
LEGACY_BOT_FILE = os.path.join(DATA_DIR, "bot_configs.json")
STATE_FILE = os.path.join(DATA_DIR, "scanner_state.json")
LOG_FILE = os.path.join(DATA_DIR, "overnight_scanner.log")

SEED_ADDRESSES = ["0x6908aafd2fbe47f1305e61b7d9706dbac97cbdb2"]

# The leaderboard slices by metric x window and nothing else: measured against
# the live API, `category` and `offset` are both ignored and `limit` saturates
# at 50, so those eight slices are the whole of what it will hand over.
LEADERBOARD_METRICS = ("profit", "volume")
LEADERBOARD_WINDOWS = ("1d", "7d", "30d", "all")
LEADERBOARD_PAGE = 50

# Category coverage therefore comes from the other direction: the busiest live
# events in a tag, then the biggest holders of those events' markets. That is
# what surfaces the politics or sports specialist who never outranks a
# crypto whale on a global board.
HOLDER_CATEGORIES = ("crypto", "politics", "sports", "economics", "pop-culture")
HOLDER_EVENTS_PER_CATEGORY = 5
HOLDER_LIMIT = 20
GAMMA_API = "https://gamma-api.polymarket.com"

TRADE_PAGE = 500
MAX_TRADE_PAGES = 6          # up to 3000 trades per wallet
POSITION_PAGE = 500
MAX_POSITION_PAGES = 4

# Classification thresholds. Each is a single observable trait; a wallet is
# called a bot on the weight of several, never on one alone, because any one
# of them has an innocent human explanation.
BOT_SCORE_THRESHOLD = 5
FAST_GAP_SECONDS = 120.0
HIGH_CADENCE_PER_DAY = 50.0
EXTREME_CADENCE_PER_DAY = 400.0
FRACTIONAL_SIZE_SHARE = 0.70
EXTREME_PRICE_SHARE = 0.15
MICRO_HOLD_SECONDS = 900.0

# Bumped whenever a scoring change makes stored records incomparable to fresh
# ones; every record below this version is re-scanned before new wallets.
SCHEMA_VERSION = 5

ALERT_WIN_RATE = 0.80
ALERT_MIN_CLOSED = 50

REPAIR_PER_CYCLE = 150
CYCLE_SLEEP_SECONDS = 900
REQUEST_SPACING_SECONDS = 0.35
MAX_RETRIES = 6

CATEGORY_KEYWORDS = (
    ("crypto", ("btc", "bitcoin", "eth", "ethereum", "solana", "crypto", "xrp", "doge")),
    ("politics", ("election", "president", "senate", "congress", "trump", "biden",
                  "governor", "poll", "parliament", "minister")),
    ("sports", ("nba", "nfl", "mlb", "nhl", "ufc", "soccer", "premier-league",
                "champions", "tennis", "f1", "olympic", "cup")),
    ("economics", ("fed", "cpi", "inflation", "rate-cut", "gdp", "jobs", "recession")),
    ("entertainment", ("oscar", "grammy", "movie", "album", "box-office", "emmy")),
)

log = logging.getLogger("overnight_scanner")
_WARNED_NO_WEBHOOK = False


# ---------------------------------------------------------------- transport

class RateLimitedSession:
    """A requests session that paces itself and backs off on 429/5xx.

    Polymarket's public APIs answer unauthenticated, but they will shed load
    under a tight loop. Spacing every call and backing off exponentially with
    jitter is what lets this run unattended for hours without being banned.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "polycop-overnight-scanner/1.0"})
        self._last_call = 0.0

    def get_json(self, url, params=None):
        """GET a JSON document, or None when the endpoint stays unavailable."""
        for attempt in range(MAX_RETRIES):
            spacing = REQUEST_SPACING_SECONDS - (time.time() - self._last_call)
            if spacing > 0:
                time.sleep(spacing)
            self._last_call = time.time()
            try:
                response = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                wait = min(60.0, (2 ** attempt)) + random.uniform(0, 1.0)
                log.warning("network error %s on %s - retrying in %.1fs", exc, url, wait)
                time.sleep(wait)
                continue

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    log.warning("non-JSON body from %s", url)
                    return None
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait = float(retry_after) if retry_after else 2 ** attempt
                except ValueError:
                    wait = 2 ** attempt
                wait = min(120.0, wait) + random.uniform(0, 1.0)
                log.warning("HTTP %s from %s - backing off %.1fs",
                            response.status_code, url, wait)
                time.sleep(wait)
                continue
            log.warning("HTTP %s from %s - giving up on this call",
                        response.status_code, url)
            return None
        return None


# ------------------------------------------------------------------- source

def _record(found, address, pseudonym, source_key, amount):
    if not address:
        return
    profile = found.setdefault(address.lower(), {
        "address": address.lower(),
        "pseudonym": pseudonym or "",
        "leaderboard": {},
    })
    if not profile["pseudonym"] and pseudonym:
        profile["pseudonym"] = pseudonym
    profile["leaderboard"][source_key] = amount


def discover_from_leaderboard(session, found, metric, window):
    rows = session.get_json(
        f"{LEADERBOARD_API}/{metric}",
        params={"window": window, "limit": LEADERBOARD_PAGE},
    )
    if not isinstance(rows, list):
        log.warning("leaderboard slice %s/%s returned no list", metric, window)
        return
    for row in rows:
        if isinstance(row, dict):
            _record(found, row.get("proxyWallet") or row.get("address"),
                    row.get("pseudonym") or row.get("name"),
                    f"{metric}_{window}", row.get("amount"))
    log.info("leaderboard %s/%s -> %d rows", metric, window, len(rows))


def discover_from_category(session, found, tag):
    """Take the top holders of the busiest live markets in one category."""
    events = session.get_json(f"{GAMMA_API}/events", params={
        "limit": HOLDER_EVENTS_PER_CATEGORY,
        "tag_slug": tag,
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false",
    })
    if not isinstance(events, list):
        log.warning("gamma events for tag %s returned no list", tag)
        return
    seen = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        for market in (event.get("markets") or [])[:2]:
            condition = market.get("conditionId") if isinstance(market, dict) else None
            if not condition:
                continue
            tokens = session.get_json(f"{DATA_API}/holders",
                                      params={"market": condition, "limit": HOLDER_LIMIT})
            if not isinstance(tokens, list):
                continue
            for token in tokens:
                for holder in (token.get("holders") or []) if isinstance(token, dict) else []:
                    if isinstance(holder, dict):
                        _record(found, holder.get("proxyWallet"),
                                holder.get("pseudonym") or holder.get("name"),
                                f"holder_{tag}", holder.get("amount"))
                        seen += 1
    log.info("category %s -> %d holder rows", tag, seen)


def discover_wallets(session, slices):
    """Collect {address: profile} across a set of discovery slices."""
    found = {}
    for slice_spec in slices:
        if slice_spec[0] == "leaderboard":
            discover_from_leaderboard(session, found, slice_spec[1], slice_spec[2])
        else:
            discover_from_category(session, found, slice_spec[1])
    return found


def fetch_paginated(session, path, address, page_size, max_pages, extra=None):
    """Pull a wallet-scoped data-API collection, page by page."""
    out = []
    for page in range(max_pages):
        params = {"user": address, "limit": page_size, "offset": page * page_size}
        if extra:
            params.update(extra)
        rows = session.get_json(f"{DATA_API}/{path}", params=params)
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)
        if len(rows) < page_size:
            break
    return out


# ---------------------------------------------------------------- analytics

def _category_of(text):
    lowered = (text or "").lower()
    for name, keywords in CATEGORY_KEYWORDS:
        if any(word in lowered for word in keywords):
            return name
    return "other"


def _is_round(size):
    """Whether a trade size looks hand-typed rather than machine-computed."""
    return abs(size - round(size)) < 0.01


def _holding_periods(events):
    """Average seconds a share is held, FIFO per asset, over closing events.

    A position closes either by being sold or by being redeemed at
    resolution, and plenty of wallets never sell at all - they buy and wait
    for the market to resolve. Counting only SELLs would report "no holding
    period" for exactly those traders, so REDEEMs close a lot too.

    Only matched pairs count: an open position has no holding period yet, and
    treating it as zero would make every live swing trade look like a
    micro-hold.
    """
    lots = defaultdict(deque)
    holds = []
    for event in events:
        asset = event.get("asset")
        size = float(event.get("size") or 0.0)
        stamp = float(event.get("timestamp") or 0.0)
        kind = event.get("type") or "TRADE"
        if not asset or size <= 0 or stamp <= 0:
            continue
        if kind == "TRADE" and event.get("side") == "BUY":
            lots[asset].append([stamp, size])
        elif kind == "REDEEM" or (kind == "TRADE" and event.get("side") == "SELL"):
            remaining = size
            queue = lots[asset]
            while remaining > 0 and queue:
                open_stamp, open_size = queue[0]
                matched = min(remaining, open_size)
                holds.append((stamp - open_stamp, matched))
                remaining -= matched
                open_size -= matched
                if open_size <= 1e-9:
                    queue.popleft()
                else:
                    queue[0][1] = open_size
    if not holds:
        return None, None
    weight = sum(w for _s, w in holds)
    mean = sum(s * w for s, w in holds) / weight if weight else None
    return mean, statistics.median([s for s, _w in holds])


def _grid_spacing_pct(trades):
    """Median gap between the distinct price levels a wallet works per market.

    A grid/market-making bot revisits a ladder of prices in one market; the
    spacing of that ladder is the parameter worth stealing. Markets where the
    wallet only ever touched one price contribute nothing.
    """
    by_market = defaultdict(set)
    for trade in trades:
        condition = trade.get("conditionId")
        price = float(trade.get("price") or 0.0)
        if condition and 0.0 < price < 1.0:
            by_market[condition].add(round(price, 3))
    spacings = []
    for prices in by_market.values():
        ordered = sorted(prices)
        if len(ordered) < 2:
            continue
        spacings.extend(b - a for a, b in zip(ordered, ordered[1:]))
    if not spacings:
        return None
    return round(statistics.median(spacings) * 100, 3)


def _settled_market_pnl(events, positions):
    """Per-market result record for every market whose outcome is already known.

    Each entry carries the USDC result, when the market closed for this wallet,
    and the notional it bought there. The summary figures the record used to
    keep - total PnL, win rate, market count - are all recoverable from these,
    but the reverse is not true: an equity curve needs the order, a
    profit/loss ratio needs the individual results, and a copy replay needs the
    size. Keeping the evidence rather than only its summary is what lets a
    derived figure be audited against the record it came from.

    Neither feed is honest on its own. The activity feed only shows a closing
    event when the wallet sold or redeemed - and a wallet only redeems what it
    won, so scoring activity alone reports implausible win rates near 100%.
    The positions feed has the mirror bias: redeemed winners drop out of it
    while worthless losers linger forever, which reports win rates near zero.

    Taking the union fixes both: wins come from closed cash flows, and the
    losses those cash flows never record are read off the positions that are
    still held at a resolved price of zero.
    """
    by_market = defaultdict(list)
    for event in events:
        condition = event.get("conditionId")
        if condition:
            by_market[condition].append(event)

    pnl = {}
    shares_bought = defaultdict(float)
    notional_bought = defaultdict(float)
    for condition, market_events in by_market.items():
        for event in market_events:
            if event.get("type") == "TRADE" and event.get("side") == "BUY":
                shares_bought[condition] += float(event.get("size") or 0.0)
                notional_bought[condition] += float(event.get("usdcSize") or 0.0)

    def _closed_at(market_events):
        """When this market last paid out or was sold down, for ordering.

        The equity curve is built in this order, so it must be the moment the
        result was realised rather than the moment the position was opened.
        Falls back to the market's last event for a position the activity feed
        never saw close - a loss read off the positions feed has no closing
        event of its own, and dropping it from the ordering would drop it from
        the curve.
        """
        closing = [
            float(event.get("timestamp") or 0.0)
            for event in market_events
            if event.get("type") == "REDEEM"
            or (event.get("type") == "TRADE" and event.get("side") == "SELL")
        ]
        if closing:
            return int(max(closing))
        stamps = [float(event.get("timestamp") or 0.0) for event in market_events]
        return int(max(stamps)) if stamps else 0

    for condition, market_events in by_market.items():
        first = market_events[0]
        # A market whose first event in our window is not the opening buy is
        # one we joined mid-story; its cash flow would be missing the cost.
        if first.get("type") != "TRADE" or first.get("side") != "BUY":
            continue
        flow = 0.0
        shares_in = shares_out = 0.0
        for event in market_events:
            usdc = float(event.get("usdcSize") or 0.0)
            size = float(event.get("size") or 0.0)
            if event.get("type") == "TRADE" and event.get("side") == "BUY":
                flow -= usdc
                shares_in += size
            elif event.get("type") == "TRADE" and event.get("side") == "SELL":
                flow += usdc
                shares_out += size
            elif event.get("type") == "REDEEM":
                flow += usdc
                shares_out += size
        if shares_out <= 0:
            continue
        # Redeeming more shares than the window saw bought means the position
        # was opened before the window and its cost basis is only partly
        # here. Scoring it would book the full payout against a fraction of
        # what was paid, which inflates PnL by whatever the window clipped -
        # on a wallet that buys at 97c it turned a ~2% edge into an apparent
        # 50%. Such a market is unscoreable, not profitable.
        if shares_out > shares_in * 1.01:
            continue
        if abs(flow) > 1.0:
            pnl[condition] = {
                "condition_id": condition,
                "result_usdc": round(flow, 4),
                "closed_at": _closed_at(market_events),
                "notional_usdc": round(notional_bought[condition], 4),
            }

    for position in positions:
        if not isinstance(position, dict):
            continue
        condition = position.get("conditionId")
        if not condition or condition in pnl:
            continue
        # The positions feed reaches back to the wallet's first ever trade,
        # while the activity feed is capped at its most recent pages. Counting
        # a loss from outside that window against wins from inside it is what
        # made an active wallet look ruinous; both halves must describe the
        # same stretch of time, so a market the window never saw is skipped.
        if condition not in by_market:
            continue
        held = float(position.get("size") or 0.0) > 0
        worthless = (float(position.get("curPrice") or 0.0) <= 0.02
                     and float(position.get("currentValue") or 0.0) <= 0.01)
        # The same completeness test the winners get. Scoring a loss whose
        # shares were mostly bought before the window, while skipping a win
        # in the same state, would bias every truncated wallet toward a loss
        # and cull it from the datasets on an artefact of the page cap.
        if float(position.get("totalBought") or 0.0) > shares_bought[condition] * 1.01:
            continue
        if held and worthless:
            loss = float(position.get("realizedPnl") or 0.0) - float(position.get("initialValue") or 0.0)
            if abs(loss) > 1.0:
                pnl[condition] = {
                    "condition_id": condition,
                    "result_usdc": round(loss, 4),
                    "closed_at": _closed_at(by_market[condition]),
                    "notional_usdc": round(notional_bought[condition], 4),
                }
    return pnl


def analyze_wallet(profile, activity, positions, copy_profile=CURRENT_PROFILE):
    """Reduce a wallet's raw history to the metrics the dataset is built on.

    `activity` is the data-API activity feed: TRADE rows carry the fills, and
    the REDEEM/MERGE rows around them are what close a holding period for a
    wallet that never sells.

    The derived figures the scoring engine reads are computed here rather than
    at score time, because this is the only moment the raw feeds exist: the
    record keeps results, and persisting thousands of events per wallet would
    be a second copy of Polymarket rather than a record of it. The copy replay
    depends on the Copy Execution Profile, so the record states which profile
    produced it and a record computed under a profile that no longer exists is
    re-scanned rather than scored.
    """
    events = sorted(
        (e for e in activity if isinstance(e, dict)),
        key=lambda e: float(e.get("timestamp") or 0.0),
    )
    trades = [e for e in events if (e.get("type") or "TRADE") == "TRADE"]
    sizes = [float(t.get("size") or 0.0) for t in trades if float(t.get("size") or 0.0) > 0]
    prices = [float(t.get("price") or 0.0) for t in trades]
    stamps = [float(t.get("timestamp") or 0.0) for t in trades if float(t.get("timestamp") or 0.0) > 0]

    span_days = ((stamps[-1] - stamps[0]) / 86400.0) if len(stamps) > 1 else 0.0
    last_trade_at = int(stamps[-1]) if stamps else None
    # Activity Recency is measured against data collection time, not read time
    # (CONTEXT.md), so the seven-day window is anchored to the last fill this
    # scan saw rather than to whenever someone later opens the page.
    week_cutoff = (last_trade_at - 7 * 86400) if last_trade_at else None
    recent = [
        t for t in trades
        if week_cutoff is not None and float(t.get("timestamp") or 0.0) >= week_cutoff
    ]
    recent_days = {
        int(float(t.get("timestamp") or 0.0) // 86400) for t in recent
    }
    gaps = [b - a for a, b in zip(stamps, stamps[1:]) if b >= a]
    median_gap = statistics.median(gaps) if gaps else None
    trades_per_day = (len(trades) / span_days) if span_days > 0.5 else None

    fractional_share = (
        1.0 - (sum(1 for s in sizes if _is_round(s)) / len(sizes)) if sizes else None
    )
    extreme_share = (
        sum(1 for p in prices if p >= 0.97 or (0.0 < p <= 0.03)) / len(prices)
        if prices else None
    )
    mean_hold, median_hold = _holding_periods(events)

    categories = Counter(
        _category_of(f"{t.get('title', '')} {t.get('eventSlug', '')}") for t in trades
    )
    markets = Counter(t.get("title") or t.get("slug") or "" for t in trades)

    settled = _settled_market_pnl(events, positions)
    # Ordered by when each market closed, because everything derived from this
    # list downstream - the equity curve above all - is a statement about
    # sequence, and the activity feed does not arrive in that order.
    settled_results = sorted(settled.values(), key=lambda entry: entry["closed_at"])
    results = [entry["result_usdc"] for entry in settled_results]
    win_rate = (sum(1 for r in results if r > 0) / len(results)) if results else None
    # None, not zero, when nothing settled. `sum([])` is 0.0, and the engine
    # reads this field as Actual PnL: a measured break-even would earn the
    # wallet an Edge-to-Friction reading, and a Slippage Cost Rate, computed
    # from a figure nothing measured (ADR 0007).
    realized_pnl = sum(results) if results else None
    open_value = sum(float(p.get("currentValue") or 0.0) for p in positions if isinstance(p, dict))
    notional = [
        float(t.get("size") or 0.0) * float(t.get("price") or 0.0) for t in trades
    ]

    return {
        "address": profile["address"],
        "pseudonym": profile.get("pseudonym", ""),
        "leaderboard": profile.get("leaderboard", {}),
        "scanned_at": int(time.time()),
        "trade_count": len(trades),
        "span_days": round(span_days, 2),
        "trades_per_day": round(trades_per_day, 2) if trades_per_day is not None else None,
        "median_gap_seconds": round(median_gap, 1) if median_gap is not None else None,
        "fractional_size_share": round(fractional_share, 3) if fractional_share is not None else None,
        "extreme_price_share": round(extreme_share, 3) if extreme_share is not None else None,
        "avg_trade_size": round(statistics.mean(sizes), 3) if sizes else None,
        "median_trade_size": round(statistics.median(sizes), 3) if sizes else None,
        "avg_position_usdc": round(statistics.mean(notional), 2) if notional else None,
        "mean_hold_seconds": round(mean_hold, 1) if mean_hold is not None else None,
        "median_hold_seconds": round(median_hold, 1) if median_hold is not None else None,
        "distinct_markets": len({t.get("conditionId") for t in trades if t.get("conditionId")}),
        "categories": dict(categories.most_common()),
        "top_markets": [m for m, _n in markets.most_common(5) if m],
        "settled_markets": len(settled),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "settled_pnl_usdc": round(realized_pnl, 2) if realized_pnl is not None else None,
        # The evidence behind the three figures above, kept so the equity
        # curve and the profit/loss ratio can be derived from the record rather
        # than only from a live scan.
        "settled_results": settled_results,
        # Measured here because the positions feed exists only during a scan.
        "hedged_pct": hedged_rate(positions),
        # What copying this wallet would have returned under the stated
        # profile. The Toxic Copy Poison gate, the Slippage Cost Rate gate and
        # 37 scored points all read this replay.
        "copy_replay": replay_copy(
            events, settled_results, copy_profile, int(RECENT_FORM_WINDOW_TRADES)
        ),
        "profile_fingerprint": copy_profile.fingerprint,
        # The denominator of Edge-to-Friction: every dollar that changed hands,
        # not the mean of it. `avg_position_usdc` above is the same series
        # reduced to a mean, and a ratio cannot be rebuilt from a mean.
        "traded_volume_usdc": round(sum(notional), 2),
        # How much history the fetched window actually covers. Distinct from
        # `history_truncated`, which says only whether the window hit its cap:
        # a wallet can be untruncated and still have three days of record.
        "coverage_days": round(span_days, 2),
        # Activity Recency, measured from the fills rather than read off an
        # aggregator's `last_active` string.
        "last_trade_at": last_trade_at,
        "trades_7d": len(recent),
        "volume_7d": round(
            sum(float(t.get("size") or 0.0) * float(t.get("price") or 0.0) for t in recent), 2
        ),
        "active_days_7d": len(recent_days),
        # True when the activity feed hit the page cap, so every figure above
        # describes the tail of this wallet's history rather than all of it.
        "history_truncated": len(events) >= TRADE_PAGE * MAX_TRADE_PAGES,
        "open_position_value": round(open_value, 2),
        "grid_spacing_pct": _grid_spacing_pct(trades),
    }


def classify(metrics):
    """Score a wallet's automation traits and return (label, score, reasons)."""
    score = 0
    reasons = []

    # Cadence and gap are graded, not binary: 60 fills a day is a busy human,
    # 3,000 is nobody's hands. The top band alone clears the threshold,
    # because no combination of the softer traits should be needed to call a
    # wallet firing several thousand times a day automated.
    gap = metrics.get("median_gap_seconds")
    if gap is not None and gap < FAST_GAP_SECONDS:
        weight = 3 if gap < 20.0 else 2
        score += weight
        reasons.append(f"median gap {gap}s < {FAST_GAP_SECONDS}s")

    cadence = metrics.get("trades_per_day")
    if cadence is not None and cadence > HIGH_CADENCE_PER_DAY:
        weight = 5 if cadence > EXTREME_CADENCE_PER_DAY else 2
        score += weight
        reasons.append(f"{cadence} trades/day > {HIGH_CADENCE_PER_DAY}")

    fractional = metrics.get("fractional_size_share")
    if fractional is not None and fractional > FRACTIONAL_SIZE_SHARE:
        score += 1
        reasons.append(f"fractional sizing {fractional:.0%}")

    extreme = metrics.get("extreme_price_share")
    if extreme is not None and extreme > EXTREME_PRICE_SHARE:
        score += 1
        reasons.append(f"{extreme:.0%} of fills at 3c/97c extremes")

    hold = metrics.get("median_hold_seconds")
    if hold is not None and hold < MICRO_HOLD_SECONDS:
        score += 2
        reasons.append(f"median hold {hold}s < {MICRO_HOLD_SECONDS}s")

    trades = metrics.get("trade_count") or 0
    markets = metrics.get("distinct_markets") or 0
    if markets and trades / markets > 20:
        score += 1
        reasons.append(f"{trades / markets:.0f} fills per market")

    label = "bot" if score >= BOT_SCORE_THRESHOLD else "human"
    return label, score, reasons


def is_profitable(metrics):
    """Whether the wallet made money by any of the figures we actually have."""
    settled = metrics.get("settled_pnl_usdc")
    if isinstance(settled, (int, float)) and settled > 0:
        return True
    return any(
        isinstance(value, (int, float)) and value > 0
        for key, value in (metrics.get("leaderboard") or {}).items()
        if key.startswith("profit")
    )


def to_scanned_record(metrics, label, score, reasons):
    """One wallet's record: what it is, what it did, and what copying it costs.

    Replaces the two per-classification record builders. They existed because
    the datasets were separate files, and the price of that was a wallet whose
    verdict flipped sitting in both at once, each copy asserting a different
    classification. One record with a `classification` field cannot disagree
    with itself.

    The union of what the two builders carried, plus the derived figures the
    scoring engine reads. Fields only one classification ever populates - grid
    spacing on a bot, category mix on a human - are carried for both, because
    a field that is absent for a reason is more useful to a later reader than a
    field that is absent by convention.
    """
    return {
        "address": metrics["address"],
        "pseudonym": metrics["pseudonym"],
        "classification": label,
        "schema_version": SCHEMA_VERSION,
        "profile_fingerprint": metrics["profile_fingerprint"],
        "bot_score": score,
        "signals": reasons,
        "scanned_at": metrics["scanned_at"],
        "primary_categories": metrics["categories"],
        "top_markets": metrics["top_markets"],
        "win_rate": metrics["win_rate"],
        "settled_markets": metrics["settled_markets"],
        "settled_pnl_usdc": metrics["settled_pnl_usdc"],
        "history_truncated": metrics["history_truncated"],
        "open_position_value": metrics["open_position_value"],
        "avg_position_usdc": metrics["avg_position_usdc"],
        "avg_trade_size": metrics["avg_trade_size"],
        "mean_hold_hours": round(metrics["mean_hold_seconds"] / 3600.0, 2)
        if metrics["mean_hold_seconds"] is not None else None,
        "median_hold_hours": round(metrics["median_hold_seconds"] / 3600.0, 2)
        if metrics["median_hold_seconds"] is not None else None,
        "trades_per_day": metrics["trades_per_day"],
        "trade_count": metrics["trade_count"],
        "distinct_markets": metrics["distinct_markets"],
        "leaderboard": metrics["leaderboard"],
        "median_trade_size": metrics["median_trade_size"],
        "median_gap_seconds": metrics["median_gap_seconds"],
        "median_hold_seconds": metrics["median_hold_seconds"],
        "fractional_size_share": metrics["fractional_size_share"],
        "extreme_price_share": metrics["extreme_price_share"],
        "estimated_grid_spacing_pct": metrics["grid_spacing_pct"],
        # The evidence the scoring engine derives its parameters from.
        "settled_results": metrics["settled_results"],
        "traded_volume_usdc": metrics["traded_volume_usdc"],
        "coverage_days": metrics["coverage_days"],
        "last_trade_at": metrics["last_trade_at"],
        "trades_7d": metrics["trades_7d"],
        "volume_7d": metrics["volume_7d"],
        "active_days_7d": metrics["active_days_7d"],
        "hedged_pct": metrics["hedged_pct"],
        "copy_replay": metrics["copy_replay"],
    }


# ------------------------------------------------------------------ storage

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def save_json(path, payload):
    """Write atomically so a kill mid-write cannot truncate a dataset."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = f"{path}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    os.replace(temp, path)


# ------------------------------------------------------------------- alerts

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def alert_setting(name):
    """Read one alert setting from the environment, else from `.env`.

    The file is re-read on every alert rather than cached at startup, so a
    webhook can be added to a scanner that is already running through the
    night without restarting it and losing the queue. An exported variable
    still wins, and `.env` is gitignored, so the URL never reaches a commit.
    """
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, raw = line.partition("=")
                if key.strip() == name:
                    return raw.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def send_alert(text):
    """Push a high-signal find to whichever webhook is configured, if any."""
    discord = alert_setting("POLYCOP_DISCORD_WEBHOOK")
    token = alert_setting("POLYCOP_TELEGRAM_TOKEN")
    chat = alert_setting("POLYCOP_TELEGRAM_CHAT")
    if not discord and not (token and chat):
        # Reported undelivered so the caller leaves the find unmarked and
        # retries it once a webhook exists. Logged once per process, because
        # an unconfigured run re-checks the whole backlog every cycle.
        global _WARNED_NO_WEBHOOK
        if not _WARNED_NO_WEBHOOK:
            log.info("no webhook configured - alerts will be held until one is set")
            _WARNED_NO_WEBHOOK = True
        log.debug("alert held: %s", text)
        return False
    try:
        if discord:
            requests.post(discord, json={"content": text}, timeout=15)
        if token and chat:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text},
                timeout=15,
            )
        log.info("alert sent: %s", text.splitlines()[0])
        return True
    except requests.RequestException as exc:
        log.warning("alert delivery failed: %s", exc)
        return False


def maybe_alert(metrics, label):
    """Alert on a wallet clearing the win-rate bar, if it has not been already.

    Every field is read defensively. This is called with stored records as well
    as with fresh `analyze_wallet` output - the cycle re-checks the dataset so a
    webhook configured mid-run still delivers earlier hits - and a stored record
    can predate any field this reads. The re-check loop runs outside the
    per-wallet try, so one legacy record indexing a missing key would end the
    whole run rather than skip one alert.
    """
    win_rate = metrics.get("win_rate")
    closed = metrics.get("settled_markets") or 0
    if win_rate is None or win_rate < ALERT_WIN_RATE or closed < ALERT_MIN_CLOSED:
        return False
    pnl = metrics.get("settled_pnl_usdc")
    pnl_text = f"${pnl:,.0f}" if isinstance(pnl, (int, float)) else "unmeasured"
    return send_alert(
        f"PolyCop scanner: {label.upper()} {metrics.get('address') or 'unknown'} "
        f"({metrics.get('pseudonym') or 'anon'})\n"
        f"win rate {win_rate:.1%} over {closed} settled markets, "
        f"net PnL {pnl_text}, "
        f"{metrics.get('trades_per_day')} trades/day, "
        f"{metrics.get('distinct_markets')} markets"
    )


# --------------------------------------------------------------------- loop

def load_scanned():
    """The wallet dataset, migrating the two legacy files on first read.

    The legacy records predate the derived figures and carry an older schema
    version, so they are re-scanned before new candidates rather than scored.
    They are merged in anyway so the scanner knows which addresses it has
    already seen and does not rediscover them as fresh work.
    """
    scanned = load_json(SCANNED_FILE, None)
    if isinstance(scanned, dict):
        return scanned

    merged = {}
    for path, label in ((LEGACY_BOT_FILE, "bot"), (LEGACY_HUMAN_FILE, "human")):
        for address, record in (load_json(path, {}) or {}).items():
            if isinstance(record, dict):
                record.setdefault("classification", label)
                merged[address] = record
    return merged


def _forget(address, scanned):
    """Drop a wallet from the dataset. True when something was removed."""
    if scanned.pop(address, None) is None:
        return False
    save_json(SCANNED_FILE, scanned)
    return True


def scan_wallet(session, profile, scanned, state):
    address = profile["address"]
    activity = fetch_paginated(session, "activity", address, TRADE_PAGE, MAX_TRADE_PAGES)
    if not any((e.get("type") or "TRADE") == "TRADE" for e in activity if isinstance(e, dict)):
        log.info("%s has no trade history - skipped", address)
        state["scanned"][address] = int(time.time())
        return
    positions = fetch_paginated(session, "positions", address, POSITION_PAGE, MAX_POSITION_PAGES)

    metrics = analyze_wallet(profile, activity, positions or [])
    label, score, reasons = classify(metrics)
    state["scanned"][address] = metrics["scanned_at"]

    if not is_profitable(metrics):
        # Any record already on file is dropped, not merely skipped. A wallet
        # that only looked profitable under the old scoring would otherwise
        # keep that stale entry forever - re-queued for repair every cycle,
        # never rewritten, and still ranking in the dataset.
        if _forget(address, scanned):
            log.info("%s no longer profitable - record removed", address)
        else:
            log.info("%s classified %s but not profitable - not recorded", address, label)
        return

    # A rescan can flip the verdict, and one record carrying its own
    # classification simply changes rather than needing the losing file
    # cleared first.
    scanned[address] = to_scanned_record(metrics, label, score, reasons)
    save_json(SCANNED_FILE, scanned)

    log.info(
        "%s -> %s (score %d) trades=%s cadence=%s hold=%s win_rate=%s pnl=%.0f",
        address, label, score, metrics["trade_count"], metrics["trades_per_day"],
        metrics["median_hold_seconds"], metrics["win_rate"], metrics["settled_pnl_usdc"],
    )

    if maybe_alert(metrics, label):
        state["alerted"].append(address)


def slice_plan():
    """Every discovery slice, in a stable order the cycle counter walks."""
    plan = [
        ("leaderboard", metric, window)
        for metric in LEADERBOARD_METRICS
        for window in LEADERBOARD_WINDOWS
    ]
    plan += [("category", tag, None) for tag in HOLDER_CATEGORIES]
    return plan


def run(once=False, max_wallets=None, rescan_after_days=7):
    session = RateLimitedSession()
    scanned = load_scanned()
    state = load_json(STATE_FILE, {"scanned": {}, "alerted": [], "cycle": 0})
    state.setdefault("scanned", {})
    state.setdefault("alerted", [])
    state.setdefault("cycle", 0)

    plan = slice_plan()
    rescan_cutoff = rescan_after_days * 86400

    while True:
        cycle = state["cycle"]
        # Anything that cleared the alert bar while no webhook was configured
        # was only written to the log, and its wallet will not be rescanned
        # for days. Re-checking the datasets every cycle - not just at startup
        # - is what makes a webhook added mid-run deliver the earlier hits
        # rather than silently losing them.
        for record in list(scanned.values()):
            address = record.get("address")
            if (address and address not in state["alerted"]
                    and maybe_alert(record, record.get("classification", ""))):
                state["alerted"].append(address)
        save_json(STATE_FILE, state)

        # Four slices per cycle: enough new addresses to keep working, few
        # enough that a night's run covers every metric/window/category
        # combination rather than hammering the same one.
        slices = [plan[(cycle * 4 + i) % len(plan)] for i in range(4)]
        log.info("=== cycle %d - slices %s ===", cycle, slices)

        # Records written by an older scoring pass, or under a Copy Execution
        # Profile that has since changed, are re-scanned before any new wallet
        # is touched: a dataset that mixes two scorings cannot be ranked, and a
        # stale record is worse than a missing one because it still looks
        # authoritative. Chunked so repair shares the night with discovery
        # instead of blocking it.
        stale = [
            record for record in list(scanned.values())
            if record.get("schema_version") != SCHEMA_VERSION
            or record.get("profile_fingerprint") != CURRENT_PROFILE.fingerprint
        ]
        profiles = {}
        for record in stale[:REPAIR_PER_CYCLE]:
            address = record.get("address")
            if address:
                state["scanned"].pop(address, None)
                profiles[address] = {
                    "address": address,
                    "pseudonym": record.get("pseudonym", ""),
                    "leaderboard": record.get("leaderboard", {}),
                }
        if stale:
            log.info("repair: %d records on an old scoring, %d queued this cycle",
                     len(stale), len(profiles))

        discovered = discover_wallets(session, slices)
        for address, profile in discovered.items():
            profiles.setdefault(address, profile)
        for address in SEED_ADDRESSES:
            profiles.setdefault(address, {"address": address, "pseudonym": "", "leaderboard": {}})

        now = int(time.time())
        queue = [
            profile for address, profile in profiles.items()
            if now - state["scanned"].get(address, 0) > rescan_cutoff
        ]
        log.info("queue: %d wallets (%d already fresh)", len(queue), len(profiles) - len(queue))
        if max_wallets:
            queue = queue[:max_wallets]

        for profile in queue:
            try:
                scan_wallet(session, profile, scanned, state)
            except Exception:  # keep the night alive through one bad wallet
                log.exception("wallet %s failed", profile.get("address"))
            save_json(STATE_FILE, state)

        state["cycle"] = cycle + 1
        save_json(STATE_FILE, state)
        humans = sum(1 for r in scanned.values() if r.get("classification") == "human")
        log.info("cycle %d done - %d wallets on disk (%d human, %d bot)",
                 cycle, len(scanned), humans, len(scanned) - humans)

        if once:
            return
        time.sleep(CYCLE_SLEEP_SECONDS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--max-wallets", type=int, default=None,
                        help="cap the wallets scanned per cycle")
    parser.add_argument("--rescan-after-days", type=float, default=7.0,
                        help="how stale a wallet's record must be before rescanning")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    try:
        run(once=args.once, max_wallets=args.max_wallets,
            rescan_after_days=args.rescan_after_days)
    except KeyboardInterrupt:
        log.info("interrupted - datasets on disk are current")


if __name__ == "__main__":
    main()
