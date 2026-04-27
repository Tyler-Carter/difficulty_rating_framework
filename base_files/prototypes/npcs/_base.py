"""
NPC prototype dataclasses mirroring base_files/prototypes/npcs/_base.yml.

Hierarchy (filled in incrementally — only Base_NPC + Base_Grunt live here for now):

    Base_NPC                        <- universal root
      |- Base_Grunt                 <- disposable combatant (Mook tier)
      |     |- Base_GangGrunt
      |     |     '- Base_Bozo_Grunt
      |     |- Base_CorpoSec_Grunt
      |     '- Base_NCPD_Officer
      |- Base_HardenedMook
      |     '- Base_HardenedGangGrunt
      |           '- Base_Bozo_HardenedGrunt
      |- Base_Elite                 <- (and the rest of the tree)
      ...

Subclasses override prototype defaults by re-declaring fields with new defaults —
that's the entire inheritance mechanism. No __init__ overrides, no super() calls.

Derived stats split by nature:
  - Pure formulas (max_hp, run) live as @property and always recompute from inputs.
  - Mutable runtime state (current_hp, humanity, luck_pool) is field(init=False),
    seeded once in __post_init__; gameplay code mutates it afterward.
"""

from dataclasses import dataclass, field
from math import ceil
from typing import ClassVar

from base_files.schema.enums import (
    AttitudeGroup,
    Faction,
    NPCRarity,
    NPCRole,
    NPCType,
    Skill,
    EquipHand
)
from base_files.schema.types import PrimaryEquipment, SecondaryEquipment, SkillRank


# =============================================================================
# UNIVERSAL NPC ROOT
# =============================================================================

@dataclass
class Base_NPC:
    """Universal NPC root prototype (mirrors NPC.Base_NPC in _base.yml)."""

    # $type contract — class-level constant, excluded from instance fields.
    TYPE: ClassVar[str] = "NPC"

    # --- Identity (overridden at leaf) ---
    name: str = ""
    handle: str = ""
    description: str | None = None
    lore: str | None = None
    age: int | None = None
    cultural_origin: str | None = None

    # --- Classification ---
    npc_type: NPCType = NPCType.EncounterNPC
    npc_role: NPCRole = NPCRole.Grunt
    npc_rarity: NPCRarity = NPCRarity.Normal
    faction: Faction = Faction.Neutral
    attitude_group: AttitudeGroup = AttitudeGroup.Hostile

    # --- Attributes (minimum defaults; override at tier or leaf) ---
    intelligence: int = 2
    reflexes: int = 2
    dexterity: int = 2
    tech: int = 2
    cool: int = 2
    willpower: int = 2
    luck: int = 2
    move: int = 2
    body: int = 2
    empathy: int = 2

    death_save_threshold: int = 10

    # --- Mutable runtime state (seeded by __post_init__, then gameplay mutates) ---
    current_hp: int = field(init=False)
    humanity: int = field(init=False)
    luck_pool: int = field(init=False)

    armor: int = 0

    # --- Skills, abilities, cyberware ---
    skills: list[SkillRank] = field(default_factory=list)
    abilities: list = field(default_factory=list)
    stat_modifiers: list = field(default_factory=list)
    cyberware: list = field(default_factory=list)
    other_drops: list = field(default_factory=list)

    # --- Equipment ---
    armor_record: str = ""
    primary_equipment: PrimaryEquipment = field(default_factory=PrimaryEquipment)
    secondary_equipment: SecondaryEquipment = field(default_factory=SecondaryEquipment)

    # --- Loot / encounter flags ---
    drops_weapon: bool = False
    is_invulnerable: bool = False

    @property
    def max_hp(self) -> int:
        return 10 + 5 * ceil((self.body + self.willpower) / 2)

    @property
    def run(self) -> int:
        return self.move * 2

    def __post_init__(self) -> None:
        self.current_hp = self.max_hp
        self.humanity = self.empathy * 10
        self.luck_pool = self.luck


# =============================================================================
# GRUNT TIER  (Mook / Normal)
# =============================================================================

@dataclass
class Base_Grunt(Base_NPC):
    """Disposable combatant prototype.

    max_hp = 10 + 5*ceil((5+4)/2) = 35   (matches _base.yml line 134)
    run    = 5 * 2 = 10
    """

    npc_role: NPCRole = NPCRole.Grunt
    npc_rarity: NPCRarity = NPCRarity.Mook

    intelligence: int = 4
    reflexes: int = 5
    dexterity: int = 5
    cool: int = 4
    willpower: int = 4
    luck: int = 3
    move: int = 5
    body: int = 5
    empathy: int = 3

    armor: int = 7

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Handgun, 10),
            SkillRank(Skill.Brawling, 8),
            SkillRank(Skill.Perception, 8),
            SkillRank(Skill.Stealth, 6),
            SkillRank(Skill.Athletics, 8),
        ]
    )

    drops_weapon: bool = True


# =============================================================================
# GRUNT TIER  (Mook / Normal)
# =============================================================================

@dataclass
class Base_Gang_Grunt(Base_Grunt):
    npc_rarity: NPCRarity = NPCRarity.Mook
    description: str = "Standard street gang member. Moderate cyberware."

    cool: int = 5
    willpower: int = 3

    armor: int = 4


@dataclass
class Base_CorpSec_Grunt(Base_Grunt):
    npc_rarity: NPCRarity = NPCRarity.Normal
    description: str = "Entry-level corporate security guard."

    intelligence: int = 5
    tech: int = 4
    willpower: int = 5

    armor: int = 7

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Handgun,        12),    # DEX 5 + SKILL 7
            SkillRank(Skill.ShoulderArms,   12),    # REF 5 + Skill 7
            SkillRank(Skill.Athletics,      10),    # DEX 5 + Skill 5
            SkillRank(Skill.Perception,     9),     # INT 5 + Skill 4
            SkillRank(Skill.Brawling,       8),     # DEX 5 + Skill 3
            SkillRank(Skill.Tactics,        6)      # INT 5 + Skill 1
        ]
    )


@dataclass
class Base_NCPD_Officer(Base_Grunt):
    npc_rarity: NPCRarity = NPCRarity.Normal
    description: str = "Night City Police Department patrol officer. Forcing justice, on mook at a time."
    faction: Faction = Faction.NCPD
    attitude_group: AttitudeGroup = AttitudeGroup.Suspicious

    intelligence: int = 5
    cool: int = 5
    willpower: int = 5

    armor: int = 7

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Handgun,            13),    # DEX 5 + Skill 8
            SkillRank(Skill.DriveLandVehicle,   12),    # REF 5 + Skill 7
            SkillRank(Skill.Brawling,           12),    # DEX 5 + Skill 7
            SkillRank(Skill.Perception,         10),    # INT 5 + Skill 5
            SkillRank(Skill.Interrogation,      9)      # COOL 5 + Skill 4
        ]
    )


# =============================================================================
# ELITE TIER  (Tough / Elite)
# =============================================================================

@dataclass
class Base_Tough(Base_NPC):
    npc_role: NPCRole = NPCRole.Tough
    npc_rarity: NPCRarity = NPCRarity.Tough

    intelligence: int = 5
    reflexes: int = 5
    dexterity: int = 5
    tech: int = 4
    cool: int = 5
    willpower: int = 5
    luck: int = 4
    move: int = 5
    body: int = 5
    empathy: int = 3

    armor: int = 11

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Perception,     10),    # INT 5 + Skill 5
            SkillRank(Skill.Athletics,      10),    # DEX 5 + Skill 5
            SkillRank(Skill.Evasion,        10),    # DEX 5 + Skill 5
            SkillRank(Skill.Tactics,        9),     # INT 5 + Skill 4
            SkillRank(Skill.Stealth,        8)      # DEX 5 + Skill 3
        ]
    )

    drops_weapon = True

@dataclass
class Base_Elite(Base_NPC):
    npc_role: NPCRole = NPCRole.Elite
    npc_rarity: NPCRarity = NPCRarity.Elite

    intelligence: int = 6
    reflexes: int = 7
    dexterity: int = 7
    tech: int = 5
    cool: int = 6
    willpower: int = 6
    luck: int = 5
    move: int = 6
    body: int = 7
    empathy: int = 4

    armor: int = 15

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.ShoulderArms,   14),    # REF 7 + Skill 7
            SkillRank(Skill.MeleeCombat,    14),    # DEX 7 + Skill 7
            SkillRank(Skill.Perception,     13),    # INT 6 + Skill 7
            SkillRank(Skill.Athletics,      12),    # DEX 7 + Skill 5
            SkillRank(Skill.Evasion,        12),    # DEX 7 + Skill 5
            SkillRank(Skill.Tactics,        11),    # INT 6 + Skill 5
            SkillRank(Skill.Stealth,        10),    # DEX 7 + Skill 3
            SkillRank(Skill.FirstAid,       9),     # TECH 5 + Skill 4
        ]
    )

    drops_weapon = True

@dataclass
class Base_Gang_Tough(Base_Tough):
    description = "A veteran gang member. Likely augmented and using slightly better than average equipment."

    body: int = 6
    willpower: int = 6

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Brawling,       12),    # REF 5 + Skill 7
            SkillRank(Skill.Intimidation,   12),    # COOL 5 + Skill 7
            SkillRank(Skill.ShoulderArms,   11),    # REF 5 + Skill 6
            SkillRank(Skill.Streetwise,     10),    # COOL 5 + Skill 5
            SkillRank(Skill.Perception,     10),    # REF 5 + Skill 5
        ]
    )


@dataclass
class Base_Gang_Elite(Base_Elite):
    description = "A veteran gang member, likely an officer. Using good equipment with average cyberware."

    body: int = 8
    reflexes: int = 7
    cool: int = 7

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Brawling,       14),  # REF 7 + Skill 7
            SkillRank(Skill.Intimidation,   14),  # COOL 7 + Skill 7
            SkillRank(Skill.Streetwise,     13),  # COOL 7 + Skill 6
        ]
    )


@dataclass
class Base_CorpSec_Tough(Base_Tough):
    description = "Corporate HQ Security. Better kit and communication/coordination abilities."

    intelligence: int = 6
    tech: int = 5
    willpower: int = 6

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Concentration,  11),    # WILL 6 + Skill 5
            SkillRank(Skill.FirstAid,       11),    # TECH 5 + Skill 6
            SkillRank(Skill.Cybertech,      9),     # TECH 5 + Skill 4
        ]
    )


@dataclass
class Base_CorpSec_Elite(Base_Elite):
    description = "Corporate Special Agents. Full kit and coordinated tactics."

    intelligence: int = 7
    tech: int = 6
    willpower: int = 7

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.ResistTortureDrugs,         13),    # COOL 6 + Skill 7
            SkillRank(Skill.HeavyWeapons,               13),    # REF 7 + Skill 6
            SkillRank(Skill.Electronics_SecurityTech,   12)     # TECH 6 + Skill 6
        ]
    )

@dataclass
class Base_Solo_Tough(Base_Tough):
    description = "Base class for an NPC Solo. NPCs do not get access to role abilities. Would generally be a hired mercenary."
    npc_role: NPCRole = NPCRole.Solo_NPC
    attitude_group: AttitudeGroup = AttitudeGroup.Neutral

    reflexes: int = 6
    cool: int = 6
    empathy: int = 5

    skills: list[SkillRank] = field(
        default_factory=lambda: [
            SkillRank(Skill.Athletics,          12),    # DEX 5  + Skill 7
            SkillRank(Skill.Handgun,            12),    # REF 6  + Skill 6
            SkillRank(Skill.HumanPerception,    10),    # EMP 5 + Skill 5
        ]
    )