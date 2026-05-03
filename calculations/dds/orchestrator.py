"""Record-driven DDS computation.

DDS measures how durable a defender is against a specific aggressor. AAC is
now per-matchup because armor ablation depends on the actual penetration
probability of the aggressor's die pool, so this entry point takes both
record IDs.
"""

from __future__ import annotations

from api.main import (
    WEAPON_STATS,
    get_effective_sp,
    load_record,
    parse_weapon_id,
)

from .dds_math import compute_dds


DEFAULT_DSR_WEIGHT: float = 5.0


def get_body(record: dict) -> int:
    return int((record.get("attributes") or {}).get("body", 0))


def get_will(record: dict) -> int:
    return int((record.get("attributes") or {}).get("willpower", 0))


def get_n_dice(record: dict) -> int:
    """Read the aggressor's primary weapon dice_count from WEAPON_STATS."""
    weapon_id = (record.get("primaryEquipment") or {}).get("weapon", "")
    weapon_type, _ = parse_weapon_id(weapon_id)
    stats = WEAPON_STATS.get(weapon_type)
    if stats is None:
        raise ValueError(
            f"Unknown weapon type for aggressor record (weapon_id={weapon_id!r})"
        )
    return int(stats["dice_count"])


def calculate_dds_for_records(
    aggressor_id: str,
    defender_id: str,
    dsr_weight: float = DEFAULT_DSR_WEIGHT,
) -> dict:
    """Compute DDS for *defender_id* against *aggressor_id*'s primary weapon.

    The aggressor's weapon `dice_count` drives the AAC ablation calculation;
    the defender's BODY/WILL/SP feed HPP, AAC, and DSR.
    """
    aggressor = load_record(aggressor_id)
    defender = load_record(defender_id)

    body = get_body(defender)
    will = get_will(defender)
    sp = get_effective_sp(defender)
    n_dice = get_n_dice(aggressor)

    result = compute_dds(
        body=body, will=will, sp=sp, n_dice=n_dice, dsr_weight=dsr_weight
    )
    result.update(
        body=body,
        will=will,
        aggressor_id=aggressor_id,
        defender_id=defender_id,
    )
    return result
