#!/usr/bin/env python3
"""What the post-cutover score distribution actually looks like.

Tier bands are absolute floors, not percentiles: a scan full of weak wallets
must not manufacture an S-Tier. That only works if the floors were set against a
real distribution, which is why ADR 0005 and ADR 0010 each re-measured rather
than adjusting by eye. The first-party cutover changes every input the score
reads, so the distribution moves and the bands have to be re-measured again.

This script is that measurement. It scores every wallet the scanner has recorded
under the current engine and reports what came out: how many were scoreable,
where the scores landed, which gates did the rejecting, and what share of
survivors each band would claim at the current floors.

It reads only what is on disk. Wallets the scanner has not measured are counted
as such rather than scored on absences, because a pending wallet is not a weak
one - and a distribution padded with zeros would move the bands for a reason
that has nothing to do with wallet quality.

    python tools/measure_tier_bands.py
    python tools/measure_tier_bands.py --json
"""
import argparse
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "src"))

from paths import DATA_DIR, SCANNED_WALLETS_FILE  # noqa: E402
from execution.copy_execution_profile import CURRENT_PROFILE  # noqa: E402
from pipeline.first_party_adapter import to_engine_metrics  # noqa: E402
from screener.score_wallets import (  # noqa: E402
    TIER_A_MIN,
    TIER_B_MIN,
    TIER_C_MIN,
    TIER_S_MIN,
    calculate_bankroll_optimized_score,
    grade_for_score,
)

BANDS = (
    ("S-Tier", TIER_S_MIN),
    ("A-Tier", TIER_A_MIN),
    ("B-Tier", TIER_B_MIN),
    ("C-Tier", TIER_C_MIN),
)


def _gate_name(reason):
    """The gate a rejection reason came from, for counting.

    Reasons are written for a reader, so the leading phrase names the gate.
    Taking the first few words groups them without teaching this script the
    exact wording of every gate, which would be one more thing to keep in sync.
    """
    return " ".join(reason.split()[:3]).rstrip(":")


def measure(records, profile=CURRENT_PROFILE):
    """Score every record and report the distribution, changing none of them."""
    scores = []
    rejected = 0
    stale = 0
    rejection_gates = Counter()
    unmeasured_inputs = Counter()
    # The gate inputs whose thresholds were calibrated against the aggregator's
    # arithmetic. After the cutover they are measured differently, so their
    # distributions are reported here rather than assumed to have held still.
    slip_rates = []
    edge_ratios = []

    for record in records:
        if record.get("profile_fingerprint") != profile.fingerprint:
            stale += 1
            continue
        metrics = to_engine_metrics(record, profile.slippage_pct)["raw_metrics"]
        actual, copy = metrics.get("actual_pnl"), metrics.get("copy_pnl")
        if actual is not None and copy is not None and abs(actual) > 0:
            slip_rates.append(max(0.0, (actual - copy) / abs(actual)))
        if metrics.get("edge_to_friction") is not None:
            edge_ratios.append(metrics["edge_to_friction"])
        result = calculate_bankroll_optimized_score(metrics, profile=profile)
        reasons = result["rejection_reasons"]
        if reasons:
            rejected += 1
            for reason in reasons:
                rejection_gates[_gate_name(reason)] += 1
                if "unmeasured" in reason:
                    unmeasured_inputs[_gate_name(reason)] += 1
            continue
        scores.append(result["final_score"])

    scores.sort()
    distribution = {
        "scoreable": len(scores),
        "rejected": rejected,
        "stale_profile": stale,
        "min": round(scores[0], 2) if scores else None,
        "p25": round(scores[int(0.25 * (len(scores) - 1))], 2) if scores else None,
        "median": round(statistics.median(scores), 2) if scores else None,
        "p75": round(scores[int(0.75 * (len(scores) - 1))], 2) if scores else None,
        "max": round(scores[-1], 2) if scores else None,
    }

    bands = {}
    for label, floor in BANDS:
        count = sum(1 for score in scores if score >= floor)
        bands[label] = {
            "floor": floor,
            "at_or_above": count,
            "share_of_survivors": round(count / len(scores), 4) if scores else None,
        }
    below_c = sum(1 for score in scores if score < TIER_C_MIN)
    bands["F-Tier"] = {
        "floor": None,
        "at_or_above": below_c,
        "share_of_survivors": round(below_c / len(scores), 4) if scores else None,
    }

    return {
        "profile_fingerprint": profile.fingerprint,
        "records_read": len(records),
        "distribution": distribution,
        "current_bands": bands,
        "grades": dict(Counter(grade_for_score(score) for score in scores)),
        "rejections_by_gate": dict(rejection_gates.most_common()),
        "rejections_for_absent_measurement": dict(unmeasured_inputs.most_common()),
        "gate_input_distributions": {
            "slippage_cost_rate": _spread(slip_rates),
            "edge_to_friction": _spread(edge_ratios),
        },
        "scores": [round(score, 2) for score in scores],
    }


def _spread(values):
    """The shape of a gate input across the scan, for recalibrating its floor."""
    if not values:
        return {"count": 0, "min": None, "p25": None, "median": None,
                "p75": None, "p90": None, "max": None}
    ordered = sorted(values)
    def at(q):
        return round(ordered[int(q * (len(ordered) - 1))], 4)
    return {
        "count": len(ordered),
        "min": round(ordered[0], 4),
        "p25": at(0.25),
        "median": round(statistics.median(ordered), 4),
        "p75": at(0.75),
        "p90": at(0.90),
        "max": round(ordered[-1], 4),
    }


def _load(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return []
    return [record for record in data.values() if isinstance(record, dict)]


def _report(result):
    dist = result["distribution"]
    print("=== TIER BAND MEASUREMENT ===")
    print(f"Records read:                                 {result['records_read']}")
    print(f"Measured under this profile and scoreable:    {dist['scoreable']}")
    print(f"Rejected by a gate:                           {dist['rejected']}")
    print(f"Measured under an older profile (not scored): {dist['stale_profile']}")

    if not dist["scoreable"]:
        print("\nNo wallet is scoreable under the current Copy Execution Profile.")
        print("The bands cannot be re-measured until the scanner has re-run:")
        print("    python overnight_scanner.py --once")
        print("Leaving the bands unchanged is the honest outcome until then.")
        return

    print("\n--- Score distribution ---")
    for key in ("min", "p25", "median", "p75", "max"):
        print(f"  {key:>6}: {dist[key]}")

    print("\n--- Share of survivors at the current floors ---")
    for label, band in result["current_bands"].items():
        floor = band["floor"]
        floor_text = f">= {floor:.0f}" if floor is not None else "below C"
        print(f"  {label:<7} {floor_text:>9}: {band['at_or_above']:>4} "
              f"({band['share_of_survivors']:.1%})")

    if result["rejections_by_gate"]:
        print("\n--- Rejections by gate ---")
        for gate, count in result["rejections_by_gate"].items():
            print(f"  {count:>4}  {gate}")

    if result["rejections_for_absent_measurement"]:
        print("\n--- Rejections for an absent measurement, not a bad one ---")
        for gate, count in result["rejections_for_absent_measurement"].items():
            print(f"  {count:>4}  {gate}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--records", default=os.path.join(DATA_DIR, SCANNED_WALLETS_FILE))
    parser.add_argument("--json", action="store_true", help="emit the measurement as JSON")
    args = parser.parse_args(argv)

    result = measure(_load(args.records))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
