# TTRPG Inheritance System
#### Adapted from CD Projekt Red's TweakDB prototype/inheritance pattern
#### Game system: Cyberpunk RED Core Rulebook (R. Talsorian Games, 2020)

---

## File structure

```
ttrpg_system/
│
├── schema/
│   ├── types.yml        ← $type contracts for all record kinds
│   ├── enums.yml        ← valid values for all enum fields
│   └── stats.yml         ← named stat identifiers (used in StatModifier.stat)
│
├── prototypes/
│   ├── characters/
│   │   └── _base.yml    ← Base_Character + all ten Role Archetypes (Solo, Netrunner, etc.)
│   ├── npcs/
│   │   └── _base.yml    ← Base_NPC + Grunt, GangGrunt, CorpSec, Elite, Sniper,
│   │                        NetrunnerNPC, Boss, NamedNPC
│   ├── networks/
│   │   └── _base.yml    ← NetworkNode prototypes (cameras, turrets, ICE, etc.)
│   │                        [previously mislocated at npcs/_base.yml]
│   ├── abilities/
│   │   └── quickhacks.yml  ← Netrunner quickhack abilities (Momentum system)
│   ├── weapons/          ← [stub — add _base.yml for weapon archetypes]
│   └── cyberware/        ← [stub — add _base.yml for cyberware archetypes]
│
└── records/
    └── examples.yml     ← leaf records: 2 PCs (Solo, Netrunner) + 5 NPCs
```

---

## Key concepts

### $type
Declares what schema this record conforms to. Determines the legal field set.
Must match a key in `schema/types.yml`.

### $base
Prototype reference. The resolver walks this chain, merging fields from
root → archetype → leaf. Later values override earlier ones.

### !append / !remove
Array merge operations.
- `!append` — add to the inherited array without replacing it
- `!remove` — strip a specific value from an inherited array
- Bare override (no tag) — replaces the entire inherited array

### StatModifier (inline)
``.yml
statModifiers:
- !append
  $type: StatModifier
  stat: StoppingPower    # key from schema/stats.yml
  modifierType: Additive # Additive | Multiplier | Override
  value: 10
```

### Resolution order (your resolver must implement this)
1. Walk `$base` chain from root to leaf, collecting all records
2. Scalar fields: leaf value wins
3. Array fields: apply `!append` / `!remove` operations in order
4. Validate all fields against `schema/types.yml`
5. Validate enum fields against `schema/enums.yml`
6. Compute derived stats (HP, Humanity, Run, CarryWeight, LuckPool)
7. Strip any leaf field that equals the resolved base value (normalisation)

---

## Character creation flow (PC)

Character creation in Cyberpunk RED follows these steps, mapped to record fields:

| Step | Rulebook (p.) | Record field(s) |
|------|--------------|-----------------|
| 1. Choose Role | 96–213 | `roleAbility.role` → selects `$base` Archetype |
| 2. Set attributes | 62–66 | `attributes.*` (62 points; min 2, max 8) |
| 3. Derive secondary stats | 64–65 | `derivedStats.*` (computed by resolver) |
| 4. Assign Career Skills | 220 | `skills` !append (86 pts; max rank 6 per career skill) |
| 5. Assign Pickup Skills | 220 | `skills` !append (40 pts; max rank 4 per pickup skill) |
| 6. Choose cyberware | 228–263 | `cyberware` !append (each costs Humanity) |
| 7. Generate Lifepath | 72–95 | `lifepath` array of LifepathEntry |
| 8. Select gear & equipment | 340–380 | `primaryEquipment`, `secondaryEquipment`, `gear` |

**Attribute budget:** 62 points across ten stats. No stat below 2 or above 8
at character creation.

**Skill total** = skill rank + governing attribute (both on the same 1–10 scale).

**Humanity:** Starting Humanity = EMP × 10. Each installed cyberware subtracts
its `humanityCost`. Effective EMP after install = `HumanityCurrent / 10`
(round down). Falling to 0 triggers cyberpsychosis.

---

## NPC creation flow

NPCs in RED are intentionally lighter than PCs. The GM assigns stats to match
the NPC's narrative role — no point-buy budget applies.

| NPC tier | Prototype | Typical use |
|----------|-----------|-------------|
| Mook / Normal | `NPCs.Base_GangGrunt`, `NPCs.Base_CorpSec` | Disposable combatants; drop in one hit |
| Tough / Elite | `NPCs.Base_Elite`, `NPCs.Base_Sniper`, `NPCs.Base_NetrunnerNPC` | Specialists; 2–3 rounds to drop |
| Boss | `NPCs.Base_Boss` | Encounter anchor; survives the full party |
| Named | `NPCs.Base_NamedNPC` | Recurring story NPC; social or quest-critical |

For vendor, quest giver, or fixer NPCs, use `NPCs.Base_NamedNPC` and set
`npcType` accordingly. The `NPCType` enum drives the web app's creation-flow
routing, not the inheritance chain.

---

## Hacking system — Momentum

Hacking uses a single encounter resource called **Momentum** (1–5 dial) instead
of RAM pools or upload timers. The goal is zero subtraction math at the table.

```
Momentum 1–2  →  Shallow access  →  depth 1 nodes (cameras, doors, lights)
Momentum 3–4  →  Mid access      →  depth 2 nodes (turrets, terminals, cyberware)
Momentum 5    →  Deep access     →  depth 3 nodes (Kraken ICE, high-value targets)
```

**Builds** on successful hack rolls (+1 per success).  
**Drops** when the Netrunner takes damage, fails a roll, or ICE retaliates.  
**Resets** to 0 on disconnect or at encounter end.

Each quickhack in `prototypes/abilities/quickhacks.yml` has:
- `minMomentum` — floor required to attempt
- `momentumCost` — 0 (free) or 1 (powerful; drops Momentum by 1 on use)
- `accessDepth` — minimum node depth required to target

ICE nodes use `hitThreshold` (1–3) rather than an HP pool. Each successful hack
roll marks one hit; no subtraction. When hits equal threshold, the ICE is
flatlined.
