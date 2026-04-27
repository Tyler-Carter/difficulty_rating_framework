from __future__ import annotations

from pathlib import Path

from pprint import pprint

import re

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

BASE_FILES_DIR = Path(__file__).parent.parent / "base_files"

# ---------------------------------------------------------------------------
# Playtesting parameters (see docs/outline.md "Requires playtesting" sections)
# ---------------------------------------------------------------------------
CTS_MULTIPLIER = 10.7        # = 5 + 0.58 + 4.41 + 0.67 as derived in outline
AUTOFIRE_ATK_PENALTY = 3     # -3 to attack pool when computing HPW for autofire

# ---------------------------------------------------------------------------
# Weapon stats registry
# Weapon YAML records do not exist yet; stats sourced from CP:RED Core Rulebook
# pp. 340-351.  avg_damage = num_dice * 3.5 (average d6 = 3.5).
# attack_skill uses the canonical skill name from _base.yml (Handgun, not HandgunRanged).
# ---------------------------------------------------------------------------
WEAPON_STATS: dict[str, dict] = {
    "Pistol":          {"avg_damage": 3.5,  "dice_count": 1, "rof": 2, "has_autofire": False, "autofire_cap": None, "attack_skill": "Handgun"},
    "MediumPistol":    {"avg_damage": 7.0, "dice_count": 2, "rof": 2, "has_autofire": False, "autofire_cap": None, "attack_skill": "Handgun"},
    "HeavyPistol":     {"avg_damage": 10.5, "dice_count": 3, "rof": 2, "has_autofire": False, "autofire_cap": None, "attack_skill": "Handgun"},
    "VeryHeavyPistol": {"avg_damage": 14.0, "dice_count": 4, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "Handgun"},
    "SMG":             {"avg_damage": 7.0,  "dice_count": 2, "rof": 1, "has_autofire": True,  "autofire_cap": 3,    "attack_skill": "ShoulderArms"},
    "HeavySMG":        {"avg_damage": 21.0, "dice_count": 6, "rof": 1, "has_autofire": True,  "autofire_cap": 3,    "attack_skill": "ShoulderArms"},
    "Shotgun":         {"avg_damage": 21.0, "dice_count": 6, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "ShoulderArms"},
    "AssaultRifle":    {"avg_damage": 14.0, "dice_count": 4, "rof": 1, "has_autofire": True,  "autofire_cap": 4,    "attack_skill": "ShoulderArms"},
    "SniperRifle":     {"avg_damage": 17.5, "dice_count": 5, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "ShoulderArms"},
    "HeavyMachineGun": {"avg_damage": 21.0, "dice_count": 6, "rof": 1, "has_autofire": True,  "autofire_cap": 4,    "attack_skill": "HeavyWeapons"},
    "VeryHeavyMelee":     {"avg_damage": 14.0, "dice_count": 4, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "MeleeCombat"},
    "HeavyMelee":         {"avg_damage": 10.5, "dice_count": 3, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "MeleeCombat"},
    "MediumMelee":        {"avg_damage": 7.0,  "dice_count": 2, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "MeleeCombat"},
    "LightMelee":         {"avg_damage": 3.5,  "dice_count": 1, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "MeleeCombat"},
    "GrenadeLauncher":    {"avg_damage": 21.0, "dice_count": 6, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "HeavyWeapons"},
    "RocketLauncher":     {"avg_damage": 28.0, "dice_count": 8, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "HeavyWeapons"},
    "FlamethrowerWeapon": {"avg_damage": 7.0,  "dice_count": 2, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "HeavyWeapons"},
    "Flamethrower":       {"avg_damage": 7.0,  "dice_count": 2, "rof": 1, "has_autofire": False, "autofire_cap": None, "attack_skill": "HeavyWeapons"},  # alias; IDs without "Weapon" suffix match this
    "Brawling":           {"avg_damage": 7.0,  "dice_count": 2, "rof": 2, "has_autofire": False, "autofire_cap": None, "attack_skill": "Brawling"},
}

# Longest-first so "VeryHeavyPistol" matches before "HeavyPistol" matches before "Pistol", etc.
_WEAPON_TYPE_KEYWORDS: list[str] = [
    "VeryHeavyPistol", "HeavyPistol", "MediumPistol", "Pistol",
    "HeavySMG", "SMG",
    "AssaultRifle", "SniperRifle",
    "Shotgun", "HeavyMachineGun",
    "VeryHeavyMelee", "HeavyMelee", "MediumMelee", "LightMelee",
    "GrenadeLauncher", "RocketLauncher",
    "FlamethrowerWeapon", "Flamethrower",  # FlamethrowerWeapon first; bare Flamethrower matches DangerGal_Flamethrower_Standard
    "Brawling", "Bow",
]


# ---------------------------------------------------------------------------
# YAML loading with !append tag support and $base prototype chain resolution
# ---------------------------------------------------------------------------

class _AppendLoader(yaml.SafeLoader):
    """SafeLoader extended to silently unwrap !append tags."""


def _append_constructor(loader: yaml.SafeLoader, node: yaml.Node) -> object:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_AppendLoader.add_constructor("!append", _append_constructor)

_record_registry: dict[str, dict] | None = None


def _build_registry() -> dict[str, dict]:
    """Load every YAML file under base_files/ and return {record_id: raw_dict}."""
    registry: dict[str, dict] = {}
    search_dirs = [
        BASE_FILES_DIR / "records" / "npcs",
        BASE_FILES_DIR / "records" / "player",
        BASE_FILES_DIR / "records" / "weapons",
        BASE_FILES_DIR / "prototypes" / "npcs",
        BASE_FILES_DIR / "prototypes" / "characters",
        BASE_FILES_DIR / "prototypes" / "weapons",
    ]
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml")):
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    data = yaml.load(fh, Loader=_AppendLoader)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for record_id, record_data in data.items():
                if isinstance(record_data, dict):
                    registry[record_id] = record_data
    return registry


def _get_registry() -> dict[str, dict] | None:
    global _record_registry
    if _record_registry is None:
        _record_registry = _build_registry()
    return _record_registry

def _merge(base: dict, leaf: dict) -> dict:
    """Merge a fully-resolved base record with a leaf record.

    Leaf values win over base values.  Special cases:
    - skills: merged by skill name; leaf entries overwrite base entries.
    - attributes / derivedStats: dicts are merged shallowly (leaf wins per key).
    """
    result = dict(base)
    for key, val in leaf.items():
        if key in ("$base", "$type"):
            continue
        if key == "skills" and val is not None:
            base_skills: dict[str, int] = {
                s["skill"]: s["rank"]
                for s in (result.get("skills") or [])
                if isinstance(s, dict) and "skill" in s
            }
            for entry in (val or []):
                if isinstance(entry, dict) and "skill" in entry:
                    base_skills[entry["skill"]] = entry["rank"]
            result["skills"] = [{"skill": sk, "rank": rk} for sk, rk in base_skills.items()]
        elif key in ("attributes", "derivedStats") and isinstance(val, dict):
            merged_sub = dict(result.get(key) or {})
            merged_sub.update({k: v for k, v in val.items() if v is not None})
            result[key] = merged_sub
        else:
            result[key] = val
    return result


def load_record(record_id: str) -> dict:
    """Return a fully resolved record dict for *record_id*, following $base chains."""
    registry = _get_registry()
    raw = registry.get(record_id)
    if raw is None:
        raise ValueError(f"Record not found: {record_id!r}")
    base_id: str | None = raw.get("$base")
    if base_id:
        base_resolved = load_record(base_id)
        return _merge(base_resolved, raw)
    return dict(raw)


# ---------------------------------------------------------------------------
# Weapon ID parsing
# ---------------------------------------------------------------------------

def parse_weapon_id(weapon_id: str) -> tuple[str, bool]:
    """Return (weapon_type_key, is_excellent) from a weapon record ID string.

    Examples:
        "Weapons.Preset_HeavyPistol_Excellent"       -> ("HeavyPistol", True)
        "Weapons.DangerGal_VeryHeavyMeleeWeapon_Poor" -> ("VeryHeavyMelee", False)
        "Weapons.Preset_AssaultRifle_Military"        -> ("AssaultRifle", False)
    """
    is_excellent = "excellent" in weapon_id.lower()
    wid_lower = weapon_id.lower()
    for keyword in _WEAPON_TYPE_KEYWORDS:
        if keyword.lower() in wid_lower:
            return keyword, is_excellent
    return "Unknown", is_excellent


# ---------------------------------------------------------------------------
# Stat extraction helpers
# ---------------------------------------------------------------------------

def is_npc(record: dict) -> bool:
    """True when the record is an NPC (has an npcType field)."""
    return "npcType" in record


def get_skill_rank(record: dict, skill_name: str) -> int:
    """Return the stored rank for *skill_name*, defaulting to 0."""
    for entry in (record.get("skills") or []):
        if isinstance(entry, dict) and entry.get("skill") == skill_name:
            rank = entry.get("rank", 0)
            return int(rank) if isinstance(rank, (int, float)) else 0
    return 0


def get_attack_pool(record: dict, skill_name: str) -> int:
    """Effective attack pool for a given skill.

    NPC records store the final total (attribute + skill rank) in the rank field,
    so the stored rank IS the attack pool.

    PC records store only the skill rank, so REF must be added.
    """
    rank = get_skill_rank(record, skill_name)
    if is_npc(record):
        return rank
    ref = (record.get("attributes") or {}).get("reflexes", 0)
    return int(ref) + rank


def get_defense_total(record: dict) -> float:
    """Return DEF_DEX + DEF_evasion_skill for use in HPW calculation.

    Returns 0.0 when the defender's REF < 8 (cannot dodge; static DV used instead).

    NPC records store Evasion as a final total (DEX + rank) → return stored rank.
    PC records store Evasion as rank only → return DEX + stored rank.
    """
    ref = int((record.get("attributes") or {}).get("reflexes", 0))
    if ref < 8:
        return 0.0
    evasion_rank = get_skill_rank(record, "Evasion")
    if is_npc(record):
        return float(evasion_rank)
    dex = int((record.get("attributes") or {}).get("dexterity", 0))
    return float(dex + evasion_rank)


def get_effective_sp(record: dict) -> int:
    """Return the defender's Stopping Power.

    Checks (in order):
    1. Top-level 'armor' field (int) — common in NPC records.
    2. derivedStats.armor (int or {armor: N} mapping from !append).
    """
    top = record.get("armor")
    if isinstance(top, int):
        return top

    derived = record.get("derivedStats") or {}
    if isinstance(derived, dict):
        da = derived.get("armor")
        if isinstance(da, int):
            return da
        if isinstance(da, dict):
            return int(da.get("armor", 0))
    return 0


# ---------------------------------------------------------------------------
# OTS math (pure functions — no I/O)
# ---------------------------------------------------------------------------

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def crit_prob(n_dice: int) -> float:
    """P(at least two 6s on N d6) using the complement method.

    P(crit) = 1 - (5/6)^N - N * (1/6) * (5/6)^(N-1)
    """
    q = 5 / 6
    p = 1 / 6
    return max(0.0, 1 - q**n_dice - n_dice * p * q ** (n_dice - 1))


def compute_hpw(attack_pool: int, def_total: float, *, autofire: bool = False) -> float:
    """Hit Probability Weight scalar.

    attack_pool  — aggressor's REF + weapon skill total.
    def_total    — DEF_DEX + DEF_evasion_skill (without the 1d10 average).
                   Pass 0.0 when the defender cannot dodge (REF < 8).
    autofire     — when True, subtract AUTOFIRE_ATK_PENALTY before calculating.

    Dodging defender (def_total > 0):
        margin = pool - (def_total + 5.5)
        HPW = clamp((margin + 5) / 10, 0.2, 1.5)

    Static-DV defender (def_total == 0, assumed DV = 15):
        margin = pool - 15 + 5.5
        HPW = clamp(margin / 10, 0.3, 1.5)
    """
    pool = attack_pool - (AUTOFIRE_ATK_PENALTY if autofire else 0)
    if def_total > 0:
        margin = pool - (def_total + 5.5)
        return clamp((margin + 5) / 10, 0.2, 1.5)
    margin = pool - 15 + 5.5
    return clamp(margin / 10, 0.3, 1.5)


def compute_edpr_ss(avg_weapon_damage: float, def_sp: int, rof: int) -> float:
    """Expected Damage Per Round — single-shot.

    EDPR_SS = max(0, avg_damage - SP) * ROF
    """
    return max(0.0, avg_weapon_damage - def_sp) * rof


def compute_edpr_af(hpw_af: float, autofire_cap: int, def_sp: int) -> float:
    """Expected Damage Per Round — autofire.

    avg_mult = HPW_AF * (cap + 1) / 2
    EDPR_AF  = max(0, avg(2d6) - SP) * avg_mult
    """
    avg_mult = hpw_af * (autofire_cap + 1) / 2
    return max(0.0, 7.0 - def_sp) * avg_mult


def compute_cts(n_dice: int) -> float:
    """Crit Threat Score.

    CTS = P(crit) * CTS_MULTIPLIER
    """
    return crit_prob(n_dice) * CTS_MULTIPLIER


def compute_ots(
    attack_pool: int,
    autofire_pool: int | None,
    weapon_stats: dict,
    def_total: float,
    def_sp: int,
    is_excellent: bool,
) -> dict:
    """Compute OTS and return a dict of OTS plus all intermediate values.

    is_excellent adds +1 to attack_pool (and autofire_pool when present),
    per the outline: attack_pool = REF + weapon_skill (+ 1 if excellent quality weapon).

    With autofire available:
        OTS = ((HPW_SS + HPW_AF) / 2) * ((EDPR_SS + EDPR_AF + CTS_SS + CTS_AF) / 2)

    Without autofire:
        OTS = HPW_SS * (EDPR_SS + CTS_SS)
    """
    quality_bonus = 1 if is_excellent else 0
    adj_pool = attack_pool + quality_bonus

    hpw_ss = compute_hpw(adj_pool, def_total)
    edpr_ss = compute_edpr_ss(weapon_stats["avg_damage"], def_sp, weapon_stats["rof"])
    cts_ss = compute_cts(weapon_stats["dice_count"])

    hpw_af: float | None = None
    edpr_af: float | None = None
    cts_af: float | None = None

    if weapon_stats.get("has_autofire") and autofire_pool is not None:
        adj_af_pool = autofire_pool + quality_bonus
        hpw_af = compute_hpw(adj_af_pool, def_total, autofire=True)
        edpr_af = compute_edpr_af(hpw_af, weapon_stats["autofire_cap"], def_sp)
        cts_af = compute_cts(2)  # autofire always rolls 2d6 regardless of base weapon

        ots = ((hpw_ss + hpw_af) / 2) * ((edpr_ss + edpr_af + cts_ss + cts_af) / 2)
    else:
        ots = hpw_ss * (edpr_ss + cts_ss)

    return {
        "ots": round(ots, 4),
        "hpw_ss": round(hpw_ss, 4),
        "edpr_ss": round(edpr_ss, 4),
        "cts_ss": round(cts_ss, 4),
        "hpw_af": round(hpw_af, 4) if hpw_af is not None else None,
        "edpr_af": round(edpr_af, 4) if edpr_af is not None else None,
        "cts_af": round(cts_af, 4) if cts_af is not None else None,
    }


# ---------------------------------------------------------------------------
# Top-level record-driven calculation
# ---------------------------------------------------------------------------

def calculate_ots_for_records(aggressor_id: str, defender_id: str) -> dict:
    """Load aggressor and defender records, extract stats, and compute OTS.

    Aggressor must be an NPC record (base_files/records/npcs/).
    Defender can be an NPC or a player character (base_files/records/player/).
    """
    agg = load_record(aggressor_id)
    defn = load_record(defender_id)

    weapon_id: str = (agg.get("primaryEquipment") or {}).get("weapon", "")
    weapon_type, is_excellent = parse_weapon_id(weapon_id)
    w_stats = WEAPON_STATS.get(weapon_type)
    if w_stats is None:
        raise ValueError(
            f"Unknown weapon type for {agg}\n'{weapon_id}'. "
            f"Add it to WEAPON_STATS or use a recognised weapon ID."
        )

    attack_skill = w_stats["attack_skill"]
    attack_pool = get_attack_pool(agg, attack_skill)

    autofire_pool: int | None = None
    if w_stats.get("has_autofire"):
        af_rank = get_skill_rank(agg, "Autofire")
        if af_rank > 0:
            autofire_pool = (
                af_rank
                if is_npc(agg)
                else int((agg.get("attributes") or {}).get("reflexes", 0)) + af_rank
            )
        else:
            autofire_pool = attack_pool

    def_total = get_defense_total(defn)
    def_sp = get_effective_sp(defn)

    result = compute_ots(attack_pool, autofire_pool, w_stats, def_total, def_sp, is_excellent)
    result.update(
        attack_pool=attack_pool,
        def_sp=def_sp,
        aggressor_weapon=weapon_id,
        aggressor_id=aggressor_id,
        defender_id=defender_id,
    )
    return result


# ---------------------------------------------------------------------------
# FastAPI models and endpoints
# ---------------------------------------------------------------------------

class OTSRequest(BaseModel):
    aggressor_id: str  # e.g. "NPC.Boss_Arasaka_Tanaka_Ryu"
    defender_id: str   # e.g. "Characters.PC_Yuki_Raines"


class OTSResult(BaseModel):
    ots: float
    hpw_ss: float
    edpr_ss: float
    cts_ss: float
    hpw_af: float | None = None
    edpr_af: float | None = None
    cts_af: float | None = None
    attack_pool: int
    def_sp: int
    aggressor_weapon: str
    aggressor_id: str
    defender_id: str


@app.get("/")
async def root() -> dict:
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str) -> dict:
    return {"message": f"Hello {name}"}


@app.post("/ots", response_model=OTSResult)
async def calculate_ots(request: OTSRequest) -> OTSResult:
    """Calculate the Offensive Threat Score (OTS) for an aggressor vs. a defender.

    Loads both records from base_files/, resolves the $base prototype chain,
    and returns the full OTS breakdown including intermediate values.
    """
    try:
        result = calculate_ots_for_records(request.aggressor_id, request.defender_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OTSResult(**result)

if __name__ == "__main__":
    from itertools import zip_longest

    list_of_pcs = []
    list_of_npcs = []

    _registry = _get_registry()
    for k,v in _registry.items():
        if k.startswith("NPC.Edgerunners_"):
            list_of_pcs.append(k)
        elif k.startswith("NPC.") and not k.startswith("NPC.Base_"):
            list_of_npcs.append(k)

    results = [calculate_ots_for_records(npc, pc) for npc in list_of_npcs for pc in list_of_pcs]

    total_ots = 0
    for result in results:
        total_ots += result["ots"]
    print(total_ots/len(results))




