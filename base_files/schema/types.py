"""
Shared structural dataclasses mirroring base_files/schema/types.yml.

These are the building blocks reused across multiple prototype/record kinds
(NPCs, characters, etc.) — kept here so they live next to the YAML schema
they represent and aren't redefined per prototype file.

Only types currently used by Base_NPC + Base_Grunt are defined here.
StatModifier, AbilityPackage, RoleAbility, LifepathEntry are deferred.
"""

from dataclasses import dataclass, field

from base_files.schema.enums import EquipHand, Skill


@dataclass
class SkillRank:
    """A single skill entry on a character or NPC record (types.yml lines 45-56)."""
    skill: Skill
    rank: int


@dataclass
class PrimaryEquipment:
    """Primary-hand equipment slot (types.yml lines 220-224)."""
    weapon: str = ""
    hand: EquipHand = EquipHand.Primary
    equip_condition: list[str] = field(default_factory=list)


@dataclass
class SecondaryEquipment:
    """Secondary-hand equipment slot (types.yml lines 225-229)."""
    weapon: str = ""
    hand: EquipHand = EquipHand.Holstered
