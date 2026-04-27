from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde, spearmanr

from eda.data import RARITY_ORDER, LABELS, CORE_METRICS, DDS_COMPONENTS

plt.rcParams.update({
    "figure.dpi":      130,
    "font.size":       9,
    "axes.titlesize":  10,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

_RARITY_COLORS = plt.get_cmap("RdYlGn_r")(np.linspace(0.1, 0.9, len(RARITY_ORDER)))
_RARITY_COLOR_MAP = dict(zip(RARITY_ORDER, _RARITY_COLORS))


def _save(fig, out: Path, name: str) -> Path:
    path = out / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# 01 ─ Univariate distributions (linear + log companion for OTS) ───────────
def distributions(df: pd.DataFrame, out: Path) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    metrics = CORE_METRICS
    for col, m in enumerate(metrics):
        data = pd.to_numeric(df[m], errors="coerce").dropna()
        # row 0 — linear
        ax = axes[0, col]
        ax.hist(data, bins=30, density=True, alpha=0.55, color="steelblue",
                edgecolor="white", linewidth=0.4)
        if data.nunique() > 1:
            kde = gaussian_kde(data)
            xs = np.linspace(data.min(), data.max(), 300)
            ax.plot(xs, kde(xs), color="navy", lw=1.6)
        ax.axvline(data.mean(),   color="red",    lw=1.1, ls="--",
                   label=f"mean={data.mean():.1f}")
        ax.axvline(data.median(), color="orange", lw=1.1, ls=":",
                   label=f"median={data.median():.1f}")
        ax.set_title(LABELS[m])
        ax.set_xlabel(m)
        ax.legend(fontsize=7)

        # row 1 — log-y companion (highlights heavy right tail / zero mass)
        ax2 = axes[1, col]
        ax2.hist(data, bins=30, color="steelblue", edgecolor="white", linewidth=0.4)
        ax2.set_yscale("log")
        ax2.set_xlabel(m)
        ax2.set_ylabel("count (log)")
        ax2.set_title(f"{m} — log-y (zero-mass = {(data == 0).mean()*100:.1f}%)")

    fig.suptitle("Metric distributions — linear (top) and log-y (bottom)",
                 fontsize=12, y=1.02)
    return _save(fig, out, "01_distributions.png")


# 02 ─ Rarity violin + strip ───────────────────────────────────────────────
def rarity_violins(df: pd.DataFrame, out: Path) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    for ax, m in zip(axes, CORE_METRICS):
        groups, labels = [], []
        for r in RARITY_ORDER:
            vals = df.loc[df["npc_rarity"] == r, m].dropna().values
            if len(vals):
                groups.append(vals)
                labels.append(f"{r}\nn={len(vals)}")
        parts = ax.violinplot(groups, showmedians=True, showextrema=False)
        for pc, color in zip(parts["bodies"], _RARITY_COLORS):
            pc.set_facecolor(color); pc.set_alpha(0.6)
        for i, vals in enumerate(groups, start=1):
            jitter = np.random.default_rng(i).normal(0, 0.05, size=len(vals))
            ax.scatter(np.full_like(vals, i, dtype=float) + jitter, vals,
                       s=4, alpha=0.25, color="black")
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels, rotation=38, ha="right", fontsize=7)
        ax.set_title(LABELS[m]); ax.set_ylabel(m)
    fig.suptitle("Metric distribution by rarity tier (violin + per-pair points)",
                 fontsize=12, y=1.02)
    return _save(fig, out, "02_rarity_violins.png")


# 03 ─ Pairwise scatter with KDE marginals + Spearman/Pearson ─────────────
def pair_scatter(df: pd.DataFrame, out: Path) -> Path:
    pairs = [("ots", "dds"), ("ots", "nts_raw"), ("dds", "nts_raw")]
    fig = plt.figure(figsize=(15, 5), constrained_layout=True)
    for i, (x, y) in enumerate(pairs, start=1):
        ax = fig.add_subplot(1, 3, i)
        sub = df[[x, y, "npc_rarity"]].dropna()
        codes = sub["npc_rarity"].cat.codes
        ax.scatter(sub[x], sub[y], c=codes, cmap="RdYlGn_r",
                   s=10, alpha=0.45)
        # LOWESS-ish trend via simple binned median
        order = sub.sort_values(x)
        if len(order) >= 30:
            bins = pd.qcut(order[x], q=12, duplicates="drop")
            tr = order.groupby(bins, observed=True)[y].median()
            xs_mid = order.groupby(bins, observed=True)[x].median()
            ax.plot(xs_mid, tr, color="black", lw=1.3, alpha=0.7, label="binned median")
        r_p = sub[[x, y]].corr().iloc[0, 1]
        r_s = spearmanr(sub[x], sub[y]).statistic
        ax.set_xlabel(x); ax.set_ylabel(y)
        ax.set_title(f"{x} vs {y}\nPearson r={r_p:.3f}  |  Spearman ρ={r_s:.3f}")
        if len(order) >= 30:
            ax.legend(fontsize=7)
    fig.suptitle("Pairwise relationships (colour = rarity tier)",
                 fontsize=12, y=1.02)
    return _save(fig, out, "03_pair_scatter.png")


# 04 ─ Side-by-side Pearson + Spearman heatmaps ───────────────────────────
def correlation_heatmaps(corrs: dict[str, pd.DataFrame], out: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    for ax, (kind, mat) in zip(axes, corrs.items()):
        im = ax.imshow(mat, vmin=-1, vmax=1, cmap="coolwarm")
        ax.set_xticks(range(len(mat.columns)))
        ax.set_yticks(range(len(mat.index)))
        ax.set_xticklabels(mat.columns, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(mat.index, fontsize=8)
        for i in range(len(mat.index)):
            for j in range(len(mat.columns)):
                val = mat.iloc[i, j]
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if abs(val) > 0.6 else "black")
        ax.set_title(f"{kind.capitalize()} correlation")
        fig.colorbar(im, ax=ax, shrink=0.7)
    fig.suptitle("Correlation matrices (metrics + subcomponents)",
                 fontsize=12, y=1.04)
    return _save(fig, out, "04_correlations.png")


# 05 ─ PC role × rarity NTS heatmap ────────────────────────────────────────
def pc_role_rarity_heatmap(df: pd.DataFrame, out: Path) -> Path:
    pivot = (df.pivot_table(index="pc_role", columns="npc_rarity",
                            values="nts_raw", aggfunc="mean", observed=True)
               .reindex(columns=[r for r in RARITY_ORDER if r in df["npc_rarity"].cat.categories]))
    fig, ax = plt.subplots(figsize=(10, max(4, 0.45 * len(pivot))),
                           constrained_layout=True)
    im = ax.imshow(pivot.values, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_yticks(range(len(pivot.index)))
    ax.set_xticklabels(pivot.columns, rotation=38, ha="right")
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                        color="white" if v < pivot.values.mean() else "black",
                        fontsize=8)
    fig.colorbar(im, ax=ax, label="mean NTS_raw")
    ax.set_title("Mean NTS_raw by PC role × NPC rarity")
    return _save(fig, out, "05_pc_role_rarity_heatmap.png")


# 06 ─ DDS subcomponent stacked bar ───────────────────────────────────────
def dds_decomposition(df: pd.DataFrame, out: Path) -> Path:
    means = (df.groupby("npc_rarity", observed=True)[DDS_COMPONENTS].mean()
                .reindex(RARITY_ORDER).dropna(how="all"))
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    bottom = np.zeros(len(means))
    palette = ["#5a9bd4", "#ed7d31", "#70ad47"]
    for col, color in zip(DDS_COMPONENTS, palette):
        ax.bar(means.index, means[col].values, bottom=bottom, color=color,
               edgecolor="white", lw=0.5, label=col.upper())
        bottom += means[col].values
    ax.set_xticks(range(len(means)))
    ax.set_xticklabels(means.index, rotation=38, ha="right")
    ax.set_ylabel("mean HP-equivalent")
    ax.set_title("DDS decomposition - HPP / AAC / DSR contribution by rarity")
    ax.legend()
    return _save(fig, out, "06_dds_decomposition.png")


# 07 ─ OTS subcomponent decomposition ─────────────────────────────────────
def ots_decomposition(df: pd.DataFrame, out: Path) -> Path:
    df = df.copy()
    df["edpr_track"] = df["hpw_ss"] * df["edpr_ss"]
    df["cts_track"]  = df["hpw_ss"] * df["cts_ss"]
    means = (df.groupby("npc_rarity", observed=True)[["edpr_track", "cts_track"]].mean()
                .reindex(RARITY_ORDER).dropna(how="all"))
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    bottom = np.zeros(len(means))
    for col, color in zip(["edpr_track", "cts_track"], ["#4472c4", "#c0504d"]):
        ax.bar(means.index, means[col].values, bottom=bottom, color=color,
               edgecolor="white", lw=0.5,
               label=("HPW * EDPR (raw damage)" if col == "edpr_track"
                      else "HPW * CTS (crit threat)"))
        bottom += means[col].values
    ax.set_xticks(range(len(means)))
    ax.set_xticklabels(means.index, rotation=38, ha="right")
    ax.set_ylabel("mean OTS contribution")
    ax.set_title("OTS decomposition - raw-damage vs crit-threat track by rarity")
    ax.legend()
    return _save(fig, out, "07_ots_decomposition.png")


# 08 ─ OTS zero-mass heatmap ──────────────────────────────────────────────
def ots_zero_mass_heatmap(zero_mass_pivot: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.4 * len(zero_mass_pivot))),
                           constrained_layout=True)
    im = ax.imshow(zero_mass_pivot.values, aspect="auto", cmap="Reds", vmin=0, vmax=1)
    ax.set_xticks(range(len(zero_mass_pivot.columns)))
    ax.set_yticks(range(len(zero_mass_pivot.index)))
    ax.set_xticklabels(zero_mass_pivot.columns, rotation=38, ha="right")
    ax.set_yticklabels(zero_mass_pivot.index)
    for i in range(zero_mass_pivot.shape[0]):
        for j in range(zero_mass_pivot.shape[1]):
            v = zero_mass_pivot.values[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v*100:.0f}%", ha="center", va="center",
                        color="white" if v > 0.5 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="P(EDPR_SS = 0)")
    ax.set_title("Penetration-failure rate by PC role × NPC rarity")
    return _save(fig, out, "08_ots_zero_mass.png")


# 09 ─ NPC threat consistency (CV of OTS across PCs) ──────────────────────
def npc_consistency(consistency: pd.DataFrame, out: Path) -> Path:
    if consistency.empty:
        fig, ax = plt.subplots(figsize=(8, 3), constrained_layout=True)
        ax.text(0.5, 0.5, "No NPCs with measurable OTS variance.",
                ha="center", va="center", fontsize=11)
        ax.set_axis_off()
        return _save(fig, out, "09_npc_consistency.png")

    fig, ax = plt.subplots(figsize=(10, max(4, 0.32 * len(consistency))),
                           constrained_layout=True)
    colors = [_RARITY_COLOR_MAP.get(r, "gray") for r in consistency["npc_rarity"]]
    ax.barh(consistency["npc_id"][::-1], consistency["ots_cv"][::-1],
            color=colors[::-1], edgecolor="white", lw=0.4)
    ax.set_xlabel("Coefficient of variation of OTS across PCs")
    ax.set_title(f"Top-{len(consistency)} most PC-dependent NPCs (high CV = inconsistent threat)")
    return _save(fig, out, "09_npc_consistency.png")


# 10 ─ Faction profile box plot ───────────────────────────────────────────
def faction_box(df: pd.DataFrame, out: Path) -> Path:
    factions = (df.groupby("faction", observed=True)["nts_raw"]
                  .median().sort_values(ascending=False).index.tolist())
    data = [df.loc[df["faction"] == f, "nts_raw"].dropna().values for f in factions]
    counts = [df[df["faction"] == f]["npc_id"].nunique() for f in factions]

    fig, ax = plt.subplots(figsize=(max(8, 0.6 * len(factions)), 5),
                           constrained_layout=True)
    bp = ax.boxplot(data, patch_artist=True,
                    medianprops=dict(color="black", lw=1.4))
    for patch in bp["boxes"]:
        patch.set_facecolor("steelblue"); patch.set_alpha(0.55)
    ax.set_xticks(range(1, len(factions) + 1))
    ax.set_xticklabels([f"{f}\n(n={c})" for f, c in zip(factions, counts)],
                       rotation=38, ha="right", fontsize=8)
    ax.set_ylabel("NTS_raw")
    ax.set_title("NTS_raw distribution by faction (sorted by median)")
    return _save(fig, out, "10_faction_box.png")


# 11 ─ Tier separation effect-size strip ──────────────────────────────────
def tier_separation_strip(sep: pd.DataFrame, out: Path) -> Path:
    sep = sep.dropna(subset=["cohen_d"]).copy()
    fig, axes = plt.subplots(1, 2, figsize=(13, 4), constrained_layout=True)
    labels = sep["lower"] + " → " + sep["higher"]
    colors = ["#c0504d" if abs(d) < 0.5 else ("#ed7d31" if abs(d) < 0.8 else "#70ad47")
              for d in sep["cohen_d"]]

    axes[0].barh(labels[::-1], sep["cohen_d"][::-1], color=colors[::-1])
    axes[0].axvline(0.5, color="gray", ls=":", lw=1)
    axes[0].axvline(0.8, color="gray", ls="--", lw=1)
    axes[0].set_xlabel("Cohen's d (negative = inverted tier)")
    axes[0].set_title("Effect size between adjacent tiers")

    axes[1].barh(labels[::-1], sep["overlap_pct"][::-1],
                 color=["#c0504d" if o > 70 else "#70ad47" for o in sep["overlap_pct"]][::-1])
    axes[1].axvline(70, color="gray", ls="--", lw=1)
    axes[1].set_xlabel("Distribution overlap %")
    axes[1].set_title("Overlap between adjacent tiers (lower is better)")

    fig.suptitle("Tier separation diagnostics for NTS_raw", fontsize=12, y=1.04)
    return _save(fig, out, "11_tier_separation.png")


# 12 ─ Weighting sensitivity (slope-style) ────────────────────────────────
def weighting_sensitivity_plot(weighting: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
    labels = [f"{int(o*100)}/{int(d*100)}" for o, d in
              zip(weighting["ots_weight"], weighting["dds_weight"])]
    ax.plot(labels, weighting["spearman_rho"], "o-", color="navy", lw=2)
    for x, y in zip(labels, weighting["spearman_rho"]):
        ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=9)
    ax.set_ylim(0.9, 1.005)
    ax.set_ylabel("Spearman ρ vs 60/40 baseline")
    ax2 = ax.twinx()
    ax2.bar(labels, weighting["top10_changes"], color="orange", alpha=0.3,
            label="top-10 changes")
    ax2.set_ylabel("# of top-10 NPCs that reshuffle", color="darkorange")
    ax.set_title("Weighting sensitivity — agreement vs 60/40 baseline")
    return _save(fig, out, "12_weighting_sensitivity.png")


# 13 ─ SP cap impact ──────────────────────────────────────────────────────
def sp_cap_impact_plot(df: pd.DataFrame, out: Path) -> Path:
    unique = df.drop_duplicates("npc_id")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    axes[0].hist(unique["sp_raw"].dropna(), bins=range(0, int(unique["sp_raw"].max()) + 2),
                 color="steelblue", edgecolor="white")
    axes[0].axvline(18, color="red", ls="--", lw=1.5, label="AAC cap (SP=18)")
    axes[0].set_xlabel("Raw SP"); axes[0].set_ylabel("Unique NPCs")
    axes[0].set_title("Distribution of raw SP across NPCs")
    axes[0].legend()

    capped = unique[unique["sp_raw"] > unique["sp_capped"]]
    counts = (capped.groupby("npc_rarity", observed=True).size()
                    .reindex(RARITY_ORDER, fill_value=0))
    axes[1].bar(counts.index, counts.values, color=_RARITY_COLORS,
                edgecolor="white", lw=0.5)
    axes[1].set_xticks(range(len(counts)))
    axes[1].set_xticklabels(counts.index, rotation=38, ha="right")
    axes[1].set_ylabel("# NPCs hitting the SP=18 cap")
    axes[1].set_title("Cap-binding NPCs by rarity")

    fig.suptitle("SP-cap binding impact on AAC", fontsize=12, y=1.05)
    return _save(fig, out, "13_sp_cap.png")


# 14 ─ NPC count by rarity ────────────────────────────────────────────────
def rarity_counts(df: pd.DataFrame, out: Path) -> Path:
    unique = df.drop_duplicates("npc_id")
    counts = (unique["npc_rarity"].value_counts().reindex(RARITY_ORDER, fill_value=0))
    pair_counts = (df["npc_rarity"].value_counts().reindex(RARITY_ORDER, fill_value=0))
    fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
    ax.bar(counts.index, counts.values, color=_RARITY_COLORS,
           edgecolor="white", lw=0.4, label="unique NPCs")
    ax.set_ylabel("Unique NPCs")
    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels(counts.index, rotation=38, ha="right")
    ax2 = ax.twinx()
    ax2.plot(counts.index, pair_counts.values, "o-", color="darkred",
             label="(PC, NPC) pairs")
    ax2.set_ylabel("(PC, NPC) pairs", color="darkred")
    ax.set_title("Sample size by rarity tier")
    fig.legend(loc="upper right", bbox_to_anchor=(0.97, 0.96))
    return _save(fig, out, "14_rarity_counts.png")
