from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class SkillEntry(BaseModel):
    skill: str
    rank: int

class AttributeBlock(BaseModel):
    intelligence:   Optional[int] = 0
    reflexes:       Optional[int] = 0
    dexterity:      Optional[int] = 0
    tech:           Optional[int] = 0
    cool:           Optional[int] = 0
    willpower:      Optional[int] = 0
    luck:           Optional[int] = 0
    move:           Optional[int] = 0
    body:           Optional[int] = 0
    empathy:        Optional[int] = 0


class DerivedStats(BaseModel):
    max_hp:         Optional[int] = None
    current_hp:     Optional[int] = None
    armor:          Optional[int] = None    # may also live at top-level; resolver normalizes


class WeaponStats(BaseModel):
    dice_count:     int
    rof:            int
    has_autofire:   bool
    autofire_cap:   Optional[int] = None
    attack_skill:   str


class ResolvedRecord(BaseModel):
    record_id:          str
    npc_type:           Optional[str] = None    # present iff record is an NPC
    handle:             Optional[str] = None
    attributes:         AttributeBlock = AttributeBlock()
    derived_stats:      DerivedStats = DerivedStats()
    skills:             list[SkillEntry] = []
    armor:              Optional[int] = None    # top-level armor field (NPC records)
    primary_weapon_id:  Optional[str] = None    # e.g., "Weapons.Preset_HeavyPistol_Excellent"