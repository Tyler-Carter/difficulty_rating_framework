from __future__ import annotations

import pandas as pd

from eda.data import RARITY_ORDER, CORE_METRICS, DDS_COMPONENTS, OTS_COMPONENTS


def frame(df: pd.DataFrame) -> dict:
    """High-level snapshot for the report's Frame section.

    Returns a dict whose keys map to report sub-blocks: shape summary, the
    rarity ladder, the join hit rate (if present), and a one-line description
    of what each row in `df` represents.
    """
    join_info = df.attrs.get("clean_join_hit_rate", (0, 0, 0.0))
    return {
        "row_grain":        "one row per (PC, NPC) pair",
        "n_rows":           len(df),
        "n_pcs":            int(df["pc_role_id"].nunique()),
        "n_pc_roles":       int(df["pc_role"].nunique()),
        "n_npcs":           int(df["npc_id"].nunique()),
        "n_factions":       int(df["faction"].nunique()),
        "rarity_tiers":     RARITY_ORDER,
        "core_metrics":     CORE_METRICS,
        "ots_components":   OTS_COMPONENTS,
        "dds_components":   DDS_COMPONENTS,
        "clean_join_hit":   join_info,
        "pc_roles":         sorted(df["pc_role"].dropna().unique().tolist()),
        "factions":         sorted(df["faction"].dropna().unique().tolist()),
    }


def quality(df: pd.DataFrame) -> dict:
    """Data quality + integrity checks the report's Profile section displays.

    Returns:
        - null_rates: per-column NaN fraction (DataFrame)
        - cardinality: per-column distinct count (Series)
        - rarity_counts: NPCs (deduped) per rarity tier
        - integrity: list of (check_name, ok, detail) for invariants
    """
    null_rates = df.isna().mean().round(4).rename("null_rate").to_frame()
    null_rates["null_count"] = df.isna().sum().astype(int)

    cardinality = df.nunique(dropna=True).rename("distinct").to_frame()

    unique_npcs = df.drop_duplicates("npc_id")
    rarity_counts = (
        unique_npcs["npc_rarity"].value_counts().reindex(RARITY_ORDER, fill_value=0)
        .rename("unique_npcs")
        .to_frame()
    )

    integrity: list[tuple[str, bool, str]] = []

    # DDS is a function of NPC only — it must be identical across PCs for the same NPC.
    dds_var = df.groupby("npc_id", observed=True)["dds"].nunique()
    dds_invariant = bool((dds_var <= 1).all())
    integrity.append((
        "DDS is constant per NPC across PCs",
        dds_invariant,
        f"{(dds_var > 1).sum()} NPC(s) showed varying DDS — should be 0",
    ))

    # OTS depends on the PC's defenses; it should usually vary across PCs unless the
    # NPC's weapon is so weak it bottoms-out at the HPW floor for everyone.
    ots_var_per_npc = df.groupby("npc_id", observed=True)["ots"].std().fillna(0.0)
    ots_floor_count = int((ots_var_per_npc < 1e-6).sum())
    integrity.append((
        "OTS varies across PCs for most NPCs",
        ots_floor_count < len(ots_var_per_npc) * 0.5,
        f"{ots_floor_count}/{len(ots_var_per_npc)} NPCs deliver identical OTS to every PC",
    ))

    # NTS_raw should equal (OTS × 0.6 + DDS × 0.4) × CM within float tolerance.
    expected = (df["ots"] * 0.6 + df["dds"] * 0.4) * df["cm"]
    delta = (df["nts_raw"] - expected).abs()
    integrity.append((
        "NTS_raw == (OTS·0.6 + DDS·0.4) · CM",
        bool((delta < 0.01).all()),
        f"max |delta| = {delta.max():.4f}",
    ))

    return {
        "null_rates":    null_rates,
        "cardinality":   cardinality,
        "rarity_counts": rarity_counts,
        "integrity":     integrity,
    }
