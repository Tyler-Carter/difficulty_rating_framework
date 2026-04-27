import bisect
import math


_RANGE_BUCKETS = (6, 12, 25, 50, 100, 200, 400, 800)
_INF = math.inf
# Longest-first so "VeryHeavyPistol" matches before "HeavyPistol" matches before "Pistol", etc.
_WEAPON_TYPE_KEYWORDS: list[str] = [
    "VeryHeavyPistol", "HeavyPistol", "MediumPistol", "Pistol",
    "HeavySMG", "SMG",
    "AssaultRifle", "SniperRifle",
    "Shotgun", "HeavyMachineGun",
    "VeryHeavyMelee", "HeavyMelee", "MediumMelee", "LightMelee",
    "GrenadeLauncher", "RocketLauncher",
    "FlamethrowerWeapon", "Flamethrower",
    "Brawling", "Bow",
]


# TODO: Replace placeholder values for HMG/flamethrower
#       with actual difficulty numbers.
_DIFFICULTY_TABLE = {
    "Pistol":           (13, 15, 20, 25, 30, 30, _INF,  _INF),
    "SMG":              (15, 13, 15, 20, 25, 25, 30,    _INF),
    "Shotgun":          (13, 15, 20, 25, 30, 35, _INF,  _INF),
    "AssaultRifle":     (17, 16, 15, 13, 15, 20, 25,     30),
    "SniperRifle":      (30, 25, 25, 20, 15, 16, 17,     20),
    "Bow":              (15, 13, 15, 17, 20, 22, _INF,  _INF),
    "GrenadeLauncher":  (16, 15, 15, 17, 20, 22, 25,    _INF),
    "RocketLauncher":   (17, 16, 15, 15, 20, 20, 25,     30),
}


# Category suffixes must match keys in _DIFFICULTY_TABLE
# Order does matter for these tuples. Longer/more-specific suffixes should be first
# E.g., 'AssaultRifle' matches before any future 'Rifle' entry would.
_CATEGORY_SUFFIXES: tuple[str, ...] = (
    "AssaultRifle", "SniperRifle",
    "GrenadeLauncher", "RocketLauncher",
    "HeavyMachineGun",
    "Pistol", "SMG", "Shotgun", "Bow",
    "Flamethrower"
)


# Explicit overrides for weapon names that don't cleanly suffix-match their category
# E.g., "FlamethrowerWeapon" doesn't end in "Flamethrower" in the way the suffix matcher expects
# Used for outlier naming schemes
_CATEGORY_OVERRIDES: dict[str, str] = {
    # "SomeOddWeaponName": "ActualCategory",
}


def _derive_category(weapon: str) -> str:
    """Map a weapon keyword to its difficulty-table category."""
    if weapon in _CATEGORY_OVERRIDES:
        return _CATEGORY_OVERRIDES[weapon]
    for suffix in _CATEGORY_SUFFIXES:
        if weapon.endswith(suffix):
            return suffix
    raise ValueError(f"No difficulty category defined for weapon {weapon!r}")


# Built once at module load; weapons without a defined category are silently skipped
# (e.g. HeavyMachineGun, Flamethrower — marked TODO in _DIFFICULTY_TABLE).
# get_difficulty() raises KeyError for skipped types; callers should handle that.
_WEAPON_TO_CATEGORY: dict[str, str] = {}
for _w in _WEAPON_TYPE_KEYWORDS:
    try:
        _WEAPON_TO_CATEGORY[_w] = _derive_category(_w)
    except ValueError:
        pass


def get_difficulty(weapon_type: str, range_m: float) -> float:
    """
    Return the difficulty value for a weapon at a given range.

    Returns math.inf when the shot cannot be made by the weapon type at the given range.
    Raises KeyError for unknown weapon types or for categories whose difficulty table hasn't
    been populated yet.
    """
    if range_m < 0:
        return _INF

    category = _WEAPON_TO_CATEGORY[weapon_type]     # KeyError if unknown
    table = _DIFFICULTY_TABLE[category]

    idx = bisect.bisect_left(_RANGE_BUCKETS, range_m)
    if idx >= len(_RANGE_BUCKETS):      # range_m > 800 m/yds
        return _INF

    value = table[idx]
    if value is None:
        raise KeyError(
            f"Difficulty for {weapon_type} at range {range_m} is not yet defined."
        )
    return value