"""Static game-balance tables for Satisfactory (Update 8+)."""


# Miner base extraction rate (items/min) at 100% clock, Normal-purity node.
MINER_TIERS: dict[str, float] = {
    "Mk1": 60.0,
    "Mk2": 120.0,
    "Mk3": 240.0,
}

# Per-purity multiplier on the miner's base rate.
PURITY_MULTIPLIER: dict[str, float] = {
    "IMPURE": 0.5,
    "NORMAL": 1.0,
    "PURE": 2.0,
}

# Conveyor belts: tier name and max items/min throughput.
BELT_TIERS: list[tuple[str, float]] = [
    ("Mk1", 60.0),
    ("Mk2", 120.0),
    ("Mk3", 270.0),
    ("Mk4", 480.0),
    ("Mk5", 780.0),
    ("Mk6", 1200.0),
]


def default_extraction_rate(miner_tier: str, purity: str) -> float:
    """Items/min a miner of the given tier pulls from a node of the given purity."""
    return MINER_TIERS[miner_tier] * PURITY_MULTIPLIER[purity]


def minimum_belt_tier(rate: float) -> str | None:
    """
    Smallest belt tier name that can carry `rate` items/min.
    Returns None if `rate` exceeds the highest tier (Mk6).
    """
    for tier, capacity in BELT_TIERS:
        if rate <= capacity:
            return tier
    return None
