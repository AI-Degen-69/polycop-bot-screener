#!/usr/bin/env python3
"""The Copy Execution Profile: the follower's complete copy-bot configuration.

A screening result is valid only for a stated profile, so every number that depends
on how the follower's bot executes is held here and asked for by name, rather than
being copied into whichever module happens to need it.
"""
import hashlib
import json
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class CopyExecutionProfile:
    """One immutable statement of how the follower's bot trades.

    Frozen because results are labelled with `fingerprint`: a profile that could be
    edited mid-run would let the label and the numbers behind it drift apart.
    """

    # What the follower brings, and how much of a target's trade it mirrors.
    bankroll_usd: float = 100.0
    copy_ratio: float = 0.03

    # Assumed adverse price movement per side, in percent. The Slippage Sensitivity
    # Sweep varies this field and holds every other one fixed.
    slippage_pct: float = 10.0

    # Markets priced outside these bounds are not copied at all.
    min_price: float = 0.05
    max_price: float = 0.95

    # Capital caps enforced by the bot.
    per_token_cap_usd: float = 5.0
    global_cap_usd: float = 100.0
    max_position_bankroll_fraction: float = 0.05

    # Polymarket will not accept an order below this.
    venue_min_order_usd: float = 1.00

    def __post_init__(self):
        """Reject a profile whose derived quantities would be undefined.

        The profile is edited by hand to match the bot's settings, so a typo here
        would otherwise surface as a ZeroDivisionError deep inside scoring.
        """
        if self.copy_ratio <= 0:
            raise ValueError(f"copy_ratio must be positive, got {self.copy_ratio}")

    @property
    def max_single_position_usd(self) -> float:
        """The most the bot will hold in any one position.

        Whichever cap binds first: the bankroll share, the per-token cap, or the
        global cap, since no single position can exceed the total deployment limit.
        """
        return round(
            min(
                self.bankroll_usd * self.max_position_bankroll_fraction,
                self.per_token_cap_usd,
                self.global_cap_usd,
            ),
            2,
        )

    @property
    def copy_trade_usd(self) -> float:
        """The bankroll share committed per copied trade, held under the position cap."""
        return min(self.bankroll_usd * self.copy_ratio, self.max_single_position_usd)

    @property
    def window_min_usd(self) -> float:
        """Lower bound of the Copyable Trade Window.

        Below it the copy order falls under the venue minimum and would have to be
        bumped up to reach it, which is over-exposure rather than a mirror.
        """
        return self.venue_min_order_usd / self.copy_ratio

    @property
    def window_max_usd(self) -> float:
        """Upper bound of the Copyable Trade Window.

        Above it the position cap clips the copy order, so the realised copy ratio
        falls below the nominal one. Read from the effective cap rather than from
        the per-token cap alone: raising a cap that is not the one binding widens
        nothing.
        """
        return self.max_single_position_usd / self.copy_ratio

    @property
    def sizing_fit_peak_usd(self) -> float:
        """The target trade size that scores full Sizing Fit points.

        The midpoint of the Copyable Trade Window, so it is derived from how the
        bot actually executes rather than picked by hand. It is the point
        furthest from both distortions at once: the venue minimum bumping small
        copies up, and the position cap clipping large ones down. Move a cap or
        the copy ratio and the peak follows, which a stated constant would not.
        """
        return (self.window_min_usd + self.window_max_usd) / 2.0

    def min_target_order_floor_usd(self, target_avg_invest_usd: float) -> float:
        """The smallest order from this target that the follower can still mirror.

        Derived from the participation rate the target's typical size produces:
        below this figure the follower's share of an order is under the venue
        minimum. Zero when the target's size is unknown, since the rate is then
        undefined.
        """
        if target_avg_invest_usd <= 0 or self.copy_trade_usd <= 0:
            return 0.0
        participation_rate = self.copy_trade_usd / target_avg_invest_usd
        return round(self.venue_min_order_usd / participation_rate, 2)

    def as_dict(self) -> dict:
        """The stated fields only — derived quantities are recomputed, never stored."""
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        """Stable identity of this profile, for labelling results and keying caches.

        Every field participates, so a settings change misses cache rather than
        serving a verdict computed under a profile that no longer exists. It is a
        content hash rather than `hash()` so that it holds across processes, and
        the full digest rather than a prefix, because a collision would silently
        serve one profile's cached verdict under another's settings.
        """
        canonical = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def with_bankroll(self, bankroll_usd: float) -> "CopyExecutionProfile":
        """The same settings sized to a different bankroll."""
        return replace(self, bankroll_usd=float(bankroll_usd))


# The profile this screen currently runs under. Changing it invalidates every
# previously computed result, which is what the fingerprint exists to make visible.
CURRENT_PROFILE = CopyExecutionProfile()
