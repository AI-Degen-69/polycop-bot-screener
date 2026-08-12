#!/usr/bin/env python3
"""Polling live targets and writing the Paper Trade Log.

The transport half of the paper-trade experiment: this module fetches, and
`execution.paper_trade_log` decides. It watches two arms of wallets, notices
each new trade they make, reads the order book at the moment the follower's bot
would have reacted, and appends what that copy would have cost.

Two arms, kept apart:

* **human_alpha** - the wallets `overnight_scanner.py` classified from
  first-party Polymarket fills. The subject of the experiment.
* **phase3_simulated** - the old pipeline's top picks, scored from third-party
  polycop.fun figures nobody has verified. A comparison arm only. It is here to
  answer whether the first-party screen picks better wallets than the pipeline
  that preceded it, and its own selection numbers are not evidence of anything.

They never share a bankroll. A single global cap across both arms would let
whichever arm happened to trade first deny the other its capital, and the
resulting difference would measure poll ordering rather than wallet quality.

**No backfill.** A wallet seen for the first time has its cursor set to its
newest trade and nothing is recorded for what came before. The log's whole claim
is that it priced a copy against the book that was actually standing when the
follower would have arrived, and that book is gone for any trade older than the
first poll. Backfilling would silently replace the measurement with a
reconstruction, which is the thing this log exists to stop doing.
"""
import argparse
import json
import logging
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from paths import DATA_DIR, PHASE3_FILE, SCANNED_WALLETS_FILE  # noqa: E402
from execution.copy_execution_profile import CURRENT_PROFILE  # noqa: E402
from execution.paper_trade_log import (  # noqa: E402
    COPIED,
    PAPER_TRADE_SCHEMA_VERSION,
    PaperPortfolio,
    record_target_trade,
)

DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

HUMAN_ALPHA_FILE = os.path.join(DATA_DIR, SCANNED_WALLETS_FILE)
PHASE3_PATH = os.path.join(DATA_DIR, PHASE3_FILE)
PAPER_TRADE_LOG_FILE = os.path.join(DATA_DIR, "paper_trades.jsonl")
PAPER_TRADE_STATE_FILE = os.path.join(DATA_DIR, "paper_trade_state.json")

HUMAN_ALPHA_ARM = "human_alpha"
PHASE3_ARM = "phase3_simulated"

# How many of each arm's wallets to follow. The arms are compared to each other,
# so they carry the same number of wallets: a comparison between 40 wallets and
# 8 is a comparison of sample sizes.
DEFAULT_WALLETS_PER_ARM = 20

# One page is enough at any sane poll interval, and a wallet that outruns it is
# reported rather than silently truncated - a missed trade is a hole in the log.
ACTIVITY_PAGE = 100

REQUEST_SPACING_SECONDS = 0.35
MAX_RETRIES = 5
DEFAULT_INTERVAL_SECONDS = 300

log = logging.getLogger("poll_paper_trades")


# ---------------------------------------------------------------- transport

class PacedSession:
    """A requests session that spaces its calls and backs off on 429/5xx.

    The same discipline `overnight_scanner.py` runs under, for the same reason:
    Polymarket's public APIs answer unauthenticated but shed load under a tight
    loop, and this poller is meant to run for weeks unattended.
    """

    def __init__(self, spacing_seconds=REQUEST_SPACING_SECONDS):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "polycop-paper-trade-log/1.0"})
        self.spacing_seconds = spacing_seconds
        self._last_call = 0.0

    def get_json(self, url, params=None):
        """GET a JSON document, or None when the endpoint stays unavailable.

        None is a measurable outcome here, not a failure to hide: a trade whose
        book could not be read is logged as unpriced (ADR 0007's absent stays
        absent), never as a copy at a guessed price.
        """
        for attempt in range(MAX_RETRIES):
            spacing = self.spacing_seconds - (time.time() - self._last_call)
            if spacing > 0:
                time.sleep(spacing)
            self._last_call = time.time()
            try:
                response = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                wait = min(60.0, 2 ** attempt) + random.uniform(0, 1.0)
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
                wait = min(120.0, 2 ** attempt) + random.uniform(0, 1.0)
                log.warning("HTTP %s from %s - backing off %.1fs",
                            response.status_code, url, wait)
                time.sleep(wait)
                continue
            log.warning("HTTP %s from %s - giving up on this call",
                        response.status_code, url)
            return None
        return None

    def fetch_activity(self, address, limit=ACTIVITY_PAGE):
        data = self.get_json(f"{DATA_API}/activity", {"user": address, "limit": limit})
        return data if isinstance(data, list) else []

    def fetch_book(self, token_id):
        data = self.get_json(f"{CLOB_API}/book", {"token_id": token_id})
        return data if isinstance(data, dict) else None


# -------------------------------------------------------------------- arms

def _wallet(address, pseudonym):
    return {"address": str(address).lower(), "pseudonym": str(pseudonym or "")}


def load_human_alpha_wallets(path=HUMAN_ALPHA_FILE, limit=DEFAULT_WALLETS_PER_ARM):
    """The first-party arm: the wallets the overnight scanner called human.

    Ranked by settled profit, because the arm is meant to carry the scanner's
    strongest claims - an unranked slice would test the file's key order.

    Reads the one scanned-wallets record and selects on `classification`. It
    used to read a separate humans file; that file could disagree with the bots
    file about the same wallet, which is why there is now one record.
    """
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        try:
            raw = json.load(handle)
        except ValueError:
            return []
    if not isinstance(raw, dict):
        return []
    humans = [
        entry for entry in raw.values()
        if isinstance(entry, dict) and entry.get("classification") == "human"
        and entry.get("address")
    ]
    humans.sort(key=lambda entry: float(entry.get("settled_pnl_usdc") or 0.0), reverse=True)
    return [_wallet(entry.get("address"), entry.get("pseudonym")) for entry in humans[:limit]]


def load_phase3_wallets(path=PHASE3_PATH, limit=DEFAULT_WALLETS_PER_ARM):
    """The baseline arm: the old pipeline's top simulated targets.

    Taken in the order the file already ranks them. These wallets arrived
    through third-party figures this project no longer trusts (ADR 0012), which
    is exactly why they are worth following: the comparison is the point, not
    the numbers that selected them.
    """
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        try:
            raw = json.load(handle)
        except ValueError:
            return []
    targets = (raw or {}).get("simulated_targets") or []
    return [
        _wallet(entry.get("address"), entry.get("name"))
        for entry in targets[:limit]
        if isinstance(entry, dict) and entry.get("address")
    ]


ARM_LOADERS = {
    HUMAN_ALPHA_ARM: load_human_alpha_wallets,
    PHASE3_ARM: load_phase3_wallets,
}


# ------------------------------------------------------------------- state

def _ensure_parent(path):
    """Make sure the directory a write is about to land in exists.

    A first run on a clean checkout, or one pointed at a fresh directory by
    `--log` or `--state`, would otherwise fail on the write - after the poll
    had already spent its API calls and priced its trades, with the records
    only in memory and no book left to re-read them from.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def load_state(path=PAPER_TRADE_STATE_FILE):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except ValueError:
        return {}
    return state if isinstance(state, dict) else {}


def save_state(state, path=PAPER_TRADE_STATE_FILE):
    """Write the state atomically.

    The poller is stopped and restarted by hand; a half-written state file would
    lose the cursors and silently re-log trades already recorded.
    """
    _ensure_parent(path)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
    os.replace(tmp, path)


def check_profile_fingerprint(state, profile):
    """Refuse to extend a log written under different execution settings.

    Every record is labelled with the profile that priced it, and a run that
    changed the copy ratio mid-experiment would produce a log whose totals mean
    nothing. The fingerprint exists to make that visible, so it is checked
    rather than trusted.
    """
    recorded = state.get("profile_fingerprint")
    if recorded and recorded != profile.fingerprint:
        raise SystemExit(
            "Copy Execution Profile has changed since this log was started "
            f"({recorded[:12]}... -> {profile.fingerprint[:12]}...). Earlier records were "
            "priced under settings that no longer exist. Start a new log file and state "
            "file rather than mixing them."
        )


def _arm_state(state, arm, profile):
    arms = state.setdefault("arms", {})
    entry = arms.setdefault(arm, {"cursors": {}, "portfolio": {}})
    entry.setdefault("cursors", {})
    return entry, PaperPortfolio.from_dict(entry.get("portfolio") or {}, profile)


# -------------------------------------------------------------------- poll

def new_activity_since(activity, cursor):
    """A wallet's unseen trades, oldest first.

    The endpoint answers newest-first, but the log is replayed forward: a sell
    must be recorded after the buy it closes, or the portfolio would book an
    exit from a position it does not yet hold.
    """
    fresh = [
        entry for entry in activity
        if isinstance(entry, dict) and float(entry.get("timestamp") or 0) > cursor
    ]
    fresh.sort(key=lambda entry: float(entry.get("timestamp") or 0))
    return fresh


def append_records(records, path=PAPER_TRADE_LOG_FILE):
    """Append records to the log, one JSON object per line.

    Append-only and line-delimited so a reader weeks later gets the whole
    history rather than a snapshot, and so an interrupted write costs at most
    the final line.
    """
    if not records:
        return
    _ensure_parent(path)
    with open(path, "a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def poll_wallet(session, arm, wallet, cursor, portfolio, now=None):
    """One wallet's new trades, priced. Returns `(records, new_cursor)`.

    A first sighting records nothing and only sets the cursor - see the module
    docstring on why the history before the first poll is not backfilled.
    """
    now = int(now if now is not None else time.time())
    activity = session.fetch_activity(wallet["address"])
    if not activity:
        return [], cursor

    # A non-empty page whose rows are not dicts leaves nothing to take a max
    # over. `max()` would raise on the empty sequence, and nothing above this
    # catches it - one malformed page would end a poller meant to run for
    # weeks, and the log has no backfill to recover the gap with.
    stamps = [
        float(entry.get("timestamp") or 0)
        for entry in activity if isinstance(entry, dict)
    ]
    if not stamps:
        log.warning("%s %s returned a page with no readable rows", arm, wallet["address"])
        return [], cursor

    newest = int(max(stamps))
    if cursor is None:
        return [], newest

    fresh = new_activity_since(activity, cursor)
    if len(fresh) >= ACTIVITY_PAGE:
        log.warning("%s %s filled the activity page - trades may have been missed",
                    arm, wallet["address"])

    books = {}
    records = []
    for entry in fresh:
        token_id = str(entry.get("asset") or "")
        if token_id and token_id not in books:
            books[token_id] = session.fetch_book(token_id)
        record = record_target_trade(arm, wallet, entry, books.get(token_id),
                                     portfolio, observed_at=now)
        # How long the follower took to react. It is the term the resting-book
        # measurement in latency_slippage_profile.json has no way to see, and
        # the one that separates depth friction from the chase.
        record["copy_latency_seconds"] = max(0, now - record["target"]["timestamp"])
        records.append(record)

    return records, max(newest, cursor)


def poll_once(session, arms, state, profile=CURRENT_PROFILE, now=None,
              log_path=PAPER_TRADE_LOG_FILE):
    """One pass over every arm. Returns a per-arm summary of what was recorded."""
    now = int(now if now is not None else time.time())
    check_profile_fingerprint(state, profile)
    state.setdefault("schema_version", PAPER_TRADE_SCHEMA_VERSION)
    state.setdefault("started_at", now)
    state["profile_fingerprint"] = profile.fingerprint
    state["last_poll_at"] = now

    summary = {}
    for arm, wallets in arms.items():
        entry, portfolio = _arm_state(state, arm, profile)
        cursors = entry["cursors"]
        arm_records = []
        for wallet in wallets:
            address = wallet["address"]
            records, cursor = poll_wallet(session, arm, wallet, cursors.get(address),
                                          portfolio, now=now)
            if cursor is not None:
                cursors[address] = cursor
            arm_records.extend(records)

        append_records(arm_records, log_path)
        entry["portfolio"] = portfolio.as_dict()
        summary[arm] = {
            "wallets": len(wallets),
            "records": len(arm_records),
            "copied": sum(1 for record in arm_records if record["decision"] == COPIED),
            "deployed_usd": portfolio.deployed_usd,
            "realised_pnl_usd": portfolio.realised_pnl_usd,
        }
    return summary


def _main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true", help="poll a single pass and exit")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS,
                        help="seconds between passes when looping")
    parser.add_argument("--arm", action="append", choices=sorted(ARM_LOADERS),
                        help="restrict to one arm (repeatable); default is both")
    parser.add_argument("--wallets-per-arm", type=int, default=DEFAULT_WALLETS_PER_ARM)
    parser.add_argument("--log", default=PAPER_TRADE_LOG_FILE)
    parser.add_argument("--state", default=PAPER_TRADE_STATE_FILE)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    chosen = args.arm or sorted(ARM_LOADERS)
    arms = {arm: ARM_LOADERS[arm](limit=args.wallets_per_arm) for arm in chosen}
    for arm, wallets in arms.items():
        log.info("arm %s: following %d wallets", arm, len(wallets))
        if not wallets:
            log.warning("arm %s has no wallets - its source file is missing or empty", arm)

    session = PacedSession()
    while True:
        state = load_state(args.state)
        summary = poll_once(session, arms, state, log_path=args.log)
        save_state(state, args.state)
        for arm, counts in summary.items():
            log.info("arm %s: %d records (%d copied), deployed $%.2f, realised $%.2f",
                     arm, counts["records"], counts["copied"],
                     counts["deployed_usd"], counts["realised_pnl_usd"])
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(_main())
