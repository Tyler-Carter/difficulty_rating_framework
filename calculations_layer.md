# Calculations Layer — Implementation Plan

## Overview

The calculations layer contains all game-balance mathematics: hit probability weights, expected damage per round, crit threat scores, death save resilience, and the OTS/DDS composite scores. It also owns the stat extraction bridge (which reads typed `ResolvedRecord` objects and returns scalar values) and the orchestration functions that tie data retrieval to scoring.

**Hard constraints:**
- The calculations layer contains **zero file I/O** — no YAML, JSON, or PDF reading.
- Repositories are always received as constructor or function parameters (dependency injection), never instantiated inside calculation or math modules.
- The data layer's internal modules (`data.registry.*`, `data.pdf_pipeline.*`, concrete repository classes) are never imported here.

**Architectural pattern:** Pure functions for all math; thin orchestrators that accept abstract repository interfaces via dependency injection; FastAPI endpoints as the outermost wiring layer.

---

## Directory Structure

```
cpred_dr_framework/
├── calculations/
│   ├── __init__.py
│   ├── stat_extraction.py
│   ├── ots/
│   │   ├── __init__.py
│   │   ├── math.py
│   │   └── orchestrator.py
│   └── dds/
│       ├── __init__.py
│       ├── math.py
│       └── orchestrator.py
└── api/
    ├── __init__.py
    ├── main.py
    └── models.py
```

---

## Module-by-Module Breakdown

### `calculations/stat_extraction.py`

**Purpose:** Bridge module. Accepts typed `ResolvedRecord` objects from the data layer and returns scalar values that math functions consume. Contains **no formulas** and **no I/O**.

**Why this belongs in the calculations layer:** These functions contain accessor/derivation logic (e.g. "NPC attack pool is stored rank; PC attack pool is rank + REF") that is part of the game's calculation rules, not a data storage concern. They are deterministic pure transformations over typed data.

**Migrated from `main.py` and `dds_calc.py`:**

| Function | Source | Signature change |
|---|---|---|
| `is_npc` | `main.py:186–188` | `record: dict` → `record: ResolvedRecord` |
| `get_skill_rank` | `main.py:191–197` | `record: dict` → `record: ResolvedRecord` |
| `get_attack_pool` | `main.py:200–212` | `record: dict` → `record: ResolvedRecord` |
| `get_defense_total` | `main.py:215–230` | `record: dict` → `record: ResolvedRecord` |
| `get_effective_sp` | `main.py:233–251` | `record: dict` → `record: ResolvedRecord` |
| `get_body` | `dds_calc.py:15–17` | `record: dict` → `record: ResolvedRecord` |
| `get_will` | `dds_calc.py:21–23` | `record: dict` → `record: ResolvedRecord` |

**Full implementation:**

```python
from __future__ import annotations
from data.models import ResolvedRecord


def is_npc(record: ResolvedRecord) -> bool:
    """True when the record is an NPC (npc_type field is set)."""
    return record.npc_type is not None


def get_skill_rank(record: ResolvedRecord, skill_name: str) -> int:
    """Return the stored rank for *skill_name*, defaulting to 0."""
    for entry in record.skills:
        if entry.skill == skill_name:
            return entry.rank
    return 0


def get_attack_pool(record: ResolvedRecord, skill_name: str) -> int:
    """Effective attack pool for a given skill.

    NPC records store the final total (attribute + skill rank) in the rank field,
    so the stored rank IS the attack pool.

    PC records store only the skill rank, so REF must be added.
    """
    rank = get_skill_rank(record, skill_name)
    if is_npc(record):
        return rank
    return (record.attributes.reflexes or 0) + rank


def get_defense_total(record: ResolvedRecord) -> float:
    """Return DEF_DEX + DEF_evasion_skill for use in HPW calculation.

    Returns 0.0 when the defender's REF < 8 (cannot dodge; static DV used instead).

    NPC records store Evasion as a final total (DEX + rank) → return stored rank.
    PC records store Evasion as rank only → return DEX + stored rank.
    """
    ref = record.attributes.reflexes or 0
    if ref < 8:
        return 0.0
    evasion_rank = get_skill_rank(record, "Evasion")
    if is_npc(record):
        return float(evasion_rank)
    dex = record.attributes.dexterity or 0
    return float(dex + evasion_rank)


def get_effective_sp(record: ResolvedRecord) -> int:
    """Return the defender's Stopping Power.

    Checks (in order):
    1. Top-level armor field (int) — common in NPC records.
    2. derived_stats.armor (int) — common in PC records.
    """
    if record.armor is not None:
        return record.armor
    if record.derived_stats.armor is not None:
        return record.derived_stats.armor
    return 0


def get_body(record: ResolvedRecord) -> int:
    """Return the BODY attribute, defaulting to 0."""
    return record.attributes.body or 0


def get_will(record: ResolvedRecord) -> int:
    """Return the WILLPOWER attribute, defaulting to 0."""
    return record.attributes.willpower or 0
```

**Key changes from original dict-based code:**
- `record.get("npcType")` → `record.npc_type`
- `(record.get("attributes") or {}).get("reflexes", 0)` → `record.attributes.reflexes or 0`
- `record.get("skills") or []` loop → iterate `record.skills` (list of `SkillEntry`)
- `entry.get("skill") == skill_name` → `entry.skill == skill_name`
- `get_effective_sp`: the two-location armor check is now reflected in the `ResolvedRecord` model fields directly (normalised by `YamlRecordRepository`)

---

### `calculations/ots/math.py`

**Purpose:** Pure OTS math functions. Zero imports from any data source. No file I/O. All inputs are scalars or typed models.

**Migrated from `main.py`:**

| Function | Source lines | Changes |
|---|---|---|
| `clamp` | 258–259 | None |
| `crit_prob` | 262–269 | None |
| `compute_hpw` | 272–293 | `AUTOFIRE_ATK_PENALTY` imported from `data.config` |
| `compute_edpr_ss` | 296–301 | None |
| `compute_edpr_af` | 304–311 | None |
| `compute_cts` | 314–319 | `CTS_MULTIPLIER` imported from `data.config` |
| `compute_ots` | 322–370 | `weapon_stats: dict` → `weapon_stats: WeaponStats`; dict access → attribute access |

**Full implementation:**

```python
from __future__ import annotations
from data.config import CTS_MULTIPLIER, AUTOFIRE_ATK_PENALTY
from data.models import WeaponStats


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
    weapon_stats: WeaponStats,       # typed model, not dict
    def_total: float,
    def_sp: int,
    is_excellent: bool,
) -> dict:
    """Compute OTS and return a dict of OTS plus all intermediate values.

    With autofire available:
        OTS = ((HPW_SS + HPW_AF) / 2) * ((EDPR_SS + EDPR_AF + CTS_SS + CTS_AF) / 2)

    Without autofire:
        OTS = HPW_SS * (EDPR_SS + CTS_SS)
    """
    quality_bonus = 1 if is_excellent else 0
    adj_pool = attack_pool + quality_bonus

    hpw_ss  = compute_hpw(adj_pool, def_total)
    edpr_ss = compute_edpr_ss(weapon_stats.avg_damage, def_sp, weapon_stats.rof)
    cts_ss  = compute_cts(weapon_stats.dice_count)

    hpw_af:  float | None = None
    edpr_af: float | None = None
    cts_af:  float | None = None

    if weapon_stats.has_autofire and autofire_pool is not None:
        adj_af_pool = autofire_pool + quality_bonus
        hpw_af  = compute_hpw(adj_af_pool, def_total, autofire=True)
        edpr_af = compute_edpr_af(hpw_af, weapon_stats.autofire_cap, def_sp)
        cts_af  = compute_cts(2)   # autofire always rolls 2d6

        ots = ((hpw_ss + hpw_af) / 2) * ((edpr_ss + edpr_af + cts_ss + cts_af) / 2)
    else:
        ots = hpw_ss * (edpr_ss + cts_ss)

    return {
        "ots":     round(ots, 4),
        "hpw_ss":  round(hpw_ss, 4),
        "edpr_ss": round(edpr_ss, 4),
        "cts_ss":  round(cts_ss, 4),
        "hpw_af":  round(hpw_af, 4)  if hpw_af  is not None else None,
        "edpr_af": round(edpr_af, 4) if edpr_af is not None else None,
        "cts_af":  round(cts_af, 4)  if cts_af  is not None else None,
    }
```

**Key change:** `weapon_stats["avg_damage"]` → `weapon_stats.avg_damage` (and for all other fields). This is the only mechanical diff from the original `compute_ots`.

---

### `calculations/ots/orchestrator.py`

**Purpose:** Load aggressor and defender records via the repository interface, extract stats, and call `compute_ots`. Receives repository instances as parameters (dependency injection) — this is the **only** place in the calculations layer that calls a repository method.

**Migrated from `main.py:377–421`** (`calculate_ots_for_records`).

**Signature change:** Two new parameters replace module-level imports:

```python
def calculate_ots_for_records(
    aggressor_id: str,
    defender_id: str,
    record_repo: AbstractRecordRepository,
    weapon_repo: AbstractWeaponRepository,
) -> dict:
```

**Full implementation:**

```python
from __future__ import annotations
from data.repositories.base import AbstractRecordRepository, AbstractWeaponRepository
from calculations.stat_extraction import (
    get_attack_pool, get_defense_total, get_effective_sp, get_skill_rank, is_npc
)
from calculations.ots.ots_math import compute_ots


def calculate_ots_for_records(
        aggressor_id: str,
        defender_id: str,
        record_repo: AbstractRecordRepository,
        weapon_repo: AbstractWeaponRepository,
) -> dict:
    """Load aggressor and defender records, extract stats, and compute OTS."""
    agg = record_repo.get_record(aggressor_id)
    defn = record_repo.get_record(defender_id)

    weapon_id = agg.primary_weapon_id or ""
    weapon_type, is_excellent = weapon_repo.parse_weapon_id(weapon_id)
    w_stats = weapon_repo.get_weapon_stats(weapon_type)  # raises KeyError if unknown

    attack_skill = w_stats.attack_skill
    attack_pool = get_attack_pool(agg, attack_skill)

    autofire_pool: int | None = None
    if w_stats.has_autofire:
        af_rank = get_skill_rank(agg, "Autofire")
        if af_rank > 0:
            autofire_pool = (
                af_rank
                if is_npc(agg)
                else (agg.attributes.reflexes or 0) + af_rank
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
```

---

### `calculations/dds/math.py`

**Purpose:** Pure DDS math functions. Zero imports from any data source.

**Migrated from `dds_calc.py`:**

| Function | Source lines | Changes |
|---|---|---|
| `compute_hpp` | 29–45 | None |
| `compute_aac` | 48–65 | `AAC_SP_CAP` imported from `data.config` (replaces inline `18` literal) |
| `compute_dsr` | 68–103 | `DSR_WEIGHT` imported from `data.config` |
| `compute_dds` | 106–134 | None |

**Full implementation:**

```python
from __future__ import annotations
from data.config import DSR_WEIGHT, AAC_SP_CAP


def compute_hpp(body: int, will: int) -> float:
    """Hit Point Pool: ((WILL + BODY) / 2) * 5 + 10"""
    return ((will + body) / 2) * 5 + 10


def compute_aac(sp: int) -> float:
    """Armor Absorption Capacity (triangular sum model).

    SP_CAPPED = min(sp, AAC_SP_CAP)
    AAC = SP_CAPPED * (SP_CAPPED + 1) / 2
    """
    sp_capped = min(sp, AAC_SP_CAP)
    return sp_capped * (sp_capped + 1) / 2


def compute_dsr(body: int) -> float:
    """Death Save Resilience in HP units.

    E_DSR(BODY) = Σ_{n=1}^{BODY-1}  ∏_{k=1}^{n}  max(0, min(9, BODY-k)) / 10
    DSR_hp = E_DSR * DSR_WEIGHT
    """
    def p(k: int) -> float:
        return max(0.0, min(9.0, body - k)) / 10.0

    e_dsr = 0.0
    for n in range(1, body):
        survival_prob = 1.0
        for k in range(1, n + 1):
            survival_prob *= p(k)
        e_dsr += survival_prob
    return e_dsr * DSR_WEIGHT


def compute_dds(body: int, will: int, sp: int) -> dict:
    """Compute DDS and return all intermediate values.

    DDS = HPP + AAC + DSR_hp
    """
    hpp    = compute_hpp(body, will)
    aac    = compute_aac(sp)
    dsr_hp = compute_dsr(body)
    dds    = hpp + aac + dsr_hp

    return {
        "dds":       round(dds, 4),
        "hpp":       round(hpp, 4),
        "aac":       round(aac, 4),
        "dsr_hp":    round(dsr_hp, 4),
        "sp_raw":    sp,
        "sp_capped": min(sp, AAC_SP_CAP),
    }
```

---

### `calculations/dds/orchestrator.py`

**Purpose:** Load a defender record via the repository interface, extract stats, and call `compute_dds`.

**Migrated from `dds_calc.py:141–171`** (`calculate_dds_for_records`).

**Signature change:** `record_repo` parameter replaces the direct `load_record` import.

```python
from __future__ import annotations
from data.repositories.base import AbstractRecordRepository
from calculations.stat_extraction import get_body, get_will, get_effective_sp
from calculations.dds.math import compute_dds


def calculate_dds_for_records(
    defender_id: str,
    record_repo: AbstractRecordRepository,
) -> dict:
    """Load a defender record, extract stats, and compute DDS."""
    record = record_repo.get_record(defender_id)

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
```

---

### `api/models.py`

**Purpose:** Pydantic request/response models for FastAPI endpoints.

**Migrated from `main.py:428–445`** (`OTSRequest`, `OTSResult`). `DDSRequest` and `DDSResult` are new additions.

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class OTSRequest(BaseModel):
    aggressor_id: str   # e.g. "NPC.6thStreet_Arbiter"
    defender_id: str    # e.g. "NPC.Edgerunners_Tetsuo"


class OTSResult(BaseModel):
    ots:             float
    hpw_ss:          float
    edpr_ss:         float
    cts_ss:          float
    hpw_af:          Optional[float] = None
    edpr_af:         Optional[float] = None
    cts_af:          Optional[float] = None
    attack_pool:     int
    def_sp:          int
    aggressor_weapon: str
    aggressor_id:    str
    defender_id:     str


class DDSRequest(BaseModel):
    defender_id: str    # e.g. "NPC.Base_Boss"


class DDSResult(BaseModel):
    dds:        float
    hpp:        float
    aac:        float
    dsr_hp:     float
    sp_raw:     int
    sp_capped:  int
    body:       int
    will:       int
    defender_id: str
```

---

### `api/main.py`

**Purpose:** FastAPI application. Constructs concrete repository instances once at startup and injects them into orchestrator calls. Contains **no business logic**.

**Migrated from `main.py:448–469`** (endpoints and app instance).

```python
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from data.repositories.yaml_repository import YamlRecordRepository
from data.repositories.weapon_repository import YamlWeaponRepository
from api.models import OTSRequest, OTSResult, DDSRequest, DDSResult
from calculations.ots.orchestrator import calculate_ots_for_records
from calculations.dds.orchestrator import calculate_dds_for_records

app = FastAPI(title="CPRED Threat Assessment API")

# Concrete implementations constructed once at startup
_record_repo = YamlRecordRepository()
_weapon_repo = YamlWeaponRepository()


@app.get("/")
async def root() -> dict:
    return {"message": "CPRED Threat Assessment API"}


@app.get("/hello/{name}")
async def say_hello(name: str) -> dict:
    return {"message": f"Hello {name}"}


@app.post("/ots", response_model=OTSResult)
async def calculate_ots(request: OTSRequest) -> OTSResult:
    """Calculate the Offensive Threat Score (OTS) for an aggressor vs. a defender."""
    try:
        result = calculate_ots_for_records(
            request.aggressor_id, request.defender_id,
            _record_repo, _weapon_repo,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OTSResult(**result)


@app.post("/dds", response_model=DDSResult)
async def calculate_dds(request: DDSRequest) -> DDSResult:
    """Calculate the Defensive Durability Score (DDS) for a defender."""
    try:
        result = calculate_dds_for_records(request.defender_id, _record_repo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DDSResult(**result)
```

**Dependency injection pattern:** The two repository instances (`_record_repo`, `_weapon_repo`) are module-level singletons. For test environments, pass mock implementations directly to the orchestrator functions — no FastAPI DI container is required since the orchestrators take repositories as plain parameters.

---

## OTS Formula Reference

```
Given:
  attack_pool   = REF + weapon_skill_rank         (NPC: stored total; PC: REF + rank)
  autofire_pool = REF + autofire_rank              (if has_autofire and autofire rank > 0)
                = attack_pool                       (if autofire rank == 0, falls back)
  adj_pool      = attack_pool + (1 if excellent else 0)

Components:
  HPW_SS = clamp((adj_pool - (def_total + 5.5) + 5) / 10, 0.2, 1.5)   [dodging defender]
         = clamp((adj_pool - 15 + 5.5) / 10, 0.3, 1.5)                 [static DV defender]
  HPW_AF = same formula with (adj_pool - AUTOFIRE_ATK_PENALTY)

  EDPR_SS = max(0, avg_damage - SP) * ROF
  EDPR_AF = max(0, 7.0 - SP) * HPW_AF * (autofire_cap + 1) / 2

  P(crit) = 1 - (5/6)^N - N * (1/6) * (5/6)^(N-1)
  CTS_SS  = P(crit on weapon_dice_count) * CTS_MULTIPLIER
  CTS_AF  = P(crit on 2d6)              * CTS_MULTIPLIER

Final score:
  With autofire:    OTS = ((HPW_SS + HPW_AF) / 2) * ((EDPR_SS + EDPR_AF + CTS_SS + CTS_AF) / 2)
  Without autofire: OTS = HPW_SS * (EDPR_SS + CTS_SS)

Constants: CTS_MULTIPLIER = 10.7, AUTOFIRE_ATK_PENALTY = 3
```

---

## DDS Formula Reference

```
Given:
  body = BODY attribute
  will = WILLPOWER attribute
  sp   = effective Stopping Power (top-level armor or derivedStats.armor)

Components:
  HPP    = ((will + body) / 2) * 5 + 10
  AAC    = min(sp, 18) * (min(sp, 18) + 1) / 2
  E_DSR  = Σ_{n=1}^{body-1}  ∏_{k=1}^{n} max(0, min(9, body-k)) / 10
  DSR_hp = E_DSR * DSR_WEIGHT

Final score:
  DDS = HPP + AAC + DSR_hp

Constants: DSR_WEIGHT = 5.0, AAC_SP_CAP = 18

Verification targets (from dds_calc.py:183–188):
  Mook        (body=4,  will=4,  sp=7 ): DDS ≈  59.8
  Hardened    (body=5,  will=5,  sp=11): DDS ≈ 103.7
  Boss        (body=10, will=8,  sp=18): DDS ≈ 239.3
  Elite Boss  (body=12, will=10, sp=18): DDS ≈ 255.3
```

---

## Migration Steps (Calculations Layer, Steps 8–15)

**Step 8 — Migrate stat extraction to `calculations/stat_extraction.py`**

1. Create `calculations/stat_extraction.py` with the seven functions from the module spec above.
2. Update all function signatures to accept `ResolvedRecord` instead of `dict`.
3. Translate internal dict access to model attribute access (see key changes table in module spec).
4. In `main.py`, add `from calculations.stat_extraction import is_npc, get_skill_rank, get_attack_pool, get_defense_total, get_effective_sp` and delete the five original function bodies.
5. In `dds_calc.py`, replace `from main import load_record, get_effective_sp` with the new imports.
6. Run both `__main__` blocks — outputs must be identical. This is the first step that changes function signatures, so confirm the `YamlRecordRepository` integration is working (Step 6 must be complete).

**Step 9 — Migrate OTS math to `calculations/ots/math.py`**

1. Create `calculations/ots/math.py` with the seven functions.
2. The only required change is in `compute_ots`: replace `weapon_stats["key"]` dict access with `weapon_stats.key` attribute access on `WeaponStats`.
3. In `main.py`, replace the seven function bodies with `from calculations.ots.math import clamp, crit_prob, compute_hpw, compute_edpr_ss, compute_edpr_af, compute_cts, compute_ots`.
4. Run `python main.py` — output must be identical.

**Step 10 — Migrate DDS math to `calculations/dds/math.py`**

1. Create `calculations/dds/math.py` with the four functions.
2. Replace the inline `18` SP cap literal with `AAC_SP_CAP` imported from `data.config`.
3. In `dds_calc.py`, replace the four function bodies with imports from `calculations.dds.math`.
4. Run `python dds_calc.py` — all four verification rows must print "OK".

**Step 11 — Migrate orchestrators with dependency injection**

1. Create `calculations/ots/orchestrator.py` with `calculate_ots_for_records`.
2. Create `calculations/dds/orchestrator.py` with `calculate_dds_for_records`.
3. In `main.py`, replace `calculate_ots_for_records` body with an import + call with `_record_repo`, `_weapon_repo` (still module-level instances for now).
4. In `dds_calc.py`, replace `calculate_dds_for_records` body with an import + call with `_record_repo`.
5. Run both `__main__` blocks. This step validates the full data → calculation pipeline end-to-end.

**Step 12 — Migrate PDF pipeline (data layer)**

*(Data layer step; included here for sequencing context.)*

1. Create `data/pdf_pipeline/extract.py`, `parse.py`, `clean.py` as described in `data_layer.md`.
2. The original `extract_pdf.py`, `parse_npcs.py`, and `clean_npcs.py` files are no longer imported by anything at this point and can be deleted after verifying the new callables produce identical JSON output.

**Step 13 — Rewrite API in `api/`**

1. Create `api/models.py` with `OTSRequest`, `OTSResult`, `DDSRequest`, `DDSResult`.
2. Create `api/main.py` with the FastAPI application as described above.
3. Update `pyproject.toml` entry point if `uvicorn` is configured to launch `main:app`; change to `cpred_dr_framework.api.main:app`.
4. Test with `uvicorn cpred_dr_framework.api.main:app --reload` and make a POST to `/ots` with a valid aggressor/defender pair.

**Step 14 — Delete original flat files**

Before deleting, capture the regression baseline:

```bash
python main.py     > baseline_ots.txt
python dds_calc.py > baseline_dds.txt
```

Run the new orchestrators on the same inputs and diff against the baselines. Once the diff is empty (allowing for floating-point formatting differences), delete `main.py`, `dds_calc.py`, `parse_npcs.py`, `clean_npcs.py`, `extract_pdf.py`.

**Step 15 — YAML weapon prototype enrichment (optional)**

Add `has_autofire`, `autofire_cap`, `avg_damage`, `dice_count`, `attack_skill` to each weapon archetype in `base_files/prototypes/weapons/_base.yml`. Update `YamlWeaponRepository.get_weapon_stats()` to resolve via `YamlRecordRepository` instead of the hardcoded dict. The calculations layer is entirely unaffected.

---

## Testing Strategy

### `tests/calculations/test_ots_math.py` — Pure unit tests, zero I/O

```python
from calculations.ots.ots_math import crit_prob, compute_hpw, compute_edpr_ss, compute_edpr_af, compute_cts, compute_ots
from data.models import WeaponStats


def test_crit_prob_one_die():
    assert crit_prob(1) == 0.0  # impossible to roll two 6s on one die


def test_crit_prob_four_dice():
    result = crit_prob(4)
    assert 0.13 < result < 0.14  # ≈ 0.1319 from outline


def test_compute_hpw_dodging_defender():
    # attack_pool=15, def_total=10 → margin = 15 - 15.5 = -0.5 → HPW = clamp(4.5/10, 0.2, 1.5) = 0.45
    assert abs(compute_hpw(15, 10.0) - 0.45) < 0.001


def test_compute_hpw_static_dv():
    # attack_pool=8, def_total=0 → margin = 8 - 15 + 5.5 = -1.5 → HPW = clamp(-0.15, 0.3, 1.5) = 0.3
    assert compute_hpw(8, 0.0) == 0.3


def test_compute_edpr_ss():
    assert compute_edpr_ss(14.0, 7, 1) == 7.0  # max(0, 14-7) * 1


def test_compute_edpr_ss_sp_exceeds_damage():
    assert compute_edpr_ss(10.5, 15, 2) == 0.0  # SP > damage → 0


def test_compute_ots_no_autofire():
    w = WeaponStats(avg_damage=14.0, dice_count=4, rof=1, has_autofire=False, autofire_cap=None,
                    attack_skill="ShoulderArms")
    result = compute_ots(attack_pool=12, autofire_pool=None, weapon_stats=w, def_total=0.0, def_sp=7,
                         is_excellent=False)
    assert "ots" in result
    assert result["ots"] > 0
    assert result["hpw_af"] is None


def test_compute_ots_with_autofire():
    w = WeaponStats(avg_damage=14.0, dice_count=4, rof=1, has_autofire=True, autofire_cap=4,
                    attack_skill="ShoulderArms")
    result = compute_ots(attack_pool=12, autofire_pool=12, weapon_stats=w, def_total=0.0, def_sp=7, is_excellent=False)
    assert result["hpw_af"] is not None
    assert result["edpr_af"] is not None
```

### `tests/calculations/test_dds_math.py` — Table-driven verification

```python
import pytest
from calculations.dds.math import compute_dds, compute_aac

@pytest.mark.parametrize("label,body,will,sp,expected", [
    ("Mook",       4,  4,  7,  59.8),
    ("Hardened",   5,  5, 11, 103.7),
    ("Boss",      10,  8, 18, 239.3),
    ("Elite Boss",12, 10, 18, 255.3),
])
def test_dds_verification_table(label, body, will, sp, expected):
    r = compute_dds(body, will, sp)
    assert abs(r["dds"] - expected) < 1.0, f"{label}: expected {expected}, got {r['dds']}"

def test_aac_cap():
    assert compute_aac(20) == compute_aac(18)   # cap enforced

def test_aac_zero():
    assert compute_aac(0) == 0.0
```

### `tests/calculations/test_stat_extraction.py` — Fixture-based, zero I/O

```python
from data.models import ResolvedRecord, AttributeBlock, DerivedStats, SkillEntry
from calculations.stat_extraction import (
    is_npc, get_skill_rank, get_attack_pool, get_defense_total, get_effective_sp,
    get_body, get_will,
)

def _make_npc(**kwargs) -> ResolvedRecord:
    defaults = dict(record_id="test", npc_type="Grunt", attributes=AttributeBlock(), skills=[], derived_stats=DerivedStats())
    defaults.update(kwargs)
    return ResolvedRecord(**defaults)

def _make_pc(**kwargs) -> ResolvedRecord:
    defaults = dict(record_id="test", npc_type=None, attributes=AttributeBlock(), skills=[], derived_stats=DerivedStats())
    defaults.update(kwargs)
    return ResolvedRecord(**defaults)

def test_is_npc_true():
    assert is_npc(_make_npc()) is True

def test_is_npc_false():
    assert is_npc(_make_pc()) is False

def test_get_skill_rank_missing():
    rec = _make_npc(skills=[])
    assert get_skill_rank(rec, "ShoulderArms") == 0

def test_get_attack_pool_npc_uses_stored_rank():
    # NPC: stored rank IS the total (no REF addition)
    rec = _make_npc(
        skills=[SkillEntry(skill="ShoulderArms", rank=14)],
        attributes=AttributeBlock(reflexes=8),
    )
    assert get_attack_pool(rec, "ShoulderArms") == 14

def test_get_attack_pool_pc_adds_ref():
    rec = _make_pc(
        skills=[SkillEntry(skill="ShoulderArms", rank=6)],
        attributes=AttributeBlock(reflexes=8),
    )
    assert get_attack_pool(rec, "ShoulderArms") == 14   # 8 + 6

def test_get_defense_total_low_ref():
    rec = _make_npc(attributes=AttributeBlock(reflexes=6))
    assert get_defense_total(rec) == 0.0   # REF < 8 → cannot dodge

def test_get_effective_sp_top_level():
    rec = _make_npc(armor=11)
    assert get_effective_sp(rec) == 11

def test_get_effective_sp_derived_stats():
    rec = _make_pc(derived_stats=DerivedStats(armor=7))
    assert get_effective_sp(rec) == 7

def test_get_body_and_will():
    rec = _make_npc(attributes=AttributeBlock(body=8, willpower=6))
    assert get_body(rec) == 8
    assert get_will(rec) == 6
```

### `tests/calculations/test_orchestrators.py` — Mock and integration tests

```python
from unittest.mock import MagicMock
from data.models import ResolvedRecord, AttributeBlock, DerivedStats, SkillEntry, WeaponStats
from calculations.ots.orchestrator import calculate_ots_for_records
from calculations.dds.orchestrator import calculate_dds_for_records


def _arbiter_record() -> ResolvedRecord:
    return ResolvedRecord(
        record_id="NPC.6thStreet_Arbiter",
        npc_type="MiniBoss",
        attributes=AttributeBlock(body=5, willpower=6, reflexes=8, dexterity=7),
        skills=[SkillEntry(skill="ShoulderArms", rank=16), SkillEntry(skill="Evasion", rank=14)],
        armor=15,
        derived_stats=DerivedStats(),
        primary_weapon_id="Weapons.DangerGal_AssaultRifle_Standard",
    )


def test_calculate_ots_calls_repo_twice():
    mock_record_repo = MagicMock()
    mock_record_repo.get_record.return_value = _arbiter_record()

    mock_weapon_repo = MagicMock()
    mock_weapon_repo.parse_weapon_id.return_value = ("AssaultRifle", False)
    mock_weapon_repo.get_weapon_stats.return_value = WeaponStats(
        avg_damage=14.0, dice_count=4, rof=1, has_autofire=True, autofire_cap=4, attack_skill="ShoulderArms"
    )

    result = calculate_ots_for_records("NPC.A", "NPC.B", mock_record_repo, mock_weapon_repo)
    assert mock_record_repo.get_record.call_count == 2
    assert "ots" in result
    assert result["ots"] > 0


def test_calculate_dds_calls_repo_once():
    mock_repo = MagicMock()
    mock_repo.get_record.return_value = _arbiter_record()

    result = calculate_dds_for_records("NPC.6thStreet_Arbiter", mock_repo)
    mock_repo.get_record.assert_called_once_with("NPC.6thStreet_Arbiter")
    assert "dds" in result
    assert result["body"] == 5


# Integration tests (marked slow; use real repos, require base_files/ on disk)
import pytest

@pytest.mark.integration
def test_ots_integration():
    from data.repositories.yaml_repository import YamlRecordRepository
    from data.repositories.weapon_repository import YamlWeaponRepository
    result = calculate_ots_for_records(
        "NPC.6thStreet_Arbiter", "NPC.Edgerunners_Tetsuo",
        YamlRecordRepository(), YamlWeaponRepository(),
    )
    assert isinstance(result["ots"], float)
    assert result["ots"] > 0

@pytest.mark.integration
def test_dds_integration():
    from data.repositories.yaml_repository import YamlRecordRepository
    result = calculate_dds_for_records("NPC.6thStreet_Arbiter", YamlRecordRepository())
    assert abs(result["hpp"] - 37.5)  < 0.01
    assert abs(result["aac"] - 120.0) < 0.01
```

---

## Regression Gate

Before deleting any original file (Step 14), capture the existing CLI output as a baseline:

```bash
python main.py     > regression/baseline_ots_avg.txt
python dds_calc.py > regression/baseline_dds_verification.txt
```

Then write regression tests that invoke the new orchestrators on the same record set and assert to 4 decimal places:

```python
# tests/regression/test_regression.py
def test_dds_regression_arbiter():
    from data.repositories.yaml_repository import YamlRecordRepository
    from calculations.dds.orchestrator import calculate_dds_for_records
    r = calculate_dds_for_records("NPC.6thStreet_Arbiter", YamlRecordRepository())
    # Values from dds_calc.py __main__ output:
    assert abs(r["hpp"]    - 37.5)   < 0.0001
    assert abs(r["aac"]    - 120.0)  < 0.0001
    assert abs(r["dsr_hp"] - 2.7344) < 0.001
```

---

## Summary

| Artefact | Source | Status after migration |
|---|---|---|
| `calculations/stat_extraction.py` | `main.py:186–251` + `dds_calc.py:15–23` | Typed model inputs |
| `calculations/ots/math.py` | `main.py:258–370` | `WeaponStats` attribute access |
| `calculations/ots/orchestrator.py` | `main.py:377–421` | DI parameters |
| `calculations/dds/math.py` | `dds_calc.py:29–134` | `AAC_SP_CAP` from config |
| `calculations/dds/orchestrator.py` | `dds_calc.py:141–171` | DI parameter |
| `api/models.py` | `main.py:428–445` | + DDSRequest/DDSResult |
| `api/main.py` | `main.py:448–469` | Concrete repos constructed once; `/dds` endpoint added |
