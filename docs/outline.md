# NPC Threat Score (NTS) System

The NPC Threat Score (NTS) is a 1–20 rating calculated for every NPC or group of NPCs. The rating is designed to summarize how dangerous that NPC (or group) is to a specified Cyberpunk: RED player character (PC) or group of PCs. Each NPC's score is derived from three independent axes: offense, defense, and capability complexity.  
These axes are combined and normalized into the final rating.

**Scoring axes:**
- Offensive Threat Score (OTS)
- Defensive Durability Score (DDS)
- Complexity Multiplier (CM)

## Threat Tier Reference

| Rating  | Tier                        | Description                                                   | Typical NPCs                                      |
|---------|-----------------------------|---------------------------------------------------------------|---------------------------------------------------|
| 1 – 4   | Street                      | Mooks, street thugs.                                          | Mooks                                             |
| 5 – 8   | Hardened                    | Organized gang soldiers, corp security.                       | Mooks + Lieutenants                               |
| 9 – 12  | Serious Threat              | Veteran mercs, black-market solos, trauma team.               | Lieutenants + Mini-bosses                         |
| 13 – 16 | Likely to Cause Casualties  | MaxTac, corp wetwork, hardened bosses.                        | Mini-bosses + Bosses                              |
| 17 – 20 | Overwhelming                | Near-certain wipe. Arasaka strike teams, legendary solos.     | Bosses + Elite Bosses                             |

## Scoring Overview

The final score blends the three axes:

$
NTS_raw = ((OTS × 0.6) + (DDS × 0.4)) × CM
NTS     = clamp(round(NTS_raw / SCALE_FACTOR), 1, 20)
$

The remaining sections define each axis in turn (OTS, DDS, CM), then pull the pieces back together in [Final NTS Calculation](#final-nts-calculation). Every tunable constant is collected in [Open Calibration Parameters](#open-calibration-parameters) at the end.

## Offensive Threat Score (OTS)

### Component 1: Hit Probability Weight (HPW)

The Hit Probability Weight (HPW) is a scalar reflecting how reliably an aggressor (AGG) threatens a defender's (DEF) defenses.

Per the defined combat system in Cyberpunk RED, NPCs and PCs alike are required to be treated as aggressors and defenders relative to the current character's turn.
However, there are differences in how skills are calculated between PCs and NPCs. This requires that the terms AGG and DEF define the appropriate calculation relative to a current term.
Additionally, the intialism NPC and PC are still required to delineate between specific calculation inputs.
To accommodate this requirement, the generalized terms 'aggressor' and 'defender' are used in addition to the initialism 'NPC' and 'PC' for this section.

### 1.1 Attack Pool
The attack pool defines an aggressor's total skill pool that will be added to a die roll in order to attempt to beat a defender's defense pool.
Weapons that have a quality of excellent or better are awarded a + 1 bonus when trying to attack.<br>

_For the piecewise expressions below, x is a binary variable where x = 1 means the weapon quality is >= excellent.<br>_

**pc_attack_pool**

$f(x) = REF + weapon skill$

$
f(x) = \begin{cases}
  x + 1  & \text{if } x = 1 \\
  x  & \text{if } x = 0
\end{cases}
$

**npc_attack_pool**

$r(x) = weapon skill$

$
r(x) = \begin{cases}
  x + 1  & \text{if } x = 1 \\
  x  & \text{if } x = 0
\end{cases}
$

### 1.2 Conditional Dodge Attempts
A defender with a REF 8 or higher can choose to attempt to dodge a Ranged Attack instead of using the range table to determine the DV.
 In general, this option will be used when the probability for dodging outweighs the static DV rating in the [Range Table](#appendix-a---range-table).

Dice rolling functionality will be used to more accurately simulate when dodging will take place.

**If DEF has REF ≥ 8 (can dodge):**
```
def_defense = DEF_DEX + DEF_evasion_skill + 1d10
margin      = attack_pool - def_defense
HPW         = clamp((margin + 5) / 10, 0.2, 1.5)
```
(margin of 0 → HPW 0.5; margin of +5 → HPW 1.0; margin of +10 → HPW 1.5)


**If DEF cannot dodge (REF < 8):**
The aggressor is shooting against a static range DV. At medium range typical DV = 15.
```
assumed_dv = 15
margin     = attack_pool - assumed_dv + 5.5
HPW        = clamp(margin / 10, 0.3, 1.5)
```

***Rationale:*** A 0.5 HPW means the aggressor is a coin-flip threat. A 1.0 HPW means they're reliably hitting. The 0.2 floor keeps even bad aggressors nonzero and the 1.5 ceiling reflects that dominant aggressors are threatening but not infinitely so (there is still variance).

### Component 2: Expected Damage Per Round (EDPR)

EDPR is calculated per fire mode.

**Single Shot** (per attack, × ROF for multi-shot weapons):
```
SS_damage_per_hit = avg_weapon_damage - DEF_effective_SP   (floor 0)
EDPR_SS           = SS_damage_per_hit * ROF
```

**Autofire** (SMG: ×3 cap, AR: ×4 cap):
- Autofire uses harder DVs. Against a dodging defender, `attack_pool` vs `def_defense` still applies.
- Expected multiplier: avg roll above DV, bounded by cap.
- With `attack_pool` 14 vs autofire DV 20 (mid-range SMG), avg margin = 0 → most rolls give ×1 or miss.
- Model expected multiplier as: `E[mult] = HPW_autofire × (cap + 1) / 2`.
- `HPW_autofire` uses a -3 penalty to `attack_pool` to reflect the higher DV.

```
autofire_attack_pool = REF + autofire_skill
HPW_AF               = (derived as above, using autofire_attack_pool vs harder DV or adjusted def_defense)
avg_mult             = HPW_AF * (autofire_cap + 1) / 2   (e.g., SMG cap 3: avg_mult up to 2.0)
EDPR_AF              = (avg(2d6) - DEF_effective_SP) * avg_mult   (floor 0 on each factor)
```

### Component 3: Crit Threat Score (CTS)

*What a Critical Injury Actually Does*

When two or more damage dice show 6, the attacker:
1. Deals +5 bonus HP damage that bypasses armor entirely.
2. Rolls on the Critical Injury Table (the result imposes a lasting mechanical penalty).

Both effects happen regardless of whether any damage penetrated SP. The +5 is guaranteed on a crit. The injury effect is variable but always mechanically significant.

#### Part A: Crit Probability by Damage Dice Count

To calculate crit probability requires P(at least two dice show 6) on N six-sided dice. It's simpler and faster to compute the complement: P(fewer than two 6s) = P(zero 6s) + P(exactly one 6).

Let p = 1/6 (probability of a single die showing 6), q = 5/6 (probability of a single die not showing 6).
```
P(zero 6s)        = q^N = (5/6)^N
P(exactly one 6)  = C(N,1) × p × q^(N-1) = N × (1/6) × (5/6)^(N-1)
P(crit)           = 1 - (5/6)^N - N × (1/6) × (5/6)^(N-1)
```

##### Working through each relevant die count

***N = 2 (e.g., medium pistol, SMG autofire base, melee weapon):***
```
P(zero 6s)       = (5/6)² = 25/36 ≈ 0.6944
P(exactly one 6) = 2 × (1/6) × (5/6) = 10/36 ≈ 0.2778
P(crit)          = 1 - 25/36 - 10/36 = 1/36 ≈ 0.0278
```

***N = 3 (e.g., heavy pistol, shotgun slug, SMG autofire if using 3d6 variant):***
```
P(zero 6s)       = (5/6)³ = 125/216 ≈ 0.5787
P(exactly one 6) = 3 × (1/6) × (5/6)² = 3 × (1/6) × (25/36) = 75/216 ≈ 0.3472
P(crit)          = 1 - 125/216 - 75/216 = 16/216 ≈ 0.0741
```

***N = 4 (e.g., very heavy pistol, assault rifle single shot):***
```
P(zero 6s)       = (5/6)⁴ = 625/1296 ≈ 0.4823
P(exactly one 6) = 4 × (1/6) × (5/6)³ = 4 × (1/6) × (125/216) = 500/1296 ≈ 0.3858
P(crit)          = 1 - 625/1296 - 500/1296 = 171/1296 ≈ 0.1319
```

***N = 5 (e.g., shotgun shell area, sniper rifle):***
```
P(zero 6s)       = (5/6)⁵ = 3125/7776 ≈ 0.4019
P(exactly one 6) = 5 × (1/6) × (5/6)⁴ = 5 × (1/6) × (625/1296) = 3125/7776 ≈ 0.4019
P(crit)          = 1 - 3125/7776 - 3125/7776 = 1526/7776 ≈ 0.1962
```

***N = 6 (e.g., heavy SMG, some assault weapons):***
```
P(zero 6s)       = (5/6)⁶ = 15625/46656 ≈ 0.3349
P(exactly one 6) = 6 × (1/6) × (5/6)⁵ = 15625/46656 ≈ 0.3349 (property of the binomial at this value)
P(crit)          = 1 - 15625/46656 - 15625/46656 = 15406/46656 ≈ 0.3302
```

#### Part B: Bonus HP Damage from Crits (+5)

The +5 damage to HP happens whenever a critical hit occurs. Below is the expected bonus HP damage from crits.

**Expected bonus HP damage from crits per attack:**
```
E[crit_HP_bonus] = P(crit) × 5
```

| N | P(crit) | E[crit HP bonus] |
|---|---------|------------------|
| 2 | 0.0278  | 0.14             |
| 3 | 0.0741  | 0.37             |
| 4 | 0.1319  | 0.66             |
| 5 | 0.1962  | 0.98             |
| 6 | 0.3302  | 1.65             |

#### Part C: Injury Severity

There are two injury tables: Body (where most attacks land) and Head (aimed shots to the head only). Typical NPC aggressors won't take aimed shots, so this part focuses on body shots.

The body critical injury table is rolled on 2d6. Results aren't uniformly distributed — the middle values (6, 7, 8) are the most likely to occur.

```
P(rolling 2)  = 1/36  ≈ 0.0278 ≈ 2.78%
P(rolling 3)  = 1/18  ≈ 0.0556 ≈ 5.56%
P(rolling 4)  = 1/12  ≈ 0.0833 ≈ 8.33%
P(rolling 5)  = 1/9   ≈ 0.1111 ≈ 11.1%
P(rolling 6)  = 5/36  ≈ 0.1389 ≈ 13.89%
P(rolling 7)  = 1/6   ≈ 0.1667 ≈ 16.67%
P(rolling 8)  = 5/36  ≈ 0.1389 ≈ 13.89%
P(rolling 9)  = 1/9   ≈ 0.1111 ≈ 11.1%
P(rolling 10) = 1/12  ≈ 0.0833 ≈ 8.33%
P(rolling 11) = 1/18  ≈ 0.0556 ≈ 5.56%
P(rolling 12) = 1/36  ≈ 0.0278 ≈ 2.78%
```

##### Body Critical Injury Table

| 2d6 | Injury           | Injury Effect                                 | Death Save Penalty | Quick Fix                   | Treatment    |
|-----|------------------|-----------------------------------------------|--------------------|-----------------------------|--------------|
|  2  | Dismembered Arm  | Lose the arm. Drop any item held in that arm. | +1                 | None                        | Surgery DV17 |
|  3  | Dismembered Arm  | Lose the arm. Drop any item held in that arm. | +1                 | None                        | Surgery DV17 |
|  4  | Collapsed Lung   | −2 to MOVE (minimum 1).                       | +1                 | None                        | Surgery DV17 |
|  5  | Broken Ribs      | −2 to all Actions except MOVE.                | None               | First Aid or Paramedic DV13 | Surgery DV13 |
|  6  | Broken Arm       | −2 to all Actions involving that arm.         | None               | First Aid or Paramedic DV13 | Surgery DV13 |
|  7  | Foreign Object   | At end of every Turn take 2 hp dmg/4m moved.  | None               | First Aid or Paramedic DV13 | Surgery DV13 |
|  8  | Torn Muscle      | −2 to all Actions involving that limb.        | None               | First Aid or Paramedic DV13 | Surgery DV13 |
|  9  | Spinal Injury    | −4 to MOVE (minimum 1).                       | None               | First Aid or Paramedic DV15 | Surgery DV15 |
| 10  | Crushed Fingers  | −4 to all Actions involving that hand.        | None               | First Aid or Paramedic DV15 | Surgery DV15 |
| 11  | Damaged Eye      | −2 to Ranged Attacks and Perception Checks.   | None               | First Aid or Paramedic DV15 | Surgery DV15 |
| 12  | Head Shot        | −2 to all Actions.                            | +1                 | None                        | Surgery DV17 |

Instead of accounting for all possible outcomes individually, the table is split into two axes:
- Death save penalty contributions
- Action penalty contributions

##### Death Save Penalty (DSP) Contributions

Outcomes 2, 3, 4, and 12 add +1 to death saves. These are relevant if a PC reaches 0 HP.

*Expected DSP per crit:*
```
P(DSP outcomes) = P(2) + P(3) + P(4) + P(12)
                = 1/36 + 2/36 + 3/36 + 1/36
                = 7/36
                ≈ 0.194
```

##### Action Penalty Contributions

Almost every outcome imposes a −2 or −4 to some category of action.

*Expected stat-penalty magnitude per crit (weighted by 2d6 probability):*

| Outcome              | Penalty            | Prob (2d6) | Weighted                  |
|----------------------|--------------------|------------|---------------------------|
| 2 (Dismembered Arm)  | severe (lose limb) | 1/36       | —                         |
| 3 (Dismembered Arm)  | severe             | 2/36       | —                         |
| 4 (Collapsed Lung)   | −2 MOVE            | 3/36       | 3 × 2 = 6                 |
| 5 (Broken Ribs)      | −2 all actions     | 4/36       | 4 × 2 = 8                 |
| 6 (Broken Arm)       | −2 arm actions     | 5/36       | 5 × 1 = 5 (partial, ~half)|
| 7 (Foreign Object)   | 2 HP/turn ongoing  | 6/36       | — (HP, not stat)          |
| 8 (Torn Muscle)      | −2 limb actions    | 5/36       | 5 × 1 = 5 (partial)       |
| 9 (Spinal Injury)    | −4 MOVE            | 4/36       | 4 × 4 = 16                |
| 10 (Crushed Fingers) | −4 Ranged/DEX/REF  | 3/36       | 3 × 4 = 12                |
| 11 (Damaged Eye)     | −2 Ranged/Percep   | 2/36       | 2 × 2 = 4                 |
| 12 (Head Shot)       | −2 all actions     | 1/36       | 1 × 2 = 2                 |

```
Sum of clearly-weighted values = 6 + 8 + 5 + 16 + 12 + 4 + 2 = 53
Partial-credit for outcomes 6 and 8 already included above as 5 + 5 = 10
Total weighted penalty sum     = 53
Total probability weight used  = 3 + 4 + 5 + 4 + 3 + 2 + 1 + 5 = 27 (of 36 outcomes)
```

Rough expected action penalty per crit ≈ 53/36 ≈ 1.47 penalty points on affected rolls, sustained for the remainder of a fight.

### Combining the Components

```
CTS = E[crit_HP_bonus] + E[DSP_value] + E[action_penalty_value] + E[bleed_hp]
```

*Where:*
- `E[crit_HP_bonus]` = P(crit) × 5 (see Part B)
- `E[DSP_value]` = P(crit) × P(DSP|crit) × DSP_weight
  - P(DSP|crit) ≈ 0.194 (from Part C)
  - `DSP_weight` = a design parameter. A +1 death save penalty materially changes survival odds at 0 HP. Proposed: `DSP_weight = 3` (reflects that pushing a PC toward death is high-value; calibrate in playtesting — see [Open Calibration Parameters](#open-calibration-parameters))
  - → `E[DSP_value]` = P(crit) × 0.194 × 3 = P(crit) × 0.58
- `E[action_penalty_value]` = P(crit) × 1.47 × fight_rounds_remaining
  - `fight_rounds_remaining` is contextual. For a generator, use a baseline of 3 rounds (typical CP:RED combat length)
  - → `E[action_penalty_value]` = P(crit) × 1.47 × 3 = P(crit) × 4.41
- `E[bleed_hp]` = P(crit) × (6/36) × 4 = P(crit) × 0.67

Combining the per-crit multipliers:
```
CTS = P(crit) × (5 + 0.58 + 4.41 + 0.67)
    = P(crit) × 10.66
    ≈ P(crit) × 10.7
```

**CTS by weapon class:**

| Weapon                             | Damage Dice | P(crit) | CTS  |
|------------------------------------|-------------|---------|------|
| Medium Pistol, SMG (autofire base) | 2d6         | 0.0278  | 0.30 |
| Heavy Pistol                       | 3d6         | 0.0741  | 0.79 |
| Very Heavy Pistol, Assault Rifle   | 4d6         | 0.1319  | 1.41 |
| Sniper Rifle                       | 5d6         | 0.1962  | 2.10 |
| Heavy SMG, Shotgun (single shot)   | 6d6         | 0.3302  | 3.53 |

### Autofire's Crit Interaction

Autofire always rolls 2d6 for damage regardless of the base weapon's damage dice. This means a Heavy SMG on autofire has lower crit probability (0.0278) than the same weapon firing single-shot (0.3302). This is an intentional design tradeoff in CP:RED — autofire trades crit threat for multiplied raw damage.

The formula handles this naturally:
- When computing `EDPR_AF`, an average 2d6 is used and P(crit) = 0.0278 for `CTS_AF`.
- Single-shot uses the weapon's full die count.

### Final OTS Formulas

*Weighted average across fire modes:*
```
CTS_AVG = (CTS_SS + CTS_AF) / 2
```

*Final OTS expression (expanded for autofire):*
```
OTS = ((HPW_SS + HPW_AF) / 2) × ((EDPR_SS + EDPR_AF + CTS_SS + CTS_AF) / 2)
```

*Final OTS expression without autofire:*
```
OTS = HPW_SS × (EDPR_SS + CTS_SS)
```

Where:
- `EDPR` = the higher of `EDPR_SS` or `EDPR_AF` (see [Open Calibration Parameters](#open-calibration-parameters))
- `CTS` = P(crit) × 10.7 (using the matching die count for the fire mode)
- `HPW` = hit probability weight for the chosen fire mode

## Defensive Durability Score (DDS)

DDS answers the question: how much total damage must an aggressor deal to eliminate this defender, accounting for armor absorption across its full lifespan and the death save buffer?

### Component 1: Hit Point Pool (HPP)

The defender's raw HP, per the core rules formula:
```
HPP = ((WILL + BODY) / 2) × 5 + 10
```

HPP is the primary damage reservoir — the amount of net (post-SP) damage required to bring the defender to 0 HP.

### Component 2: Armor Absorption Capacity (AAC)

SP is not a one-time pool. It reduces damage on every penetrating hit and ablates by 1 each time damage gets through (incoming damage > current SP). To model the total damage SP absorbs before breaking, sum its full ablation lifespan:

```
AAC = SP_CAPPED + (SP_CAPPED - 1) + (SP_CAPPED - 2) + ... + 1 + 0
    = SP_CAPPED × (SP_CAPPED + 1) / 2

where SP_CAPPED = min(sp, 18)
```

This is the total damage absorbed by armor across its full ablation lifespan. SP 7 absorbs 7+6+5+4+3+2+1 = 28 damage. SP 11 absorbs 66. The formula follows directly from the triangular number sum.

*Validity condition:*
AAC is defined only when the attacker's EDPR > 0. If a weapon cannot penetrate SP at all, the defender is functionally immune to that aggressor. DDS is infinite relative to them and the comparison is meaningless.

*On partial ablation:*
AAC assumes the armor is fully ablated before the defender dies. This is the minimum-penetration case (attacker damage just barely exceeds SP). For stronger attackers, actual absorption per-hit is identical. Each penetrating hit still absorbs exactly SP-at-that-round. The total absorbed sum is the same regardless of how far over SP the damage lands. AAC can be understated only when the NPC dies before all ablation steps complete (very powerful attacker vs very low-HP NPC).

*SP cap justification:*
The triangular sum grows quadratically. An SP value of 18 absorbs 171 total damage; SP 28 absorbs 406. Values above SP 18 represent military-grade borgware and classified augmentation, not standard armor ratings. At SP 28+ the AAC term dominates the entire DDS calculation and collapses the separation between Boss and Elite Boss tiers.

Capping AAC input at SP 18 preserves meaningful tier differentiation. Excess SP beyond 18 is accounted for implicitly: it takes more hits to begin ablating the armor, but the formula treats this as a conservative floor rather than an exponentially scaled outlier.

In that scenario:
- AAC still correctly rank-orders defenders. Higher SP always implies equal or greater absorption.
- The discrepancy only becomes material at extreme ratios. For typical CP:RED combat it is an acceptable baseline.

### Component 3: Death Save Resilience (DSR)

When a defender reaches 0 HP they enter the Mortally Wounded state but are not immediately eliminated. At the start of each of their turns they must make a Death Save: roll a d10 and survive if the result is strictly less than BODY.

A roll of 10 always fails regardless of BODY.

Each consecutive save increases the cumulative penalty by +1, making each subsequent save harder. The defender dies on any single failed save.

#### Deriving E[rounds survived at 0 HP]

Let `p(BODY, k)` = probability of surviving round k of the death spiral:
```
P(BODY, k) = max(0, min(9, BODY − k)) / 10
```

Breakdown of the terms:
- `BODY − k`: the effective threshold after k rounds (penalty = k−1 by round k, so need roll < BODY − (k−1), i.e., ≤ BODY − k)
- `min(9, ...)`: caps the success range at 9 because 10 always auto-fails
- `max(0, ...)`: floor at 0 because the save cannot be made once the threshold is exhausted

##### Expected rounds survived at 0 HP

```
E_DSR(BODY) = Σ_{n=1}^{BODY−1} ∏_{k=1}^{n} p(BODY, k)
```

Each term is the probability of surviving all rounds 1 through n. The outer sum accumulates across all possible survival lengths.

| BODY | p(round 1) | E_DSR |
|------|------------|-------|
|  3   | 0.20       | 0.22  |
|  4   | 0.30       | 0.37  |
|  5   | 0.40       | 0.55  |
|  6   | 0.50       | 0.77  |
|  7   | 0.60       | 1.06  |
|  8   | 0.70       | 1.44  |
|  9   | 0.80       | 1.96  |
| 10   | 0.90       | 2.66  |
| 12   | 0.90*      | 3.86  |
| 14   | 0.90*      | 4.84  |

To make DSR commensurable with HPP and AAC (both in HP units), multiply by a reference damage rate:
```
DSR_hp = E_DSR(BODY) × DSR_weight
```

### Final DDS Formula

$$
DDS = HPP + AAC + DSR_hp
    = ((WILL + BODY) / 2) × 5 + 10
    + min(SP, 18) × (min(SP, 18) + 1) / 2
    + E_DSR(BODY) × DSR_weight
$$

**Sample values across NPC tiers** (representative stats, `DSR_weight = 5`):

| NPC Tier      | BODY | WILL | SP  | HPP | AAC | DSR_hp | DDS   |
|---------------|------|------|-----|-----|-----|--------|-------|
| Mook          | 4    | 4    | 7   | 30  | 28  | 1.8    | 59.8  |
| Hardened Mook | 5    | 5    | 11  | 35  | 66  | 2.7    | 103.7 |
| Lieutenant    | 6    | 6    | 11  | 40  | 66  | 3.9    | 109.9 |
| Mini-Boss     | 8    | 7    | 11  | 47  | 66  | 7.2    | 120.2 |
| Boss          | 10   | 8    | 18  | 55  | 171 | 13.3   | 239.3 |
| Elite Boss    | 12   | 10   | 18  | 65  | 171 | 19.3   | 255.3 |

## Complexity Multiplier (CM)

CM adjusts the final score upward when the NPC has capabilities beyond basic combat. It starts at 1.0 and caps at 2.0:

```
CM = clamp(1.0 + Σ(cyberware_tier_bonuses) + Σ(special_gear_bonuses) + netrun_bonus, 1.0, 2.0)

  + 0.15 per cyberware tier above Basic  (Basic → Standard → Premium → Military)
  + 0.10 per special-gear item           (grenade launcher, EMP, smartgun link, etc.)
  + 0.20 if NPC can netrun
```

## Final NTS Calculation

### Raw Score

```
NTS_raw = ((OTS × 0.6) + (DDS × 0.4)) × CM
```

The 60/40 offense/defense weighting reflects CP:RED's lethality. A single well-rolled autofire burst can drop an NPC/PC in one action. Offense is weighted higher because the threat of being eliminated in a single round is mechanically distinct from a war of attrition. **This split requires playtesting** (see [Open Calibration Parameters](#open-calibration-parameters)); if burst damage consistently over-rates NPCs, shifting toward 55/45 is the first adjustment.

### Normalization

```
NTS = clamp(round(NTS_raw / SCALE_FACTOR), 1, 20)
```

`SCALE_FACTOR` is a calibration constant derived by plugging official Mook, Lieutenant, and Mini-Boss stat blocks into the formula against a median PC baseline (REF 6, weapon skill 4, SP 11) and back-solving so each anchor lands in its target band.

## Open Calibration Parameters

Every tunable constant in the system is collected here for playtesting and adjustment. Each has a current proposed value; none should be considered final until playtested.

- **`DSP_weight`** — currently `3`. Governs how much a +1 death save penalty contributes to CTS. A higher value increases the crit-threat contribution of outcomes that push PCs toward death.
- **`fight_rounds_remaining`** — currently `3`. Baseline number of rounds over which a crit's action penalty is assumed to apply. Matches typical CP:RED combat length.
- **Single-shot vs. autofire selection** — when an aggressor has both fire modes available, which is used to compute OTS?
  - Best fire mode: whichever of `EDPR_SS` or `EDPR_AF` is higher.
  - Weighted average: `(EDPR_SS + EDPR_AF) / 2`.
  Both values are explicit and adjustable. Determining which choice produces better calibration requires further testing.
- **`DSR_weight`** — currently `5`. The reference damage rate used to convert expected rounds survived at 0 HP into HP-equivalent units for DDS.
- **60/40 offense/defense split in `NTS_raw`** — if burst damage consistently over-rates NPCs, shifting toward 55/45 is the first adjustment to try.

## Appendix A - Range Table

| Weapon Type      | 0 to 6 m/yds | 7 to 12m/yds | 13 to 25 m/yds | 26 to 50 m/yds | 51 to 100 m/yds | 101 to 200 m/yds | 201 to 400 m/yds | 401 to 800 m/yds |
|------------------|:------------:|:------------:|:--------------:|:--------------:|:---------------:|:----------------:|:----------------:|:----------------:|
| Pistol           |      13      |      15      |       20       |       25       |       30        |        30        |       INF        |       INF        |
| SMG              |      15      |      13      |       15       |       20       |       25        |        25        |        30        |       INF        |
| Shotgun (Slug)   |      13      |      15      |       20       |       25       |       30        |        35        |       INF        |       INF        |
| Assault Rifle    |      17      |      16      |       15       |       13       |       15        |        20        |        25        |        30        |
| Sniper Rifle     |      30      |      25      |       25       |       20       |       15        |        16        |        17        |        20        |
| Bows & Xbows     |      15      |      13      |       15       |       17       |       20        |        22        |       INF        |       INF        |
| Grenade Launcher |      16      |      15      |       15       |       17       |       20        |        22        |        25        |       INF        |
| Rocket Launcher  |      17      |      16      |       15       |       15       |       20        |        20        |        25        |        30        |

## Resources

- [DND Mathematics Profile](https://github.com/tomedunn/the-finished-book/blob/master/assets/python/dice_roller/nodes.py)
