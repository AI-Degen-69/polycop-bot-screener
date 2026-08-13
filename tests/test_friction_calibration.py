#!/usr/bin/env python3
"""Whether the Paper Trade Log can actually re-derive the 4.2 multiplier.

ADR 0001 fixed the Friction Realism Multiplier from three fills and called it a
tracked estimate. `latency_slippage_profile.json` then measured 0.0-0.41% and
was never reconciled with it. These tests pin the arithmetic that closes that
gap: the ratio the log computes, the component split that explains why the two
existing measurements disagree, and the refusal to recommend a revision from a
sample too small to carry one.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from execution.friction_calibration import (  # noqa: E402
    MIN_FILLS_FOR_REVISION,
    calibration_by_arm,
    derive_friction_realism_multiplier,
    read_log,
)
from execution.paper_trade_log import (  # noqa: E402
    COPIED,
    MODELLED_SLIPPAGE_PCT_PER_SIDE,
    SKIPPED,
)


def _fill(total_pct, arm="human_alpha", latency_pct=None, depth_pct=None):
    latency = total_pct if latency_pct is None else latency_pct
    depth = 0.0 if depth_pct is None else depth_pct
    return {
        "arm": arm,
        "decision": COPIED,
        "pricing": {
            "latency_slippage_pct": latency,
            "depth_slippage_pct": depth,
            "total_slippage_pct": total_pct,
            "modelled_slippage_pct": MODELLED_SLIPPAGE_PCT_PER_SIDE,
            "friction_realism_sample": total_pct / MODELLED_SLIPPAGE_PCT_PER_SIDE,
        },
    }


def _fills(total_pct, count, arm="human_alpha"):
    return [_fill(total_pct, arm=arm) for _ in range(count)]


def test_a_log_of_fills_re_derives_the_multiplier():
    """8.4% observed against the leaderboard's 2% assumption is exactly the 4.2
    ADR 0001 asserts - computed from the log instead of from three fills."""
    result = derive_friction_realism_multiplier(_fills(8.4, MIN_FILLS_FOR_REVISION))
    assert result["recommended_multiplier"] == 4.2
    assert result["measured_fills"] == MIN_FILLS_FOR_REVISION


def test_a_thin_sample_reports_the_figure_but_refuses_to_recommend_it():
    """ADR 0001 was set from three observations and quoted as settled ever
    since. A caller must not be able to repeat that from four."""
    result = derive_friction_realism_multiplier(_fills(8.4, 3))
    assert result["observed_multiplier"]["median"] == 4.2
    assert result["recommended_multiplier"] is None
    assert result["sufficient_sample"] is False


def test_an_empty_log_derives_nothing_rather_than_zero():
    result = derive_friction_realism_multiplier([])
    assert result["measured_fills"] == 0
    assert result["recommended_multiplier"] is None
    assert result["observed_multiplier"]["median"] is None


def test_the_median_leads_so_one_illiquid_market_cannot_set_the_multiplier():
    records = _fills(2.0, MIN_FILLS_FOR_REVISION) + [_fill(400.0)]
    result = derive_friction_realism_multiplier(records)
    assert result["recommended_multiplier"] == 1.0
    assert result["observed_multiplier"]["mean"] > result["observed_multiplier"]["median"]


def test_latency_and_depth_are_reported_apart_so_the_two_measurements_can_agree():
    """The resting-book profile sees depth only; ADR 0001's fills carried the
    chase on top. Split, both numbers can be right at once."""
    result = derive_friction_realism_multiplier(
        [_fill(8.4, latency_pct=8.0, depth_pct=0.4) for _ in range(MIN_FILLS_FOR_REVISION)]
    )
    assert result["depth_slippage_pct"]["median"] == 0.4
    assert result["latency_slippage_pct"]["median"] == 8.0
    assert result["total_slippage_pct"]["median"] == 8.4


def test_a_refused_trade_contributes_no_friction_sample():
    """A trade the profile never copied has no fill, so it has no friction. It
    must not be averaged in as a zero."""
    records = _fills(8.4, 4) + [{"arm": "human_alpha", "decision": SKIPPED, "pricing": {}}]
    assert derive_friction_realism_multiplier(records)["measured_fills"] == 4


def test_an_unmeasured_fill_is_skipped_rather_than_counted_as_zero():
    unmeasured = _fill(8.4)
    unmeasured["pricing"]["total_slippage_pct"] = None
    records = _fills(8.4, 4) + [unmeasured]
    assert derive_friction_realism_multiplier(records)["measured_fills"] == 4


def test_the_arms_are_calibrated_separately_and_pooled():
    """Friction belongs to the markets a wallet trades, so the arms should
    agree. A difference between them is a finding, and pooling hides it."""
    records = _fills(8.4, 4, arm="human_alpha") + _fills(2.0, 4, arm="phase3_simulated")
    result = calibration_by_arm(records)
    assert result["arms"]["human_alpha"]["observed_multiplier"]["median"] == 4.2
    assert result["arms"]["phase3_simulated"]["observed_multiplier"]["median"] == 1.0
    assert result["pooled"]["measured_fills"] == 8


def test_a_truncated_final_line_does_not_deny_a_reader_the_complete_ones(tmp_path):
    """The log is appended to by a long-running poller, so a read taken
    mid-write can catch a partial line."""
    path = tmp_path / "paper_trades.jsonl"
    path.write_text(
        json.dumps(_fill(8.4)) + "\n" + json.dumps(_fill(8.4)) + "\n" + '{"arm": "hum',
        encoding="utf-8",
    )
    assert len(read_log(str(path))) == 2


def test_a_log_that_does_not_exist_yet_reads_as_empty(tmp_path):
    assert read_log(str(tmp_path / "absent.jsonl")) == []
