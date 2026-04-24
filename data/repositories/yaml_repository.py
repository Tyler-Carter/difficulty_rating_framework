from data.repositories import AbstractRecordRepository
from data.registry import load_record
from data.models import (
ResolvedRecord, AttributeBlock, DerivedStats, SkillEntry
)


# ---------------------------------------------------------------------------
# Implementation of AbstractRecordRepository backed by the YAML registry.
# Calls `load_record()` and maps the result into the `ResolvedRecord`
# typed model.
# ---------------------------------------------------------------------------
class YamlRecordRepository(AbstractRecordRepository):

    def get_record(self, record_id: str) -> ResolvedRecord:
        raw = load_record(record_id)    # fully resolved dictionary

        attrs_raw = raw.get("attributes") or {}
        ds_raw = raw.get("derivedStats") or {}

        # Normalize the two possible armor locations into model fields
        top_armor = raw.get("armor")
        ds_armor = ds_raw.get("armor")
        armor_val: int | None = None
        ds_armor_val: int | None = None
        if isinstance(top_armor, int):
            armor_val = top_armor
        elif isinstance(ds_armor, int):
            ds_armor_val = ds_armor
        elif isinstance(ds_armor, dict):
            ds_armor_val = int(ds_armor.get("armor", 0))

        skills = [
            SkillEntry(skill=e["skill"], rank=int(e.get("rank", 0)))
            for e in (raw.get("skills") or [])
            if isinstance(e, dict) and "skill" in e
        ]

        primary_weapon = (raw.get("primaryEquipment") or {}).get("weapon")

        return ResolvedRecord(
            record_id=record_id,
            npc_type=raw.get("npcType"),
            handle=raw.get("handle"),
            attributes=AttributeBlock(**{
                k: (int(v) if v is not None else 0)
                for k, v in attrs_raw.items()
                if k in AttributeBlock.model_fields
            }),
            derived_stats=DerivedStats(
                max_hp=ds_raw.get("maxHP"),
                current_hp=ds_raw.get("currentHP"),
                armor=ds_armor_val,
            ),
            skills=skills,
            armor=armor_val,
            primary_weapon_id=primary_weapon,
        )
