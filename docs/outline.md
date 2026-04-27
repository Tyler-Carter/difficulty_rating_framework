# NPC Threat Score (NTS) System

The NPC Threat Score (NTS) is a 1–20 rating calculated for every NPC or group of NPCs. The rating is designed to summarize how dangerous that NPC (or group) is to a specified Cyberpunk: RED player character (PC) or group of PCs. Each NPC's score is derived from three independent axes: offense, defense, and capability complexity.  
These axes are combined and normalized into the final rating.

**Scoring axes:**
- Offensive Threat Score (OTS)
- Defensive Durability Score (DDS)
- Complexity Multiplier (CM)

---

## Threat Tier Reference

| Rating  | Tier                        | Description                                                   | Typical NPCs                                      |
|---------|-----------------------------|---------------------------------------------------------------|---------------------------------------------------|
| 1 – 4   | Street                      | Mooks, street thugs.                                          | Mooks                                             |
| 5 – 8   | Hardened                    | Organized gang soldiers, corp security.                       | Mooks + Lieutenants                               |
| 9 – 12  | Serious Threat              | Veteran mercs, black-market solos, trauma team.               | Lieutenants + Mini-bosses                         |
| 13 – 16 | Likely to Cause Casualties  | MaxTac, corp wetwork, hardened bosses.                        | Mini-bosses + Bosses                              |
| 17 – 20 | Overwhelming                | Near-certain wipe. Arasaka strike teams, legendary solos.     | Bosses + Elite Bosses                             |

---

## Scoring Overview

The final score blends the three axes:

$
NTS_raw = ((OTS × 0.6) + (DDS × 0.4)) × CM
NTS     = clamp(round(NTS_raw / SCALE_FACTOR), 1, 20)
$

The remaining sections define each axis in turn (OTS, DDS, CM), then pull the pieces back together in [Final NTS Calculation](#final-nts-calculation). Every tunable constant is collected in [Open Calibration Parameters](#open-calibration-parameters) at the end.

## Offensive Threat Score (OTS)

### Component 1: Hit Probability Weight (HPW)

The Hit Probability Weight (HPW) is the probability that an aggressor's attack lands against the defender's optimally-chosen defense option (static range DV or active dodge), clamped to the range [0.2, 1.0]. The full derivation is in [§1.2](#12-conditional-dodge-attempts).

Per the defined combat system in Cyberpunk RED, NPCs and PCs alike are required to be treated as aggressors and defenders relative to the current character's turn.
However, there are differences in how skills are calculated between PCs and NPCs. This requires that the terms AGG and DEF define the appropriate calculation relative to a current term.
Additionally, the intialism NPC and PC are still required to delineate between specific calculation inputs.
To accommodate this requirement, the generalized terms 'aggressor' and 'defender' are used in addition to the initialism 'NPC' and 'PC' for this section.

---

#### <u>1.1 Attack Pool</u>
The attack pool defines an aggressor's total skill pool that will be added to a die roll in order to attempt to beat a defender's defense pool.
Weapons that have a quality of excellent or better are awarded a +1 bonus when trying to attack.<br>

_Let `q = 1` if the weapon's quality is ≥ excellent, otherwise `q = 0`._

```
pc_attack_pool  = REF + weapon_skill + q
npc_attack_pool =       weapon_skill + q
```

---

#### <u>1.2 Conditional Dodge Attempts</u>

A defender with REF ≥ 8 may choose, when targeted by a Ranged Attack, to roll an active dodge (DEX + Evasion + 1d10) instead of letting the attack be resolved against the static DV from the [Range Table](#appendix-a---range-table). The defender is assumed to choose optimally (i.e., to pick whichever option minimizes the probability of being hit).

The damage distribution *given a hit* is identical under either option (neither d10 affects the damage dice), so minimizing P(hit) also minimizes E[damage taken from this attack]. Both probabilities have closed forms which removes any requirement for a per-roll simulation.

#### Inputs

- `attack_pool` — the aggressor's attack roll modifier from [§1.1](#11-attack-pool) (with the +1 Excellent-quality bonus already applied if applicable). For autofire, substitute `autofire_attack_pool` (and any DV penalty handled by the caller).
- `range_dv` — static DV returned by `get_difficulty(weapon_type, range_m)` in [calculations/range_dv.py](../calculations/range_dv.py); see also the [Range Table](#appendix-a---range-table).
- `def_static = DEF_DEX + DEF_evasion_skill` — deterministic part of the dodge defense.

#### P_static — attack lands against the static range DV

The attacker hits when `d10_a + attack_pool ≥ range_dv`. With a flat d10:

```
need     = range_dv − attack_pool
P_static = clamp((11 − need) / 10, 0, 1)
```

#### P_dodge — attack lands against an active dodge

The attacker hits when `d10_a + attack_pool ≥ d10_d + def_static`. Let `D = d10_a − d10_d`. With both dice flat-uniform on {1..10}, `D` is triangular on {−9..9} with PMF `P(D = k) = (10 − |k|) / 100`. Writing `shift = def_static − attack_pool`:

```
              ⎧ 1                                   shift ≤ −9
P_dodge   =   ⎨ 1 − (9 + shift)(10 + shift) / 200   −9 ≤ shift ≤ 0
              ⎨ (10 − shift)(11 − shift) / 200       0 ≤ shift ≤ 9
              ⎩ 0                                    shift ≥ 10
```

(Both middle cases agree at `shift = 0`, giving 0.55.)

#### Decision rule

```
if DEF_REF ≥ 8:
    dodge = P_dodge < P_static
    P_hit = P_dodge if dodge else P_static
else:
    P_hit = P_static
```

#### Hit Probability Weight (HPW)

HPW is derived directly from the chosen `P_hit`:

```
HPW = clamp(P_hit, 0.2, 1.0)
```

The 0.2 floor preserves a nonzero threat for aggressors who cannot statistically land a hit at the current range. An enemy that is armed is not a non-threat. They may move, reposition, switch weapons, etc. The ceiling is 1.0 by definition of probability. The idea of "dominance" beyond reliable hitting is captured downstream by EDPR (damage volume) and CTS (crit threat).

***Rationale:*** HPW = 0.5 means the aggressor is a coin-flip threat. HPW = 1.0 means they're reliably hitting. Mapping HPW directly to `P_hit` collapses the dodge and no-dodge branches onto a single coherent probability scale.

#### Caveat: exploding / imploding d10

Both closed forms treat the d10 as flat-uniform on {1..10}. CP:RED's exploding/imploding d10 (a 10 rerolls and adds; a 1 rerolls and subtracts) shifts both `P_static` and `P_dodge` by a small amount in each tail. If exact probabilities are required, substitute the explode/implode PMF for the uniform PMF and recompute the `D = d10_a − d10_d` convolution; the decision rule itself is unchanged.

---

### Component 2: Expected Damage Per Round (EDPR)

EDPR is calculated per fire mode.

**Single Shot** (per attack, × ROF for multi-shot weapons):
```
SS_damage_per_hit = avg_weapon_damage - DEF_effective_SP   (floor 0)
EDPR_SS           = SS_damage_per_hit * ROF
```

**Autofire** (SMG: ×3 cap, AR: ×4 cap):
- Against any defender, the same `P_hit` calculation from [§1.2](#12-conditional-dodge-attempts) applies. Substitute `autofire_attack_pool` for `attack_pool` and add a +3 penalty to `range_dv` (handled by the caller per §1.2) before invoking the rule.
- Conditional on a hit, the multiplier is uniform on {1..cap}, so `E[mult | hit] ≈ (cap + 1) / 2`.
- The unconditional expected multiplier is therefore `HPW_AF × (cap + 1) / 2`. To keep `EDPR_AF` symmetric with `EDPR_SS` (per-hit damage volume)

```
pc_autofire_attack_pool  = REF + autofire_skill
npc_autofire_attack_pool = autofire_skill
HPW_AF                   = (derived per §1.2, using autofire_attack_pool vs range_dv + 3)
avg_mult                 = (autofire_cap + 1) / 2          # conditional on a hit; e.g., SMG cap 3 → 2.0
EDPR_AF                  = (avg(2d6) - DEF_effective_SP) * avg_mult   (floor 0 on each factor)
```

---

### Component 3: Crit Threat Score (CTS)

Understanding *what a critical injury actually does* is an inherent requirement when defining a model for calculating damage. In Cyberpunk RED a critical hit occurs whenever two or more dice rolled for damage from a melee or ranged attack come up 6.

When two or more damage dice show 6, the attacker:
1. Deals +5 bonus HP damage that bypasses armor entirely.
2. Rolls on the Critical Injury Table (the result imposes a lasting mechanical penalty).

Both effects happen regardless of whether any damage penetrated SP. The +5 is guaranteed on a crit. The injury effect is variable but always mechanically significant.

---

#### <u>3.1 Crit Probability by Damage Dice Count</u>

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
---

#### <u>3.2 Bonus HP Damage from Crits (+5)</u>

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

---

#### <u>3.3 Injury Severity</u>

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

##### _Body Critical Injury Table_

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

##### _Death Save Penalty (DSP) Contributions_

Outcomes 2, 3, 4, and 12 add +1 to death saves. These are relevant if a PC reaches 0 HP.

*Expected DSP per crit:*
```
P(DSP outcomes) = P(2) + P(3) + P(4) + P(12)
                = 1/36 + 2/36 + 3/36 + 1/36
                = 7/36
                ≈ 0.194
```

##### _Action Penalty Contributions_

Almost every outcome imposes a −2 or −4 to some category of action.

*Expected stat-penalty magnitude per crit (weighted by 2d6 probability):*

| Outcome              | Penalty            | Prob (2d6) | Weighted                   |
|----------------------|--------------------|------------|----------------------------|
| 2 (Dismembered Arm)  | severe (lose limb) | 1/36       | —                          |
| 3 (Dismembered Arm)  | severe             | 2/36       | —                          |
| 4 (Collapsed Lung)   | −2 MOVE            | 3/36       | 3 × 2 = 6                  |
| 5 (Broken Ribs)      | −2 all actions     | 4/36       | 4 × 2 = 8                  |
| 6 (Broken Arm)       | −2 arm actions     | 5/36       | 5 × 1 = 5 (partial, ~half) |
| 7 (Foreign Object)   | 2 HP/turn ongoing  | 6/36       | — (HP, not stat)           |
| 8 (Torn Muscle)      | −2 limb actions    | 5/36       | 5 × 1 = 5 (partial)        |
| 9 (Spinal Injury)    | −4 MOVE            | 4/36       | 4 × 4 = 16                 |
| 10 (Crushed Fingers) | −4 Ranged/DEX/REF  | 3/36       | 3 × 4 = 12                 |
| 11 (Damaged Eye)     | −2 Ranged/Percep   | 2/36       | 2 × 2 = 4                  |
| 12 (Head Shot)       | −2 all actions     | 1/36       | 1 × 2 = 2                  |

```
Sum of clearly-weighted values = 6 + 8 + 5 + 16 + 12 + 4 + 2 = 53
Partial-credit for outcomes 6 and 8 already included above as 5 + 5 = 10
Total weighted penalty sum     = 53
Total probability weight used  = 3 + 4 + 5 + 4 + 3 + 2 + 1 + 5 = 27 (of 36 outcomes)
```

Rough expected action penalty per crit ≈ 53/36 ≈ 1.47 penalty points on affected rolls, sustained for the remainder of a fight.

---

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

---

### Autofire's Crit Interaction

Autofire always rolls 2d6 for damage regardless of the base weapon's damage dice. This means a Heavy SMG on autofire has lower crit probability (0.0278) than the same weapon firing single-shot (0.3302). This is an intentional design tradeoff in CP:RED. Autofire trades crit threat for multiplied raw damage.

The formula handles this naturally:
- When computing `EDPR_AF`, an average 2d6 is used and P(crit) = 0.0278 for `CTS_AF`.
- Single-shot uses the weapon's full die count.

---

## Final OTS Formulas

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
- `EDPR` is averaged across fire modes per the formula above; selecting the higher of the two instead is a candidate calibration option (see [Open Calibration Parameters](#open-calibration-parameters))
- `CTS` = P(crit) × 10.7 (using the matching die count for the fire mode)
- `HPW` = P_hit per [§1.2](#u12-conditional-dodge-attemptsu), computed per fire mode (with `autofire_attack_pool` and the +3 DV penalty for `HPW_AF`)

---

## Defensive Durability Score (DDS)

DDS answers the question: how much total damage must an aggressor deal to eliminate this defender, accounting for armor absorption across its full lifespan and the death save buffer?

---

### Component 1: Hit Point Pool (HPP)

A character's raw HP, per the core rulebook's formula:
```
HPP = ((WILL + BODY) / 2) × 5 + 10
```

HPP is the primary damage reservoir. It represents the amount of net (post-SP) damage required to bring a character to 0 HP.

---

### Component 2: Armor Absorption Capacity (AAC)

Stopping Power (SP) is not a one-time pool. The previous calculation produced a value that was the theoretical maximum if armor were fully ablated to zero. This calculation
blended difficulty tiers together and made it harder to delineate between difficulty tiers.

Per the Cyberpunk: RED rules SP reduces damage on every penetrating hit and ablates by 1 each time damage gets through (incoming damage > current SP). The revised AAC calculation models the total damage SP actually absorbs across the combat that ends with the NPC's death.

#### Reference attacker

AAC is computed against a fixed **reference attacker** that deals `REF_DAMAGE` per hit. The reference damage is set to `SP_CAPPED + 1 = 19`: the minimum damage that penetrates the strongest armor in CP:RED (Metalgear, SP 18). This ensures the formula is universally defined for all valid SP values and represents a realistic high-end attacker (between a sniper rifle averaging 17.5 and a heavy SMG averaging 21 per hit).

#### Algorithm

```
SP_CAPPED = min(sp, 18)

cumulative_hp_damage ← 0
absorbed             ← 0

for k = 0, 1, 2, … , SP_CAPPED:
    current_sp        = SP_CAPPED − k
    net_hp            = REF_DAMAGE − current_sp
    cumulative_hp    += net_hp
    absorbed         += current_sp
    if cumulative_hp ≥ HPP:
        break          # NPC is dead; stop counting ablation

AAC = absorbed
```

Each iteration represents one penetrating hit from the reference attacker. The loop stops as soon as the NPC's HP pool is exhausted, counting only the ablation steps that actually occur before death.

*Key property:* Because the loop terminates based on HPP, two NPCs with the same SP but different BODY/WILL produce different AAC values. A higher-HP NPC survives more hits and therefore extracts more absorption from their armor (which is mechanically correct).

#### Worked examples (REF_DAMAGE = 19)

**Mook (SP = 7, HPP = 30):**

| Hit | Current SP | Net HP dmg | Cumul. HP | Armor absorbed |
|-----|------------|------------|-----------|----------------|
| 1   | 7          | 12         | 12        | 7              |
| 2   | 6          | 13         | 25        | 6              |
| 3   | 5          | 14         | 39 ≥ 30   | 5              |

AAC = 7 + 6 + 5 = **18**
Per the previous AAC calculation AAC = 7 + 6 + 5 + 4 + 3 + 2 + 1 = **28**

**Boss (SP = 18, HPP = 55):**

| Hit | Current SP | Net HP dmg | Cumul. HP | Armor absorbed |
|-----|------------|------------|-----------|----------------|
| 1   | 18         | 1          | 1         | 18             |
| 2   | 17         | 2          | 3         | 17             |
| 3   | 16         | 3          | 6         | 16             |
| 4   | 15         | 4          | 10        | 15             |
| 5   | 14         | 5          | 15        | 14             |
| 6   | 13         | 6          | 21        | 13             |
| 7   | 12         | 7          | 28        | 12             |
| 8   | 11         | 8          | 36        | 11             |
| 9   | 10         | 9          | 45        | 10             |
| 10  | 9          | 10         | 55 ≥ 55   | 9              |

AAC = 18 + 17 + … + 9 = **135**

*Validity condition:*
AAC is defined only when the attacker's EDPR > 0. If a weapon cannot penetrate SP at all, the defender is functionally immune to that aggressor. DDS is infinite relative to them and the comparison is meaningless.

---

### Component 3: Death Save Resilience (DSR)

When a defender reaches 0 HP they enter the Mortally Wounded state but are not immediately eliminated. At the start of each of their turns they must make a Death Save: roll a d10 and survive if the result is strictly less than BODY.

A roll of 10 always fails regardless of BODY.

Each consecutive save increases the cumulative penalty by +1, making each subsequent save harder. The defender dies on any single failed save.

#### <u>Deriving E[rounds survived at 0 HP]</u>

Let `p(BODY, k)` = probability of surviving round k of the death spiral:
```
P(BODY, k) = max(0, min(9, BODY − k)) / 10
```

Breakdown of the terms:
- `BODY − k`: the effective threshold after k rounds (penalty = k−1 by round k, so need roll < BODY − (k−1), i.e., ≤ BODY − k)
- `min(9, ...)`: caps the success range at 9 because 10 always auto-fails
- `max(0, ...)`: floor at 0 because the save cannot be made once the threshold is exhausted

##### <u>Expected rounds survived at 0 HP</u>

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

---

### Final DDS Formula

$
DDS = HPP + AAC + DSR_hp
    = ((WILL + BODY) / 2) × 5 + 10
    + realized_absorption(min(SP, 18), HPP, REF_DAMAGE)
    + E_DSR(BODY) × DSR_weight
$

**Sample values across NPC tiers** (representative stats, `DSR_weight = 5`, `REF_DAMAGE = 19`):

| NPC Tier      | BODY | WILL | SP  | HPP  | AAC (realized) | DSR_hp | DDS   |
|---------------|------|------|-----|------|----------------|--------|-------|
| Mook          | 4    | 4    | 7   | 30.0 | 18             | 1.8    | 49.8  |
| Hardened Mook | 5    | 5    | 11  | 35.0 | 38             | 2.7    | 75.7  |
| Lieutenant    | 6    | 6    | 11  | 40.0 | 45             | 3.9    | 88.9  |
| Mini-Boss     | 8    | 7    | 11  | 47.5 | 51             | 7.2    | 105.7 |
| Boss          | 10   | 8    | 18  | 55.0 | 135            | 13.3   | 203.3 |
| Elite Boss    | 12   | 10   | 18  | 65.0 | 143            | 19.3   | 227.3 |

Note: Lieutenant and Mini-Boss now produce different AAC (45 vs 51) despite sharing SP 11,
because Mini-Boss has a higher HPP (47.5 vs 40.0) and survives one additional ablation step.

---

## Complexity Multiplier (CM)

CM adjusts the final score upward when the NPC has capabilities beyond basic combat. It starts at 1.0 and caps at 2.0:

```
CM = clamp(1.0 + Σ(cyberware_tier_bonuses) + Σ(special_gear_bonuses) + netrun_bonus, 1.0, 2.0)

  + 0.15 per cyberware tier above Basic  (Basic → Standard → Premium → Military)
  + 0.10 per special-gear item           (grenade launcher, EMP, smartgun link, etc.)
  + 0.20 if NPC can netrun
```

---

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

---

## Open Calibration Parameters

Every tunable constant in the system is collected here for playtesting and adjustment. Each has a current proposed value yet none should be considered final until playtested.

- **`SCALE_FACTOR`**
- **`DSP_weight`** — currently `3`. Governs how much a +1 death save penalty contributes to CTS. A higher value increases the crit-threat contribution of outcomes that push PCs toward death.
- **`fight_rounds_remaining`** — currently `3`. Baseline number of rounds over which a crit's action penalty is assumed to apply. Matches typical CP:RED combat length.
- **Single-shot vs. autofire selection** — when an aggressor has both fire modes available, which is used to compute OTS?
  - Best fire mode: whichever of `EDPR_SS` or `EDPR_AF` is higher.
  - Weighted average: `(EDPR_SS + EDPR_AF) / 2`.
  Both values are explicit and adjustable. Determining which choice produces better calibration requires further testing.
- **`DSR_weight`** — currently `5`. The reference damage rate used to convert expected rounds survived at 0 HP into HP-equivalent units for DDS.
- **`REF_DAMAGE`** — currently `19` (`SP_CAPPED + 1`). The reference attacker damage used in the realized AAC computation. Must always exceed `SP_CAPPED` so the formula is defined for all valid SP values. Raise if future NPC stat blocks introduce armor above SP 18.
- **60/40 offense/defense split in `NTS_raw`** — if burst damage consistently over-rates NPCs, shifting toward 55/45 is the first adjustment to try.

---

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

---

## Appendix B - Mook NTS Score

This appendix walks through a complete NTS calculation for a single Mook-tier NPC against a specific PC. 

**NPC (the threat being scored):** `NPC.NCPD_Cherub` — Officer Ranbir Majumdar, handle "Cherub"<br>
**PC (the defender baseline):** `NPC.Edgerunners_TiaPuao` — Tía Puño, handle "Tia Pu'ao"

### Abridged Character Stat Summary

| Stat                 |          Cherub (NPC)          |            TiaPuao (PC)             |
|----------------------|:------------------------------:|:-----------------------------------:|
| REF                  |               4                |                  6                  |
| DEX                  |               4                |                  5                  |
| BODY                 |               5                |                  8                  |
| WILL                 |               4                |                  7                  |
| SP                   |               11               |                 15                  |
| maxHP                |               35               |                 50                  |
| Evasion (total)      |               10               |                 15                  |
| Handgun (total)      |               12               |                 14                  |
| Death Save Threshold |               5                |                  8                  |
| Primary Weapon       | Heavy Pistol Poor (3d6, ROF 2) | Heavy Pistol Excellent (3d6, ROF 2) |

**Assumed engagement range:** 12 m (7–12 m band). `get_difficulty("HeavyPistol", 12)` → Pistol row, index 1 → **DV 15**.

---

### Step 1 — Offensive Threat Score (OTS)

#### 1.1 Attack Pool

Cherub is the aggressor (NPC). The weapon is a Heavy Pistol of Poor quality, so `q = 0`.

```
npc_attack_pool = weapon_skill + q
               = 12 + 0
               = 12
```

#### 1.2 Hit Probability Weight (HPW)

TiaPuao's `REF = 6`, which does **not** satisfy the `REF ≥ 8` threshold for active dodge. The defender uses the static range DV only.

```
need     = range_dv − attack_pool = 15 − 12 = 3
P_static = clamp((11 − need) / 10, 0, 1)
         = clamp((11 − 3) / 10, 0, 1)
         = clamp(0.8, 0, 1)
         = 0.8

P_hit    = P_static = 0.8
HPW      = clamp(P_hit, 0.2, 1.0) = 0.8
```

#### 1.3 Expected Damage Per Round (EDPR)

The Heavy Pistol has ROF 2 with no autofire mode. Both shots are single-shot.

```
avg_weapon_damage = avg(3d6) = 3 × 3.5 = 10.5
DEF_effective_SP  = 15  (TiaPuao's armor)

SS_damage_per_hit = max(0, 10.5 − 15) = 0
EDPR_SS           = 0 × 2 = 0
```

Cherub's Heavy Pistol (Poor) averages 10.5 damage, which does not penetrate TiaPuao's SP 15 armor. Raw damage contribution is zero. The offensive threat reduces entirely to critical hit output.

#### 1.4 Crit Threat Score (CTS)

The Heavy Pistol rolls 3d6 for damage.

```
P(zero 6s)       = (5/6)³ = 125/216 ≈ 0.5787
P(exactly one 6) = 3 × (1/6) × (5/6)² = 75/216 ≈ 0.3472
P(crit)          = 1 − 0.5787 − 0.3472 = 0.0741

CTS_SS = P(crit) × 10.7
       = 0.0741 × 10.7
       = 0.79
```

#### 1.5 Final OTS

No autofire mode, so the single-shot formula applies.

```
OTS = HPW_SS × (EDPR_SS + CTS_SS)
    = 0.8 × (0 + 0.79)
    = 0.8 × 0.79
    = 0.632
```

---

### Step 2 — Defensive Durability Score (DDS)

DDS measures Cherub's own durability — how much total damage is required to eliminate him.

#### 2.1 Hit Point Pool (HPP)

```
HPP = ceil((BODY + WILL) / 2) × 5 + 10
    = ceil((5 + 4) / 2) × 5 + 10
    = ceil(4.5) × 5 + 10
    = 5 × 5 + 10
    = 35
```

_The ceiling is applied because (BODY + WILL) is odd. This matches the character sheet value of `maxHP: 35`._

#### 2.2 Armor Absorption Capacity (AAC)

```
SP_CAPPED = min(SP, 18) = min(11, 18) = 11
REF_DAMAGE = 19
```

Iterate hit-by-hit until cumulative HP damage ≥ HPP (35):

| Hit | Current SP | Net HP dmg | Cumul. HP | Armor absorbed |
|-----|------------|------------|-----------|----------------|
| 1   | 11         | 8          | 8         | 11             |
| 2   | 10         | 9          | 17        | 10             |
| 3   | 9          | 10         | 27        | 9              |
| 4   | 8          | 11         | 38 ≥ 35   | 8              |

```
AAC = 11 + 10 + 9 + 8 = 38
```

Cherub dies on hit 4. Realized absorption is 38 — the remaining SP 7 (hits 5–11) is never reached.

#### 2.3 Death Save Resilience (DSR)

Cherub's death save threshold equals his `BODY = 5`.

From the E_DSR table:

| BODY | p(round 1) | E_DSR |
|------|:----------:|:-----:|
| 5    |    0.40    | 0.55  |

```
DSR_hp = E_DSR(5) × DSR_weight
       = 0.55 × 5.0
       = 2.75
```

#### 2.4 Final DDS

```
DDS = HPP + AAC + DSR_hp
    = 35 + 38 + 2.75
    = 75.75
```

---

### Step 3 — Final NTS Calculation

```
NTS_raw = (OTS × 0.6) + (DDS × 0.4)
        = (0.632 × 0.6) + (75.75 × 0.4)
        = 0.3792 + 30.30
        = 30.68

NTS = clamp(round(NTS_raw / SCALE_FACTOR), 1, 20)
```

`SCALE_FACTOR` is a pending calibration constant (see [Open Calibration Parameters](#open-calibration-parameters)). The final integer NTS cannot be resolved until it is back-solved from the Mook, Lieutenant, and Mini-Boss anchor stat blocks.

---

## Appendix C - Probability Mass Function for the Sum of Nd6
The mean damage potential for weapons has been used to calculate damage as part of the total NTS calculation. After reviewing the data from calculating the NTS for extracted character stat blocks it has been determined that this method requires a more rigorous approach.

### Why Mean Damage Fails as a Proxy Number
The mean damage doesn't provide the probability that the amount of damage done by the weapon exceeds the character's SP rating. The Armor Absorption Capacity (AAC) within the DDS calculation relies on armor ablation that only occurs when the amount of damage done to a character exceeds the SP rating. Two weapons with the same mean can have very different probabilities of beating a given armor value because dice pools have different spreads.

For example, compare 1d6 vs. a hypothetical weapon that always deals exactly 3.5 damage:
- The mean damage for both weapons is 3.5
- Against SP 4, the hypothetical weapon (flat 3.5 damage) never beats this SP rating
- Against SP 4, the 1d6 weapon beats the SP rating 33% of the time
- Against SP 2, the hypothetical weapon (flat 3.5 damage) always beats this SP rating
- Against SP 2, the 1d6 weapons only beats this SP rating 67% of the time

As the dice pools grow the distribution gets tighter relative to its mean (central limit theorem). The mean is a good proxy number but the calculation requires more accuracy than a proxy provides.

### Calculating Ablation when Damage Exceeds SP

As previously stated, armor ablation only occurs when the amount of damage received exceeds the SP rating (crit hits do not count toward ablation).

The range of armor values in Cyberpunk RED are as follows: 4 to 18.

The range of damage dice pools in Cyberpunk RED are as follows: 1d6 to 8d6.

The result of this calculation will be a lookup table that contains the probability of each pool exceeding each SP rating

---

#### <u>Probability Mass Function (PMF) General Form (for any NdF)</u>

This is the closed form derived from the inclusion-exclusion expansion of the convolution (uniform$_{1..f}$)$^*n$.

The expression below applies for $n$ dice with $f$ faces each summing to $s$:

$P(S=s)=\frac{1}{f^n} \sum_{k=0}^{\lfloor(s-n)/f\rfloor} (-1)^k \binom{n}{k} \binom{s-fk-1}{n-1}$

This closed form is applied to an example in the next section.

---

#### <u>The Probability Mass Function (PMF) for the sum of 4d6</u>

The 4d6 die pool is being used for this example because it has a chance to exceed SP across all armor values. It makes a good example to explain the calculation and logic.

Let S = $X_{1}+X_{2}+X_{3}+X_{4}$ where each $X_{i}$ is independent and identically distributed uniformly on {1,2,3,4,5,6}.

The PMF for the sum $s∈{4,5,…,24}$ is:

$P(S=s)=\frac{1}{6^4} \sum_{k=0}^{\lfloor(s-4)/6\rfloor} (-1)^k \binom{4}{k}\binom{s-6k-1}{3}$

Where:
- $s$   → the target sum(integer, 4 ≤ s ≤ 24)
- $n=4$ → number of dice (appears as $\binom{4}{k}$ and the exponent in $6^4$)
- $f=6$ → number of faces per die (appears in $6^4$ and in the $6k$ term)
- $k$   → summation index ranging from 0 to $\lfloor(s-4)/6\rfloor$
- $\binom{n}{k}$ → binomial coefficient (inclusion-exclusion weight)
- $\binom{s-6k-1}{3}$ → counts compositions of $s-6k$ into 4 positive parts, the lower index is $n-1=3$
 
By convention, $\binom{m}{3}=0$ when $m<3$, which automatically zeroes out invalid terms.

---

##### <u>Sanity Check</u>

To contextualize the sanity check I've described the 4d6 distribution below.

There are $6^4=1296$ equally likely outcomes. The probability of any particular sum $s$ is:

$P(S=s)= \frac{number\ of\ outcomes\ summing\ to\ s}{1296}$

The range of possible sums:

- Minimum: 1 + 1 + 1 + 1 = 4
- Maximum: 6 + 6 + 6 + 6 = 24

So $s$ ranges over the 21 integers from 4 to 24.

For $s=4$ there's only one way to achieve that result: (1,1,1,1)

For $s=14$ every ordered tuple needs to be counted $\left( x_{1},\ x_{2},\ x_{3},\ x_{4} \right)$ with $1\ \leq\ x_{i}\ \leq\ 6$ that sums to 14. Instead, the inclusion-exclusion formula is used.

<u>**Verifying the PMF**</u>

The PMF is checked by plugging in $s=14$ (peak of the distribution). The result of the term below should match the final probability result shown above.

$P(S=14)=\frac{1}{1296} \left[ \binom{4}{0} \binom{13}{3} - \binom{4}{1} \binom{7}{3} + \binom{4}{2} \binom{1}{3} \right]$<br>
$\qquad\qquad\ \ = \frac{1}{1296} \left[ 286-4(35)+6(0) \right]$<br>
$\qquad\qquad\ \ = \frac{146}{1296}$<br>
$\qquad\qquad\ \ \approx 11.27\%$

Which matches the known peak of the 4d6 distribution. To understand how the integer 14 was obtained see [Appendix D](#appendix-d---pmf-breakdown).

---

#### **<u>The Probability of Exceeding Armor Value</u> $a$**

Below is the application of the PMF term from above. It calculates the probability a die pool of 4d6 exceeds an SP rating of 10.

$P(S>a)= \sum_{s=a+1}^{4f}\ P(S=s)= \sum_{s=a+1}^{24}\ P(S=s)$

For $P(damage\ >\ SP\ 10)$ with 4d6 the following is computed:

$P(S\ >\ 10)= \sum_{s=11}^{24}\ P(S=s)=1-P(S\leq10)$

Computing each $P(S=s)$ for $s=4$ through 10 via the same formula and summing:

$P(S\leq10)= \frac{1+4+10+20+35+56+80}{1296}=\frac{206}{1296}\approx 15.9\%$

So $P(S > 10)=1-0.159\approx 84.1\%$

---

## Appendix D - PMF Breakdown
<u>**Decoding the Formula**</u>

$P(S=s)=\ \frac{1}{6^4} \sum_{k=0}^{\lfloor \left( s-4 \right)/6 \rfloor} \left( -1 \right)^k \binom{4}{k} \binom{s-6k-1}{3}$

The $\binom{s-1}{3}$ term (when $k=0$): This counts the number of ways to write $s$ as an ordered sum of 4 _positive integers_, which overcounts because it allows values like 7,8,9, etc. on a single die.

The $\binom{4}{k}\binom{s-6k-1}{3}$ correction terms: Inclusion-exclusion subtracts off the overcounted cases where one die exceeds 6, then adds back where two die exceed 6, etc. The $6k$ comes from "if k dice each exceeded 6, that's at least 6k extra summed values to remove."

The summation upper bound $\lfloor (s-4)/6 \rfloor$: Stops when no more dice could possibly exceed 6 simultaneously while still summing to $s$.

**Computing $P(S=14)$ term by term**

Term $k=0$:

$(-1)^0\binom{4}{0} \binom{14-0-1}{3}=1*1*\binom{13}{3}$

$\binom{13}{3}=\frac{13*12*11}{3*2*1}=\frac{1716}{6}=286$

Term $k=1$:

$(-1)^1 \binom{4}{1}\binom{14-6-1}{3}=-1*4*\binom{7}{3}$

$\binom{7}{3}=\frac{7*6*5}{3*2*1}=\frac{210}{6}=35$

So this term evaluates as $-4*35=-140$

Term $k=2$:

$(-1)^2 \binom{4}{2} \binom{14-12-1}{3}=1*6*\binom{1}{3}$

$\binom{1}{3}=\frac{1*0}{3*2*1}=\frac{0}{6}=0$

So this term evaluates as $6*0=0$

The total sum evaluates as $286-140+0=146$

**Final Probability**:

$P(S=14)= \frac{146}{1296} \approx 0.1127 = 11.27\%$

---

## Appendix E - P(damage > armor) Lookup Table

The term for calculating the probability of a die pool exceeding an armor rating as defined in [Appendix C](#uthe-probability-of-exceeding-armor-valueu-a) is as follows:

$P(S>a)= \sum_{s=a+1}^{4f}\ P(S=s)= \sum_{s=a+1}^{24}\ P(S=s)$

Applying this term to the stopping power (SP) ratings for armor available in the Cyberpunk: RED game the following lookup table is defined:

| Weapon | SP 4  | SP 7  | SP 10 | SP 11 | SP 12 | SP 15 | SP 18 |
|:-------|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|
| 1d6    | 33.3% |  0%   |  0%   |  0%   |  0%   |  0%   |  0%   |
| 2d6    | 83.3% | 41.7% | 8.3%  | 2.8%  |  0%   |  0%   |  0%   |
| 3d6    | 98.1% | 83.8% | 50.0% | 37.5% | 25.9% | 4.6%  |  0%   |
| 4d6    | 99.9% | 97.5% | 83.4% | 74.5% | 63.4% | 24.0% | 4.4%  |
| 5d6    | 100%  | 99.7% | 96.2% | 92.5% | 87.0% | 53.7% | 21.5% |
| 6d6    | 100%  | 100%  | 99.3% | 98.3% | 96.5% | 78.5% | 47.7% |
| 7d6    | 100%  | 100%  | 99.9% | 99.7% | 99.2% | 91.7% | 72.2% |
| 8d6    | 100%  | 100%  | 100%  | 99.9% | 99.8% | 97.3% | 87.2% |

---

## Resources

- [DND Mathematics Profile](https://github.com/tomedunn/the-finished-book/blob/master/assets/python/dice_roller/nodes.py)
