from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

RARITY_ORDER: list[str] = [
    "Mook", "Tough", "HardenedMook",
    "HardenedLieutenant", "Elite",
    "HardenedMiniBoss",
    "Boss", "HardenedBoss"
]

# Anchor tiers used by the calibration sections (outline.md SCALE_FACTOR
ANCHOR_TIERS: dict[str, tuple[int, int]] = {
    "Mook":                 (1,4),
    "Tough":                (1,4),
    "HardenedMook":         (5,8),
    "HardenedLieutenant":   (5,8),
    "Elite":                (9,12),
    "HardenedMiniBoss":     (9,12),
    "Boss":                 (13, 16),
    "HardenedBoss":         (17,20)
}

CORE_METRICS:    list[str] = ["nts_raw", "ots", "dds"]
DDS_COMPONENTS:  list[str] = ["hpp", "aac", "dsr_hp"]
OTS_COMPONENTS:  list[str] = ["hpw_ss", "edpr_ss", "cts_ss", "hpw_af", "edpr_af", "cts_af"]
DEFENDER_FIELDS: list[str] = ["def_static", "def_ref", "def_sp"]

LABELS: dict[str, str] = {
    "nts_raw":                 "NTS Raw Score",
    "ots":                     "Offensive Threat Score",
    "dds":                     "Defensive Durability Score",
    "hpp":                     "Hit Point Pool",
    "aac":                     "Armor Absorption Capacity",
    "dsr_hp":                  "Death Save Resilience (HP)",
    "hpw_ss":                  "Hit Probability Weight (single shot)",
    "edpr_ss":                 "Expected Damage Per Round (single shot)",
    "cts_ss":                  "Crit Threat Score (single shot)",
    "hpw_af":                  "Hit Probability Weight (autofire)",
    "edpr_af":                 "Expected Damage Per Round (autofire)",
    "cts_af":                  "Crit Threat Score (autofire)",
    "cm":                      "Complexity Multiplier",
    "def_static":              "Defender static defense pool",
    "def_ref":                 "Defender REF",
    "def_sp":                  "Defender effective SP",
    "penetration_probability": "Penetration Probability p",
}


def parse_faction(npc_id: str) -> str | None:
    """`NPC.6thStreet_Arbiter` → `6thStreet`. Returns None on unparseable IDs."""
    m = re.match(r"^NPC\.([^_]+)_", npc_id)
    return m.group(1) if m else None


def parse_npc_short_name(npc_id: str) -> str:
    """`NPC.6thStreet_Arbiter` → `Arbiter`. Falls back to the raw id."""
    m = re.match(r"^NPC\.[^_]+_(.+)$", npc_id)
    return m.group(1) if m else npc_id


def load_nts(json_path: str | Path) -> pd.DataFrame:
    """Flatten the nested PC → NPC → metrics JSON into a tidy DataFrame.

    One row per (PC, NPC) pair. Adds derived columns: `faction`, `npc_name`,
    `pc_role_id` (the PC's record id, which often differs from `pc_role` —
    multiple PCs can share a role).
    """
    raw = json.loads(Path(json_path).read_text())

    rows: list[dict] = []
    for pc_id, pc_block in raw.items():
        pc_role = pc_block.get("pc_role", pc_id)
        for npc_id, vals in pc_block.items():
            if npc_id == "pc_role":
                continue
            rows.append({
                "pc_role_id": pc_id,
                "pc_role":    pc_role,
                "npc_id":     npc_id,
                "faction":    parse_faction(npc_id),
                "npc_name":   parse_npc_short_name(npc_id),
                **vals,
            })

    df = pd.DataFrame(rows)
    df["npc_rarity"] = pd.Categorical(df["npc_rarity"], categories=RARITY_ORDER, ordered=True)
    return df


_FACTION_NOISE = {"the", "squad", "precinct", "mission", "team", "puma", "nc42"}


def _alnum_lower(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _faction_keys(s: str) -> set[str]:
    """Generate the set of fuzzy keys a clean-data faction might map to.

    Handles 'THE BOZOS' → 'bozos', 'NCPD PRECINCT #1' → 'ncpd',
    'DANGER GAL PUMA SQUAD' → {'dangergal', 'dangergalpuma'}, etc.
    """
    if not s:
        return set()
    raw = re.sub(r"[^A-Za-z0-9 ]", " ", s.lower())
    tokens = [t for t in raw.split() if t and t not in _FACTION_NOISE]
    keys = {"".join(tokens)}
    if tokens:
        keys.add(tokens[0])
        for n in range(2, len(tokens) + 1):
            keys.add("".join(tokens[:n]))
    return {k for k in keys if k}


def join_clean_npcs(df: pd.DataFrame, clean_path: str | Path) -> pd.DataFrame:
    """Left-join scraped NPC attributes from npc_data_clean.json onto the EDA frame.

    Adds: `clean_hp_raw`, `clean_death_save`, `clean_descriptor`, `clean_role_text`,
    `clean_weapon_count`, `clean_cyberware_count`, `clean_gear_text`.

    Match is fuzzy: lowercase-alnum on (faction, name), with several candidate
    faction keys per clean record to tolerate the YAML's habit of dropping noise
    words like 'THE', 'SQUAD', 'PRECINCT'. Records that still miss keep NaN
    attributes — the join is enrichment, never on the critical path.
    """
    clean_path = Path(clean_path)
    if not clean_path.exists():
        return df

    records = json.loads(clean_path.read_text(encoding="utf-8"))

    by_key: dict[str, dict] = {}
    for r in records:
        name_key = _alnum_lower(r.get("name", ""))
        if not name_key:
            continue
        for fk in _faction_keys(r.get("faction", "")):
            by_key.setdefault(fk + "|" + name_key, r)

    def _attrs(npc_id: str) -> dict:
        m = re.match(r"^NPC\.([^_]+)_(.+)$", npc_id)
        if not m:
            return {}
        key = _alnum_lower(m.group(1)) + "|" + _alnum_lower(m.group(2))
        rec = by_key.get(key)
        if rec is None:
            return {}
        weapons = rec.get("weapons") or []
        cyber   = rec.get("cyberware") or ""
        return {
            "clean_hp_raw":          _to_int(rec.get("hp")),
            "clean_death_save":      _to_int(rec.get("death_save")),
            "clean_descriptor":      rec.get("descriptor"),
            "clean_role_text":       rec.get("role"),
            "clean_weapon_count":    len(weapons) if isinstance(weapons, list) else 0,
            "clean_cyberware_count": cyber.count("•") + 1 if cyber else 0,
            "clean_gear_text":       rec.get("gear"),
        }

    enrich = pd.DataFrame([_attrs(nid) for nid in df["npc_id"]])
    out = pd.concat([df.reset_index(drop=True), enrich.reset_index(drop=True)], axis=1)

    unique_npc_ids = df["npc_id"].drop_duplicates()
    matched = sum(1 for n in unique_npc_ids if _attrs(n))
    total = len(unique_npc_ids)
    out.attrs["clean_join_hit_rate"] = (matched, total, matched / total if total else 0.0)
    return out


def _to_int(v) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None
