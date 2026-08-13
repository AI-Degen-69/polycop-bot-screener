#!/usr/bin/env python3
"""The poller's contract with the Paper Trade Log.

Everything here is about not corrupting a record that will be read weeks from
now: replaying a wallet's trades in the order they happened, never logging the
same trade twice, never inventing history from before the first poll, and
refusing to extend a log whose execution settings have changed underneath it.

No network. The session is a stub, so these tests pin behaviour rather than
Polymarket's uptime.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

import pytest  # noqa: E402

from execution.copy_execution_profile import CURRENT_PROFILE, CopyExecutionProfile  # noqa: E402
from execution.paper_trade_log import PaperPortfolio  # noqa: E402
from pipeline.poll_paper_trades import (  # noqa: E402
    HUMAN_ALPHA_ARM,
    PHASE3_ARM,
    activity_key,
    advance_cursor,
    check_profile_fingerprint,
    load_human_alpha_wallets,
    load_phase3_wallets,
    load_state,
    new_activity_since,
    poll_once,
    poll_wallet,
    read_cursor,
    save_state,
)

WALLET = {"address": "0xtest", "pseudonym": "Test-Wallet"}
ASSET = "token-a"


class FakeSession:
    """A session that answers from a script instead of from Polymarket.

    The scripted page advances once per *poll*, not once per call, so a pass
    over several arms sees one consistent view of the world - which is what the
    real endpoint gives, and what a per-call script would quietly break.
    """

    def __init__(self, activity_pages, book=None):
        self.activity_pages = list(activity_pages)
        self.book = book if book is not None else {
            "asks": [{"price": "0.51", "size": "10000"}],
            "bids": [{"price": "0.49", "size": "10000"}],
        }
        self.activity_calls = []
        self.book_calls = []

    def fetch_activity(self, address, limit=None):
        self.activity_calls.append(address)
        return self.activity_pages[0] if self.activity_pages else []

    def fetch_book(self, token_id):
        self.book_calls.append(token_id)
        return self.book

    def advance(self):
        """Let the world move on to the next scripted page."""
        if len(self.activity_pages) > 1:
            self.activity_pages.pop(0)
        return self


def _trade(timestamp, side="BUY", price=0.5, shares=100.0, usdc_size=50.0, asset=ASSET,
           tx=None):
    return {
        "timestamp": timestamp,
        "transactionHash": tx or f"0x{timestamp}",
        "conditionId": "0xcondition",
        "asset": asset,
        "title": "Test market",
        "slug": "test-market",
        "outcome": "Yes",
        "type": "TRADE",
        "side": side,
        "price": price,
        "size": shares,
        "usdcSize": usdc_size,
    }


def _paths(tmp_path):
    return str(tmp_path / "paper_trades.jsonl"), str(tmp_path / "paper_trade_state.json")


def _lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _portfolio():
    return PaperPortfolio(profile=CURRENT_PROFILE)


# ------------------------------------------------------------------ cursor

def test_the_first_sighting_of_a_wallet_records_nothing():
    """The book that was standing before the first poll is gone. Backfilling
    would replace the measurement with a reconstruction, which is the thing
    this log exists to stop doing."""
    session = FakeSession([[_trade(1000), _trade(900)]])
    records, cursor = poll_wallet(session, HUMAN_ALPHA_ARM, WALLET, None,
                                  _portfolio(), now=2000)
    assert records == []
    assert cursor["timestamp"] == 1000
    # The rows inside that second are remembered, so the next poll can tell a
    # genuinely new fill in the same second from one already accounted for.
    assert cursor["keys"] == [activity_key(_trade(1000))]


def test_only_trades_newer_than_the_cursor_are_recorded():
    session = FakeSession([[_trade(1200), _trade(1100), _trade(1000)]])
    cursor_in = advance_cursor([_trade(1000)], 1000)
    records, cursor = poll_wallet(session, HUMAN_ALPHA_ARM, WALLET, cursor_in,
                                  _portfolio(), now=2000)
    assert [record["target"]["timestamp"] for record in records] == [1100, 1200]
    assert cursor["timestamp"] == 1200


def test_a_second_fill_in_the_same_second_is_not_lost():
    """Polymarket stamps activity to the second, and the wallets followed here
    fill thousands of times a day. A cursor that advanced past the whole second
    would drop every fill after the first one in it - permanently, because the
    log is append-only and has no backfill."""
    first = _trade(1000, tx="0xaaa")
    second = _trade(1000, tx="0xbbb", shares=50.0, usdc_size=40.0)
    cursor = advance_cursor([first], 1000)

    fresh = new_activity_since([second, first], cursor)
    assert [entry["transactionHash"] for entry in fresh] == ["0xbbb"]


def test_a_fill_already_logged_in_that_second_is_not_recorded_twice():
    first = _trade(1000, tx="0xaaa")
    cursor = advance_cursor([first], 1000)
    assert new_activity_since([first], cursor) == []


def test_two_fills_in_one_transaction_are_told_apart():
    """One transaction can carry several fills, so the hash alone is not an
    identity."""
    buy = _trade(1000, tx="0xsame", side="BUY")
    sell = _trade(1000, tx="0xsame", side="SELL")
    assert activity_key(buy) != activity_key(sell)


def test_a_buy_replays_before_a_sell_stamped_to_the_same_second():
    """The activity endpoint exposes no sequence and answers newest-first, so
    rows sharing a second carry no true order. Replaying the sell first would
    book a ghost exit against inventory the follower does not hold yet."""
    sell = _trade(1000, tx="0xsell", side="SELL", price=0.8)
    buy = _trade(1000, tx="0xbuy", side="BUY")
    fresh = new_activity_since([sell, buy], None)
    assert [entry["side"] for entry in fresh] == ["BUY", "SELL"]


def test_a_row_with_an_unreadable_timestamp_is_skipped_not_fatal():
    """One malformed row would otherwise raise out of a float() and end a
    poller meant to run unattended for weeks."""
    broken = _trade(1000, tx="0xbad")
    broken["timestamp"] = "not-a-number"
    good = _trade(1100, tx="0xgood")

    fresh = new_activity_since([broken, good], 1000)
    assert [entry["transactionHash"] for entry in fresh] == ["0xgood"]

    session = FakeSession([[broken]])
    records, cursor = poll_wallet(session, HUMAN_ALPHA_ARM, WALLET, 1000,
                                  _portfolio(), now=2000)
    assert records == []
    assert cursor == 1000


def test_a_short_page_does_not_forget_a_fill_an_earlier_page_carried():
    """Rebuilding the key set from the current page alone would forget a fill
    a stale or partial page omits, and the next poll would append a second
    record for a trade already in the log."""
    first = _trade(1000, tx="0xaaa")
    second = _trade(1000, tx="0xbbb", shares=50.0)
    cursor = advance_cursor([first, second], 1000)
    assert len(cursor["keys"]) == 2

    # A later page that only carries one of them must not drop the other.
    merged = advance_cursor([first], 1000, previous=cursor)
    assert len(merged["keys"]) == 2
    assert new_activity_since([first, second], merged) == []


def test_a_cursor_written_before_ties_were_handled_still_reads():
    """The poller runs unattended for weeks, so an upgrade meets a state file
    already on disk. Its second counts as consumed: which rows inside it were
    logged is unknown, and admitting them would duplicate the ones that were."""
    timestamp, seen = read_cursor(1000)
    assert timestamp == 1000
    assert seen is None
    assert new_activity_since([_trade(1000)], 1000) == []


def test_trades_are_replayed_oldest_first():
    """The endpoint answers newest-first, but a sell must be recorded after the
    buy it closes or the portfolio books an exit it does not hold."""
    activity = [_trade(1200, side="SELL", price=0.6), _trade(1100)]
    assert [entry["timestamp"] for entry in new_activity_since(activity, 1000)] == [1100, 1200]


def test_a_cursor_never_moves_backwards():
    """A page that arrives short or stale must not re-open trades already
    logged: the log is append-only and a duplicate cannot be withdrawn."""
    session = FakeSession([[_trade(900)]])
    _records, cursor = poll_wallet(session, HUMAN_ALPHA_ARM, WALLET, 1000,
                                   _portfolio(), now=2000)
    assert cursor == 1000


def test_an_unreachable_endpoint_leaves_the_cursor_untouched():
    session = FakeSession([[]])
    records, cursor = poll_wallet(session, HUMAN_ALPHA_ARM, WALLET, 1000,
                                  _portfolio(), now=2000)
    assert records == []
    assert cursor == 1000


def test_a_second_poll_does_not_re_log_the_same_trade(tmp_path):
    log_path, _state_path = _paths(tmp_path)
    session = FakeSession([[_trade(1000)], [_trade(1100), _trade(1000)]])
    state = {}
    arms = {HUMAN_ALPHA_ARM: [WALLET]}

    poll_once(session, arms, state, now=2000, log_path=log_path)
    poll_once(session.advance(), arms, state, now=2100, log_path=log_path)

    assert [record["target"]["timestamp"] for record in _lines(log_path)] == [1100]


# -------------------------------------------------------------------- arms

def test_the_two_arms_keep_separate_portfolios(tmp_path):
    """A shared global cap would let whichever arm polled first deny the other
    its capital, and the difference would measure poll order, not wallets."""
    log_path, _state_path = _paths(tmp_path)
    session = FakeSession([[_trade(1000)], [_trade(1100)]])
    state = {}
    arms = {HUMAN_ALPHA_ARM: [WALLET], PHASE3_ARM: [WALLET]}

    poll_once(session, arms, state, now=2000, log_path=log_path)
    poll_once(session.advance(), arms, state, now=2100, log_path=log_path)

    human = state["arms"][HUMAN_ALPHA_ARM]["portfolio"]
    phase3 = state["arms"][PHASE3_ARM]["portfolio"]
    assert human["deployed_usd"] > 0
    assert human["deployed_usd"] == phase3["deployed_usd"]


def test_every_record_names_the_arm_it_belongs_to(tmp_path):
    log_path, _state_path = _paths(tmp_path)
    session = FakeSession([[_trade(1000)], [_trade(1100)]])
    state = {}
    arms = {PHASE3_ARM: [WALLET]}

    poll_once(session, arms, state, now=2000, log_path=log_path)
    poll_once(session.advance(), arms, state, now=2100, log_path=log_path)

    assert {record["arm"] for record in _lines(log_path)} == {PHASE3_ARM}


def test_a_record_carries_the_latency_the_copy_would_have_run_at(tmp_path):
    """It is the term the resting-book measurement has no way to see."""
    log_path, _state_path = _paths(tmp_path)
    session = FakeSession([[_trade(1000)], [_trade(1100)]])
    state = {}

    poll_once(session, {HUMAN_ALPHA_ARM: [WALLET]}, state, now=2000, log_path=log_path)
    poll_once(session.advance(), {HUMAN_ALPHA_ARM: [WALLET]}, state, now=2400,
              log_path=log_path)

    assert _lines(log_path)[0]["copy_latency_seconds"] == 1300


def test_the_human_alpha_arm_takes_the_scanner_s_humans_by_profit(tmp_path):
    path = tmp_path / "human_alpha.json"
    path.write_text(json.dumps({
        "0xa": {"address": "0xA", "pseudonym": "Small", "classification": "human",
                "settled_pnl_usdc": 10.0},
        "0xb": {"address": "0xB", "pseudonym": "Big", "classification": "human",
                "settled_pnl_usdc": 900.0},
        "0xc": {"address": "0xC", "pseudonym": "Bot", "classification": "bot",
                "settled_pnl_usdc": 5000.0},
    }), encoding="utf-8")

    wallets = load_human_alpha_wallets(str(path), limit=5)
    assert [wallet["address"] for wallet in wallets] == ["0xb", "0xa"]


def test_the_baseline_arm_takes_the_old_pipeline_s_ranking_as_it_stands(tmp_path):
    path = tmp_path / "phase3_simulated_targets.json"
    path.write_text(json.dumps({
        "simulated_targets": [
            {"address": "0xFIRST", "name": "First"},
            {"address": "0xSECOND", "name": "Second"},
            {"address": "0xTHIRD", "name": "Third"},
        ]
    }), encoding="utf-8")

    wallets = load_phase3_wallets(str(path), limit=2)
    assert [wallet["address"] for wallet in wallets] == ["0xfirst", "0xsecond"]


def test_a_missing_arm_source_yields_no_wallets_rather_than_failing(tmp_path):
    assert load_human_alpha_wallets(str(tmp_path / "absent.json")) == []
    assert load_phase3_wallets(str(tmp_path / "absent.json")) == []


# ------------------------------------------------------------------- state

def test_a_changed_execution_profile_refuses_to_extend_the_log():
    """Records priced under settings that no longer exist cannot be totalled
    with fresh ones. The fingerprint exists to make that visible."""
    state = {"profile_fingerprint": CopyExecutionProfile(copy_ratio=0.06).fingerprint}
    with pytest.raises(SystemExit):
        check_profile_fingerprint(state, CURRENT_PROFILE)


def test_an_unchanged_profile_extends_the_log():
    check_profile_fingerprint({"profile_fingerprint": CURRENT_PROFILE.fingerprint},
                              CURRENT_PROFILE)


def test_the_state_survives_a_restart(tmp_path):
    """The poller is stopped and restarted by hand; a lost cursor would re-log
    trades already recorded."""
    log_path, state_path = _paths(tmp_path)
    session = FakeSession([[_trade(1000)], [_trade(1100), _trade(1000)]])

    state = {}
    poll_once(session, {HUMAN_ALPHA_ARM: [WALLET]}, state, now=2000, log_path=log_path)
    save_state(state, state_path)

    reloaded = load_state(state_path)
    poll_once(session.advance(), {HUMAN_ALPHA_ARM: [WALLET]}, reloaded, now=2100,
              log_path=log_path)

    assert [record["target"]["timestamp"] for record in _lines(log_path)] == [1100]


def test_a_poll_summarises_what_each_arm_recorded(tmp_path):
    log_path, _state_path = _paths(tmp_path)
    session = FakeSession([[_trade(1000)], [_trade(1100)]])
    state = {}

    poll_once(session, {HUMAN_ALPHA_ARM: [WALLET]}, state, now=2000, log_path=log_path)
    summary = poll_once(session.advance(), {HUMAN_ALPHA_ARM: [WALLET]}, state, now=2100,
                        log_path=log_path)

    assert summary[HUMAN_ALPHA_ARM]["records"] == 1
    assert summary[HUMAN_ALPHA_ARM]["copied"] == 1
    assert summary[HUMAN_ALPHA_ARM]["deployed_usd"] > 0
