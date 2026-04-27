# Data Layer — Implementation Plan

## Overview

The data layer is the single point of contact between the application and all persistent storage: YAML prototype/record files, JSON exports, and PDF source material. It owns all file I/O, prototype-chain resolution, type-safe data modelling, and the PDF ingestion pipeline.

**Hard constraints:**
- The data layer contains **zero math or scoring logic** — no formulas, no weighted averages, no game-balance calculations.
- All public return types are typed Pydantic models, never raw `dict`s.
- The calculations layer imports only from `data.repositories.base` and `data.models` — never from `data.registry.*` or `data.pdf_pipeline.*` directly.

**Architectural pattern:** Repository Pattern with abstract interfaces (ABCs), backed by concrete YAML/JSON implementations. This allows swapping the storage backend (e.g. to SQLite or a REST API) without touching any calculation or API code.

---

## Directory Structure

```
cpred_dr_framework/
└── data/
    ├── __init__.py
    ├── config.py
    ├── models.py
    ├── registry/
    │   ├── __init__.py
    │   ├── loader.py
    │   └── resolver.py
    ├── repositories/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── yaml_repository.py
    │   └── weapon_repository.py
    └── pdf_pipeline/
        ├── __init__.py
        ├── extract.py
        ├── parse.py
        └── clean.py
```

---

## Module-by-Module Breakdown

### `data/config.py`

**Purpose:** Single authoritative source for all tuning constants and path configuration. Eliminates scattered magic numbers.

**Migrated from:**
- `main.py:20` — `CTS_MULTIPLIER = 10.7`
- `main.py:21` — `AUTOFIRE_ATK_PENALTY = 3`
- `main.py:15` — `BASE_FILES_DIR = Path(__file__).parent / "base_files"`
- `dds_calc.py:8` — `DSR_WEIGHT: float = 5.0`

**New additions:**
- `JSON_OUTPUT_DIR` — path to `json_output/`
- `TEXT_OUTPUT_DIR` — path to `text_output/`

**Full content:**

```python
from pathlib import Path

# Resolved at import time relative to the package root
_PKG_ROOT = Path(__file__).parent.parent.parent  # project root

BASE_FILES_DIR:   Path  = _PKG_ROOT / "base_files"
JSON_OUTPUT_DIR:  Path  = _PKG_ROOT / "json_output"
TEXT_OUTPUT_DIR:  Path  = _PKG_ROOT / "text_output"

# ---------------------------------------------------------------------------
# Playtesting parameters (see docs/outline.md "Requires playtesting" sections)
# ---------------------------------------------------------------------------
CTS_MULTIPLIER:        float = 10.7  # = 5 + 0.58 + 4.41 + 0.67 (derived in outline)
AUTOFIRE_ATK_PENALTY:  int   = 3     # -3 to attack pool for HPW autofire branch
DSR_WEIGHT:            float = 5.0   # Scales E_DSR to HP-equivalent units

# ---------------------------------------------------------------------------
# AAC cap — prevents military-grade SP from collapsing tier separation
# ---------------------------------------------------------------------------
AAC_SP_CAP: int = 18
```

**Migration impact on existing files:**
- In `main.py`, replace `CTS_MULTIPLIER`, `AUTOFIRE_ATK_PENALTY`, `BASE_FILES_DIR` literals with `from data.config import ...`.
- In `dds_calc.py`, replace `DSR_WEIGHT` literal.
- Run both `__main__` blocks after this step to confirm no behavioural change.

---

### `data/models.py`

**Purpose:** Pydantic `BaseModel` definitions that form the typed boundary between the data layer and the calculations layer. The calculations layer consumes these models; it never sees raw `dict`s.

**No migration — these are new code.**

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class SkillEntry(BaseModel):
    skill: str
    rank: int


class AttributeBlock(BaseModel):
    intelligence:  Optional[int] = 0
    reflexes:      Optional[int] = 0
    dexterity:     Optional[int] = 0
    tech:          Optional[int] = 0
    cool:          Optional[int] = 0
    willpower:     Optional[int] = 0
    luck:          Optional[int] = 0
    move:          Optional[int] = 0
    body:          Optional[int] = 0
    empathy:       Optional[int] = 0


class DerivedStats(BaseModel):
    max_hp:         Optional[int] = None
    current_hp:     Optional[int] = None
    armor:          Optional[int] = None   # may also live at top-level; resolver normalises


class WeaponStats(BaseModel):
    avg_damage:    float
    dice_count:    int
    rof:           int
    has_autofire:  bool
    autofire_cap:  Optional[int]   = None
    attack_skill:  str


class ResolvedRecord(BaseModel):
    record_id:          str
    npc_type:           Optional[str]   = None   # present iff record is an NPC
    handle:             Optional[str]   = None
    attributes:         AttributeBlock  = AttributeBlock()
    derived_stats:      DerivedStats    = DerivedStats()
    skills:             list[SkillEntry] = []
    armor:              Optional[int]   = None   # top-level armor field (NPC records)
    primary_weapon_id:  Optional[str]   = None   # e.g. "Weapons.Preset_HeavyPistol_Excellent"
```

**Design notes:**
- `armor` exists at both top-level and inside `DerivedStats` in different record types. `YamlRecordRepository.get_record()` normalises this: if a top-level `armor` int is found it populates `ResolvedRecord.armor`; if only `derivedStats.armor` is present it populates `DerivedStats.armor`. The stat extraction functions in the calculations layer check `record.armor` first, then `record.derived_stats.armor`.
- `npc_type` being `None` distinguishes PC records from NPC records (replaces `"npcType" in record` dict check).

---

### `data/registry/loader.py`

**Purpose:** Load all YAML files from `base_files/` into a flat registry dict and merge prototype chains. No external imports beyond `yaml` and `pathlib`.

**Migrated from `main.py`:**

| Function | Source lines | Notes |
|---|---|---|
| `_AppendLoader` class | 68–80 | YAML SafeLoader extended with `!append` tag support |
| `_append_constructor` | 72–77 | Registered on `_AppendLoader` |
| `_build_registry() -> dict[str, dict]` | 85–110 | Scans six YAML directories; skips non-dict files |
| `_get_registry() -> dict[str, dict]` | 113–117 | Singleton accessor with lazy init |
| `_merge(base: dict, leaf: dict) -> dict` | 119–146 | Prototype chain merge: leaf wins; skills merged by name; attributes/derivedStats merged shallowly |

**Migration steps:**
1. Copy the five items above verbatim into `data/registry/loader.py`.
2. Change `BASE_FILES_DIR` import to `from data.config import BASE_FILES_DIR`.
3. Remove the module-level `_record_registry` global from `main.py`; it now lives in `loader.py`.
4. `main.py` `load_record` call sites become `from data.registry.resolver import load_record`.

**Key behaviour to preserve:**
- `_merge` strips `$base` and `$type` keys from leaf before merging.
- Skills array is merged by the `skill` name key (leaf entry overwrites base entry of same name).
- `attributes` and `derivedStats` are shallow-merged (leaf dict values win per key, but absent leaf keys keep base values).

---

### `data/registry/resolver.py`

**Purpose:** Recursively resolve a record ID through its `$base` prototype chain, producing a fully-merged flat dict.

**Migrated from `main.py`:**

| Function | Source lines |
|---|---|
| `load_record(record_id: str) -> dict` | 149–159 |

```python
from data.registry.loader import _get_registry, _merge


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
```

**Note:** This function returns a raw `dict`. The repository layer (`yaml_repository.py`) wraps the result in a `ResolvedRecord` Pydantic model before handing it to the calculations layer.

---

### `data/repositories/base.py`

**Purpose:** Abstract base classes that define the public contract of the data layer. The calculations layer imports only from this module — never the concrete implementations.

```python
from abc import ABC, abstractmethod
from data.models import ResolvedRecord, WeaponStats


class AbstractRecordRepository(ABC):
    """Provides resolved game records (NPCs, player characters)."""

    @abstractmethod
    def get_record(self, record_id: str) -> ResolvedRecord:
        """Return a fully resolved ResolvedRecord for *record_id*.

        Raises:
            ValueError: If record_id does not exist in the data source.
        """
        ...


class AbstractWeaponRepository(ABC):
    """Provides weapon stat lookups and weapon ID parsing."""

    @abstractmethod
    def get_weapon_stats(self, weapon_type_key: str) -> WeaponStats:
        """Return WeaponStats for a canonical weapon type key (e.g. 'AssaultRifle').

        Raises:
            KeyError: If the weapon type key is not recognised.
        """
        ...

    @abstractmethod
    def parse_weapon_id(self, weapon_id: str) -> tuple[str, bool]:
        """Parse a weapon record ID string into (weapon_type_key, is_excellent).

        Examples:
            "Weapons.Preset_HeavyPistol_Excellent"        -> ("HeavyPistol", True)
            "Weapons.DangerGal_VeryHeavyMeleeWeapon_Poor" -> ("VeryHeavyMelee", False)
            "Weapons.Preset_AssaultRifle_Military"         -> ("AssaultRifle", False)
        """
        ...
```

---

### `data/repositories/yaml_repository.py`

**Purpose:** Concrete implementation of `AbstractRecordRepository` backed by the YAML registry. Calls `load_record()` and maps the result into the `ResolvedRecord` typed model.

**No existing function to migrate — this is new bridge code** (the mapping from raw dict to typed model).

```python
from data.repositories.base import AbstractRecordRepository
from data.registry.resolver import load_record
from data.models import (
    ResolvedRecord, AttributeBlock, DerivedStats, SkillEntry
)


class YamlRecordRepository(AbstractRecordRepository):

    def get_record(self, record_id: str) -> ResolvedRecord:
        raw = load_record(record_id)   # fully resolved dict

        attrs_raw = raw.get("attributes") or {}
        ds_raw    = raw.get("derivedStats") or {}

        # Normalise the two possible armor locations into model fields
        top_armor = raw.get("armor")
        ds_armor  = ds_raw.get("armor")
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
```

**Smoke test (run after implementing):**
```python
repo = YamlRecordRepository()
rec  = repo.get_record("NPC.6thStreet_Arbiter")
assert rec.attributes.body == 5
assert rec.attributes.willpower == 6
assert rec.armor == 15
assert any(s.skill == "ShoulderArms" for s in rec.skills)
```

---

### `data/repositories/weapon_repository.py`

**Purpose:** Concrete implementation of `AbstractWeaponRepository`. Provides typed `WeaponStats` objects and weapon ID parsing.

**Migrated from `main.py`:**

| Item | Source lines | Notes |
|---|---|---|
| `WEAPON_STATS` dict (as typed `WeaponStats` objects) | 29–49 | Re-typed from `dict[str, dict]` to `dict[str, WeaponStats]` |
| `_WEAPON_TYPE_KEYWORDS` list | 52–61 | Longest-first ordering preserved |
| `parse_weapon_id()` function | 166–179 | Moved as a method |

```python
from data.repositories.base import AbstractWeaponRepository
from data.models import WeaponStats


_WEAPON_STATS: dict[str, WeaponStats] = {
    "Pistol":          WeaponStats(avg_damage=3.5,  dice_count=1, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "MediumPistol":    WeaponStats(avg_damage=7.0,  dice_count=2, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "HeavyPistol":     WeaponStats(avg_damage=10.5, dice_count=3, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "VeryHeavyPistol": WeaponStats(avg_damage=14.0, dice_count=4, rof=1, has_autofire=False, autofire_cap=None, attack_skill="Handgun"),
    "SMG":             WeaponStats(avg_damage=7.0,  dice_count=2, rof=1, has_autofire=True,  autofire_cap=3,    attack_skill="ShoulderArms"),
    "HeavySMG":        WeaponStats(avg_damage=21.0, dice_count=6, rof=1, has_autofire=True,  autofire_cap=3,    attack_skill="ShoulderArms"),
    "Shotgun":         WeaponStats(avg_damage=21.0, dice_count=6, rof=1, has_autofire=False, autofire_cap=None, attack_skill="ShoulderArms"),
    "AssaultRifle":    WeaponStats(avg_damage=14.0, dice_count=4, rof=1, has_autofire=True,  autofire_cap=4,    attack_skill="ShoulderArms"),
    "SniperRifle":     WeaponStats(avg_damage=17.5, dice_count=5, rof=1, has_autofire=False, autofire_cap=None, attack_skill="ShoulderArms"),
    "HeavyMachineGun": WeaponStats(avg_damage=21.0, dice_count=6, rof=1, has_autofire=True,  autofire_cap=4,    attack_skill="HeavyWeapons"),
    "VeryHeavyMelee":  WeaponStats(avg_damage=14.0, dice_count=4, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "HeavyMelee":      WeaponStats(avg_damage=10.5, dice_count=3, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "MediumMelee":     WeaponStats(avg_damage=7.0,  dice_count=2, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "LightMelee":      WeaponStats(avg_damage=3.5,  dice_count=1, rof=1, has_autofire=False, autofire_cap=None, attack_skill="MeleeCombat"),
    "GrenadeLauncher": WeaponStats(avg_damage=21.0, dice_count=6, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "RocketLauncher":  WeaponStats(avg_damage=28.0, dice_count=8, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "FlamethrowerWeapon": WeaponStats(avg_damage=7.0, dice_count=2, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "Flamethrower":    WeaponStats(avg_damage=7.0,  dice_count=2, rof=1, has_autofire=False, autofire_cap=None, attack_skill="HeavyWeapons"),
    "Brawling":        WeaponStats(avg_damage=7.0,  dice_count=2, rof=2, has_autofire=False, autofire_cap=None, attack_skill="Brawling"),
}

# Longest-first so "VeryHeavyPistol" matches before "HeavyPistol" before "Pistol"
_WEAPON_TYPE_KEYWORDS: list[str] = [
    "VeryHeavyPistol", "HeavyPistol", "MediumPistol", "Pistol",
    "HeavySMG", "SMG",
    "AssaultRifle", "SniperRifle",
    "Shotgun", "HeavyMachineGun",
    "VeryHeavyMelee", "HeavyMelee", "MediumMelee", "LightMelee",
    "GrenadeLauncher", "RocketLauncher",
    "FlamethrowerWeapon", "Flamethrower",
    "Brawling", "Bow",
]


class YamlWeaponRepository(AbstractWeaponRepository):

    def get_weapon_stats(self, weapon_type_key: str) -> WeaponStats:
        stats = _WEAPON_STATS.get(weapon_type_key)
        if stats is None:
            raise KeyError(
                f"Unknown weapon type key: {weapon_type_key!r}. "
                f"Valid keys: {list(_WEAPON_STATS)}"
            )
        return stats

    def parse_weapon_id(self, weapon_id: str) -> tuple[str, bool]:
        is_excellent = "excellent" in weapon_id.lower()
        wid_lower = weapon_id.lower()
        for keyword in _WEAPON_TYPE_KEYWORDS:
            if keyword.lower() in wid_lower:
                return keyword, is_excellent
        return "Unknown", is_excellent
```

**Future enrichment (optional):** Once weapon archetypes in `base_files/prototypes/weapons/_base.yml` are augmented with `has_autofire`, `autofire_cap`, `avg_damage`, `dice_count`, and `attack_skill` fields, replace `_WEAPON_STATS` with a YAML lookup via `YamlRecordRepository`. The method signatures are unchanged; the calculations layer is unaffected.

---

### `data/pdf_pipeline/extract.py`

**Purpose:** Wrap `pdfplumber` extraction as a callable function (replaces module-level execution in `extract_pdf.py`).

**Migrated from `extract_pdf.py`** (entire 53-line file refactored into a function).

```python
from pathlib import Path
import pdfplumber


def extract_pdf(pdf_path: str | Path, output_path: str | Path) -> tuple[int, str]:
    """Extract raw text from a PDF and write it to *output_path* with PAGE markers.

    Returns:
        (page_count, output_path_str) on success.
    """
    pdf_path    = Path(pdf_path)
    output_path = Path(output_path)

    with pdfplumber.open(pdf_path) as pdf:
        lines: list[str] = []
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines.append(f"=== PAGE {i} ===\n{text}")
        full_text = "\n\n".join(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")
    return len(pdf.pages), str(output_path)
```

---

### `data/pdf_pipeline/parse.py`

**Purpose:** Parse NPC stat blocks out of the extracted PDF text. All module-level execution from `parse_npcs.py` is refactored into named, callable functions.

**Migrated from `parse_npcs.py`:**

| Function/Block | Source | Notes |
|---|---|---|
| `split_pages(full_text: str) -> dict[int, str]` | Lines 15–23 (module-level) | Refactored into function |
| `extract_stats(text: str) -> dict` | Existing function | Unchanged |
| `extract_section(text, start_keyword, end_keywords) -> str` | Existing function | Unchanged |
| `parse_level_rep_hp(text: str) -> dict` | Existing function | Unchanged |
| `parse_role(text: str) -> str` | Existing function | Unchanged |
| `parse_weapons(text: str) -> list[str]` | Existing function | Unchanged |
| `parse_skills(text: str) -> str` | Existing function | Unchanged |
| `parse_gear(text: str) -> str` | Existing function | Unchanged |
| `parse_cyberware(text: str) -> str` | Existing function | Unchanged |
| `parse_bio(text: str) -> str` | Existing function | Unchanged |
| `parse_npc_pages(pages: dict[int, str]) -> list[dict]` | Lines 244–324 (module-level) | Refactored into function |

**New entry point:**
```python
def run_pipeline(pdf_text_path: str | Path, output_json_path: str | Path) -> list[dict]:
    """Full parse pipeline: read extracted PDF text → return list of NPC dicts."""
    text = Path(pdf_text_path).read_text(encoding="utf-8")
    pages = split_pages(text)
    npcs = parse_npc_pages(pages)
    import json
    Path(output_json_path).write_text(json.dumps(npcs, indent=2, ensure_ascii=False))
    return npcs
```

All regex constants (`NPC_STAT_PATTERN`, etc.) remain as module-level constants inside this file.

---

### `data/pdf_pipeline/clean.py`

**Purpose:** Normalise raw parsed NPC data: fix PDF font-encoding artefacts, apply manual overrides, deduplicate.

**Migrated from `clean_npcs.py`:**

| Item | Source | Notes |
|---|---|---|
| `FACTION_OVERRIDES: dict[int, str]` | Module-level constant | Unchanged |
| `NAME_OVERRIDES: dict[int, str]` | Module-level constant | Unchanged |
| `DESCRIPTOR_OVERRIDES: dict[int, str]` | Module-level constant | Unchanged |
| `undouble(s: str) -> str` | Existing function | Collapses consecutive identical chars |
| `clean_text(s: str) -> str` | Existing function | Combines undouble + strip + whitespace norm |
| `clean_npc_list(npcs: list[dict]) -> list[dict]` | Lines 89–137 (module-level) | Refactored into function |

**New entry point:**
```python
def run_clean_pipeline(
    input_json_path: str | Path,
    output_json_path: str | Path,
    output_txt_path:  str | Path,
) -> list[dict]:
    """Load raw NPC JSON, clean it, and write cleaned JSON + summary text."""
    import json
    npcs = json.loads(Path(input_json_path).read_text(encoding="utf-8"))
    cleaned = clean_npc_list(npcs)
    Path(output_json_path).write_text(json.dumps(cleaned, indent=2, ensure_ascii=False))
    # write text summary
    lines = [f"{n.get('name', '?')} ({n.get('faction', '?')})" for n in cleaned]
    Path(output_txt_path).write_text("\n".join(lines), encoding="utf-8")
    return cleaned
```

---

### `data/__init__.py`

Re-exports the public surface of the data layer:

```python
from data.repositories.base import AbstractRecordRepository, AbstractWeaponRepository
from data.repositories.yaml_repository import YamlRecordRepository
from data.repositories.weapon_repository import YamlWeaponRepository
from data.models import ResolvedRecord, WeaponStats
from data.config import (
    CTS_MULTIPLIER, AUTOFIRE_ATK_PENALTY, DSR_WEIGHT,
    AAC_SP_CAP, BASE_FILES_DIR,
)

__all__ = [
    "AbstractRecordRepository", "AbstractWeaponRepository",
    "YamlRecordRepository", "YamlWeaponRepository",
    "ResolvedRecord", "WeaponStats",
    "CTS_MULTIPLIER", "AUTOFIRE_ATK_PENALTY", "DSR_WEIGHT", "AAC_SP_CAP",
    "BASE_FILES_DIR",
]
```

---

## Public API Surface (what the calculations layer may import)

```python
# Permitted imports from the data layer into the calculations layer:
from data.repositories.base import AbstractRecordRepository, AbstractWeaponRepository
from data.models import ResolvedRecord, WeaponStats
from data.config import CTS_MULTIPLIER, AUTOFIRE_ATK_PENALTY, DSR_WEIGHT, AAC_SP_CAP
```

The calculations layer **must not** import:
- `data.registry.*` — internal implementation detail
- `data.repositories.yaml_repository` — concrete implementation; only the ABC is visible
- `data.repositories.weapon_repository` — same
- `data.pdf_pipeline.*` — ingestion pipeline; irrelevant to scoring

---

## Migration Steps (Data Layer, Steps 1–7)

Each step is independently committable and leaves the application functional.

**Step 1 — Create package skeleton**

Create the directory tree and empty `__init__.py` files. Update `pyproject.toml` to reference the `cpred_dr_framework` package:

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["cpred_dr_framework*"]
```

No logic changes. Verify `import cpred_dr_framework` succeeds.

**Step 2 — Migrate constants to `data/config.py`**

1. Create `data/config.py` with content from the module spec above.
2. In `main.py`: add `from data.config import CTS_MULTIPLIER, AUTOFIRE_ATK_PENALTY, BASE_FILES_DIR` and delete the three literal assignments.
3. In `dds_calc.py`: add `from data.config import DSR_WEIGHT` and delete the literal assignment.
4. Run `python main.py` and `python dds_calc.py` — outputs must be identical to pre-migration.

**Step 3 — Migrate YAML registry to `data/registry/`**

1. Create `data/registry/loader.py` with `_AppendLoader`, `_append_constructor`, `_build_registry`, `_get_registry`, `_merge`.
2. Create `data/registry/resolver.py` with `load_record`.
3. In `main.py`: replace the five functions + `_record_registry` global with `from data.registry.loader import _get_registry, _merge` and `from data.registry.resolver import load_record`.
4. In `dds_calc.py`: replace `from main import load_record, get_effective_sp` — `load_record` now comes from `data.registry.resolver`. (`get_effective_sp` will move to the calculations layer in Step 8, but for now keep the `main` import as-is.)
5. Run both `__main__` blocks.

**Step 4 — Define Pydantic models in `data/models.py`**

Create `data/models.py` with the five model classes from the module spec above. No existing code changes. Import and instantiate in a Python REPL to confirm no syntax errors.

**Step 5 — Write repository ABCs in `data/repositories/base.py`**

Create `data/repositories/base.py` with `AbstractRecordRepository` and `AbstractWeaponRepository`. No existing code changes.

**Step 6 — Implement `YamlRecordRepository`**

1. Create `data/repositories/yaml_repository.py`.
2. Run the smoke test from the module spec above (no test framework required, just a `python -c "..."` invocation).
3. No changes to `main.py` or `dds_calc.py` yet.

**Step 7 — Implement `YamlWeaponRepository`**

1. Create `data/repositories/weapon_repository.py` by copying `WEAPON_STATS` and `_WEAPON_TYPE_KEYWORDS` from `main.py` (lines 29–61) and re-typing them.
2. Move `parse_weapon_id` (lines 166–179) into `YamlWeaponRepository.parse_weapon_id`.
3. Verify: `YamlWeaponRepository().parse_weapon_id("Weapons.Preset_HeavyPistol_Excellent") == ("HeavyPistol", True)`.
4. `main.py` still uses its own `WEAPON_STATS` and `parse_weapon_id` until Step 11 (orchestrator migration). That is intentional — the original files remain functional throughout.

---

## YAML Weapon Prototype Enrichment (Optional Follow-On)

The five calculation-facing fields (`has_autofire`, `autofire_cap`, `avg_damage`, `dice_count`, `attack_skill`) are currently absent from the weapon YAML prototypes in `base_files/prototypes/weapons/_base.yml`. Two migration paths exist:

**Path A — Enrich YAML (recommended long-term)**

Add the five fields to each weapon archetype entry in `_base.yml`. Update `YamlWeaponRepository.get_weapon_stats()` to call `YamlRecordRepository().get_record(f"Weapons.{weapon_type_key}")` and construct a `WeaponStats` from the result. The `_WEAPON_STATS` hardcoded dict is then deleted. The calculations layer is entirely unaffected.

**Path B — Keep hardcoded dict (safe interim)**

Ship Path B first (Steps 1–7 above). The hardcoded dict now lives inside the data layer boundary, which is correct — it is isolated from calculations. Path A can follow as a pure data-engineering task without touching any math.

---

## Testing Strategy

All data layer tests use real YAML files (no mocks). They assert on data shape and correctness, not on calculation results.

### `tests/data/test_loader.py`

```python
def test_build_registry_contains_known_key():
    reg = _build_registry()
    assert "NPC.6thStreet_Arbiter" in reg

def test_merge_skill_leaf_wins():
    base = {"skills": [{"skill": "ShoulderArms", "rank": 10}]}
    leaf = {"skills": [{"skill": "ShoulderArms", "rank": 16}]}
    result = _merge(base, leaf)
    assert result["skills"][0]["rank"] == 16

def test_merge_strips_base_key():
    base = {"armor": 5}
    leaf = {"$base": "NPC.Something", "armor": 7}
    result = _merge(base, leaf)
    assert "$base" not in result
    assert result["armor"] == 7

def test_merge_attributes_shallow():
    base = {"attributes": {"body": 4, "reflexes": 6}}
    leaf = {"attributes": {"body": 8}}
    result = _merge(base, leaf)
    assert result["attributes"]["body"] == 8
    assert result["attributes"]["reflexes"] == 6  # base value preserved
```

### `tests/data/test_resolver.py`

```python
def test_load_record_resolves_base_chain():
    rec = load_record("NPC.6thStreet_Arbiter")
    assert "$base" not in rec

def test_load_record_missing_raises():
    with pytest.raises(ValueError, match="Record not found"):
        load_record("NPC.DoesNotExist_XYZ")

def test_yaml_record_repository_returns_typed_model():
    repo = YamlRecordRepository()
    rec  = repo.get_record("NPC.6thStreet_Arbiter")
    assert isinstance(rec, ResolvedRecord)
    assert rec.attributes.body == 5
    assert rec.attributes.willpower == 6
    assert rec.armor == 15
```

### `tests/data/test_weapon_repository.py`

```python
def test_assault_rifle_stats():
    repo = YamlWeaponRepository()
    w = repo.get_weapon_stats("AssaultRifle")
    assert w.has_autofire is True
    assert w.autofire_cap == 4
    assert w.avg_damage == 14.0
    assert w.attack_skill == "ShoulderArms"

def test_parse_weapon_id_excellent():
    repo = YamlWeaponRepository()
    key, is_exc = repo.parse_weapon_id("Weapons.Preset_HeavyPistol_Excellent")
    assert key == "HeavyPistol"
    assert is_exc is True

def test_parse_weapon_id_priority():
    repo = YamlWeaponRepository()
    key, _ = repo.parse_weapon_id("Weapons.Preset_VeryHeavyPistol_Standard")
    assert key == "VeryHeavyPistol"   # must not match "HeavyPistol" or "Pistol"

def test_unknown_weapon_type_raises():
    repo = YamlWeaponRepository()
    with pytest.raises(KeyError):
        repo.get_weapon_stats("LaserCannon")
```

---

## Summary

| Artefact | Source | Status after migration |
|---|---|---|
| `data/config.py` | `main.py:15,20,21` + `dds_calc.py:8` | Centralised constants |
| `data/models.py` | New | Typed layer boundary |
| `data/registry/loader.py` | `main.py:68–146` | Extracted, unchanged logic |
| `data/registry/resolver.py` | `main.py:149–159` | Extracted, unchanged logic |
| `data/repositories/base.py` | New | ABC contracts |
| `data/repositories/yaml_repository.py` | New (wraps resolver) | Typed dict → model mapping |
| `data/repositories/weapon_repository.py` | `main.py:29–61,166–179` | Typed, isolated |
| `data/pdf_pipeline/extract.py` | `extract_pdf.py` | Callable function |
| `data/pdf_pipeline/parse.py` | `parse_npcs.py` | Module-level → named functions |
| `data/pdf_pipeline/clean.py` | `clean_npcs.py` | Module-level → named functions |
