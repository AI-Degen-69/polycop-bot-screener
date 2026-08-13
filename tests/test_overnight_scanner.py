#!/usr/bin/env python3
"""The scanner's record: the evidence every derived figure is built on.

`_settled_market_pnl` is where three measured bugs were fixed - redemption cost
basis, the asymmetric win/loss guard, and a positions feed that reaches back
further than the activity window. Those fixes are load-bearing and easy to undo
by accident, so they are pinned here alongside the fields the cutover added.

The scanner is a root entry script rather than a package module, so it is
loaded by path.
"""
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_scanner():
    spec = importlib.util.spec_from_file_location(
        "overnight_scanner", os.path.join(REPO_ROOT, "overnight_scanner.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scanner = _load_scanner()

DAY = 86400
BASE = 1786000000


def _buy(market, timestamp, price=0.5, shares=100.0, usdc=50.0):
    return {"timestamp": timestamp, "conditionId": market, "type": "TRADE",
            "side": "BUY", "price": price, "size": shares, "usdcSize": usdc,
            "title": "Test market", "slug": "test-market"}


def _sell(market, timestamp, price=0.8, shares=100.0, usdc=80.0):
    return {"timestamp": timestamp, "conditionId": market, "type": "TRADE",
            "side": "SELL", "price": price, "size": shares, "usdcSize": usdc,
            "title": "Test market", "slug": "test-market"}


def _redeem(market, timestamp, shares=100.0, usdc=100.0):
    return {"timestamp": timestamp, "conditionId": market, "type": "REDEEM",
            "size": shares, "usdcSize": usdc, "title": "Test market"}


def _position(market, **overrides):
    base = {"conditionId": market, "asset": "yes", "size": 100.0, "curPrice": 0.0,
            "currentValue": 0.0, "realizedPnl": 0.0, "initialValue": 50.0,
            "totalBought": 100.0}
    base.update(overrides)
    return base


def _analyze(activity, positions=()):
    return scanner.analyze_wallet(
        {"address": "0xtest", "pseudonym": "Fixture"}, activity, list(positions)
    )


# -------------------------------------------------------- the settled record

def test_a_redeemed_market_records_its_result_close_time_and_notional():
    activity = [_buy("0xa", BASE), _redeem("0xa", BASE + DAY, usdc=100.0)]
    entry = _analyze(activity)["settled_results"][0]
    assert entry["condition_id"] == "0xa"
    assert entry["result_usdc"] == 50.0
    assert entry["closed_at"] == BASE + DAY
    assert entry["notional_usdc"] == 50.0


def test_the_close_time_is_when_the_market_paid_not_when_it_opened():
    """The equity curve is built in this order, so it has to be the moment the
    result was realised."""
    activity = [_buy("0xa", BASE), _sell("0xa", BASE + 5 * DAY)]
    assert _analyze(activity)["settled_results"][0]["closed_at"] == BASE + 5 * DAY


def test_results_are_ordered_by_close_time_whatever_order_the_feed_arrived_in():
    activity = [
        _buy("0xb", BASE + 10 * DAY), _sell("0xb", BASE + 11 * DAY),
        _buy("0xa", BASE), _sell("0xa", BASE + DAY),
    ]
    closes = [e["closed_at"] for e in _analyze(activity)["settled_results"]]
    assert closes == sorted(closes)


def test_a_redemption_larger_than_the_window_saw_bought_is_not_scored():
    """Booking a full payout against a fraction of its cost once turned a 2%
    edge into an apparent 50% one."""
    activity = [_buy("0xa", BASE, shares=10.0, usdc=5.0),
                _redeem("0xa", BASE + DAY, shares=100.0, usdc=100.0)]
    assert _analyze(activity)["settled_results"] == []


def test_a_loss_whose_cost_basis_predates_the_window_is_skipped_symmetrically():
    """Applying the completeness guard to one side only would bias every
    truncated wallet toward a loss."""
    activity = [_buy("0xa", BASE, shares=10.0, usdc=5.0)]
    positions = [_position("0xa", totalBought=1000.0, initialValue=500.0)]
    assert _analyze(activity, positions)["settled_results"] == []


def test_a_worthless_held_position_is_recorded_as_the_loss_it_is():
    activity = [_buy("0xa", BASE, shares=100.0, usdc=50.0)]
    positions = [_position("0xa", initialValue=50.0)]
    entry = _analyze(activity, positions)["settled_results"][0]
    assert entry["result_usdc"] == -50.0


def test_a_market_the_activity_window_never_saw_is_not_scored():
    """Counting a loss from outside the window against wins from inside it made
    an active wallet look ruinous."""
    activity = [_buy("0xa", BASE), _sell("0xa", BASE + DAY)]
    positions = [_position("0xoutside")]
    conditions = {e["condition_id"] for e in _analyze(activity, positions)["settled_results"]}
    assert conditions == {"0xa"}


# -------------------------------------------------------- the derived fields

def test_traded_volume_is_the_sum_of_every_fill_not_its_mean():
    """A ratio cannot be rebuilt from a mean, and Edge-to-Friction needs the
    denominator."""
    activity = [_buy("0xa", BASE, price=0.5, shares=100.0),
                _sell("0xa", BASE + DAY, price=0.8, shares=100.0)]
    assert _analyze(activity)["traded_volume_usdc"] == 50.0 + 80.0


def test_coverage_days_measures_the_span_the_window_actually_covers():
    activity = [_buy("0xa", BASE), _sell("0xa", BASE + 10 * DAY)]
    assert _analyze(activity)["coverage_days"] == 10.0


def test_a_single_fill_covers_no_span_which_is_measured_not_absent():
    assert _analyze([_buy("0xa", BASE)])["coverage_days"] == 0.0


def test_the_record_states_which_execution_profile_priced_its_replay():
    from execution.copy_execution_profile import CURRENT_PROFILE

    metrics = _analyze([_buy("0xa", BASE), _sell("0xa", BASE + DAY)])
    assert metrics["profile_fingerprint"] == CURRENT_PROFILE.fingerprint


def test_the_seven_day_window_is_anchored_to_the_last_fill_not_to_read_time():
    """Activity Recency is measured against data collection time, so a cached
    record never claims a trader went quiet while it sat on disk."""
    activity = [_buy("0xa", BASE), _buy("0xb", BASE + 100 * DAY)]
    metrics = _analyze(activity)
    assert metrics["last_trade_at"] == BASE + 100 * DAY
    assert metrics["trades_7d"] == 1


def test_the_replay_and_the_hedged_rate_are_measured_while_the_feeds_exist():
    activity = [_buy("0xa", BASE), _sell("0xa", BASE + DAY)]
    positions = [_position("0xa", size=100.0), _position("0xa", asset="no", size=100.0)]
    metrics = _analyze(activity, positions)
    assert metrics["copy_replay"]["modelled_copy_pnl"] is not None
    assert metrics["hedged_pct"] == 100.0


# ------------------------------------------------------------ the one record

def test_one_wallet_produces_one_record_carrying_its_classification():
    metrics = _analyze([_buy("0xa", BASE), _sell("0xa", BASE + DAY)])
    record = scanner.to_scanned_record(metrics, "bot", 7, ["fast gaps"])
    assert record["classification"] == "bot"
    assert record["bot_score"] == 7
    assert record["schema_version"] == scanner.SCHEMA_VERSION


def test_the_record_carries_the_evidence_the_engine_scores_from():
    metrics = _analyze([_buy("0xa", BASE), _sell("0xa", BASE + DAY)])
    record = scanner.to_scanned_record(metrics, "human", 1, [])
    for field in ("settled_results", "traded_volume_usdc", "coverage_days",
                  "hedged_pct", "copy_replay", "profile_fingerprint"):
        assert field in record


def test_the_two_legacy_files_migrate_into_one_record(tmp_path, monkeypatch):
    """Two files let one wallet hold two contradictory verdicts. The migration
    has to bring both forward, or the scanner rediscovers them as fresh work."""
    human = tmp_path / "human_alpha.json"
    bot = tmp_path / "bot_configs.json"
    human.write_text(json.dumps({"0xh": {"address": "0xh"}}), encoding="utf-8")
    bot.write_text(json.dumps({"0xb": {"address": "0xb"}}), encoding="utf-8")

    monkeypatch.setattr(scanner, "SCANNED_FILE", str(tmp_path / "scanned_wallets.json"))
    monkeypatch.setattr(scanner, "LEGACY_HUMAN_FILE", str(human))
    monkeypatch.setattr(scanner, "LEGACY_BOT_FILE", str(bot))

    merged = scanner.load_scanned()
    assert merged["0xh"]["classification"] == "human"
    assert merged["0xb"]["classification"] == "bot"


def test_the_migration_is_skipped_once_the_one_record_exists(tmp_path, monkeypatch):
    scanned = tmp_path / "scanned_wallets.json"
    scanned.write_text(json.dumps({"0xa": {"address": "0xa"}}), encoding="utf-8")
    monkeypatch.setattr(scanner, "SCANNED_FILE", str(scanned))
    monkeypatch.setattr(scanner, "LEGACY_HUMAN_FILE", str(tmp_path / "absent.json"))
    monkeypatch.setattr(scanner, "LEGACY_BOT_FILE", str(tmp_path / "absent.json"))

    assert list(scanner.load_scanned()) == ["0xa"]
