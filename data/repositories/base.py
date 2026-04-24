from abc import ABC, abstractmethod
from data import ResolvedRecord, WeaponStats


class AbstractRecordRepository(ABC):
    """Provides resolved game records (NPCS & PCs)."""

    @abstractmethod
    def get_record(self, record_id: str) -> ResolvedRecord:
        """
        Return a fully resolved ResolvedRecord for 'record_id'.

        Raises:
              ValueError: If record_id does not exist in the data source.
        """
        ...


class AbstractWeaponRepository(ABC):
    """Provides weapon stat lookups and weapon ID parsing."""

    @abstractmethod
    def get_weapon_stats(self, weapon_type_key: str) -> WeaponStats:
        """
        Return WeaponStats for a canonical weapon type key (e.g., 'AssaultRifle')

        Raises:
              KeyError: If the weapon type key is not recognized.
        """
        ...

    @abstractmethod
    def parse_weapon_id(self, weapon_id: str) -> tuple[str, bool]:
        """
        Parse a weapon record ID string into (weapon_type_key, is_excellent).

        Examples:
            "Weapons.Preset_HeavyPistol_Excellent"      -> ("HeavyPistol", True)
            "Weapons.VeryHeavyMeleeWeapon_Poor"         -> ("VeryHeavyMelee", False)
            "Weapons.Preset_AssaultRifle_Military"      -> ("AssaultRifle", False)
        """
        ...
