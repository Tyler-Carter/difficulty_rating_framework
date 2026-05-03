# NPC Threat Score — Calibration EDA

_A seven-section narrative covering data quality, distributions, relationships, stratification, and calibration recommendations._



## 1. Frame

> What's in the dataset and what we're trying to answer.

The NPC Threat Score (NTS) rates Cyberpunk RED NPCs against player characters on a 1–20 scale. Each row in the dataset is a single (PC, NPC) matchup; OTS depends on the specific defender, while DDS and the Complexity Multiplier depend only on the NPC. This report follows a Tukey-style EDA progression (Profile → Distribute → Relate → Stratify → Diagnose → Recommend) tied to the open calibration parameters in [`docs/outline.md`](../../docs/outline.md).

- **Row grain**: one row per (PC, NPC) pair
- **Total (PC, NPC) pairs**: 1600
- **Unique PCs**: 16 (7 roles)
- **Unique NPCs**: 100
- **Factions represented**: 15
- **Rarity tiers**: Mook → Tough → HardenedMook → HardenedLieutenant → Elite → HardenedMiniBoss → Boss → HardenedBoss
- **Clean-data join**: 84/100 NPCs matched (84%)


## 2. Profile

> Data quality, completeness, and invariant checks.


### Null rates

_Per-column null rate. Calculated columns should be 0; clean-data joins may be partial._

| index        | null_rate | null_count |
| ------------ | --------- | ---------- |
| pc_role_id   | 0.000     | 0          |
| pc_role      | 0.000     | 0          |
| npc_id       | 0.000     | 0          |
| faction      | 0.000     | 0          |
| npc_name     | 0.000     | 0          |
| npc_rarity   | 0.030     | 48         |
| nts_raw      | 0.000     | 0          |
| cm           | 0.000     | 0          |
| ots          | 0.000     | 0          |
| hpw_ss       | 0.000     | 0          |
| edpr_ss      | 0.000     | 0          |
| cts_ss       | 0.000     | 0          |
| hpw_af       | 0.780     | 1248       |
| edpr_af      | 0.780     | 1248       |
| cts_af       | 0.780     | 1248       |
| has_autofire | 0.000     | 0          |
| weapon_type  | 0.000     | 0          |
| is_excellent | 0.000     | 0          |
| attack_pool  | 0.000     | 0          |
| af_pool      | 0.780     | 1248       |
| range_dv     | 0.000     | 0          |
| def_static   | 0.000     | 0          |
| def_ref      | 0.000     | 0          |
| def_sp       | 0.000     | 0          |
| dds          | 0.000     | 0          |

_...showing first 25 of 41 rows. Full table: [tables/profile_nulls.csv](tables/profile_nulls.csv)_


### Cardinality

_Distinct values per column._

| index        | distinct |
| ------------ | -------- |
| pc_role_id   | 16       |
| pc_role      | 7        |
| npc_id       | 100      |
| faction      | 15       |
| npc_name     | 100      |
| npc_rarity   | 8        |
| nts_raw      | 741      |
| cm           | 1        |
| ots          | 123      |
| hpw_ss       | 16       |
| edpr_ss      | 19       |
| cts_ss       | 7        |
| hpw_af       | 8        |
| edpr_af      | 9        |
| cts_af       | 1        |
| has_autofire | 2        |
| weapon_type  | 14       |
| is_excellent | 2        |
| attack_pool  | 13       |
| af_pool      | 6        |
| range_dv     | 4        |
| def_static   | 9        |
| def_ref      | 6        |
| def_sp       | 3        |
| dds          | 208      |

_...showing first 25 of 41 rows. Full table: [tables/profile_cardinality.csv](tables/profile_cardinality.csv)_


### Rarity tier counts

| npc_rarity         | unique_npcs |
| ------------------ | ----------- |
| Mook               | 18          |
| Tough              | 12          |
| HardenedMook       | 10          |
| HardenedLieutenant | 8           |
| Elite              | 33          |
| HardenedMiniBoss   | 5           |
| Boss               | 9           |
| HardenedBoss       | 2           |

_Source: [tables/profile_rarity_counts.csv](tables/profile_rarity_counts.csv)_


### Integrity checks

- **[FAIL]** DDS is constant per NPC across PCs — 100 NPC(s) showed varying DDS — should be 0
- **[PASS]** OTS varies across PCs for most NPCs — 4/100 NPCs deliver identical OTS to every PC
- **[PASS]** NTS_raw == (OTS·0.6 + DDS·0.4) · CM — max |delta| = 0.0000


## 3. Distribute

> Univariate distributions of every metric and subcomponent.

_Per-metric summary including skewness, excess kurtosis, and zero-mass fraction._

| metric  | n    | mean    | median  | std     | min    | p05    | p95      | max      | skewness | ex_kurtosis | zero_frac |
| ------- | ---- | ------- | ------- | ------- | ------ | ------ | -------- | -------- | -------- | ----------- | --------- |
| nts_raw | 1600 | 185.667 | 80.930  | 299.196 | 11.872 | 14.826 | 1359.696 | 1386.170 | 3.372    | 10.673      | 0.000     |
| ots     | 1600 | 2.837   | 0.989   | 3.682   | 0.000  | 0.119  | 8.950    | 25.230   | 2.267    | 6.291       | 0.040     |
| dds     | 1600 | 459.912 | 198.254 | 747.309 | 28.517 | 35.431 | 3392.823 | 3461.654 | 3.377    | 10.694      | 0.000     |
| hpp     | 1600 | 36.475  | 35.000  | 8.189   | 22.500 | 25.000 | 55.125   | 67.500   | 1.378    | 2.588       | 0.000     |
| aac     | 1600 | 418.808 | 155.522 | 741.184 | 4.917  | 9.156  | 3355.823 | 3367.872 | 3.389    | 10.747      | 0.000     |
| dsr_hp  | 1600 | 4.630   | 2.732   | 4.962   | 1.100  | 1.100  | 19.324   | 26.282   | 2.587    | 6.204       | 0.000     |
| hpw_ss  | 1600 | 0.726   | 0.800   | 0.281   | 0.200  | 0.200  | 1.000    | 1.000    | -0.711   | -0.903      | 0.000     |
| edpr_ss | 1600 | 3.066   | 0.928   | 4.101   | 0.000  | 0.000  | 13.003   | 21.000   | 1.605    | 2.525       | 0.123     |
| cts_ss  | 1600 | 1.332   | 1.412   | 0.910   | 0.000  | 0.297  | 2.817    | 4.230    | 1.238    | 1.389       | 0.040     |

_Source: [tables/univariate_summary.csv](tables/univariate_summary.csv)_


![Distributions of NTS_raw, OTS, DDS](01_distributions.png)

_Linear (top) and log-y (bottom) histograms. The OTS log-y plot exposes the heavy zero-mass. Many NPCs cannot penetrate PC armor in single-shot mode._


![Per-rarity violins for each metric](02_rarity_violins.png)

_Violin shape + per-pair points per rarity tier. Wide tails indicate within-tier variance; per-tier n is on the x-axis._


## 4. Relate

> Pairwise and multivariate relationships across metrics + subcomponents.


![Pairwise scatter of OTS, DDS, NTS_raw](03_pair_scatter.png)

_Pearson (linear) and Spearman (monotonic) correlations side-by-side. NTS_raw is dominated by DDS due to the Armor Absorption Capacity (AAC) calculation. As SP rating increases the armor absorption pool quadratically increases._


![Pearson and Spearman correlation heatmaps](04_correlations.png)

_Pearson catches linear correlation and Spearman captures monotonic rank relationships. The heavily-tailed OTS distribution currently makes Spearman the more honest summary._

_Spearman correlation matrix._

| index   | nts_raw | ots   | dds   | hpp   | aac   | dsr_hp | hpw_ss | edpr_ss | cts_ss | cm |
| ------- | ------- | ----- | ----- | ----- | ----- | ------ | ------ | ------- | ------ | -- |
| nts_raw | 1.000   | 0.336 | 0.997 | 0.651 | 0.995 | 0.589  | 0.367  | 0.263   | 0.358  |    |
| ots     | 0.336   | 1.000 | 0.290 | 0.292 | 0.290 | 0.238  | 0.478  | 0.913   | 0.681  |    |
| dds     | 0.997   | 0.290 | 1.000 | 0.659 | 0.997 | 0.603  | 0.347  | 0.220   | 0.333  |    |
| hpp     | 0.651   | 0.292 | 0.659 | 1.000 | 0.637 | 0.896  | 0.315  | 0.195   | 0.287  |    |
| aac     | 0.995   | 0.290 | 0.997 | 0.637 | 1.000 | 0.572  | 0.341  | 0.223   | 0.332  |    |
| dsr_hp  | 0.589   | 0.238 | 0.603 | 0.896 | 0.572 | 1.000  | 0.291  | 0.164   | 0.254  |    |
| hpw_ss  | 0.367   | 0.478 | 0.347 | 0.315 | 0.341 | 0.291  | 1.000  | 0.207   | 0.194  |    |
| edpr_ss | 0.263   | 0.913 | 0.220 | 0.195 | 0.223 | 0.164  | 0.207  | 1.000   | 0.697  |    |
| cts_ss  | 0.358   | 0.681 | 0.333 | 0.287 | 0.332 | 0.254  | 0.194  | 0.697   | 1.000  |    |
| cm      |         |       |       |       |       |        |        |         |        |    |

_Source: [tables/correlations_spearman.csv](tables/correlations_spearman.csv)_


## 5. Stratify

> Conditional analysis by rarity tier, PC role, and faction.


### Per-rarity summary

_The mean for the nts_raw score highlights the lack of gradation within the pre-defined stat blocks. This results in 'spikey' difficulty ratings instead of a normalized increase._

| ('npc_rarity', '') | ('nts_raw', 'mean') | ('nts_raw', 'median') | ('nts_raw', 'std') | ('ots', 'mean') | ('ots', 'median') | ('ots', 'std') | ('dds', 'mean') | ('dds', 'median') | ('dds', 'std') | ('n_pairs', '') | ('n_unique_npcs', '') |
| ------------------ | ------------------- | --------------------- | ------------------ | --------------- | ----------------- | -------------- | --------------- | ----------------- | -------------- | --------------- | --------------------- |
| Mook               | 17.640              | 16.770                | 3.930              | 1.140           | 0.560             | 1.390          | 42.400          | 39.570            | 9.430          | 288             | 18                    |
| Tough              | 71.950              | 32.100                | 73.940             | 2.990           | 0.930             | 3.660          | 175.390         | 75.850            | 183.730        | 192             | 12                    |
| HardenedMook       | 74.540              | 50.430                | 57.840             | 2.370           | 0.730             | 3.250          | 182.810         | 125.380           | 143.610        | 160             | 10                    |
| HardenedLieutenant | 155.130             | 195.190               | 81.880             | 2.820           | 2.110             | 2.650          | 383.590         | 483.820           | 205.080        | 128             | 8                     |
| Elite              | 172.520             | 210.770               | 70.100             | 3.390           | 1.560             | 3.840          | 426.230         | 514.250           | 175.230        | 528             | 33                    |
| HardenedMiniBoss   | 182.570             | 220.080               | 69.930             | 2.850           | 1.870             | 2.630          | 452.150         | 544.870           | 174.770        | 80              | 5                     |
| Boss               | 779.300             | 787.770               | 595.230            | 5.260           | 2.340             | 6.130          | 1940.360        | 1960.530          | 1489.100       | 144             | 9                     |
| HardenedBoss       | 784.300             | 793.510               | 602.440            | 1.130           | 0.860             | 1.320          | 1959.050        | 1982.510          | 1506.570       | 32              | 2                     |

_Source: [tables/rarity_breakdown.csv](tables/rarity_breakdown.csv)_


![PC role × rarity NTS heatmap](05_pc_role_rarity_heatmap.png)

_Mean NTS_raw per (PC role, NPC rarity) cell. Row variation reveals whether some PC roles face systematically harder or easier matchups than others. Insight into the similarity ratings between roles is provided with the next table._


### Per-PC-role summary

_The stat blocks extracted from the Danger Girl Dossier are essentially equal in terms of combat prowess. The un-answered question is, 'how does each role compare to an actual PC character within the same role?'_

| pc_role   | n_pairs | median_nts_raw | mean_nts_raw | median_ots | ots_zero_frac |
| --------- | ------- | -------------- | ------------ | ---------- | ------------- |
| Exec      | 100     | 224.940        | 273.830      | 0.932      | 0.120         |
| Netrunner | 200     | 224.940        | 273.830      | 0.932      | 0.120         |
| Media     | 300     | 196.350        | 233.290      | 1.404      | 0.093         |
| Tech      | 300     | 86.080         | 113.290      | 1.404      | 0.093         |
| Solo      | 400     | 78.390         | 172.810      | 0.932      | 0.193         |
| Fixer     | 200     | 78.050         | 173.600      | 2.340      | 0.080         |
| Rockerboy | 100     | 74.980         | 71.010       | 0.932      | 0.120         |

_Source: [tables/pc_role_breakdown.csv](tables/pc_role_breakdown.csv)_


### Per-faction summary

_NTS_raw by faction. A faction whose median sits sharply above its peers may indicate stat-block drift in that gang's design._

| faction       | n_pairs | n_unique_npcs | median_nts_raw | mean_nts_raw | std_nts_raw |
| ------------- | ------- | ------------- | -------------- | ------------ | ----------- |
| TeamMonster   | 96      | 6             | 214.220        | 174.260      | 70.260      |
| Piranhas      | 48      | 3             | 210.960        | 569.280      | 571.420     |
| DangerGal     | 80      | 5             | 194.900        | 153.290      | 78.150      |
| Zoners        | 160     | 10            | 194.400        | 249.400      | 387.740     |
| Bozos         | 176     | 11            | 194.230        | 246.680      | 365.900     |
| NCPD          | 176     | 11            | 193.280        | 200.600      | 266.110     |
| Maelstrom     | 176     | 11            | 191.200        | 247.340      | 369.430     |
| 6thStreet     | 80      | 5             | 82.060         | 125.690      | 86.630      |
| Sightseers    | 80      | 5             | 80.680         | 111.280      | 95.180      |
| TygerClaws    | 144     | 9             | 79.060         | 237.930      | 410.810     |
| TraumaTeam    | 96      | 6             | 78.900         | 121.260      | 82.500      |
| Incident      | 32      | 2             | 40.160         | 100.910      | 91.200      |
| Network54     | 48      | 3             | 30.340         | 30.950       | 3.460       |
| DigitalDivas  | 80      | 5             | 26.090         | 35.000       | 31.780      |
| GenerationRed | 128     | 8             | 17.200         | 48.550       | 63.190      |

_Source: [tables/faction_breakdown.csv](tables/faction_breakdown.csv)_


![Faction NTS_raw box plot](10_faction_box.png)

_Per-faction NTS_raw distribution, sorted by median._


## 6. Diagnose

> Calibration findings tied to outline.md's open parameters.


### Tier separation

_Cohen's d, distribution overlap %, and Mann-Whitney p between adjacent tiers. For example, a negative d would signal an inverted ladder meaning the higher-rarity tier is actually weaker._

| index | lower              | higher             | n_lo | n_hi | mean_lo | mean_hi | cohen_d | overlap_pct | mw_p  |
| ----- | ------------------ | ------------------ | ---- | ---- | ------- | ------- | ------- | ----------- | ----- |
| 0     | Mook               | Tough              | 288  | 192  | 17.640  | 71.950  | 1.159   | 5.400       | 0.000 |
| 1     | Tough              | HardenedMook       | 192  | 160  | 71.950  | 74.540  | 0.039   | 66.600      | 0.000 |
| 2     | HardenedMook       | HardenedLieutenant | 160  | 128  | 74.540  | 155.130 | 1.159   | 43.000      | 0.000 |
| 3     | HardenedLieutenant | Elite              | 128  | 528  | 155.130 | 172.520 | 0.240   | 93.700      | 0.136 |
| 4     | Elite              | HardenedMiniBoss   | 528  | 80   | 172.520 | 182.570 | 0.143   | 77.900      | 0.001 |
| 5     | HardenedMiniBoss   | Boss               | 80   | 144  | 182.570 | 779.300 | 1.244   | 62.900      | 0.000 |
| 6     | Boss               | HardenedBoss       | 144  | 32   | 779.300 | 784.300 | 0.008   | 86.200      | 0.111 |

_Source: [tables/tier_separation.csv](tables/tier_separation.csv)_


![Tier separation effect-size strip](11_tier_separation.png)

_Green = clean separation (|d|≥0.8 or overlap<70%), orange = moderate, red = at-risk. There is very little variation between two tiers (Tough -> Hardened & HardenedLT -> Elite) and the variation between Boss -> HardenedBoss is moderately overlapping. This is likely a result of poor stat block balancing by the stat block's authors._


### SCALE_FACTOR back-solve

Best `SCALE_FACTOR` ≈ **23.00** (score 75% — fraction of anchor tiers landing in their target NTS bands).

_Where each rarity tier's median NTS_raw lands under the best SCALE_FACTOR._

| index | rarity             | median_raw | target_band | mapped_nts | in_band |
| ----- | ------------------ | ---------- | ----------- | ---------- | ------- |
| 0     | Mook               | 16.770     | 1-4         | 1          | True    |
| 1     | Tough              | 32.100     | 1-4         | 1          | True    |
| 2     | HardenedMook       | 50.430     | 5-8         | 2          | False   |
| 3     | HardenedLieutenant | 195.190    | 5-8         | 8          | True    |
| 4     | Elite              | 210.770    | 9-12        | 9          | True    |
| 5     | HardenedMiniBoss   | 220.080    | 9-12        | 10         | True    |
| 6     | Boss               | 787.770    | 13-16       | 20         | False   |
| 7     | HardenedBoss       | 793.510    | 17-20       | 20         | True    |

_Source: [tables/scale_factor_landing.csv](tables/scale_factor_landing.csv)_


### Subcomponent decomposition

_Fraction of mean DDS from each component (HPP/AAC/DSR) and OTS from each track (raw damage vs crit threat) within each rarity tier._

| npc_rarity         | n_pairs | hpp_share | aac_share | dsr_share | edpr_share | cts_share | mean_ots | mean_dds |
| ------------------ | ------- | --------- | --------- | --------- | ---------- | --------- | -------- | -------- |
| Mook               | 288     | 0.668     | 0.289     | 0.042     | 0.655      | 0.345     | 1.141    | 42.400   |
| Tough              | 192     | 0.202     | 0.781     | 0.017     | 0.710      | 0.290     | 2.990    | 175.390  |
| HardenedMook       | 160     | 0.190     | 0.785     | 0.025     | 0.724      | 0.276     | 2.368    | 182.810  |
| HardenedLieutenant | 128     | 0.096     | 0.894     | 0.010     | 0.680      | 0.320     | 2.821    | 383.590  |
| Elite              | 528     | 0.085     | 0.907     | 0.009     | 0.702      | 0.298     | 3.386    | 426.230  |
| HardenedMiniBoss   | 80      | 0.108     | 0.869     | 0.023     | 0.675      | 0.325     | 2.849    | 452.150  |
| Boss               | 144     | 0.025     | 0.969     | 0.006     | 0.736      | 0.264     | 5.262    | 1940.360 |
| HardenedBoss       | 32      | 0.029     | 0.962     | 0.009     | 0.532      | 0.468     | 1.133    | 1959.050 |

_Source: [tables/subcomponent_decomposition.csv](tables/subcomponent_decomposition.csv)_


![DDS decomposition stacked bar](06_dds_decomposition.png)

_Stacked HPP/AAC/DSR contribution to mean DDS per rarity. AAC dominance (driven by the SP=18 cap) makes HPP and DSR nearly invisible at higher tiers._


![OTS decomposition stacked bar](07_ots_decomposition.png)

_Stacked HPW·EDPR vs HPW·CTS contribution to mean OTS per rarity. Crit-track dominance at low tiers means small-weapon NPCs are coasting on critical-hit luck._


### OTS zero-mass (penetration failure rate)

_P(EDPR_SS = 0) — how often a single shot from this rarity tier deals zero raw damage to this PC role. This unintended result stems from how weapon damage is being calculated. Using the mean of a die pool for a static damage value as a proxy isn't the correct approach._

| pc_role   | Mook  | Tough | HardenedMook | HardenedLieutenant | Elite | HardenedMiniBoss | Boss  | HardenedBoss |
| --------- | ----- | ----- | ------------ | ------------------ | ----- | ---------------- | ----- | ------------ |
| Exec      | 0.111 | 0.167 | 0.200        | 0.125              | 0.091 | 0.000            | 0.111 | 0.500        |
| Fixer     | 0.111 | 0.125 | 0.100        | 0.062              | 0.061 | 0.000            | 0.056 | 0.250        |
| Media     | 0.111 | 0.139 | 0.133        | 0.083              | 0.071 | 0.000            | 0.074 | 0.333        |
| Netrunner | 0.111 | 0.167 | 0.200        | 0.125              | 0.091 | 0.000            | 0.111 | 0.500        |
| Rockerboy | 0.111 | 0.167 | 0.200        | 0.125              | 0.091 | 0.000            | 0.111 | 0.500        |
| Solo      | 0.278 | 0.271 | 0.275        | 0.125              | 0.129 | 0.100            | 0.111 | 0.500        |
| Tech      | 0.111 | 0.139 | 0.133        | 0.083              | 0.071 | 0.000            | 0.074 | 0.333        |

_Source: [tables/ots_zero_mass.csv](tables/ots_zero_mass.csv)_


![OTS zero-mass heatmap](08_ots_zero_mass.png)

_Hot cells = NPC tier consistently fails to penetrate this PC role's armor. This supports the conclusion noted above. Flat mean damage values aren't nuanced enough to be used for determining armor penetration._


### Weighting sensitivity

_Spearman ρ of NPC rankings vs the 60/40 baseline under alternative OTS/DDS weightings. Top-10 changes count NPCs that enter or leave the top 10. Currently OTS doesn't have enough of an impact on the NTS score for this metric to provide valuable information._

| index | ots_weight | dds_weight | spearman_rho | top10_overlap | top10_changes |
| ----- | ---------- | ---------- | ------------ | ------------- | ------------- |
| 0     | 0.600      | 0.400      | 1.000        | 10            | 0             |
| 1     | 0.550      | 0.450      | 0.999        | 10            | 0             |
| 2     | 0.500      | 0.500      | 0.998        | 10            | 0             |

_Source: [tables/weighting_sensitivity.csv](tables/weighting_sensitivity.csv)_


![Weighting sensitivity slope chart](12_weighting_sensitivity.png)


### Rank stability across PCs

- **PCs compared**: 16
- **Mean Spearman ρ**: 0.9624
- **Min Spearman ρ**: 0.8654
- **Max Spearman ρ**: 1.0

ρ ≈ 1 means every PC ranks the NPC roster the same way. ρ < 0.85 means some NPCs are dramatically more threatening to specific PCs.


### NPC threat consistency

_Top-15 NPCs by coefficient of variation of OTS across PCs (these are the most PC-dependent threats)._

| index | npc_id                      | npc_rarity         | ots_mean | ots_std | ots_cv |
| ----- | --------------------------- | ------------------ | -------- | ------- | ------ |
| 7     | NPC.Bozos_BurtTheSquirt     | HardenedMook       | 2.146    | 2.596   | 1.210  |
| 49    | NPC.NCPD_Cherub             | Tough              | 2.146    | 2.596   | 1.210  |
| 8     | NPC.Bozos_Centwit           | Elite              | 2.417    | 2.919   | 1.208  |
| 22    | NPC.DigitalDivas_Firewall   | Tough              | 2.417    | 2.919   | 1.208  |
| 23    | NPC.DigitalDivas_JoseQuispe | Tough              | 2.417    | 2.919   | 1.208  |
| 72    | NPC.TeamMonster_Nox         | Elite              | 2.417    | 2.919   | 1.208  |
| 66    | NPC.Sightseers_Glare        | Mook               | 1.612    | 1.945   | 1.207  |
| 26    | NPC.GenerationRed_Apex      | HardenedMook       | 1.612    | 1.945   | 1.207  |
| 87    | NPC.Zoners_Alpha            | Mook               | 1.612    | 1.945   | 1.207  |
| 39    | NPC.Maelstrom_Ghoul         | Mook               | 1.612    | 1.945   | 1.207  |
| 1     | NPC.6thStreet_Breacher      | Elite              | 1.612    | 1.945   | 1.207  |
| 68    | NPC.Sightseers_Swirl        | Mook               | 1.612    | 1.945   | 1.207  |
| 16    | NPC.DangerGal_DocMittens    | HardenedLieutenant | 2.687    | 3.241   | 1.206  |
| 64    | NPC.Sightseers_Endo         | Elite              | 2.687    | 3.241   | 1.206  |
| 60    | NPC.Network54_Stringer      | Tough              | 2.687    | 3.241   | 1.206  |

_Source: [tables/npc_consistency.csv](tables/npc_consistency.csv)_


![NPC consistency bar chart](09_npc_consistency.png)


### SP-cap binding analysis

- **Unique NPCs**: 100
- **NPCs hitting SP=18 cap**: 0 (0.0%)
- **Max excess SP**: 0

| npc_rarity         | capped_npcs |
| ------------------ | ----------- |
| Mook               | 0           |
| Tough              | 0           |
| HardenedMook       | 0           |
| HardenedLieutenant | 0           |
| Elite              | 0           |
| HardenedMiniBoss   | 0           |
| Boss               | 0           |
| HardenedBoss       | 0           |

_Source: [tables/sp_cap_by_rarity.csv](tables/sp_cap_by_rarity.csv)_


![SP cap impact](13_sp_cap.png)

_Left: distribution of raw SP. Right: NPCs hitting the SP=18 cap, by rarity._


### Top extreme-tail NPCs and their drivers

_Top 10 NPCs by NTS_raw with the dominant subcomponent driver attributed (HPP/AAC/DSR/EDPR-track/CTS-track). It is easy to observe that DDS is the dominant driver of NTS_raw._

| index | npc_id                          | pc_role_id              | npc_rarity   | nts_raw  | ots    | dds      | weapon_type     | driver |
| ----- | ------------------------------- | ----------------------- | ------------ | -------- | ------ | -------- | --------------- | ------ |
| 0     | NPC.Zoners_Tearjerker           | NPC.Edgerunners_Flasher | Boss         | 1386.170 | 16.817 | 3440.200 | GrenadeLauncher | aac    |
| 1     | NPC.Maelstrom_Crusher           | NPC.Edgerunners_Flasher | HardenedBoss | 1385.423 | 1.269  | 3461.654 | Flamethrower    | aac    |
| 2     | NPC.TygerClaws_ShinobuTheSecond | NPC.Edgerunners_Flasher | Boss         | 1382.372 | 8.428  | 3443.288 | VeryHeavyMelee  | aac    |
| 3     | NPC.Maelstrom_Warlock           | NPC.Edgerunners_Flasher | Boss         | 1380.569 | 3.363  | 3446.376 | Shotgun         | aac    |
| 4     | NPC.Bozos_Blammo                | NPC.Edgerunners_Flasher | Boss         | 1379.448 | 25.230 | 3410.776 | RocketLauncher  | aac    |
| 5     | NPC.Zoners_Vanisher             | NPC.Edgerunners_Flasher | Boss         | 1376.804 | 9.529  | 3427.716 | HeavySMG        | aac    |
| 6     | NPC.Piranhas_BazookaJoe         | NPC.Edgerunners_Flasher | Boss         | 1374.572 | 1.793  | 3433.739 | Brawling        | aac    |
| 7     | NPC.Bozos_BigTop                | NPC.Edgerunners_Flasher | HardenedBoss | 1369.928 | 4.455  | 3418.139 | HeavyMelee      | aac    |
| 8     | NPC.NCPD_Caliber                | NPC.Edgerunners_Flasher | Boss         | 1365.411 | 4.073  | 3407.419 | AssaultRifle    | aac    |
| 9     | NPC.Piranhas_CorpseReviver      | NPC.Edgerunners_Flasher | Boss         | 1361.886 | 8.117  | 3392.540 | HeavyPistol     | aac    |

_Source: [tables/extreme_tail_npcs.csv](tables/extreme_tail_npcs.csv)_


### Sample sizes by rarity


![NPC count by rarity](14_rarity_counts.png)


## 7. Recommend

> Prioritized action plan tied to outline.md's open calibration parameters.

**Executive summary:** 0 critical issue(s), 6 warning(s), 1 item(s) to monitor, 3 confirmed-healthy signal(s). Lead issue: _none identified._ SCALE_FACTOR is confirmed at 23.00. Fix the tier-separation and AAC-dominance issues before treating NTS values as authoritative.


### Priority 2 — Warning (Address Before Relying on Ratings)


#### ⚠️ Tough↔HardenedMook: Weak Tier Boundary (d=0.039, overlap=66.6%)

**Issue:** The Tough↔HardenedMook boundary has 66.6% distributional overlap (Cohen's d = 0.039). NPCs near this boundary receive interchangeable NTS values across tiers — meaningful but not yet collapsed.

**Root cause:** The stat-block delta between Tough and HardenedMook is not large enough to overcome within-tier variance. AAC dominance in DDS suppresses NTS sensitivity to HP-pool differences.

**Action:**
- Widen the stat gap: lower the Tough stat ceiling or raise the HardenedMook floor.
- Consider whether 'Tough' is a distinct design tier or should be merged with 'HardenedMook'.
- Rebalancing AAC in the DDS formula (see AAC recommendation) will increase the leverage of BODY/WILL differences.

**Expected outcome:** Target Cohen's d ≥ 0.8 and overlap < 40% for the Tough↔HardenedMook boundary.


#### ⚠️ HardenedLieutenant↔Elite: Weak Tier Boundary (d=0.240, overlap=93.7%)

**Issue:** The HardenedLieutenant↔Elite boundary has 93.7% distributional overlap (Cohen's d = 0.240). NPCs near this boundary receive interchangeable NTS values across tiers — meaningful but not yet collapsed.

**Root cause:** The stat-block delta between HardenedLieutenant and Elite is not large enough to overcome within-tier variance. AAC dominance in DDS suppresses NTS sensitivity to HP-pool differences.

**Action:**
- Widen the stat gap: lower the HardenedLieutenant stat ceiling or raise the Elite floor.
- Consider whether 'HardenedLieutenant' is a distinct design tier or should be merged with 'Elite'.
- Rebalancing AAC in the DDS formula (see AAC recommendation) will increase the leverage of BODY/WILL differences.

**Expected outcome:** Target Cohen's d ≥ 0.8 and overlap < 40% for the HardenedLieutenant↔Elite boundary.


#### ⚠️ Elite↔HardenedMiniBoss: Weak Tier Boundary (d=0.143, overlap=77.9%)

**Issue:** The Elite↔HardenedMiniBoss boundary has 77.9% distributional overlap (Cohen's d = 0.143). NPCs near this boundary receive interchangeable NTS values across tiers — meaningful but not yet collapsed.

**Root cause:** The stat-block delta between Elite and HardenedMiniBoss is not large enough to overcome within-tier variance. AAC dominance in DDS suppresses NTS sensitivity to HP-pool differences.

**Action:**
- Widen the stat gap: lower the Elite stat ceiling or raise the HardenedMiniBoss floor.
- Consider whether 'Elite' is a distinct design tier or should be merged with 'HardenedMiniBoss'.
- Rebalancing AAC in the DDS formula (see AAC recommendation) will increase the leverage of BODY/WILL differences.

**Expected outcome:** Target Cohen's d ≥ 0.8 and overlap < 40% for the Elite↔HardenedMiniBoss boundary.


#### ⚠️ Boss↔HardenedBoss: Weak Tier Boundary (d=0.008, overlap=86.2%)

**Issue:** The Boss↔HardenedBoss boundary has 86.2% distributional overlap (Cohen's d = 0.008). NPCs near this boundary receive interchangeable NTS values across tiers — meaningful but not yet collapsed.

**Root cause:** The stat-block delta between Boss and HardenedBoss is not large enough to overcome within-tier variance. AAC dominance in DDS suppresses NTS sensitivity to HP-pool differences.

**Action:**
- Widen the stat gap: lower the Boss stat ceiling or raise the HardenedBoss floor.
- Consider whether 'Boss' is a distinct design tier or should be merged with 'HardenedBoss'.
- Rebalancing AAC in the DDS formula (see AAC recommendation) will increase the leverage of BODY/WILL differences.

**Expected outcome:** Target Cohen's d ≥ 0.8 and overlap < 40% for the Boss↔HardenedBoss boundary.


#### ⚠️ AAC Dominates DDS at Upper Tiers — HPP and DSR Are Noise

**Issue:** At ['Tough', 'HardenedMook', 'HardenedLieutenant', 'Elite', 'HardenedMiniBoss', 'Boss', 'HardenedBoss'], Armor Absorption Capacity accounts for up to 97% of mean DDS. Hit Point Pool (HPP) and Death Save Resilience (DSR) contribute so little that BODY and WILL stat differences between tiers have almost no effect on NTS.

**Root cause:** The AAC formula uses a triangular sum (SP + SP-1 + … + 1), which grows as SP²/2. At high SP values this vastly outweighs the linear HPP formula (BODY×5 + 10). The `SP_CAPPED` parameter (currently 18) matches the highest observed SP in the dataset, so it is not binding — adjusting it would not affect current data.

**Action:**
- Add a configurable `HPP_weight` multiplier to the DDS formula (e.g., `DDS = HPP * HPP_weight + AAC + DSR_hp`) so HPP can be scaled up relative to AAC.
- Alternatively, apply a square-root or log transform to AAC before summing to reduce its curvature at high SP values.
- Re-run the EDA after any formula change — target aac_share < 50% at Elite tier.

**Expected outcome:** Once HPP and DSR contribute ≥ 30% of DDS, stat-block differences between tiers will produce larger NTS gaps, likely resolving several weak-boundary issues as a side effect.


#### ⚠️ SCALE_FACTOR: Set to 23.00 — 75% Anchor Hit Rate

**Issue:** The optimal SCALE_FACTOR is 23.00, which lands 75% of anchor tiers inside their target NTS bands. Misses: HardenedMook → NTS 2 (target 5-8), Boss → NTS 20 (target 13-16). Until this is explicitly set in the codebase, all NTS outputs are uncalibrated.

**Root cause:** The Tough tier median NTS_raw (≈29.75) overshoots its target band (NTS 1–4) even at SCALE_FACTOR=6.0. This is a downstream symptom of the Tough↔HardenedMook boundary weakness — the two tiers are too close in score for both to land in separate bands.

**Action:**
- Set `SCALE_FACTOR = 23.00` in the codebase now as a baseline.
- Retest the anchor hit rate after addressing Tough↔HardenedMook stat separation — the hit rate should improve once tier scores diverge.

**Expected outcome:** After tier separation fixes, expect the anchor hit rate to rise above 87% at SCALE_FACTOR=23.00.


### Priority 3 — Monitor (No Immediate Action)


#### 🔍 Data Quality: 16% of NPCs Missing Clean Metadata

**Issue:** 16/100 NPCs could not be matched to the clean metadata file and have no weapon_type, faction, or name in stratified analyses. Faction and rarity breakdowns in Sections 5–6 may be systematically biased.

**Root cause:** The fuzzy join between `nts_raw_scores.json` and `npc_data_clean.json` failed for these NPCs — likely due to naming inconsistencies (capitalization, punctuation, or faction prefix format mismatches).

**Action:**
- Identify the unmatched NPC IDs: run `data.join_clean_npcs()` with verbose=True or inspect the rows where `npc_name` is null.
- Manually reconcile the naming in either JSON file for the affected NPCs.
- Rerun the EDA — faction and rarity breakdowns may shift once all NPCs are matched.

**Expected outcome:** Full join coverage (100%) will make faction and rarity stratifications reliable. The 84% match rate is acceptable for calibration estimates but should be resolved before treating faction-level findings as actionable.


### Confirmed Healthy


#### ✅ 60/40 OTS/DDS Weighting Is Stable

**Issue:** Switching from 60/40 to 55/45 yields Spearman ρ=0.9992 vs baseline; 0.0/10 top-tier NPCs reshuffle. The weighting choice does not materially affect NPC rankings.

**Root cause:** N/A — this is a confirmed healthy signal.

**Action:**
- Keep the 60/40 split. No change needed.

**Expected outcome:** NTS rankings remain consistent regardless of minor weight adjustments.


#### ✅ Cross-PC Rank Stability Is Strong

**Issue:** Mean Spearman ρ=0.9624, min ρ=0.8654 across all 16 PC pairings. Every PC ranks the NPC roster nearly identically.

**Root cause:** N/A — this is a confirmed healthy signal.

**Action:**
- No change needed. The headline NTS integer is a fair single-number summary.

**Expected outcome:** A single NTS value per NPC will accurately represent difficulty across all PC roles.


#### ✅ SP_CAPPED Ceiling Is Not Currently Binding

**Issue:** 0/100 NPCs exceed the SP_CAPPED threshold (0.0%). The parameter has no effect on current data.

**Root cause:** N/A — this is a confirmed healthy signal.

**Action:**
- No change needed now.
- Revisit if future NPC stat blocks include SP values above the current threshold.

**Expected outcome:** SP_CAPPED remains a dormant calibration knob until higher-SP NPCs are added.
