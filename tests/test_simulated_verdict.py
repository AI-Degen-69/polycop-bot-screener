import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from execution.copy_execution_profile import CURRENT_PROFILE  # noqa: E402
from screener.simulated_verdict import (  # noqa: E402
    backtest_wallet_at_caps,
    triage_fallback_verdict,
    verdict_for_wallet,
)


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


def _dead_at(failing_levels):
    """A fetcher the endpoint does not answer for at the given slippage levels."""
    def fetcher(payload):
        if payload["slippage"] in failing_levels:
            raise RuntimeError("Network down")
        return _ok_fetcher(payload)
    return fetcher


def test_a_sweep_that_raises_is_an_endpoint_failure_with_no_row(monkeypatch):
    """ADR 0007 classification, written once: an unexpected sweep error is an
    endpoint signal that counts toward the outage streak — and never a row."""
    import screener.simulated_verdict as simulated_verdict

    def exploding_sweep(wallet, **kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(simulated_verdict, "run_slippage_sensitivity_sweep", exploding_sweep)

    verdict = verdict_for_wallet("0x1111", _triage_target("0x1111"), profile=CURRENT_PROFILE)

    assert verdict.endpoint_failure is True
    assert verdict.failure_error == "Endpoint unavailable: Boom"
    assert verdict.entry is None


def test_an_unmeasured_gated_level_is_an_endpoint_failure():
    """A gated level the endpoint did not answer for rejects with the endpoint
    signal (ADR 0007), carrying the failed level's error for the fallback
    reason — and produces no feed row."""
    verdict = verdict_for_wallet(
        "0x1111", _triage_target("0x1111"),
        profile=CURRENT_PROFILE, fetcher=_dead_at([10.0]),
    )

    assert verdict.endpoint_failure is True
    assert "Endpoint unavailable" in (verdict.failure_error or "")
    assert verdict.entry is None


def test_a_measured_rejection_is_not_an_endpoint_failure():
    """A genuinely measured non-positive PnL is a rejection, not an outage
    signal: the flag is False so the scan loop resets the failure streak."""
    def losing_fetcher(payload):
        pnl = 100.0 if payload["slippage"] == 2.0 else -5.0
        return {"sim_total_pnl": pnl, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    verdict = verdict_for_wallet(
        "0x1111", _triage_target("0x1111"),
        profile=CURRENT_PROFILE, fetcher=losing_fetcher,
    )

    assert verdict.endpoint_failure is False
    assert verdict.failure_error is None
    assert verdict.entry is None


def test_a_successful_sweep_yields_the_full_feed_row():
    verdict = verdict_for_wallet(
        "0x1111", _triage_target("0x1111"),
        profile=CURRENT_PROFILE, fetcher=_ok_fetcher,
    )
    entry = verdict.entry

    assert verdict.endpoint_failure is False
    assert verdict.failure_error is None
    assert entry is not None
    assert entry["verdict_source"] == "simulation"
    assert entry["address"] == "0x1111"
    # Retention 0.80 -> A-Tier; PnL 80.0 at the 10% run.
    assert entry["edge_retention"] == pytest.approx(0.8)
    assert entry["tier"] == "A-Tier (Strong Copy Target)"
    assert entry["simulated_copy_pnl_10"] == 80.0
    # No per-day results in the fixture: absent stays absent (ADR 0007).
    assert entry["simulated_daily_green_rate"] is None
    assert entry["simulated_trading_days"] == 0
    assert entry["simulated_max_drawdown"] is None
    assert entry["skip_reasons"] == []
    assert entry["balance_miss_details"] == []
    # The cap backtest runs on the scan's default levels and stamps tiers.
    assert [l["cap_usd"] for l in entry["cap_sweep"]] == [5.0, 10.0, 15.0, 20.0]
    assert all(l["tier"] for l in entry["cap_sweep"])


def test_a_cap_backtest_failure_is_recorded_not_fatal(monkeypatch):
    """The cap backtest is extra analysis on top of the headline verdict: an
    unexpected failure there must not cost a wallet whose headline simulation
    already succeeded."""
    import screener.simulated_verdict as simulated_verdict

    def exploding_cap_sweep(wallet, **kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(simulated_verdict, "run_cap_sensitivity_sweep", exploding_cap_sweep)

    verdict = verdict_for_wallet(
        "0x1111", _triage_target("0x1111"),
        profile=CURRENT_PROFILE, fetcher=_ok_fetcher,
    )

    assert verdict.endpoint_failure is False
    assert verdict.entry is not None
    assert verdict.entry["tier"] is not None
    assert verdict.entry["cap_sweep"][0].get("error") == "Boom"


def test_triage_fallback_verdict_presents_no_simulated_figures():
    """The degraded-shape contract: a wallet with no simulation carries its
    triage grade under its own name and none of the verdict-side figures."""
    entry = triage_fallback_verdict(_triage_target("0x1111"))

    assert entry["verdict_source"] == "triage"
    assert entry["tier"] is None
    assert entry["triage_grade"] == "A-Tier (Strong Copy Target)"
    assert entry["triage_copyability_score"] == 80.0
    assert entry["simulated_daily_green_rate"] is None
    assert entry["simulated_trading_days"] == 0
    assert entry["simulated_max_drawdown"] is None
    assert entry["skip_reasons"] == []
    assert entry["balance_miss_details"] == []
    assert entry["cap_sweep"] == []
    # Triage's own work still travels with the row.
    assert entry["activity"]["trades_7d"] == 12
    assert entry["bankroll_analysis"]["min_target_order_floor_usd"] == 8.33


def test_backtest_wallet_at_caps_runs_one_wallet_at_custom_levels():
    """The web endpoint's single-wallet backtest honours caller-chosen caps
    and stamps the simulated tier per level."""
    def fetcher(payload):
        cap = payload["sim_max_per_token"]
        pnl = 20.0 * cap if payload["slippage"] == 2.0 else 15.0 * cap
        return {"sim_total_pnl": pnl, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    levels = backtest_wallet_at_caps(
        "0x1111", [8.0, 25.0], profile=CURRENT_PROFILE, fetcher=fetcher
    )

    assert [l["cap_usd"] for l in levels] == [8.0, 25.0]
    assert [l["edge_retention"] for l in levels] == [pytest.approx(0.75)] * 2
    assert [l["tier"] for l in levels] == ["A-Tier (Strong Copy Target)"] * 2
