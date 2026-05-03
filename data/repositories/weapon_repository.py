from data.repositories import AbstractWeaponRepository, AbstractRecordRepository
from data.models import WeaponStats


# ---------------------------------------------------------------------------
# Implementation of `AbstractWeaponRepository`.
# Provides typed `WeaponStats` objects and weapon ID parsing
# ---------------------------------------------------------------------------
_WEAPON_STATS: dict[str, WeaponStats] = {
    "Pistol":               WeaponStats(dice_count=1, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "MediumPistol":         WeaponStats(dice_count=2, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "HeavyPistol":          WeaponStats(dice_count=3, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "VeryHeavyPistol":      WeaponStats(dice_count=4, rof=1, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "SMG":                  WeaponStats(dice_count=2, rof=1, has_autofire=True,  autofire_cap=3,    attack_skill="ShoulderArms"),
    "HeavySMG":             WeaponStats(dice_count=6, rof=1, has_autofire=True,  autofire_cap=3,    attack_skill="ShoulderArms"),
    "Shotgun":              WeaponStats(dice_count=6, rof=1, has_autofire=False, autofire_cap=None, attack_skill="ShoulderArms"),
    "AssaultRifle":         WeaponStats(dice_count=4, rof=1, has_autofire=True,  autofire_cap=4,    attack_skill="ShoulderArms"),
    "SniperRifle":          WeaponStats(dice_count=5, rof=1, has_autofire=False, autofire_cap=None, attack_skill="ShoulderArms"),
    "HeavyMachineGun":      WeaponStats(dice_count=6, rof=1, has_autofire=True,  autofire_cap=4,    attack_skill="HeavyWeapons"),
    "VeryHeavyMelee":       WeaponStats(dice_count=4, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "HeavyMelee":           WeaponStats(dice_count=3, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "MediumMelee":          WeaponStats(dice_count=2, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "LightMelee":           WeaponStats(dice_count=1, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "GrenadeLauncher":      WeaponStats(dice_count=6, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "RocketLauncher":       WeaponStats(dice_count=8, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "FlamethrowerWeapon":   WeaponStats(dice_count=2, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "Flamethrower":         WeaponStats(dice_count=2, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "Brawling":             WeaponStats(dice_count=2, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Brawling"),
}


# Longest-first so "VeryHeavyPistol" matches before "HeavyPistol" before "Pistol"
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


class YamlWeaponRepository(AbstractRecordRepository):

    def get_weapon_stats(self, weapon_type_key: str) -> WeaponStats:
        stats = _WEAPON_STATS.get(weapon_type_key)
        if stats is None:
            raise KeyError(
                f"Unknown weapon type key: {weapon_type_key!r}."
                f"Valid keys: {list(_WEAPON_STATS)}"
            )
        return stats

    def parse_weapon_id(self, weapon_id: str) -> tuple[str, bool]:
        # TODO: Augment weapon archetypes in `base_files/prototypes/weapons/_base.yml` with `has_autofire`,
        #       `autofire_cap`, `dice_count`, and `attack_skill` fields.
        #       Then replace `_WEAPON_STATS` with a YAML lookup via `YamlRecordRepository`.
        is_excellent = "excellent" in weapon_id.lower()
        weap_id_lower = weapon_id.lower()
        for keyword in _WEAPON_TYPE_KEYWORDS:
            if keyword.lower() in weap_id_lower:
                return keyword, is_excellent
        return "Unknown", is_excellent

