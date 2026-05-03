"""DDS components — Hit Point Pool, Armor Absorption Capacity, Death Save
Resilience — using the closed-form damage PMF for AAC.

AAC is computed per matchup: it depends on the aggressor's weapon dice_count
because absorption ablation is driven by the actual penetration probability
P(Nd6 > SP), not a fixed reference damage value.

Ablation rule (CP:RED): SP reduces by 1 only on a *penetrating* hit (damage >
current SP).  Non-penetrating hits absorb all damage without ablating SP.  The
Wald's-identity loop models this correctly — T_k = 1/π(k) attacks at SP=k
until the first penetrating hit.

When the weapon cannot penetrate the current SP level (π_k = 0), that SP level
does not ablate and delivers zero HP damage per attack — it contributes nothing
to the trajectory toward defender death.  Those immune SP levels are therefore
skipped in the AAC sum; the loop resumes at the first SP level where π_k > 0.
The `is_immune` flag records that the weapon started in an immune phase.

See docs/outline.md Component 2 of DDS for the full algorithm derivation.
"""

from __future__ import annotations

from .pmf import e_abs, e_pen, p_exceeds

SP_CAPPED = 18  # Metalgear, the strongest armor in CP:RED Core p. 351.


def compute_hpp(body: int, will: int) -> float:
    """HPP = ((WILL + BODY) / 2) * 5 + 10. CP:RED core formula."""
    return ((will + body) / 2) * 5 + 10


def compute_aac(sp: int, hpp: float, n_dice: int) -> float:
    """Expected armor absorption across the matchup that ends with the defender
    at 0 HP, using the aggressor's actual damage die pool.

    At each SP level k, attacks are i.i.d. Bernoulli(π_k = P(Nd6 > k)) for
    penetration.  By Wald's identity the expected total absorption during the
    geometric waiting time at SP=k is T_k · E_abs(N,k), where T_k = 1/π_k.
    Only the single penetrating attack that ends the phase delivers HP damage
    (= E_pen(N,k) = E[Nd6−k | Nd6>k]).

    When π_k = 0 (weapon cannot penetrate at the current SP level), that level
    contributes zero HP damage and its T_k is undefined (infinite).  Such levels
    are skipped — they do not move the defender toward death and therefore add
    nothing measurable to AAC.  The loop continues at lower SP levels where
    π_k > 0, always returning a finite value.
    """
    sp_capped = min(sp, SP_CAPPED)
    cumulative_hp = 0.0
    absorbed = 0.0

    for k in range(sp_capped, 0, -1):
        pi = p_exceeds(n_dice, k)
        if pi == 0.0:
            # Weapon cannot penetrate at SP = k: no HP damage, no ablation.
            # This level contributes nothing to AAC; skip it.
            continue

        ea = e_abs(n_dice, k)
        t_k = 1.0 / pi
        ep = e_pen(n_dice, k)

        if cumulative_hp + ep >= hpp:
            # Defender dies during this ablation phase — count only the partial
            # fraction of the phase needed to reach HPP.
            remaining = hpp - cumulative_hp
            partial_t = remaining / ep          # ≤ 1 ablation step
            absorbed += partial_t * t_k * ea
            return absorbed

        absorbed += t_k * ea
        cumulative_hp += ep

    return absorbed


def compute_dsr(body: int, dsr_weight: float = 5.0) -> float:
    """Expected rounds survived at 0 HP * dsr_weight, in HP-equivalent units.

    Per round k of the death spiral the survival probability is
    p(BODY, k) = max(0, min(9, BODY - k)) / 10. Expected rounds survived is
    sum over n=1..BODY-1 of prod over k=1..n of p(BODY, k).
    """

    def p(k: int) -> float:
        return max(0.0, min(9.0, body - k)) / 10.0

    e_dsr = 0.0
    for n in range(1, body):
        survival = 1.0
        for k in range(1, n + 1):
            survival *= p(k)
        e_dsr += survival
    return e_dsr * dsr_weight


def compute_dds(
    *, body: int, will: int, sp: int, n_dice: int, dsr_weight: float = 5.0
) -> dict:
    """DDS = HPP + AAC(per-matchup) + DSR_hp.

    Returns the full breakdown so callers can inspect each component.
    Includes `penetration_probability` (P(Nd6 > SP), always in [0, 1]) and
    """
    sp_capped = min(sp, SP_CAPPED)
    hpp = compute_hpp(body, will)
    aac = compute_aac(sp, hpp, n_dice)
    dsr_hp = compute_dsr(body, dsr_weight)
    dds = hpp + aac + dsr_hp

    p_pen = p_exceeds(n_dice, sp_capped)

    return {
        "dds": round(dds, 4),
        "hpp": round(hpp, 4),
        "aac": round(aac, 4),
        "dsr_hp": round(dsr_hp, 4),
        "sp_raw": sp,
        "sp_capped": sp_capped,
        "n_dice": n_dice,
        "penetration_probability": round(p_pen, 6),
    }
