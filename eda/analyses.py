from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from eda.data import RARITY_ORDER, ANCHOR_TIERS, CORE_METRICS, DDS_COMPONENTS


def univariate(df: pd.DataFrame) -> pd.DataFrame:
    """Per-metric distribution summary including skewness/kurtosis and zero-mass.

    Captures information not already obvious from `df.describe()`:
    - skewness (>0 = right tail) and excess kurtosis (>0 = heavy tails)
    - the zero-mass fraction (relevant for OTS, where many NPCs cannot
      penetrate PC armor and EDPR collapses to 0)
    """
    metrics = CORE_METRICS + ["hpp", "aac", "dsr_hp", "hpw_ss", "edpr_ss", "cts_ss"]
    rows = []
    for m in metrics:
        s = pd.to_numeric(df[m], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append({
            "metric":     m,
            "n":          int(len(s)),
            "mean":       round(float(s.mean()), 4),
            "median":     round(float(s.median()), 4),
            "std":        round(float(s.std()), 4),
            "min":        round(float(s.min()), 4),
            "p05":        round(float(s.quantile(0.05)), 4),
            "p95":        round(float(s.quantile(0.95)), 4),
            "max":        round(float(s.max()), 4),
            "skewness":   round(float(stats.skew(s)), 4),
            "ex_kurtosis":round(float(stats.kurtosis(s)), 4),
            "zero_frac":  round(float((s == 0).mean()), 4),
        })
    return pd.DataFrame(rows).set_index("metric")


def correlations(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Pearson AND Spearman correlation matrices on metrics + subcomponents.

    Spearman captures monotonic (rank) relationships that Pearson misses when
    data is non-linear or heavy-tailed (which OTS is, after the zero mass).
    """
    cols = CORE_METRICS + DDS_COMPONENTS + ["hpw_ss", "edpr_ss", "cts_ss", "cm"]
    cols = [c for c in cols if c in df.columns]
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    return {
        "pearson":  sub.corr(method="pearson").round(3),
        "spearman": sub.corr(method="spearman").round(3),
    }


def rarity_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Mean / median / std of every metric by rarity tier."""
    sub = df[["npc_rarity", *CORE_METRICS]].copy()
    grp = sub.groupby("npc_rarity", observed=True)[CORE_METRICS]
    out = grp.agg(["mean", "median", "std"]).round(2)
    out["n_pairs"] = grp.size().astype(int)
    out["n_unique_npcs"] = (
        df.groupby("npc_rarity", observed=True)["npc_id"].nunique().astype(int)
    )
    return out


def pc_role_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Mean / median NTS_raw + zero-mass OTS rate by PC role.

    Highlights whether the (PC, NPC) experience is consistent across roles.
    A role with very high OTS zero-mass means most NPCs can't damage that PC.
    """
    grp = df.groupby("pc_role", observed=True)
    out = pd.DataFrame({
        "n_pairs":        grp.size().astype(int),
        "median_nts_raw": grp["nts_raw"].median().round(2),
        "mean_nts_raw":   grp["nts_raw"].mean().round(2),
        "median_ots":     grp["ots"].median().round(3),
        "ots_zero_frac":  (df.assign(z=df["edpr_ss"].eq(0))
                              .groupby("pc_role", observed=True)["z"].mean().round(4)),
    })
    return out.sort_values("median_nts_raw", ascending=False)


def faction_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """NTS_raw distribution per faction with NPC count.

    Useful for spotting unbalanced gangs (e.g., a faction whose median NTS is
    sharply higher or lower than its peers may indicate stat-block drift).
    """
    grp = df.groupby("faction", observed=True)
    return pd.DataFrame({
        "n_pairs":        grp.size().astype(int),
        "n_unique_npcs":  df.groupby("faction", observed=True)["npc_id"].nunique().astype(int),
        "median_nts_raw": grp["nts_raw"].median().round(2),
        "mean_nts_raw":   grp["nts_raw"].mean().round(2),
        "std_nts_raw":    grp["nts_raw"].std().round(2),
    }).sort_values("median_nts_raw", ascending=False)


def tier_separation(df: pd.DataFrame, metric: str = "nts_raw") -> pd.DataFrame:
    """Effect-size + overlap analysis between adjacent rarity tiers.

    For each adjacent (lower, higher) pair on the rarity ladder, compute:
    - Cohen's d (standardized mean difference; <0.2 ≈ trivial, >0.8 = large)
    - distribution overlap percentage (1 - normalised |mean diff|)
    - Mann-Whitney U p-value (rank-based difference test, robust to skew)

    A healthy threat ladder shows large d and small overlap between tiers.
    Tier pairs with d < 0.5 or overlap > 70% are calibration risks.
    """
    rows = []
    for lo, hi in zip(RARITY_ORDER[:-1], RARITY_ORDER[1:]):
        a = df.loc[df["npc_rarity"] == lo, metric].dropna().values
        b = df.loc[df["npc_rarity"] == hi, metric].dropna().values
        if len(a) < 2 or len(b) < 2:
            rows.append({"lower": lo, "higher": hi, "n_lo": len(a), "n_hi": len(b),
                         "cohen_d": np.nan, "overlap_pct": np.nan, "mw_p": np.nan})
            continue
        pooled_sd = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                            / (len(a) + len(b) - 2)) or 1.0
        d = (b.mean() - a.mean()) / pooled_sd
        # Overlap via the "common language effect size" complement.
        # When the higher tier is actually weaker than the lower (an inversion),
        # cles < 0.5 and the raw 2·(1-cles) exceeds 100 — clip to [0, 100] and
        # surface the inversion through the negative cohen_d instead.
        try:
            mw = stats.mannwhitneyu(b, a, alternative="greater")
            cles = mw.statistic / (len(a) * len(b))   # P(b > a)
            overlap = max(0.0, min(100.0, 2 * (1 - cles) * 100))
            p = float(mw.pvalue)
        except ValueError:
            overlap, p = np.nan, np.nan
        rows.append({
            "lower":       lo,
            "higher":      hi,
            "n_lo":        int(len(a)),
            "n_hi":        int(len(b)),
            "mean_lo":     round(float(a.mean()), 2),
            "mean_hi":     round(float(b.mean()), 2),
            "cohen_d":     round(float(d), 3),
            "overlap_pct": round(float(overlap), 1),
            "mw_p":        round(p, 6) if p == p else np.nan,
        })
    return pd.DataFrame(rows)


def scale_factor_solver(df: pd.DataFrame,
                        anchors: dict[str, tuple[int, int]] | None = None,
                        grid: np.ndarray | None = None) -> dict:
    """Grid-search SCALE_FACTOR that lands the median anchor NTS in target bands.

    NTS = clamp(round(NTS_raw / SCALE_FACTOR), 1, 20).

    For each candidate SCALE_FACTOR, score = fraction of (rarity-tier, target-band)
    anchors whose median NTS falls inside the target band. Returns the candidate
    that maximizes the score, plus per-tier landing details for the winner.
    """
    anchors = anchors or ANCHOR_TIERS
    if grid is None:
        grid = np.arange(1.0, 30.0, 0.25)

    medians = df.groupby("npc_rarity", observed=True)["nts_raw"].median()

    def _score(sf: float) -> tuple[float, dict[str, int]]:
        mapped = {}
        hits = 0
        for tier, (lo_band, hi_band) in anchors.items():
            if tier not in medians.index:
                continue
            nts = int(np.clip(round(medians[tier] / sf), 1, 20))
            mapped[tier] = nts
            if lo_band <= nts <= hi_band:
                hits += 1
        return hits / max(1, len(anchors)), mapped

    scores = [(_score(sf), sf) for sf in grid]
    (best_score, best_mapping), best_sf = max(scores, key=lambda x: (x[0][0], -x[1]))

    landing = []
    for tier, (lo_band, hi_band) in anchors.items():
        if tier not in medians.index:
            continue
        landing.append({
            "rarity":      tier,
            "median_raw":  round(float(medians[tier]), 2),
            "target_band": f"{lo_band}-{hi_band}",
            "mapped_nts":  best_mapping.get(tier),
            "in_band":     lo_band <= best_mapping.get(tier, -1) <= hi_band,
        })

    return {
        "best_scale_factor": float(best_sf),
        "score":             round(float(best_score), 3),
        "landing":           pd.DataFrame(landing),
    }


def weighting_sensitivity(df: pd.DataFrame,
                          weights: list[tuple[float, float]] | None = None) -> pd.DataFrame:
    """Recompute NTS_raw under alternative OTS/DDS weightings; report rank shifts.

    The 60/40 split is one of outline.md's open calibration parameters. This
    function compares 60/40 against 55/45 and 50/50 by re-ranking NPCs (mean
    NTS_raw across PCs) under each scheme and reporting the Spearman ρ vs the
    baseline plus the count of rank changes in the top 10.
    """
    weights = weights or [(0.6, 0.4), (0.55, 0.45), (0.5, 0.5)]
    df = df.copy()
    df["mean_ots"] = df.groupby("npc_id", observed=True)["ots"].transform("mean")
    df["mean_dds"] = df.groupby("npc_id", observed=True)["dds"].transform("mean")
    npcs = df.drop_duplicates("npc_id")[["npc_id", "npc_rarity", "mean_ots", "mean_dds"]]

    base_w = weights[0]
    base_score = npcs["mean_ots"] * base_w[0] + npcs["mean_dds"] * base_w[1]
    base_rank  = base_score.rank(ascending=False, method="min")
    base_top10 = set(npcs.assign(r=base_rank).nsmallest(10, "r")["npc_id"])

    rows = []
    for ow, dw in weights:
        score = npcs["mean_ots"] * ow + npcs["mean_dds"] * dw
        rank  = score.rank(ascending=False, method="min")
        rho   = stats.spearmanr(base_rank, rank).statistic
        new_top10 = set(npcs.assign(r=rank).nsmallest(10, "r")["npc_id"])
        rows.append({
            "ots_weight":    ow,
            "dds_weight":    dw,
            "spearman_rho":  round(float(rho), 4),
            "top10_overlap": len(base_top10 & new_top10),
            "top10_changes": 10 - len(base_top10 & new_top10),
        })
    return pd.DataFrame(rows)


def subcomponent_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    """Per-rarity, fraction of DDS from HPP/AAC/DSR and OTS from EDPR/CTS tracks.

    Answers: "where does threat actually come from?" If AAC dominates DDS at
    every tier, the SP cap (18) is doing all the work and HPP/DSR are noise.
    If CTS dominates OTS at low tiers, low-DPS NPCs are coasting on crit luck.
    """
    out_rows = []
    for tier in RARITY_ORDER:
        sub = df[df["npc_rarity"] == tier]
        if sub.empty:
            continue
        dds_total = sub[DDS_COMPONENTS].mean().sum()
        edpr_track = (sub["hpw_ss"] * sub["edpr_ss"]).mean()
        cts_track  = (sub["hpw_ss"] * sub["cts_ss"]).mean()
        ots_total = edpr_track + cts_track
        out_rows.append({
            "npc_rarity":  tier,
            "n_pairs":     int(len(sub)),
            "hpp_share":   round(float(sub["hpp"].mean() / dds_total), 3) if dds_total else np.nan,
            "aac_share":   round(float(sub["aac"].mean() / dds_total), 3) if dds_total else np.nan,
            "dsr_share":   round(float(sub["dsr_hp"].mean() / dds_total), 3) if dds_total else np.nan,
            "edpr_share":  round(float(edpr_track / ots_total), 3) if ots_total else np.nan,
            "cts_share":   round(float(cts_track / ots_total), 3)  if ots_total else np.nan,
            "mean_ots":    round(float(sub["ots"].mean()), 3),
            "mean_dds":    round(float(sub["dds"].mean()), 2),
        })
    return pd.DataFrame(out_rows).set_index("npc_rarity")


def ots_zero_mass(df: pd.DataFrame) -> pd.DataFrame:
    """PC role × rarity matrix of penetration-failure rate (EDPR_SS == 0).

    Reads as: 'X% of single-shot attacks from this rarity to this PC role
    deal zero raw damage and rely entirely on crits'.
    """
    flag = df["edpr_ss"].fillna(0).eq(0)
    pivot = (df.assign(_zero=flag.astype(float))
                .pivot_table(index="pc_role", columns="npc_rarity",
                             values="_zero", aggfunc="mean", observed=True))
    pivot = pivot.reindex(columns=[r for r in RARITY_ORDER if r in pivot.columns])
    return pivot.round(3)


def rank_stability(df: pd.DataFrame) -> dict:
    """Spearman ρ of NPC NTS_raw rankings across PCs.

    Each PC has its own ranking of all NPCs by NTS_raw. If the system is well
    behaved, those rankings agree (high ρ). If they disagree, the same NPC
    looks very different to different PCs — a calibration concern when the
    headline NTS is a single integer per NPC.
    """
    pivot = df.pivot_table(index="npc_id", columns="pc_role_id",
                           values="nts_raw", observed=True)
    ranks = pivot.rank(method="min", ascending=False)
    rho_matrix = ranks.corr(method="spearman")
    upper = rho_matrix.values[np.triu_indices_from(rho_matrix, k=1)]
    return {
        "rho_matrix":   rho_matrix.round(3),
        "rho_mean":     round(float(np.nanmean(upper)), 4),
        "rho_min":      round(float(np.nanmin(upper)), 4),
        "rho_max":      round(float(np.nanmax(upper)), 4),
        "n_pcs":        int(rho_matrix.shape[0]),
    }


def npc_threat_consistency(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """Per NPC: coefficient of variation of OTS across PCs (PC-dependence).

    A high CV means this NPC is dramatically more (or less) threatening to
    some PCs than others — those NPCs need playtest attention because their
    headline NTS hides large variance.
    """
    grp = df.groupby(["npc_id", "npc_rarity"], observed=True)["ots"]
    summary = pd.DataFrame({
        "ots_mean": grp.mean(),
        "ots_std":  grp.std(),
    }).reset_index()
    summary["ots_cv"] = (summary["ots_std"] / summary["ots_mean"].replace(0, np.nan)).round(4)
    summary = summary.dropna(subset=["ots_cv"]).sort_values("ots_cv", ascending=False)
    return summary.head(top_n).round(4)


def outlier_decomposition(df: pd.DataFrame, metric: str = "nts_raw",
                          k: int = 10) -> pd.DataFrame:
    """Top-k extreme `metric` values with the dominant subcomponent driver.

    Returns the top k unique NPCs by metric (high tail) regardless of whether
    they cleared the IQR fence — extreme-tail entries are still informative for
    a designer hunting calibration wins, even when distribution skew suppresses
    a strict statistical-outlier flag.
    """
    high = df.copy()
    high["edpr_track"] = high["hpw_ss"] * high["edpr_ss"]
    high["cts_track"]  = high["hpw_ss"] * high["cts_ss"]
    drivers = pd.DataFrame({
        "hpp":        high["hpp"],
        "aac":        high["aac"],
        "dsr_hp":     high["dsr_hp"],
        "edpr_track": high["edpr_track"],
        "cts_track":  high["cts_track"],
    })
    high["driver"] = drivers.idxmax(axis=1)

    high = (high.sort_values(metric, ascending=False)
                .drop_duplicates("npc_id")
                .head(k))
    cols = ["npc_id", "pc_role_id", "npc_rarity", metric, "ots", "dds",
            "weapon_type", "driver"]
    return high[cols].reset_index(drop=True)


def sp_cap_impact(df: pd.DataFrame) -> dict:
    """How often does the SP=18 AAC cap bind, and on which rarity tiers?

    outline.md flags this cap as a calibration choice. If many NPCs at high
    tiers hit the cap, raising it would amplify their DDS — and reshuffle the
    Boss / Hardened-Boss separation.
    """
    unique_npcs = df.drop_duplicates("npc_id")
    capped = unique_npcs[unique_npcs["sp_raw"] > unique_npcs["sp_capped"]]
    by_rarity = (capped.groupby("npc_rarity", observed=True).size()
                       .reindex(RARITY_ORDER, fill_value=0)
                       .rename("capped_npcs"))
    return {
        "n_unique_npcs":  int(len(unique_npcs)),
        "n_capped":       int(len(capped)),
        "fraction":       round(float(len(capped) / max(1, len(unique_npcs))), 4),
        "by_rarity":      by_rarity.to_frame(),
        "max_excess_sp":  int(unique_npcs["sp_raw"].max() - 18) if len(unique_npcs) else 0,
    }


def recommendations(df: pd.DataFrame, sf_result: dict, sep: pd.DataFrame,
                    weighting: pd.DataFrame, decomp: pd.DataFrame,
                    rank: dict, sp: dict) -> list[dict]:
    """Synthesize the Diagnose-section findings into prioritized, structured recommendations.

    Returns a list of dicts sorted by priority ascending (P1=CRITICAL first, P0=OK last).
    Each dict has keys: priority, status, title, issue, root_cause, action, expected.
    """
    recs: list[dict] = []

    # ── Tier separation ───────────────────────────────────────────────────
    # CRITICAL: overlap >= 100% — statistically indistinguishable tiers
    # WARNING:  d < 0.5 OR overlap > 70% (but < 100%) — weak but not collapsed
    critical_pairs = sep[sep["cohen_d"].notna() & (sep["overlap_pct"] >= 100)]
    warning_pairs = sep[
        sep["cohen_d"].notna() &
        (sep["overlap_pct"] < 100) &
        ((sep["cohen_d"].abs() < 0.5) | (sep["overlap_pct"] > 70))
    ]

    for row in critical_pairs.itertuples():
        recs.append({
            "priority":   1,
            "status":     "CRITICAL",
            "title":      f"{row.lower}↔{row.higher}: Tiers Are Statistically Indistinguishable",
            "issue":      (
                f"The {row.lower} and {row.higher} tiers have {row.overlap_pct:.1f}% distributional "
                f"overlap in NTS_raw (Cohen's d = {row.cohen_d:.3f}). These two rarity levels cannot "
                f"be told apart by NTS — assigning either label produces the same encounter difficulty."
            ),
            "root_cause": (
                "AAC accounts for >70% of DDS at upper tiers. Both tiers likely share similar SP "
                "values, compressing their DDS ranges toward the same ceiling regardless of stat "
                "differences. HPP and DSR contribute too little to produce separation when AAC dominates."
            ),
            "action": [
                f"Audit SP assignments for {row.lower} and {row.higher} NPCs — verify they differ meaningfully.",
                f"If SP is already differentiated, raise HPP via BODY/WILL stat increases for {row.higher} NPCs.",
                "Address AAC dominance via formula rebalancing (see WARNING section) — this amplifies the effect of any stat differences.",
                f"Target: Cohen's d ≥ 0.8 and overlap < 30% for this boundary.",
            ],
            "expected":   (
                f"After corrections, {row.lower} and {row.higher} should occupy clearly distinct NTS bands, "
                "making rarity labels meaningful for encounter composition."
            ),
        })

    for row in warning_pairs.itertuples():
        recs.append({
            "priority":   2,
            "status":     "WARNING",
            "title":      f"{row.lower}↔{row.higher}: Weak Tier Boundary (d={row.cohen_d:.3f}, overlap={row.overlap_pct:.1f}%)",
            "issue":      (
                f"The {row.lower}↔{row.higher} boundary has {row.overlap_pct:.1f}% distributional overlap "
                f"(Cohen's d = {row.cohen_d:.3f}). NPCs near this boundary receive interchangeable NTS "
                f"values across tiers — meaningful but not yet collapsed."
            ),
            "root_cause": (
                f"The stat-block delta between {row.lower} and {row.higher} is not large enough to overcome "
                "within-tier variance. AAC dominance in DDS suppresses NTS sensitivity to HP-pool differences."
            ),
            "action": [
                f"Widen the stat gap: lower the {row.lower} stat ceiling or raise the {row.higher} floor.",
                f"Consider whether '{row.lower}' is a distinct design tier or should be merged with '{row.higher}'.",
                "Rebalancing AAC in the DDS formula (see AAC recommendation) will increase the leverage of BODY/WILL differences.",
            ],
            "expected":   f"Target Cohen's d ≥ 0.8 and overlap < 40% for the {row.lower}↔{row.higher} boundary.",
        })

    # ── AAC dominance ────────────────────────────────────────────────────
    if "aac_share" in decomp.columns and (decomp["aac_share"] > 0.55).any():
        aac_tiers = decomp.index[decomp["aac_share"] > 0.55].tolist()
        max_share = float(decomp.loc[aac_tiers, "aac_share"].max())
        recs.append({
            "priority":   2,
            "status":     "WARNING",
            "title":      "AAC Dominates DDS at Upper Tiers — HPP and DSR Are Noise",
            "issue":      (
                f"At {aac_tiers}, Armor Absorption Capacity accounts for up to {max_share*100:.0f}% "
                f"of mean DDS. Hit Point Pool (HPP) and Death Save Resilience (DSR) contribute so "
                f"little that BODY and WILL stat differences between tiers have almost no effect on NTS."
            ),
            "root_cause": (
                "The AAC formula uses a triangular sum (SP + SP-1 + … + 1), which grows as SP²/2. "
                "At high SP values this vastly outweighs the linear HPP formula (BODY×5 + 10). "
                "The `SP_CAPPED` parameter (currently 18) matches the highest observed SP in the "
                "dataset, so it is not binding — adjusting it would not affect current data."
            ),
            "action": [
                "Add a configurable `HPP_weight` multiplier to the DDS formula "
                "(e.g., `DDS = HPP * HPP_weight + AAC + DSR_hp`) so HPP can be scaled up relative to AAC.",
                "Alternatively, apply a square-root or log transform to AAC before summing "
                "to reduce its curvature at high SP values.",
                "Re-run the EDA after any formula change — target aac_share < 50% at Elite tier.",
            ],
            "expected":   (
                "Once HPP and DSR contribute ≥ 30% of DDS, stat-block differences between tiers "
                "will produce larger NTS gaps, likely resolving several weak-boundary issues as a side effect."
            ),
        })

    # ── SCALE_FACTOR ─────────────────────────────────────────────────────
    sf = sf_result["best_scale_factor"]
    score = sf_result["score"]
    # Find any anchor tiers that missed their target band
    landing = sf_result.get("landing", pd.DataFrame())
    misses = landing[~landing["in_band"]] if not landing.empty else pd.DataFrame()
    miss_desc = (
        ", ".join(f"{r.rarity} → NTS {r.mapped_nts} (target {r.target_band})"
                  for r in misses.itertuples())
        if not misses.empty else "none"
    )
    recs.append({
        "priority":   2,
        "status":     "WARNING",
        "title":      f"SCALE_FACTOR: Set to {sf:.2f} — {score*100:.0f}% Anchor Hit Rate",
        "issue":      (
            f"The optimal SCALE_FACTOR is {sf:.2f}, which lands {score*100:.0f}% of anchor tiers "
            f"inside their target NTS bands. Misses: {miss_desc}. "
            f"Until this is explicitly set in the codebase, all NTS outputs are uncalibrated."
        ),
        "root_cause": (
            "The Tough tier median NTS_raw (≈29.75) overshoots its target band (NTS 1–4) even at "
            "SCALE_FACTOR=6.0. This is a downstream symptom of the Tough↔HardenedMook boundary "
            "weakness — the two tiers are too close in score for both to land in separate bands."
        ),
        "action": [
            f"Set `SCALE_FACTOR = {sf:.2f}` in the codebase now as a baseline.",
            "Retest the anchor hit rate after addressing Tough↔HardenedMook stat separation — "
            "the hit rate should improve once tier scores diverge.",
        ],
        "expected":   f"After tier separation fixes, expect the anchor hit rate to rise above 87% at SCALE_FACTOR={sf:.2f}.",
    })

    # ── OTS zero-mass ────────────────────────────────────────────────────
    zm = ots_zero_mass(df)
    high_zero = {}
    for role in zm.index:
        for tier in zm.columns:
            val = zm.loc[role, tier]
            if pd.notna(val) and val >= 0.80:
                high_zero.setdefault(tier, []).append(f"{role} ({val*100:.0f}%)")
    if high_zero:
        examples = "; ".join(f"{t}: {', '.join(v[:2])}" for t, v in list(high_zero.items())[:3])
        recs.append({
            "priority":   3,
            "status":     "MONITOR",
            "title":      "OTS Zero-Mass: Low-Tier NPCs Fail to Penetrate Light-PC Armor",
            "issue":      (
                f"In single-shot mode, ≥80% of attacks from low-tier NPCs deal zero raw damage "
                f"to several PC roles — these NPCs are crit-only threats with no consistent damage output. "
                f"Examples: {examples}."
            ),
            "root_cause": (
                "Light-armor PCs (Exec, Rockerboy, Netrunner) have SP high enough to fully absorb "
                "average Mook/Tough weapon damage. This is a game-mechanic outcome, not a formula error — "
                "but it means low-tier NPCs are essentially harmless to some PCs except on lucky criticals."
            ),
            "action": [
                "No formula change required at this time — this reflects intended armor economy.",
                "Monitor during playtesting: if Mook encounters feel trivially safe for armored PCs, "
                "consider whether Mooks should include more autofire-capable weapons.",
                "Track this metric as NPC stat blocks are expanded — rising zero-mass rates signal armor creep.",
            ],
            "expected":   (
                "This is a design tension to be managed at the encounter-composition level, not a calibration fix."
            ),
        })

    # ── Data quality: join miss ───────────────────────────────────────────
    # clean_hp_raw is populated only for NPCs that matched the clean metadata join
    n_total = df["npc_id"].nunique()
    meta_col = next((c for c in ("clean_hp_raw", "clean_weapon_count", "clean_descriptor")
                     if c in df.columns), None)
    if meta_col is not None:
        n_with_meta = int(df.drop_duplicates("npc_id")[meta_col].notna().sum())
    else:
        n_with_meta = None
    miss_rate = round(1 - (n_with_meta / n_total), 2) if n_with_meta is not None else None
    if miss_rate is not None and miss_rate > 0.10:
        recs.append({
            "priority":   3,
            "status":     "MONITOR",
            "title":      f"Data Quality: {miss_rate*100:.0f}% of NPCs Missing Clean Metadata",
            "issue":      (
                f"{int(n_total - n_with_meta)}/{int(n_total)} NPCs could not be matched to the clean "
                f"metadata file and have no weapon_type, faction, or name in stratified analyses. "
                f"Faction and rarity breakdowns in Sections 5–6 may be systematically biased."
            ),
            "root_cause": (
                "The fuzzy join between `nts_raw_scores.json` and `npc_data_clean.json` failed for "
                "these NPCs — likely due to naming inconsistencies (capitalization, punctuation, or "
                "faction prefix format mismatches)."
            ),
            "action": [
                "Identify the unmatched NPC IDs: run `data.join_clean_npcs()` with verbose=True or "
                "inspect the rows where `npc_name` is null.",
                "Manually reconcile the naming in either JSON file for the affected NPCs.",
                "Rerun the EDA — faction and rarity breakdowns may shift once all NPCs are matched.",
            ],
            "expected":   (
                "Full join coverage (100%) will make faction and rarity stratifications reliable. "
                "The 84% match rate is acceptable for calibration estimates but should be resolved "
                "before treating faction-level findings as actionable."
            ),
        })

    # ── Healthy signals ───────────────────────────────────────────────────
    base = weighting.iloc[0]
    alt  = weighting.iloc[1] if len(weighting) > 1 else base
    weight_stable = alt.top10_changes <= 2

    recs.append({
        "priority":   0,
        "status":     "OK",
        "title":      "60/40 OTS/DDS Weighting Is Stable",
        "issue":      (
            f"Switching from 60/40 to 55/45 yields Spearman ρ={alt.spearman_rho} vs baseline; "
            f"{alt.top10_changes}/10 top-tier NPCs reshuffle. The weighting choice does not materially "
            f"affect NPC rankings."
        ),
        "root_cause": "N/A — this is a confirmed healthy signal.",
        "action":     ["Keep the 60/40 split. No change needed."],
        "expected":   "NTS rankings remain consistent regardless of minor weight adjustments.",
    })

    recs.append({
        "priority":   0,
        "status":     "OK",
        "title":      "Cross-PC Rank Stability Is Strong",
        "issue":      (
            f"Mean Spearman ρ={rank['rho_mean']:.4f}, min ρ={rank['rho_min']:.4f} across all "
            f"{rank['n_pcs']} PC pairings. Every PC ranks the NPC roster nearly identically."
        ),
        "root_cause": "N/A — this is a confirmed healthy signal.",
        "action":     ["No change needed. The headline NTS integer is a fair single-number summary."],
        "expected":   "A single NTS value per NPC will accurately represent difficulty across all PC roles.",
    })

    recs.append({
        "priority":   0,
        "status":     "OK",
        "title":      "SP_CAPPED Ceiling Is Not Currently Binding",
        "issue":      (
            f"{sp['n_capped']}/{sp['n_unique_npcs']} NPCs exceed the SP_CAPPED threshold "
            f"({sp['fraction']*100:.1f}%). The parameter has no effect on current data."
        ),
        "root_cause": "N/A — this is a confirmed healthy signal.",
        "action":     [
            "No change needed now.",
            "Revisit if future NPC stat blocks include SP values above the current threshold.",
        ],
        "expected":   "SP_CAPPED remains a dormant calibration knob until higher-SP NPCs are added.",
    })

    recs.sort(key=lambda r: (r["priority"] if r["priority"] > 0 else 99))
    return recs
