from __future__ import annotations

from pathlib import Path

from eda import data, profile, analyses, plots, report

NTS_PATH   = Path("outputs/json_output/nts_raw_scores.json")
CLEAN_PATH = Path("outputs/json_output/npc_data_clean.json")
OUT        = Path("outputs/eda_outputs")

_TOTAL_STEPS = 7


def _step(i: int, label: str) -> None:
    print(f"[{i}/{_TOTAL_STEPS}] {label}...")


def _clean_outputs(out: Path) -> None:
    """Wipe report.md, *.png and the tables/ dir so re-runs leave no orphans."""
    if not out.exists():
        return
    for p in out.glob("*.png"):
        p.unlink()
    for f in (out / "tables").glob("*.csv") if (out / "tables").exists() else []:
        f.unlink()
    report_path = out / "report.md"
    if report_path.exists():
        report_path.unlink()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _clean_outputs(OUT)

    df = data.join_clean_npcs(data.load_nts(NTS_PATH), CLEAN_PATH)

    rpt = report.MarkdownReport(OUT / "report.md")
    rpt.add_title(
        "NPC Threat Score — Calibration EDA",
        subtitle=("A seven-section narrative covering data quality, distributions, "
                  "relationships, stratification, and calibration recommendations."),
    )

    # ── 1. FRAME ──────────────────────────────────────────────────────────
    _step(1, "Framing the dataset")
    f = profile.frame(df)
    rpt.add_section("Frame", subtitle="What's in the dataset and what we're trying to answer.")
    rpt.add_paragraph(
        "The NPC Threat Score (NTS) rates Cyberpunk RED NPCs against player characters on a "
        "1–20 scale. Each row in the dataset is a single (PC, NPC) matchup; OTS depends on the "
        "specific defender, while DDS and the Complexity Multiplier depend only on the NPC. "
        "This report follows a Tukey-style EDA progression (Profile → Distribute → Relate → "
        "Stratify → Diagnose → Recommend) tied to the open calibration parameters in "
        "[`docs/outline.md`](../../docs/outline.md)."
    )
    matched, total, frac = f["clean_join_hit"]
    rpt.add_kv({
        "Row grain":           f["row_grain"],
        "Total (PC, NPC) pairs": f["n_rows"],
        "Unique PCs":          f"{f['n_pcs']} ({f['n_pc_roles']} roles)",
        "Unique NPCs":         f["n_npcs"],
        "Factions represented": f["n_factions"],
        "Rarity tiers":        " → ".join(f["rarity_tiers"]),
        "Clean-data join":     f"{matched}/{total} NPCs matched ({frac*100:.0f}%)",
    })

    # ── 2. PROFILE ────────────────────────────────────────────────────────
    _step(2, "Profiling data quality")
    q = profile.quality(df)
    rpt.add_section("Profile", subtitle="Data quality, completeness, and invariant checks.")
    rpt.add_subsection("Null rates")
    rpt.add_table(q["null_rates"], name="profile_nulls",
                  caption="Per-column null rate. Calculated columns should be 0; clean-data joins may be partial.")
    rpt.add_subsection("Cardinality")
    rpt.add_table(q["cardinality"], name="profile_cardinality",
                  caption="Distinct values per column.")
    rpt.add_subsection("Rarity tier counts")
    rpt.add_table(q["rarity_counts"], name="profile_rarity_counts")
    rpt.add_subsection("Integrity checks")
    rpt.add_integrity_block(q["integrity"])

    # ── 3. DISTRIBUTE ─────────────────────────────────────────────────────
    _step(3, "Univariate distributions")
    rpt.add_section("Distribute", subtitle="Univariate distributions of every metric and subcomponent.")
    uni = analyses.univariate(df)
    rpt.add_table(uni, name="univariate_summary",
                  caption="Per-metric summary including skewness, excess kurtosis, and zero-mass fraction.")
    img = plots.distributions(df, OUT)
    rpt.add_image(img, alt="Distributions of NTS_raw, OTS, DDS",
                  caption="Linear (top) and log-y (bottom) histograms. The OTS log-y plot exposes the heavy zero-mass. Many NPCs cannot penetrate PC armor in single-shot mode.")
    img = plots.rarity_violins(df, OUT)
    rpt.add_image(img, alt="Per-rarity violins for each metric",
                  caption="Violin shape + per-pair points per rarity tier. Wide tails indicate within-tier variance; per-tier n is on the x-axis.")

    # ── 4. RELATE ─────────────────────────────────────────────────────────
    _step(4, "Bivariate relationships")
    rpt.add_section("Relate", subtitle="Pairwise and multivariate relationships across metrics + subcomponents.")
    img = plots.pair_scatter(df, OUT)
    rpt.add_image(img, alt="Pairwise scatter of OTS, DDS, NTS_raw",
                  caption="Pearson (linear) and Spearman (monotonic) correlations side-by-side. NTS_raw is dominated by DDS due to the Armor Absorption Capacity (AAC) calculation. As SP rating increases the armor absorption pool quadratically increases.")
    corrs = analyses.correlations(df)
    img = plots.correlation_heatmaps(corrs, OUT)
    rpt.add_image(img, alt="Pearson and Spearman correlation heatmaps",
                  caption="Pearson catches linear correlation and Spearman captures monotonic rank relationships. The heavily-tailed OTS distribution currently makes Spearman the more honest summary.")
    rpt.add_table(corrs["spearman"], name="correlations_spearman",
                  caption="Spearman correlation matrix.")

    # ── 5. STRATIFY ───────────────────────────────────────────────────────
    _step(5, "Stratifying by rarity, role, faction")
    rpt.add_section("Stratify", subtitle="Conditional analysis by rarity tier, PC role, and faction.")
    rpt.add_subsection("Per-rarity summary")
    rpt.add_table(analyses.rarity_breakdown(df), name="rarity_breakdown",
                  caption="The mean for the nts_raw score highlights the lack of gradation within the pre-defined stat blocks. This results in 'spikey' difficulty ratings instead of a normalized increase.")
    img = plots.pc_role_rarity_heatmap(df, OUT)
    rpt.add_image(img, alt="PC role × rarity NTS heatmap",
                  caption="Mean NTS_raw per (PC role, NPC rarity) cell. Row variation reveals whether some PC roles face systematically harder or easier matchups than others. Insight into the similarity ratings between roles is provided with the next table.")
    rpt.add_subsection("Per-PC-role summary")
    rpt.add_table(analyses.pc_role_breakdown(df), name="pc_role_breakdown",
                  caption="The stat blocks extracted from the Danger Girl Dossier are essentially equal in terms of combat prowess. The un-answered question is, 'how does each role compare to an actual PC character within the same role?'")
    rpt.add_subsection("Per-faction summary")
    rpt.add_table(analyses.faction_breakdown(df), name="faction_breakdown",
                  caption="NTS_raw by faction. A faction whose median sits sharply above its peers may indicate stat-block drift in that gang's design.")
    img = plots.faction_box(df, OUT)
    rpt.add_image(img, alt="Faction NTS_raw box plot", caption="Per-faction NTS_raw distribution, sorted by median.")

    # ── 6. DIAGNOSE ───────────────────────────────────────────────────────
    _step(6, "Calibration diagnostics")
    rpt.add_section("Diagnose", subtitle="Calibration findings tied to outline.md's open parameters.")

    rpt.add_subsection("Tier separation")
    sep = analyses.tier_separation(df, "nts_raw")
    rpt.add_table(sep, name="tier_separation",
                  caption="Cohen's d, distribution overlap %, and Mann-Whitney p between adjacent tiers. For example, a negative d would signal an inverted ladder meaning the higher-rarity tier is actually weaker.")
    img = plots.tier_separation_strip(sep, OUT)
    rpt.add_image(img, alt="Tier separation effect-size strip",
                  caption="Green = clean separation (|d|≥0.8 or overlap<70%), orange = moderate, red = at-risk. There is very little variation between two tiers (Tough -> Hardened & HardenedLT -> Elite) and the variation between Boss -> HardenedBoss is moderately overlapping. This is likely a result of poor stat block balancing by the stat block's authors.")

    rpt.add_subsection("SCALE_FACTOR back-solve")
    sf = analyses.scale_factor_solver(df)
    rpt.add_paragraph(
        f"Best `SCALE_FACTOR` ≈ **{sf['best_scale_factor']:.2f}** "
        f"(score {sf['score']*100:.0f}% — fraction of anchor tiers landing in their target NTS bands)."
    )
    rpt.add_table(sf["landing"], name="scale_factor_landing",
                  caption="Where each rarity tier's median NTS_raw lands under the best SCALE_FACTOR.")

    rpt.add_subsection("Subcomponent decomposition")
    decomp = analyses.subcomponent_decomposition(df)
    rpt.add_table(decomp, name="subcomponent_decomposition",
                  caption="Fraction of mean DDS from each component (HPP/AAC/DSR) and OTS from each track (raw damage vs crit threat) within each rarity tier.")
    rpt.add_image(plots.dds_decomposition(df, OUT),
                  alt="DDS decomposition stacked bar",
                  caption="Stacked HPP/AAC/DSR contribution to mean DDS per rarity. AAC dominance (driven by the SP=18 cap) makes HPP and DSR nearly invisible at higher tiers.")
    rpt.add_image(plots.ots_decomposition(df, OUT),
                  alt="OTS decomposition stacked bar",
                  caption="Stacked HPW·EDPR vs HPW·CTS contribution to mean OTS per rarity. Crit-track dominance at low tiers means small-weapon NPCs are coasting on critical-hit luck.")

    rpt.add_subsection("OTS zero-mass (penetration failure rate)")
    zm = analyses.ots_zero_mass(df)
    rpt.add_table(zm, name="ots_zero_mass",
                  caption="P(EDPR_SS = 0) — how often a single shot from this rarity tier deals zero raw damage to this PC role. This unintended result stems from how weapon damage is being calculated. Using the mean of a die pool for a static damage value as a proxy isn't the correct approach.")
    rpt.add_image(plots.ots_zero_mass_heatmap(zm, OUT),
                  alt="OTS zero-mass heatmap", caption="Hot cells = NPC tier consistently fails to penetrate this PC role's armor. This supports the conclusion noted above. Flat mean damage values aren't nuanced enough to be used for determining armor penetration.")

    rpt.add_subsection("Weighting sensitivity")
    weighting = analyses.weighting_sensitivity(df)
    rpt.add_table(weighting, name="weighting_sensitivity",
                  caption="Spearman ρ of NPC rankings vs the 60/40 baseline under alternative OTS/DDS weightings. Top-10 changes count NPCs that enter or leave the top 10. Currently OTS doesn't have enough of an impact on the NTS score for this metric to provide valuable information.")
    rpt.add_image(plots.weighting_sensitivity_plot(weighting, OUT),
                  alt="Weighting sensitivity slope chart")

    rpt.add_subsection("Rank stability across PCs")
    rank = analyses.rank_stability(df)
    rpt.add_kv({
        "PCs compared":   rank["n_pcs"],
        "Mean Spearman ρ": rank["rho_mean"],
        "Min Spearman ρ":  rank["rho_min"],
        "Max Spearman ρ":  rank["rho_max"],
    })
    rpt.add_paragraph(
        "ρ ≈ 1 means every PC ranks the NPC roster the same way. "
        "ρ < 0.85 means some NPCs are dramatically more threatening to specific PCs."
    )

    rpt.add_subsection("NPC threat consistency")
    consistency = analyses.npc_threat_consistency(df, top_n=15)
    rpt.add_table(consistency, name="npc_consistency",
                  caption="Top-15 NPCs by coefficient of variation of OTS across PCs (these are the most PC-dependent threats).")
    rpt.add_image(plots.npc_consistency(consistency, OUT),
                  alt="NPC consistency bar chart")

    rpt.add_subsection("SP-cap binding analysis")
    sp = analyses.sp_cap_impact(df)
    rpt.add_kv({
        "Unique NPCs":           sp["n_unique_npcs"],
        "NPCs hitting SP=18 cap": f"{sp['n_capped']} ({sp['fraction']*100:.1f}%)",
        "Max excess SP":         sp["max_excess_sp"],
    })
    rpt.add_table(sp["by_rarity"], name="sp_cap_by_rarity")
    rpt.add_image(plots.sp_cap_impact_plot(df, OUT),
                  alt="SP cap impact",
                  caption="Left: distribution of raw SP. Right: NPCs hitting the SP=18 cap, by rarity.")

    rpt.add_subsection("Top extreme-tail NPCs and their drivers")
    out_df = analyses.outlier_decomposition(df, k=10)
    rpt.add_table(out_df, name="extreme_tail_npcs",
                  caption="Top 10 NPCs by NTS_raw with the dominant subcomponent driver attributed (HPP/AAC/DSR/EDPR-track/CTS-track). It is easy to observe that DDS is the dominant driver of NTS_raw.")

    rpt.add_subsection("Sample sizes by rarity")
    rpt.add_image(plots.rarity_counts(df, OUT),
                  alt="NPC count by rarity")

    # ── 7. RECOMMEND ──────────────────────────────────────────────────────
    _step(7, "Recommendations")
    rpt.add_section("Recommend", subtitle="Prioritized action plan tied to outline.md's open calibration parameters.")
    recs = analyses.recommendations(df, sf, sep, weighting, decomp, rank, sp)

    n_critical = sum(1 for r in recs if r["priority"] == 1)
    n_warning  = sum(1 for r in recs if r["priority"] == 2)
    n_monitor  = sum(1 for r in recs if r["priority"] == 3)
    n_ok       = sum(1 for r in recs if r["priority"] == 0)
    lead_issue = next((r["title"] for r in recs if r["priority"] == 1), "none identified")
    rpt.add_paragraph(
        f"**Executive summary:** {n_critical} critical issue(s), {n_warning} warning(s), "
        f"{n_monitor} item(s) to monitor, {n_ok} confirmed-healthy signal(s). "
        f"Lead issue: _{lead_issue}._ "
        f"SCALE_FACTOR is confirmed at {sf['best_scale_factor']:.2f}. "
        f"Fix the tier-separation and AAC-dominance issues before treating NTS values as authoritative."
    )
    rpt.add_recommendations(recs)

    out_path = rpt.write()
    print(f"\nReport -> {out_path}")


if __name__ == "__main__":
    main()
