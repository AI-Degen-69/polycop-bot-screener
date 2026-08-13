#!/usr/bin/env python3
"""Re-deriving the Friction Realism Multiplier from the Paper Trade Log.

ADR 0001 set `FRICTION_REALISM_MULTIPLIER = 4.2` from three hand-logged fills and
called it a tracked estimate that every logged fill should revise. It has not
been revised since, and the only other friction measurement in the repo -
`app/data/latency_slippage_profile.json` - reports 0.0% to 0.41%, which read
naively would put the multiplier near zero. Both numbers can be right: they
measure different things.

* The latency/slippage profile quotes a resting book against a hypothetical
  order. Nobody is competing for that liquidity and no price has moved since a
  decision was taken, so it measures **depth** friction only.
* ADR 0001's fills were copies chasing a target who had already traded. The
  price had moved before the follower arrived, so those figures carry **latency**
  friction on top of depth.

A single blended number cannot settle the disagreement, so this module reports
the components separately and lets each be compared against the measurement it
belongs to. Every quantity here is read off the Paper Trade Log; nothing is
assumed, and a sample too small to support a revision says so rather than
producing a confident figure from four fills.
"""
import json
import os
import statistics
import sys
from typing import Any, Dict, Iterable, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.paper_trade_log import COPIED, MODELLED_SLIPPAGE_PCT_PER_SIDE  # noqa: E402

# Below this many measured fills, a re-derived multiplier is a coincidence
# rather than a calibration. ADR 0001 was set from three observations and has
# been quoted as settled fact ever since; the threshold exists so this module
# cannot repeat that mistake with a marginally larger sample.
MIN_FILLS_FOR_REVISION = 30


def _samples(records: Iterable[Dict[str, Any]], key: str) -> List[float]:
    """Measured values of one pricing field across copied fills.

    Skips absent figures rather than defaulting them to zero: a fill whose
    friction could not be measured is not a fill that had none (ADR 0007).
    """
    values = []
    for record in records:
        if record.get("decision") != COPIED:
            continue
        value = (record.get("pricing") or {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def _distribution(values: List[float]) -> Dict[str, Optional[float]]:
    """The shape of a friction sample, not just its centre.

    The median leads because a single illiquid market can move a mean by more
    than every other fill combined, and the multiplier it feeds is applied to
    every wallet the screen scores.
    """
    if not values:
        return {"count": 0, "median": None, "mean": None, "p25": None, "p75": None,
                "min": None, "max": None}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "median": round(statistics.median(ordered), 4),
        "mean": round(statistics.fmean(ordered), 4),
        "p25": round(ordered[int(0.25 * (len(ordered) - 1))], 4),
        "p75": round(ordered[int(0.75 * (len(ordered) - 1))], 4),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
    }


def derive_friction_realism_multiplier(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """What the log says the multiplier should be, and whether to believe it yet.

    `recommended_multiplier` is the median observed round-trip friction over the
    leaderboard's modelled assumption - the same ratio ADR 0001 states, computed
    over every fill instead of three. It is None until the sample is large enough
    to act on, so a caller cannot quietly adopt a figure the data does not carry.
    """
    records = list(records)
    total = _distribution(_samples(records, "total_slippage_pct"))
    latency = _distribution(_samples(records, "latency_slippage_pct"))
    depth = _distribution(_samples(records, "depth_slippage_pct"))
    multiplier = _distribution(_samples(records, "friction_realism_sample"))

    sufficient = total["count"] >= MIN_FILLS_FOR_REVISION
    return {
        "modelled_slippage_pct_per_side": MODELLED_SLIPPAGE_PCT_PER_SIDE,
        "min_fills_for_revision": MIN_FILLS_FOR_REVISION,
        "measured_fills": total["count"],
        "sufficient_sample": sufficient,
        # Reported whatever the sample size, because a reader watching the figure
        # settle needs to see it move; only the recommendation is gated.
        "observed_multiplier": multiplier,
        "recommended_multiplier": multiplier["median"] if sufficient else None,
        "total_slippage_pct": total,
        # The two components, so this log's figures can be compared against the
        # measurement each one actually corresponds to: depth against
        # latency_slippage_profile.json, latency against ADR 0001's chase.
        "latency_slippage_pct": latency,
        "depth_slippage_pct": depth,
    }


def calibration_by_arm(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """The same derivation per arm, plus the two arms pooled.

    Friction is a property of the markets a wallet trades, not of the wallet
    list it came from, so the arms should agree. If they do not, the difference
    is evidence about the markets each arm's wallets frequent - which is a
    finding, and is lost if only the pooled figure is kept.
    """
    records = list(records)
    arms = sorted({str(record.get("arm") or "") for record in records if record.get("arm")})
    return {
        "pooled": derive_friction_realism_multiplier(records),
        "arms": {
            arm: derive_friction_realism_multiplier(
                [record for record in records if record.get("arm") == arm]
            )
            for arm in arms
        },
    }


def read_log(path: str) -> List[Dict[str, Any]]:
    """Every record in a Paper Trade Log file.

    A malformed line is skipped rather than fatal: the log is appended to by a
    long-running poller, so a read taken mid-write can catch a partial final
    line, and one truncated record must not deny a reader every complete one
    before it.
    """
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


def _main() -> int:
    import argparse

    from paths import DATA_DIR

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", default=os.path.join(DATA_DIR, "paper_trades.jsonl"),
                        help="Paper Trade Log to re-derive the multiplier from")
    args = parser.parse_args()

    print(json.dumps(calibration_by_arm(read_log(args.log)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
