from __future__ import annotations

from api.main import load_record, get_effective_sp

# ---------------------------------------------------------------------------
# Playtesting parameters (see docs/outline.md "Requires playtesting" section)
# ---------------------------------------------------------------------------
DSR_WEIGHT: float = 5.0

SP_CAPPED: int = 18
# REF_DAMAGE: minimum damage that penetrates any armor in CP:RED (must exceed SP_CAPPED).
# Represents a reference attacker used to compute realistic armor absorption.
# Default = SP_CAPPED + 1 so the formula is universally defined for all valid SP values.
REF_DAMAGE: float = SP_CAPPED + 1


# ---------------------------------------------------------------------------
# Stat extraction helpers
# ---------------------------------------------------------------------------

def get_body(record: dict) -> int:
    """Return the BODY attribute from a resolved record, defaulting to 0."""
    return int((record.get("attributes") or {}).get("body", 0))


def get_will(record: dict) -> int:
    """Return the WILLPOWER attribute from a resolved record, defaulting to 0."""
    return int((record.get("attributes") or {}).get("willpower", 0))


# ---------------------------------------------------------------------------
# DDS math (pure functions — no I/O)
# ---------------------------------------------------------------------------

def compute_hpp(body: int, will: int) -> float:
    """Compute the Hit Point Pool component of DDS.

    HPP = ((WILL + BODY) / 2) * 5 + 10

    This is the defender's raw HP using the CP:RED core rules formula.
    When (BODY + WILL) is odd the result is a .5 float; the spec does not
    apply floor or ceil — callers receive the exact value.

    Args:
        body: Resolved BODY attribute value.
        will: Resolved WILLPOWER attribute value.

    Returns:
        HPP as a float (e.g. 30.0 for BODY=4, WILL=4).
    """
    return ((will + body) / 2) * 5 + 10


def compute_aac(sp: int, hpp: float, ref_damage: float = REF_DAMAGE) -> float:
    """Compute the Armor Absorption Capacity component of DDS.

    Simulates hit-by-hit armor ablation against a reference attacker until the
    NPC's HP pool is exhausted, then sums only the absorption that actually
    occurred. This is the realized absorption — the amount of damage armor
    blocks during the combat that ends with the NPC's death.

    The reference attacker deals ref_damage per hit (default: SP_CAPPED + 1 = 19,
    the minimum damage that penetrates the strongest armor in CP:RED). Each
    penetrating hit ablates SP by 1 and absorbs current_sp damage before the
    remainder reaches HP.

    Using hpp in the computation means two NPCs with identical SP but different
    BODY/WILL produce different AAC values — higher-HP defenders survive more
    ablation steps and therefore extract more value from their armor.

    If ref_damage <= sp_capped the attacker cannot penetrate; falls back to the
    full triangular sum as a conservative upper bound.

    Args:
        sp:         Raw effective SP, before capping.
        hpp:        Hit Point Pool (output of compute_hpp).
        ref_damage: Reference attacker damage per hit. Must exceed SP_CAPPED.

    Returns:
        Realized AAC as a float.
    """
    sp_capped = min(sp, SP_CAPPED)

    if ref_damage <= sp_capped:
        return sp_capped * (sp_capped + 1) / 2

    cumulative_hp = 0.0
    absorbed = 0.0
    for k in range(sp_capped + 1):
        current_sp = sp_capped - k
        net_hp = ref_damage - current_sp
        cumulative_hp += net_hp
        absorbed += current_sp
        if cumulative_hp >= hpp:
            break

    return absorbed


def compute_dsr(body: int) -> float:
    """Compute the Death Save Resilience component of DDS (in HP units).

    Death saves work as follows: at 0 HP the defender rolls d10 each turn
    and survives if the result is strictly less than BODY. Each subsequent
    save accumulates a cumulative +1 penalty, making the effective threshold
    BODY - k on round k.

    Survival probability for a single round k:
        p(BODY, k) = max(0, min(9, BODY - k)) / 10

    Expected rounds survived at 0 HP (E_DSR):
        E_DSR(BODY) = Σ_{n=1}^{BODY-1}  ∏_{k=1}^{n} p(BODY, k)

    Each term in the outer sum is the probability of surviving all rounds
    1 through n. When body <= 1 the range is empty and E_DSR = 0.0.

    The raw E_DSR is then scaled to HP units by DSR_WEIGHT:
        DSR_hp = E_DSR(BODY) * DSR_WEIGHT

    Args:
        body: Resolved BODY attribute value.

    Returns:
        DSR_hp as a float, already multiplied by DSR_WEIGHT.
    """
    def p(k: int) -> float:
        return max(0.0, min(9.0, body - k)) / 10.0

    e_dsr = 0.0
    for n in range(1, body):           # outer sum: n = 1 to BODY-1
        survival_prob = 1.0
        for k in range(1, n + 1):      # inner product: k = 1 to n
            survival_prob *= p(k)
        e_dsr += survival_prob
    return e_dsr * DSR_WEIGHT


def compute_dds(body: int, will: int, sp: int) -> dict:
    """Compute the Defense Durability Score and return all intermediate values.

    DDS = HPP + AAC + DSR_hp
        = ( (WILL + BODY) / 2 ) * 5 + 10
        + realized_absorption(min(SP, 18), HPP, REF_DAMAGE)
        + E_DSR(BODY) * DSR_WEIGHT

    Args:
        body: Resolved BODY attribute value.
        will: Resolved WILLPOWER attribute value.
        sp:   Raw effective SP (before the SP_CAPPED cap is applied).

    Returns:
        Dict with keys: dds, hpp, aac, dsr_hp, sp_raw, sp_capped.
    """
    hpp    = compute_hpp(body, will)
    aac    = compute_aac(sp, hpp)
    dsr_hp = compute_dsr(body)
    dds    = hpp + aac + dsr_hp

    return {
        "dds":       round(dds, 4),
        "hpp":       round(hpp, 4),
        "aac":       round(aac, 4),
        "dsr_hp":    round(dsr_hp, 4),
        "sp_raw":    sp,
        "sp_capped": min(sp, SP_CAPPED),
    }


# ---------------------------------------------------------------------------
# Top-level record-driven calculation
# ---------------------------------------------------------------------------

def calculate_dds_for_records(defender_id: str) -> dict:
    """Load a defender record, extract stats, and compute DDS.

    The defender can be an NPC (base_files/records/npcs/) or a player
    character (base_files/records/player/). The $base prototype chain is
    fully resolved before stat extraction.

    Args:
        defender_id: Record ID string, e.g. "NPC.Base_Boss" or
                     "Characters.PC_Yuki_Raines".

    Returns:
        Dict with all keys from compute_dds() plus body, will, and
        defender_id for traceability.

    Raises:
        ValueError: If defender_id is not found in the registry.
    """
    record = load_record(defender_id)

    body = get_body(record)
    will = get_will(record)
    sp   = get_effective_sp(record)

    result = compute_dds(body, will, sp)
    result.update(
        body=body,
        will=will,
        defender_id=defender_id,
    )
    return result


# ---------------------------------------------------------------------------
# Verification — run `python dds_calc.py` to check against outline.md values
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pprint import pprint

    # Pure-math checks (DSR_WEIGHT=5, REF_DAMAGE=19).
    # AAC is now realized absorption, not the triangular sum — expected DDS values
    # are lower than the old outline.md table (see docs/outline.md §Component 2).
    test_cases = [
        # (label,  body, will, sp, expected_dds)
        ("Mook",        4,  4,  7,  49.8),   # AAC=18  (was 28)
        ("Hardened",    5,  5, 11,  75.7),   # AAC=38  (was 66)
        ("Boss",       10,  8, 18, 203.3),   # AAC=135 (was 171)
        ("Elite Boss", 12, 10, 18, 227.3),   # AAC=143 (was 171)
    ]
    print("=== DDS pure-math verification ===")
    print(f"{'Tier':<12}  {'HPP':>6}  {'AAC':>6}  {'DSR_hp':>7}  {'DDS':>7}  {'Expected':>9}  Match")
    for label, body, will, sp, expected in test_cases:
        r = compute_dds(body, will, sp)
        match = "OK" if abs(r["dds"] - expected) < 1.0 else "MISMATCH"
        print(
            f"{label:<12}  {r['hpp']:>6.1f}  {r['aac']:>6.1f}  "
            f"{r['dsr_hp']:>7.2f}  {r['dds']:>7.2f}  {expected:>9.1f}  {match}"
        )

    # Record-driven check
    print("\n=== Record-driven check: NPC.6thStreet_Arbiter ===")
    print("  (BODY=5, WILL=6, armor=15 -> HPP=37.5, realized AAC=75.0, DSR_hp~2.73)")
    pprint(calculate_dds_for_records("NPC.6thStreet_Arbiter"))
