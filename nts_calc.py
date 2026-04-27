from __future__ import annotations

import json
from pathlib import Path

import yaml

from api.main import (
    _AppendLoader,
    load_record,
    parse_weapon_id,
    get_attack_pool,
    get_effective_sp,
    get_skill_rank,
    is_npc,
    WEAPON_STATS,
    compute_edpr_ss,
    compute_edpr_af,
    compute_cts,
    AUTOFIRE_ATK_PENALTY,
)
from dds_calc import compute_dds, get_body, get_will
from calculations.range_dv import get_difficulty

BASE = Path(__file__).parent / "base_files"

ENGAGEMENT_RANGE_M: float = 12.0
MELEE_DV: float = 15.0
_MELEE_ATTACK_SKILLS = {"MeleeCombat", "Brawling"}


# ---------------------------------------------------------------------------
# Directory enumeration
# ---------------------------------------------------------------------------

def get_record_ids_from_dir(directory: Path) -> list[str]:
    ids: list[str] = []
    for path in sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                data = yaml.load(fh, Loader=_AppendLoader)
        except Exception:
            continue
        if isinstance(data, dict):
            ids.extend(k for k, v in data.items() if isinstance(v, dict))
    return ids


# ---------------------------------------------------------------------------
# Stat extraction (defenders)
# ---------------------------------------------------------------------------

def get_def_ref(record: dict) -> int:
    return int((record.get("attributes") or {}).get("reflexes", 0))


def get_def_static(record: dict) -> float:
    """DEF_DEX + DEF_evasion_skill (deterministic part of the dodge roll)."""
    evasion = get_skill_rank(record, "Evasion")
    if is_npc(record):
        return float(evasion)       # NPC: stored rank already includes DEX total
    dex = int((record.get("attributes") or {}).get("dexterity", 0))
    return float(dex + evasion)


# ---------------------------------------------------------------------------
# Correct HPW — closed-form per outline §1.2
# ---------------------------------------------------------------------------

def _p_static(attack_pool: int, range_dv: float) -> float:
    need = range_dv - attack_pool
    return max(0.0, min(1.0, (11 - need) / 10))


def _p_dodge(attack_pool: int, def_static: float) -> float:
    shift = def_static - attack_pool
    if shift <= -9:
        return 1.0
    if shift <= 0:
        return 1 - (9 + shift) * (10 + shift) / 200
    if shift <= 9:
        return (10 - shift) * (11 - shift) / 200
    return 0.0


def compute_hpw(
    attack_pool: int,
    range_dv: float,
    def_static: float,
    def_ref: int,
    *,
    autofire: bool = False,
) -> float:
    """Hit Probability Weight per outline §1.2.

    Applies the decision rule: defender with REF ≥ 8 chooses whichever option
    (static DV or active dodge) minimises P(hit). Result clamped to [0.2, 1.0].
    """
    pool = attack_pool - (AUTOFIRE_ATK_PENALTY if autofire else 0)
    ps = _p_static(pool, range_dv)
    if def_ref >= 8:
        pd = _p_dodge(pool, def_static)
        p_hit = min(ps, pd)
    else:
        p_hit = ps
    return max(0.2, min(1.0, p_hit))


# ---------------------------------------------------------------------------
# Range DV lookup with melee / unsupported-weapon fallback
# ---------------------------------------------------------------------------

def get_range_dv(weapon_type: str) -> float:
    if WEAPON_STATS.get(weapon_type, {}).get("attack_skill") in _MELEE_ATTACK_SKILLS:
        return MELEE_DV
    try:
        return get_difficulty(weapon_type, ENGAGEMENT_RANGE_M)
    except (KeyError, ValueError):
        return MELEE_DV


# ---------------------------------------------------------------------------
# OTS — correct implementation
# ---------------------------------------------------------------------------

def compute_ots(agg: dict, defn: dict) -> dict:
    """Compute OTS for agg (attacker) vs defn (defender) per outline §1–3.

    Returns the OTS scalar plus every intermediate the downstream EDA needs to
    decompose threat: per-fire-mode HPW/EDPR/CTS, the attacker pool, the range
    DV used, and the defender stats baked into the calculation.
    """
    weapon_id = (agg.get("primaryEquipment") or {}).get("weapon", "")
    weapon_type, is_excellent = parse_weapon_id(weapon_id)
    w = WEAPON_STATS.get(weapon_type)
    if w is None:
        raise ValueError(f"Unknown weapon type {weapon_type!r} (from {weapon_id!r})")

    quality_bonus = 1 if is_excellent else 0
    attack_pool = get_attack_pool(agg, w["attack_skill"]) + quality_bonus

    range_dv   = get_range_dv(weapon_type)
    def_static = get_def_static(defn)
    def_ref    = get_def_ref(defn)
    def_sp     = get_effective_sp(defn)

    hpw_ss  = compute_hpw(attack_pool, range_dv, def_static, def_ref)
    edpr_ss = compute_edpr_ss(w["avg_damage"], def_sp, w["rof"])
    cts_ss  = compute_cts(w["dice_count"])

    has_autofire = bool(w["has_autofire"])
    hpw_af = edpr_af = cts_af = af_pool = None
    if has_autofire:
        af_rank = get_skill_rank(agg, "Autofire")
        af_pool = (af_rank if af_rank > 0 else get_attack_pool(agg, w["attack_skill"])) + quality_bonus
        hpw_af  = compute_hpw(af_pool, range_dv, def_static, def_ref, autofire=True)
        edpr_af = compute_edpr_af(hpw_af, w["autofire_cap"], def_sp)
        cts_af  = compute_cts(2)
        ots = ((hpw_ss + hpw_af) / 2) * ((edpr_ss + edpr_af + cts_ss + cts_af) / 2)
    else:
        ots = hpw_ss * (edpr_ss + cts_ss)

    return {
        "ots":          round(ots, 4),
        "hpw_ss":       round(hpw_ss, 4),
        "edpr_ss":      round(edpr_ss, 4),
        "cts_ss":       round(cts_ss, 4),
        "hpw_af":       round(hpw_af, 4)  if hpw_af  is not None else None,
        "edpr_af":      round(edpr_af, 4) if edpr_af is not None else None,
        "cts_af":       round(cts_af, 4)  if cts_af  is not None else None,
        "has_autofire": has_autofire,
        "weapon_type":  weapon_type,
        "is_excellent": bool(is_excellent),
        "attack_pool":  int(attack_pool),
        "af_pool":      int(af_pool) if af_pool is not None else None,
        "range_dv":     float(range_dv),
        "def_static":   float(def_static),
        "def_ref":      int(def_ref),
        "def_sp":       int(def_sp),
    }


# ---------------------------------------------------------------------------
# Complexity Multiplier (CM) — placeholder
# ---------------------------------------------------------------------------

def compute_cm(_npc: dict) -> float:
    """Capability Complexity Multiplier per outline §CM.

    The cyberware-tier / special-gear / netrun bonuses are not yet implemented
    in this codebase — emit a 1.0 placeholder so the downstream EDA can still
    run end-to-end and the field will light up automatically once CM logic
    arrives.
    """
    return 1.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pc_ids  = get_record_ids_from_dir(BASE / "records" / "player")
    npc_ids = get_record_ids_from_dir(BASE / "records" / "npcs")

    print(f"Players (PCs): {len(pc_ids)}  |  NPCs: {len(npc_ids)}")

    # Pre-compute DDS + CM per NPC — both depend only on the NPC, not the PC
    npc_dds: dict[str, dict] = {}
    npc_cm:  dict[str, float] = {}
    for npc_id in npc_ids:
        try:
            rec = load_record(npc_id)
            npc_dds[npc_id] = compute_dds(get_body(rec), get_will(rec), get_effective_sp(rec))
            npc_cm[npc_id]  = compute_cm(rec)
        except Exception as exc:
            print(f"  [DDS SKIP] {npc_id}: {exc}")

    output: dict[str, dict] = {}
    skipped = 0

    for pc_id in pc_ids:
        defn = load_record(pc_id)
        output[pc_id] = {"pc_role": defn.get("npcRole")}

        for npc_id in npc_ids:
            try:
                agg = load_record(npc_id)
                ots_data = compute_ots(agg, defn)
                dds_data = npc_dds.get(npc_id) or {}
                cm = npc_cm.get(npc_id, 1.0)
                dds_value = float(dds_data.get("dds", 0.0))
                nts_raw = round((ots_data["ots"] * 0.6 + dds_value * 0.4) * cm, 4)
                output[pc_id][npc_id] = {
                    "npc_rarity": agg.get("npcRarity"),
                    "nts_raw":    nts_raw,
                    "cm":         cm,
                    # OTS family
                    "ots":          ots_data["ots"],
                    "hpw_ss":       ots_data["hpw_ss"],
                    "edpr_ss":      ots_data["edpr_ss"],
                    "cts_ss":       ots_data["cts_ss"],
                    "hpw_af":       ots_data["hpw_af"],
                    "edpr_af":      ots_data["edpr_af"],
                    "cts_af":       ots_data["cts_af"],
                    "has_autofire": ots_data["has_autofire"],
                    "weapon_type":  ots_data["weapon_type"],
                    "is_excellent": ots_data["is_excellent"],
                    "attack_pool":  ots_data["attack_pool"],
                    "af_pool":      ots_data["af_pool"],
                    "range_dv":     ots_data["range_dv"],
                    # Defender (function of PC only)
                    "def_static":   ots_data["def_static"],
                    "def_ref":      ots_data["def_ref"],
                    "def_sp":       ots_data["def_sp"],
                    # DDS family (function of NPC only)
                    "dds":          dds_data.get("dds"),
                    "hpp":          dds_data.get("hpp"),
                    "aac":          dds_data.get("aac"),
                    "dsr_hp":       dds_data.get("dsr_hp"),
                    "sp_raw":       dds_data.get("sp_raw"),
                    "sp_capped":    dds_data.get("sp_capped"),
                    "body":         get_body(agg),
                    "will":         get_will(agg),
                }
            except Exception as exc:
                print(f"  [SKIP] {npc_id} vs {pc_id}: {exc}")
                skipped += 1

    out_path = Path("outputs/json_output") / "nts_raw_scores.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    total = sum(len(v) - 1 for v in output.values())  # minus 1 for the pc_role key
    print(f"Written to {out_path}  ({total} pairs, {skipped} skipped)")


# ---------------------------------------------------------------------------
# Verification — reproduces the Appendix B worked example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # --- Appendix B cross-check ---
    # Cherub (NPC.6thStreet_Cherub-like) attacks Tia Pu'ao
    # attack_pool=12, weapon=HeavyPistol (DV=15 at 12m), SP=15, REF<8
    # Expected: P_static=0.8, EDPR_SS=0 (10.5-15<0), CTS_SS=0.0741×10.7≈0.7929
    # OTS = 0.8 × (0 + 0.7929) ≈ 0.634
    print("=== Appendix B cross-check (manual) ===")
    ps = _p_static(12, 15)
    cts = compute_cts(3)
    edpr = compute_edpr_ss(10.5, 15, 2)
    hpw = max(0.2, min(1.0, ps))
    ots_manual = hpw * (edpr + cts)
    print(f"  P_static={ps:.3f}  HPW={hpw:.3f}  EDPR_SS={edpr:.3f}  CTS_SS={cts:.4f}")
    print(f"  OTS (manual) = {ots_manual:.4f}  (outline target ~0.632)")

    print()
    main()
