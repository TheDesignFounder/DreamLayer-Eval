# Research statistical methods

These estimators describe the supplied experiments and observed labels. They do
not establish general model rankings, causal effects, production prevalence or
human ground truth. Freeze the intended estimand, independent groups, exclusions,
rubric and evaluation protocol before a held-out study.

## Units and missingness

Results are separated by metric/version/settings, scope, model, category and split.
Superseded attempts are excluded from current analyses but remain immutable records.
Per-dataset FID/FVD values are reported with membership and status, never averaged
as per-image quality. Failed/unavailable values are null; successful zeros remain.

Human-linked comparisons join exact asset units, rubric, criterion and rater.
Duplicate rater units select the latest timestamp/ID with a warning. Adjudicated
labels replace affected units only; they are not independent additional votes.
Uncertain, not-applicable and missing outcomes remain visible in denominators.
Complete-case estimates may be biased when missingness depends on difficulty.

## Estimators

| Output | Definition and assumptions |
|---|---|
| Binary errors | Human pass is the positive class. Report TP/TN/FP/FN on paired binary labels, human binary count, judge coverage and abstentions. `P(judge pass \| human fail)=FP/(FP+TN)` differs from `P(human fail \| judge pass)=FP/(FP+TP)`. Zero denominators are null. |
| Correlations | SciPy Spearman correlation with average ranks for ties; Kendall tau-b adjusts for ties. Use complete pairs; fewer than three or constant observations return null. No independent-observation p-values are reported. |
| Mean interval | Observation-weighted mean over non-null values. Resample entire independent `group_id` clusters with replacement, retaining all observations/repeats in each selected cluster. Use 2,000 seeded NumPy draws and the empirical 2.5/97.5 percentiles. Fewer than two groups gives a point estimate only. |
| Stratified interval | Resample the same number of clusters independently within each supplied stratum. A cluster cannot span strata. Singleton strata contribute no within-stratum uncertainty. |
| Paired model difference | Pair by prompt and repeat, require the same group, subtract B from A, and bootstrap those differences by independent group. Missing pairs are excluded and counted. Duplicate model/task rows require explicit evaluator/attempt selection. |
| Rater agreement | Observed nominal agreement and unweighted Cohen kappa: `(p_observed-p_expected)/(1-p_expected)`, with expected agreement from empirical marginals. Uncertainty is a category; nulls are excluded. Fewer than two pairs or constant identical marginals gives null kappa. |
| Pairwise/adjudicated agreement | Unit-specific asset choices have no common nominal category across pairs; pooled kappa is suppressed. Adjudication is not independent rater evidence, so its kappa is also suppressed. |
| Threshold fitting | Only train/development rows are accepted. Maximize observed binary accuracy over the supplied thresholds; ties use the first supplied threshold. Evaluate the frozen choice on separate held-out data. |
| Best-of-N selection | All selectors share nested candidate pools within a prompt. Ties and a random baseline use a seeded RNG. Human labels enter evaluation after selection, not ranking. Summaries use group-bootstrap task pass rates and report missing candidates/scores/labels. |

The bootstrap assumes the declared groups are independent and representative of
the target sampling process. Repeats, prompt paraphrases and derived media should
remain in the same group. Unequal cluster sizes affect this observation-weighted
estimand; it is not an equal-weight average of prompt means. Percentile intervals
can be unstable with few clusters or extreme outcomes. There is no automatic
multiple-comparison correction, rater/random-effects model, selection-bias
correction or guarantee that a fixed candidate pool represents future generation.

## Reference checks

`tests/research/test_public_readiness.py` compares nominal kappa against
[scikit-learn's implementation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html)
on binary/uncertain categories and missing labels. It also checks a known discrete
bootstrap case: two independent clusters contain four zeros and four tens. The
four equally likely cluster-resampled means are 0, 5, 5 and 10, so the population
bootstrap 95% interval is [0,10] and the observation mean is 5. The seeded Monte
Carlo implementation recovers that interval. This check would fail if the eight
rows were treated as independent bootstrap units.

Existing fixtures cover paired exclusions, constants, ties, enriched failure
sets, single-group uncertainty and development/test separation. Numerical parity
is evidence about implementation, not evidence that a study's assumptions hold.
See the [validation record](research-validation.md) for executed environments.
