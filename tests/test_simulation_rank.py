import pytest
from app.src.execution.copy_execution_profile import CURRENT_PROFILE
from app.src.pipeline.phase3_simulation_rank import run_phase3_simulation_rank

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

    out = run_phase3_simulation_rank(targets=sample_targets, profile=CURRENT_PROFILE, fetcher=failing_fetcher)

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
        "breakdown": {"1. Edge-to-Friction Ratio (22%)": 18.0},
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
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=failing_fetcher
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
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=fetcher
    )
    row = out["simulated_targets"][0]

    for field in ("activity", "breakdown", "bankroll_analysis", "metrics",
                  "is_hidden_gem", "triage_grade", "triage_copyability_score"):
        assert field in row, f"{field} was dropped, so the page loses it"
    assert row["activity"]["trades_7d"] == 12
    assert row["bankroll_analysis"]["min_target_order_floor_usd"] == 8.33


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


def test_the_feed_states_the_profile_its_numbers_were_computed_under():
    out = run_phase3_simulation_rank(
        targets=[_triage_target("0x1111")], profile=CURRENT_PROFILE, fetcher=_ok_fetcher
    )
    profile = out["copy_execution_profile"]

    assert profile["bankroll_usd"] == CURRENT_PROFILE.bankroll_usd
    assert profile["copy_ratio"] == CURRENT_PROFILE.copy_ratio
    assert profile["fingerprint"] == CURRENT_PROFILE.fingerprint
