import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from execution.copy_execution_profile import CURRENT_PROFILE  # noqa: E402
from pipeline.phase3_simulation_rank import (  # noqa: E402
    DATA_DIR,
    PHASE3_FILE,
    run_phase3_simulation_rank,
)
from screener.simulated_verdict import (  # noqa: E402
    assign_simulated_tier,
    backtest_wallet_at_caps,
)
from screener.score_wallets import (  # noqa: E402
    SIM_TIER_A_MIN,
    SIM_TIER_B_MIN,
    SIM_TIER_C_MIN,
    SIM_TIER_S_MIN,
)

def test_the_simulated_verdict_bands_are_the_documented_constants():
    """The tier a reader sees is assigned by the same constants the docs render.

    ADR 0002 makes simulation the verdict; these bands are that verdict's
    source of truth, so the boundary behaviour is pinned to the constants
    rather than to prose.
    """
    assert assign_simulated_tier(SIM_TIER_S_MIN, 100.0) == "S-Tier (God-Tier Target)"
    assert assign_simulated_tier(SIM_TIER_A_MIN, 100.0) == "A-Tier (Strong Copy Target)"
    assert assign_simulated_tier(SIM_TIER_B_MIN, 100.0) == "B-Tier (Moderate Copy Target)"
    assert assign_simulated_tier(SIM_TIER_C_MIN, 100.0) == "C-Tier (High Risk / Volatile)"
    assert assign_simulated_tier(SIM_TIER_C_MIN - 0.01, 100.0) == "F-Tier / REJECT"


def test_a_non_positive_simulated_pnl_or_absent_retention_rejects():
    assert assign_simulated_tier(0.99, 0.0) == "F-Tier / REJECT"
    assert assign_simulated_tier(None, 100.0) == "F-Tier / REJECT"


def test_scan_rank_is_stamped_from_the_final_ordering():
    """Rank within the scan is read off the published order, 1-based.

    Stamped after sorting so it always matches the order the feed ships,
    including on the degraded path where the fallback ordering differs.
    """
    def ok_fetcher(payload):
        return {"sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    out = run_phase3_simulation_rank(
        targets=[
            {"address": "0x1111", "name": "T1", "final_score": 70.0, "grade": "B-Tier", "metrics": {"avg_invest": 25.0}},
            {"address": "0x2222", "name": "T2", "final_score": 90.0, "grade": "S-Tier", "metrics": {"avg_invest": 25.0}},
        ],
        profile=CURRENT_PROFILE,
        fetcher=ok_fetcher,
    )
    assert [r["scan_rank"] for r in out["simulated_targets"]] == [1, 2]

    # The degraded path ranks by triage score, and the rank follows that order.
    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    degraded = run_phase3_simulation_rank(
        targets=[
            {"address": "0x1111", "name": "T1", "final_score": 70.0, "grade": "B-Tier", "metrics": {"avg_invest": 25.0}},
            {"address": "0x2222", "name": "T2", "final_score": 90.0, "grade": "S-Tier", "metrics": {"avg_invest": 25.0}},
        ],
        profile=CURRENT_PROFILE,
        fetcher=failing_fetcher,
        # Every wallet failing counts as an outage for this dead-endpoint test.
        endpoint_failure_threshold=1,
    )
    assert [r["address"] for r in degraded["simulated_targets"]] == ["0x2222", "0x1111"]
    assert [r["scan_rank"] for r in degraded["simulated_targets"]] == [1, 2]


def test_simulation_rank_ordering_and_tier_assignment():
    """Verify targets are ranked by edge retention and assigned simulated tiers."""
    sample_targets = [
        {
            "address": "0x1111",
            "name": "Target Alpha",
            "final_score": 85.0,
            "grade": "A-Tier",
            "metrics": {"avg_invest": 25.0}
        },
        {
            "address": "0x2222",
            "name": "Target Beta",
            "final_score": 92.0,
            "grade": "S-Tier",
            "metrics": {"avg_invest": 25.0}
        }
    ]

    # Target Alpha: 2% -> 100, 10% -> 90 (retention = 0.90 -> S-Tier)
    # Target Beta: 2% -> 100, 10% -> 75 (retention = 0.75 -> A-Tier)
    def mock_fetcher(payload):
        addr = payload["wallet"]
        slip = payload["slippage"]
        if addr == "0x1111":
            pnl = 100.0 if slip == 2.0 else 90.0
        else:
            pnl = 100.0 if slip == 2.0 else 75.0
        return {"sim_total_pnl": pnl, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    out = run_phase3_simulation_rank(targets=sample_targets, profile=CURRENT_PROFILE, fetcher=mock_fetcher)

    assert out["reduced_confidence"] is False
    assert len(out["simulated_targets"]) == 2
    # Ranked by Edge Retention descending: Alpha (0.90) > Beta (0.75)
    assert out["simulated_targets"][0]["address"] == "0x1111"
    assert out["simulated_targets"][0]["edge_retention"] == 0.90
    assert out["simulated_targets"][0]["tier"] == "S-Tier (God-Tier Target)"

    assert out["simulated_targets"][1]["address"] == "0x2222"
    assert out["simulated_targets"][1]["edge_retention"] == 0.75
    assert out["simulated_targets"][1]["tier"] == "A-Tier (Strong Copy Target)"

def test_simulation_rank_endpoint_failure_fallback():
    """Verify fallback to copyability score ordering on endpoint failure."""
    sample_targets = [
        {"address": "0x1111", "final_score": 75.0, "name": "Trader One"},
        {"address": "0x2222", "final_score": 95.0, "name": "Trader Two"}
    ]

    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    out = run_phase3_simulation_rank(
        targets=sample_targets,
        profile=CURRENT_PROFILE,
        fetcher=failing_fetcher,
        # Every wallet failing counts as an outage for this dead-endpoint test.
        endpoint_failure_threshold=1,
    )

    assert out["reduced_confidence"] is True
    assert out["fallback_reason"] == "Endpoint unavailable: Network down"
    # Ordered by triage copyability score descending (95.0 > 75.0)
    assert out["simulated_targets"][0]["address"] == "0x2222"
    assert out["simulated_targets"][0]["triage_copyability_score"] == 95.0


def _triage_target(address, **overrides):
    base = {
        "address": address,
        "name": "Carried Trader",
        "final_score": 80.0,
        "grade": "A-Tier (Strong Copy Target)",
        "is_hidden_gem": True,
        "activity": {"hours_since_active": 3.0, "trades_7d": 12},
        "breakdown": {"edge_to_friction": 18.0},
        "bankroll_analysis": {"min_target_order_floor_usd": 8.33},
        "metrics": {"avg_invest": 100.0, "polycop_site_score": 70.0},
    }
    base.update(overrides)
    return base


def _ok_fetcher(payload):
    return {
        "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0,
        "target_total_pnl": 500.0,
        "logs": [{"type": "INTERCEPT"}],
    }


def test_a_degraded_run_never_presents_a_triage_grade_as_a_simulated_tier():
    """The letter is identical either way; only the label distinguishes them.

    Filling `tier` with the triage grade would put a Copyability Score verdict
    in the position a reader reads as simulated performance.
    """
    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=failing_fetcher,
        endpoint_failure_threshold=1,
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "triage"
    assert row["tier"] is None
    # The grade is still published, under a name that says what it is.
    assert row["triage_grade"] == "A-Tier (Strong Copy Target)"


def test_a_simulated_run_labels_its_verdict_as_simulated():
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert row["tier"] is not None


def test_the_verdict_side_window_share_is_published_from_the_10pct_run():
    """ADR 0006: window share is simulation-only, so the feed's value is the
    verdict side's measurement, never a triage default.

    The share is computed from the 10%-slippage run's decision log: five BUY
    entries, two refused by the size window, admit three of five.
    """
    def fetcher(payload):
        logs = []
        if payload["slippage"] == 10.0:
            logs = [
                {"type": "BUY", "action": "BUY",
                 "msg": "[m] Target BUY 10.00 shares @ $0.500."},
                {"type": "BUY", "action": "BUY",
                 "msg": "[m] Target BUY 10.00 shares @ $0.500."},
                {"type": "BUY", "action": "BUY",
                 "msg": "[m] Target BUY 10.00 shares @ $0.500."},
                {"type": "INTERCEPT", "action": "SKIP_FILTER",
                 "msg": "[m] Target BUY 10.00 shares @ $0.500. Sim skipped: Target size out of bounds"},
                {"type": "INTERCEPT", "action": "SKIP_FILTER",
                 "msg": "[m] Target BUY 10.00 shares @ $0.500. Sim skipped: Target size out of bounds"},
            ]
        return {
            "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0,
            "target_total_pnl": 500.0,
            "logs": logs,
        }

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=fetcher
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert row["copyable_window_share"] == 0.6


def test_a_degraded_run_publishes_no_window_share():
    """With no simulation there is no measured share, and none is fabricated."""
    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=failing_fetcher,
        endpoint_failure_threshold=1,
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "triage"
    assert row["copyable_window_share"] is None


@pytest.mark.parametrize("fetcher_name", ["ok", "failing"])
def test_the_feed_carries_what_the_page_needs_from_triage(fetcher_name):
    """Phase 3 publishes the feed the page reads, so anything it drops vanishes.

    Activity filters, the breakdown bars, the copy-ready floor and the gems
    toggle are all driven by fields triage produced.
    """
    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    fetcher = _ok_fetcher if fetcher_name == "ok" else failing_fetcher
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=fetcher,
        endpoint_failure_threshold=1,
    )
    row = out["simulated_targets"][0]

    for field in ("activity", "breakdown", "bankroll_analysis", "metrics",
                  "is_hidden_gem", "triage_grade", "triage_copyability_score"):
        assert field in row, f"{field} was dropped, so the page loses it"
    assert row["activity"]["trades_7d"] == 12
    assert row["bankroll_analysis"]["min_target_order_floor_usd"] == 8.33


def test_one_transient_endpoint_failure_keeps_the_rest_of_the_scan():
    """Issue #25's core: a single wallet the endpoint did not answer for is
    rejected honestly (ADR 0007) while the scan continues — one flaky request
    no longer throws the whole scan's simulation work away.
    """
    def flaky_fetcher(payload):
        if payload["wallet"] == "0x2222":
            raise RuntimeError("Transient network blip")
        return _ok_fetcher(payload)

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111"), _triage_target("0x2222"), _triage_target("0x3333")],
        profile=CURRENT_PROFILE,
        fetcher=flaky_fetcher,
    )

    assert out["reduced_confidence"] is False
    # 0x2222 was dropped (endpoint-failure rejection); the other two keep
    # simulated verdicts.
    assert [t["address"] for t in out["simulated_targets"]] == ["0x1111", "0x3333"]
    assert all(t["verdict_source"] == "simulation" for t in out["simulated_targets"])


def test_a_sustained_failure_streak_degrades_but_keeps_prior_verdicts():
    """Once consecutive endpoint failures cross the threshold, the scan stops
    and the unreached wallets fall back to triage order — but the verdicts
    already computed are published, not thrown away.
    """
    def partially_dead_fetcher(payload):
        if payload["wallet"] in ("0x1111", "0x2222"):
            return _ok_fetcher(payload)
        raise RuntimeError("Network down")

    out = run_phase3_simulation_rank(
        targets=[
            _triage_target("0x1111"),
            _triage_target("0x2222"),
            _triage_target("0x3333"),
            _triage_target("0x4444"),
        ],
        profile=CURRENT_PROFILE,
        fetcher=partially_dead_fetcher,
        # The first failure (0x3333) is a flake and the scan continues; the
        # second consecutive one (0x4444) crosses the threshold.
        endpoint_failure_threshold=2,
    )

    assert out["reduced_confidence"] is True
    assert out["fallback_reason"] == "Endpoint unavailable: Network down"
    # 0x1111 and 0x2222 keep simulated verdicts; 0x4444 (never reached) falls
    # back to triage. 0x3333 was reached and endpoint-rejected, so it is not
    # in the feed at all.
    assert [t["address"] for t in out["simulated_targets"]] == ["0x1111", "0x2222", "0x4444"]
    assert [t["verdict_source"] for t in out["simulated_targets"]] == ["simulation", "simulation", "triage"]
    assert out["simulated_targets"][2]["tier"] is None
    # The cap summary counts only wallets that were actually backtested: the
    # triage fallback has no backtest, so it is neither an upgrade nor part
    # of the denominator. The two simulated wallets stay flat, so every level
    # reports zero upgrades — an answer, not a hidden line.
    assert out["cap_sweep_backtested"] == 2
    assert out["cap_sweep_upgrades"] == [
        {"cap_usd": 10.0, "upgrades": 0},
        {"cap_usd": 15.0, "upgrades": 0},
        {"cap_usd": 20.0, "upgrades": 0},
    ]


def test_a_measured_rejection_is_not_an_outage_signal():
    """A wallet that measured a non-positive PnL is a normal rejection, not an
    endpoint failure — it must reset the failure streak, never trigger it.
    """
    def fetcher(payload):
        if payload["wallet"] in ("0x1111", "0x4444"):
            raise RuntimeError("Network down")
        if payload["wallet"] == "0x2222":
            # Genuine measured loss at 10%: the endpoint answered.
            return {
                "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else -5.0,
                "target_total_pnl": 500.0,
                "logs": [{"type": "INTERCEPT"}],
            }
        return _ok_fetcher(payload)

    out = run_phase3_simulation_rank(
        targets=[
            _triage_target("0x1111"),
            _triage_target("0x2222"),
            _triage_target("0x3333"),
            _triage_target("0x4444"),
        ],
        profile=CURRENT_PROFILE,
        fetcher=fetcher,
        endpoint_failure_threshold=2,
    )

    # The streak is 0x1111 (failure), then reset by 0x2222's measured
    # rejection, then 0x4444's single failure — never two consecutive, so the
    # scan never degrades.
    assert out["reduced_confidence"] is False
    assert [t["address"] for t in out["simulated_targets"]] == ["0x3333"]


def test_the_feed_publishes_none_at_a_failed_non_gated_level():
    """ADR 0007 consequence: a failed non-gated level is a visible `None` gap
    in the published decay curve — it neither rejects the wallet nor degrades
    the scan.
    """
    def fetcher(payload):
        if payload["slippage"] == 5.0:
            raise RuntimeError("Network down")
        return _ok_fetcher(payload)

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=fetcher
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert row["pnl_by_slippage_level"][5.0] is None
    assert row["pnl_by_slippage_level"][10.0] == 80.0


def test_the_verdict_side_publishes_green_rate_and_drawdown_from_the_sim():
    """Issue #26: Daily Green Rate and Drawdown Depth on the verdict side come
    from the simulation's per-day results, not the leaderboard's lifetime
    series — a follower's 1 green day of 3 trading days is 33.33%, and the
    sim's reported drawdown (percent) is published as measured.
    """
    def fetcher(payload):
        return {
            "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0,
            "target_total_pnl": 500.0,
            "winning_days": 1,
            "losing_days": 2,
            "flat_days": 0,
            "trading_days": 3,
            "max_drawdown": 7.18,
            "logs": [{"type": "INTERCEPT"}],
        }

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=fetcher
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert row["simulated_daily_green_rate"] == pytest.approx(33.33)
    assert row["simulated_trading_days"] == 3
    assert row["simulated_max_drawdown"] == 7.18


def test_the_verdict_side_publishes_skip_reasons_from_the_decision_log():
    """Spec #13: the simulation's decision log is retained on the reader's
    side — the refusals arrive with the message naming the failing filter.
    """
    def fetcher(payload):
        logs = [
            {"action": "SKIP_FILTER",
             "msg": "[m] Target BUY 10.00 shares @ $0.500. Sim skipped: Target size out of bounds"},
            {"action": "SKIP_CAP",
             "msg": "[m] Target BUY 5.00 shares @ $0.600. Sim skipped: risk cap"},
            {"action": "BUY", "msg": "[m] Target BUY 3.00 shares @ $0.500."},
        ]
        return {
            "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0,
            "target_total_pnl": 500.0,
            "logs": logs,
        }

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=fetcher
    )
    row = out["simulated_targets"][0]

    assert [r["action"] for r in row["skip_reasons"]] == ["SKIP_FILTER", "SKIP_CAP"]
    assert "Target size out of bounds" in row["skip_reasons"][0]["msg"]


def test_absent_sim_figures_stay_absent_on_the_verdict_side():
    """A response without per-day results or a drawdown reports nothing, not
    zero: a 0% green rate or a 0.0% drawdown would be fabricated verdicts.
    """
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )
    row = out["simulated_targets"][0]

    assert row["simulated_daily_green_rate"] is None
    assert row["simulated_trading_days"] == 0
    assert row["simulated_max_drawdown"] is None
    assert row["skip_reasons"] == []


def test_a_malformed_verdict_field_does_not_crash_the_scan():
    """A malformed upstream figure (e.g. `max_drawdown: "N/A"`) reads as
    unmeasured on the verdict side rather than crashing the whole scan or
    fabricating a number.
    """
    def fetcher(payload):
        return {
            "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0,
            "target_total_pnl": 500.0,
            "winning_days": 1,
            "losing_days": 2,
            "flat_days": 0,
            "trading_days": 3,
            "max_drawdown": "N/A",
            "logs": [{"type": "INTERCEPT"}],
        }

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=fetcher
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert row["simulated_daily_green_rate"] == pytest.approx(33.33)
    assert row["simulated_max_drawdown"] is None


def test_a_degraded_run_publishes_no_verdict_metrics():
    """The triage fallback carries none of the verdict-side figures: there is
    no simulation, so nothing is fabricated in their place.
    """
    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=failing_fetcher,
        endpoint_failure_threshold=1,
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "triage"
    assert row["simulated_daily_green_rate"] is None
    assert row["simulated_trading_days"] == 0
    assert row["simulated_max_drawdown"] is None
    assert row["skip_reasons"] == []


def test_a_sweep_exception_does_not_degrade_the_scan(monkeypatch):
    """A sweep that raises is a data or code fault, not an outage: a dead
    endpoint is already reported as `endpoint_failure` by the fetch layer, so
    an exception says nothing about the endpoint. It must not degrade the scan
    into triage fallbacks that claim an outage. (CodeRabbit, PR #34.)
    """
    import pipeline.phase3_simulation_rank as phase3
    import screener.simulated_verdict as simulated_verdict

    def exploding_sweep(wallet, **kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(simulated_verdict, "run_slippage_sensitivity_sweep", exploding_sweep)

    out = phase3.run_phase3_simulation_rank(
        targets=[_triage_target("0x1111"), _triage_target("0x2222")],
        profile=CURRENT_PROFILE,
        fetcher=_ok_fetcher,
        endpoint_failure_threshold=1,
    )

    assert out["reduced_confidence"] is False
    assert out["fallback_reason"] is None
    # Neither wallet produced a row, and none is invented in their place.
    assert out["simulated_targets"] == []
    assert out["simulated_survivors_count"] == 0


def test_a_recovered_flake_publishes_no_fallback_reason():
    """A failure that never becomes a streak is a flake: the scan does not
    degrade and the summary carries no fallback reason.
    """
    def flaky_fetcher(payload):
        if payload["wallet"] == "0x1111":
            raise RuntimeError("Transient blip")
        return _ok_fetcher(payload)

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111"), _triage_target("0x2222")],
        profile=CURRENT_PROFILE,
        fetcher=flaky_fetcher,
        endpoint_failure_threshold=3,
    )

    assert out["reduced_confidence"] is False
    assert out["fallback_reason"] is None


def _fetcher_with_market_stats(market_stats):
    def fetcher(payload):
        return {
            "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0,
            "target_total_pnl": 500.0,
            "logs": [{"type": "INTERCEPT"}, {"type": "BUY", "action": "SKIP_FILTER"}],
            "market_stats": market_stats,
        }
    return fetcher


def test_balance_miss_reports_the_markets_the_bankroll_could_not_fund():
    """Balance Miss comes off `market_stats`, not the decision logs.

    The logs answer why a trade was filtered out; only `sim_missed_amount`
    says the money ran out. Reading the miss off the logs finds nothing and
    reports every wallet as fully funded.
    """
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=_fetcher_with_market_stats([
            {"title": "Fed cuts in March?", "sim_missed_amount": 12.5},
            {"title": "Funded market", "sim_missed_amount": 0.0},
            {"title": "Biggest miss", "sim_missed_amount": 40.0},
        ]),
    )
    misses = out["simulated_targets"][0]["balance_miss_details"]

    # Markets that funded everything are dropped, largest miss first.
    assert misses == [
        {"market": "Biggest miss", "amount": 40.0},
        {"market": "Fed cuts in March?", "amount": 12.5},
    ]


def test_balance_miss_is_empty_when_every_copyable_trade_was_funded():
    """An empty list is the only honest way to claim the bankroll held."""
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=_fetcher_with_market_stats([
            {"title": "Funded market", "sim_missed_amount": 0.0},
        ]),
    )

    assert out["simulated_targets"][0]["balance_miss_details"] == []


def test_balance_miss_survives_a_response_without_market_stats():
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )

    assert out["simulated_targets"][0]["balance_miss_details"] == []


def test_the_feed_carries_the_per_cap_backtest_for_each_wallet():
    """Wallets that passed screening are backtested under rising per-position
    caps; each level's verdict is published beside the headline one, labelled
    by cap so a reader can see what a wider cap would have changed."""
    def fetcher(payload):
        cap = payload["sim_max_per_token"]
        # A wallet that only pays off once allowed to size up.
        pnl = 10.0 * cap if payload["slippage"] == 2.0 else 7.0 * cap
        return {"sim_total_pnl": pnl, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=fetcher
    )
    row = out["simulated_targets"][0]
    sweep = row["cap_sweep"]

    assert [r["cap_usd"] for r in sweep] == [5.0, 10.0, 15.0, 20.0]
    # 7/10 retention at every level in this fixture -> A-Tier everywhere.
    assert all(r["edge_retention"] == pytest.approx(0.7) for r in sweep)
    assert [r["tier"] for r in sweep] == ["A-Tier (Strong Copy Target)"] * 4
    assert [round(r["window_max_usd"], 2) for r in sweep] == [166.67, 333.33, 500.0, 666.67]
    assert out["cap_sweep_levels"] == [5.0, 10.0, 15.0, 20.0]
    assert out["cap_sweep_baseline_cap"] == 5.0
    # Constant retention means no level outranks the headline — zero upgrades
    # at every level, reported as zeros rather than hidden.
    assert out["cap_sweep_upgrades"] == [
        {"cap_usd": 10.0, "upgrades": 0},
        {"cap_usd": 15.0, "upgrades": 0},
        {"cap_usd": 20.0, "upgrades": 0},
    ]
    assert out["cap_sweep_backtested"] == 1


def test_a_degraded_run_publishes_no_cap_backtest():
    """With no simulation there is no cap backtest, and none is fabricated."""
    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=failing_fetcher,
        endpoint_failure_threshold=1,
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "triage"
    assert row["cap_sweep"] == []
    # With nothing backtested, the summary claims no upgrades and no sample.
    assert out["cap_sweep_upgrades"] == []
    assert out["cap_sweep_backtested"] == 0


def test_the_summary_counts_wallets_that_would_upgrade_at_wider_caps():
    """The header summary's promise: for each wider cap, how many backtested
    wallets earn a tier above their headline verdict."""
    def cap_dependent_fetcher(payload):
        # PnL at 10% slippage varies by wallet and by the cap in force; the
        # 2% baseline is flat, so Edge Retention is pnl_10 / 100.
        pnl_10 = {
            # Upgrades at every wider level: C -> B -> A -> S.
            "0x1111": {5: 40.0, 10: 55.0, 15: 75.0, 20: 90.0},
            # A-Tier at every cap, so never an upgrade.
            "0x2222": {5: 80.0, 10: 80.0, 15: 80.0, 20: 80.0},
            # Only a $20 cap unlocks it: C at 5/10/15, S at 20.
            "0x3333": {5: 45.0, 10: 45.0, 15: 45.0, 20: 90.0},
        }[payload["wallet"]][payload["sim_max_per_token"]]
        return {
            "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else pnl_10,
            "target_total_pnl": 500.0,
            "logs": [{"type": "INTERCEPT"}],
        }

    out = run_phase3_simulation_rank(
        targets=[
            _triage_target("0x1111"),
            _triage_target("0x2222"),
            _triage_target("0x3333"),
        ],
        profile=CURRENT_PROFILE,
        fetcher=cap_dependent_fetcher,
    )

    # Headline verdicts come from the $5 cap: 0.40 -> C, 0.80 -> A, 0.45 -> C.
    tiers = {t["address"]: t["tier"].split(" ")[0] for t in out["simulated_targets"]}
    assert tiers == {"0x1111": "C-Tier", "0x2222": "A-Tier", "0x3333": "C-Tier"}

    assert out["cap_sweep_backtested"] == 3
    assert out["cap_sweep_baseline_cap"] == 5.0
    assert out["cap_sweep_upgrades"] == [
        {"cap_usd": 10.0, "upgrades": 1},
        {"cap_usd": 15.0, "upgrades": 1},
        {"cap_usd": 20.0, "upgrades": 2},
    ]


def test_a_wallet_whose_backtest_errored_is_not_counted(monkeypatch):
    """A backtest that raised produced no measurement, so it contributes to
    neither the upgrade counts nor the backtested denominator."""
    import pipeline.phase3_simulation_rank as phase3
    import screener.simulated_verdict as simulated_verdict

    def exploding_cap_sweep(wallet, **kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(simulated_verdict, "run_cap_sensitivity_sweep", exploding_cap_sweep)

    out = phase3.run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert row["cap_sweep"][0].get("error") == "Boom"
    assert out["cap_sweep_upgrades"] == []
    assert out["cap_sweep_backtested"] == 0


def test_a_wallet_the_endpoint_failed_at_one_cap_is_not_counted():
    """A cap level the endpoint did not answer for leaves the wallet without a
    complete backtest. Reading only the first level counted such a wallet in
    the denominator the upgrade rate is reported against, even when every
    later level failed. (CodeRabbit, PR #34.)"""
    def dead_above_the_baseline(payload):
        # The headline verdict (the $5 cap) succeeds, so the wallet publishes
        # a simulated row; every wider cap is an endpoint failure.
        if payload["sim_max_per_token"] > 5:
            raise RuntimeError("Network down")
        pnl = 100.0 if payload["slippage"] == 2.0 else 80.0
        return {"sim_total_pnl": pnl, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")],
        profile=CURRENT_PROFILE,
        fetcher=dead_above_the_baseline,
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert any(level.get("endpoint_failure") for level in row["cap_sweep"])
    assert out["cap_sweep_upgrades"] == []
    assert out["cap_sweep_backtested"] == 0


def test_backtest_wallet_at_caps_runs_one_wallet_at_custom_levels():
    """The web endpoint's single-wallet backtest honours caller-chosen caps,
    stamps the simulated tier per level, and never touches the profile
    defaults — the derived profiles exist only for the run."""
    def fetcher(payload):
        cap = payload["sim_max_per_token"]
        # Flat 75% retention: pnl_10 / pnl_2 = 15 / 20 at every cap.
        pnl = 20.0 * cap if payload["slippage"] == 2.0 else 15.0 * cap
        return {"sim_total_pnl": pnl, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    levels = backtest_wallet_at_caps(
        "0x1111", [8.0, 25.0], profile=CURRENT_PROFILE, fetcher=fetcher
    )

    assert [level["cap_usd"] for level in levels] == [8.0, 25.0]
    assert [level["edge_retention"] for level in levels] == [pytest.approx(0.75)] * 2
    assert [level["tier"] for level in levels] == ["A-Tier (Strong Copy Target)"] * 2
    # The window follows the derived cap, not the $5 default.
    assert [round(level["window_max_usd"], 2) for level in levels] == [
        round(CURRENT_PROFILE.with_position_cap(8.0).window_max_usd, 2),
        round(CURRENT_PROFILE.with_position_cap(25.0).window_max_usd, 2),
    ]


def test_backtest_wallet_at_caps_rejects_a_non_positive_cap():
    """A cap the profile machinery refuses (0 / negative / non-finite) is a
    client error, surfaced by the endpoint as a 400."""
    for bad_levels in ([0.0], [-5.0], [float("nan")]):
        with pytest.raises(ValueError):
            backtest_wallet_at_caps(
                "0x1111", bad_levels, profile=CURRENT_PROFILE, fetcher=_ok_fetcher
            )


def test_a_cap_sweep_failure_does_not_cost_the_wallet_its_verdict(monkeypatch):
    """The cap backtest is extra analysis on top of the headline verdict: an
    unexpected failure there must not reject a wallet whose headline
    simulation already succeeded."""
    import pipeline.phase3_simulation_rank as phase3
    import screener.simulated_verdict as simulated_verdict

    def exploding_cap_sweep(wallet, **kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(simulated_verdict, "run_cap_sensitivity_sweep", exploding_cap_sweep)

    out = phase3.run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )
    row = out["simulated_targets"][0]

    assert row["verdict_source"] == "simulation"
    assert row["tier"] is not None
    assert row["cap_sweep"][0].get("error") == "Boom"


def test_the_feed_states_the_profile_its_numbers_were_computed_under():
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )
    profile = out["copy_execution_profile"]

    assert profile["bankroll_usd"] == CURRENT_PROFILE.bankroll_usd
    assert profile["copy_ratio"] == CURRENT_PROFILE.copy_ratio
    assert profile["fingerprint"] == CURRENT_PROFILE.fingerprint


def test_a_fixture_run_never_touches_the_live_feed_file():
    """Fixture-driven runs (all of the tests here) must not write the feed the

    web app serves. An earlier version wrote unconditionally, so every
    test-suite run clobbered app/data/phase3_simulated_targets.json with
    synthetic wallets. The production path (targets=None, reading Phase 2)
    is the only one allowed to publish.
    """
    feed = os.path.join(DATA_DIR, PHASE3_FILE)
    before = open(feed, "rb").read() if os.path.exists(feed) else None

    run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )

    after = open(feed, "rb").read() if os.path.exists(feed) else None
    assert after == before, "a fixture run rewrote the live feed file"


def test_the_production_path_publishes_the_feed(tmp_path, monkeypatch):
    """The run that reads Phase 2 must actually write the feed.

    Only the negative half of this rule was pinned, and the guard that
    enforced it asked `targets is None` after `targets` had already been
    filled in from the Phase 2 file — so it was never true on the path that
    publishes, and a real scan silently left the web app serving whatever
    was there before.
    """
    import json

    import pipeline.phase3_simulation_rank as phase3

    monkeypatch.setattr(phase3, "DATA_DIR", str(tmp_path))
    phase2 = tmp_path / "phase2_verified_targets.json"
    phase2.write_text(
        json.dumps({"verified_targets": [_triage_target("0x1111")]}), encoding="utf-8"
    )

    summary = phase3.run_phase3_simulation_rank(
        profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )

    feed = tmp_path / "phase3_simulated_targets.json"
    assert feed.exists(), "the production path did not publish the feed"
    published = json.loads(feed.read_text(encoding="utf-8"))
    assert published["total_targets_evaluated"] == 1
    # Not object equality: JSON renders the sweep's float slippage keys as
    # strings, so the published copy differs from the in-memory one there.
    assert [t["address"] for t in published["simulated_targets"]] == [
        t["address"] for t in summary["simulated_targets"]
    ]
    assert published["simulated_targets"][0]["tier"] == summary["simulated_targets"][0]["tier"]
