# RSS evaluation and reproduction

These files document the frozen accession-level evaluation used for CropMaestro. They reproduce the reported result-set score (RSS) without model calls or database access. The package covers the 18 configurations in Table 1 and three additional fixed-round settings; CM-Robust is the three-round setting. Each configuration has three runs and 150 query records per run.

## Run the calculation

Download this directory and run Python 3.9 or later:

```sh
python recompute.py
```

The script writes `query_scores.csv`, `run_scores.csv`, and `configuration_scores.csv` to `recomputed/`. Copies of these outputs are supplied here for comparison. No additional Python packages are required.

The three inputs are:

- `query_reference.csv`: the 150 query policies, original Chinese and reference English conditions, effective Chinese scoring conditions and any boundary normalization, positive reference accession numbers, maximum relevance grade, normalization denominator, inclusion flags, and exclusion reasons.
- `relevance_judgments.csv`: all frozen query–accession judgments, including grade 0, with the rule used for each judgment. The 26 new candidates from the later Vanna runs are included; all received grade 0 under the frozen policy.
- `retrieved_accessions.csv`: the normalized accession numbers used in scoring each query and run, with output provenance. Identifiers separated by semicolons represent up to five unique accessions in their scored order.

`excluded_queries.csv` separately lists the 11 queries excluded from RSS. Supplementary Table 13 presents the query policies and configuration-level comparisons in a readable form.

## Scoring rules

The original evaluation checked reference conditions against the B-class crop records with nonmissing accession numbers. The labels are frozen computational judgments, not newly obtained independent expert annotations.

For a query with strict database matches, a candidate satisfying all reference conditions receives grade 2; the other candidates receive grade 0. For a strict-empty query, a candidate may receive grade 1 if it satisfies all but at most one atomic condition. Alternative categorical values for the same field form one condition. Numeric bounds and explicit OR groups follow the predicate grouping used by the original scorer. The stored reference conditions preserve the original Chinese experimental definitions; English versions are reading translations. Counts and judgments are not recalculated against a changing database by this script.

There is also a historical model-derived relaxation rule. If no pooled candidate satisfies the ordinary relaxation rule for a strict-empty query, a candidate nominated in any valid CM-Robust three-round run may receive grade 1 when it satisfies at least half the atomic conditions, rounded up. This affects 18 queries and 84 positive query–accession judgments. Fifteen of these queries enter the evaluable set through this rule. These cases are explicitly flagged as `fixed3_derived`; they must not be described as independent expert judgments. A frozen label for the same query–accession pair is applied to every evaluated configuration.

For each run:

```text
RSS = sum of relevance grades over scored output positions
      / (5 * sum of query maximum grades)
```

Missing output positions contribute zero. The 94 queries with maximum grade 2 and 45 with maximum grade 1 give a common denominator of `5 * (94*2 + 45*1) = 1165`. The 11 maximum-grade-0 queries contribute neither gain nor denominator. Configuration-level RSS is the arithmetic mean across the three run-level scores, rather than an unweighted mean of normalized query scores. W-Q29 remains in RSS with maximum grade 1 despite having no positive candidate in the frozen pool.

## Conventional set comparison and scope

The reference accession lists contain positively judged candidates from pooled experimental outputs and historical reference seeds. They are not exhaustive lists of all matching database accessions. Supplementary Table 2 provides the same positive reference lists; the present files also expose negative judgments, query grades, and exclusions.

As a complementary comparison, positive grades are treated as binary relevance. For returned set P and the released pooled reference set G:

```text
Precision = |P intersect G| / |P|
Pooled-reference recall = |P intersect G| / |G|
Pooled-reference F1 = 2 * |P intersect G| / (|P| + |G|)
```

All three measures use the same 138 queries with nonempty pooled reference sets. W-Q29 is excluded from this comparison in addition to the 11 RSS exclusions. Empty predictions receive zero. Measures are averaged over these queries within each run, then equally over the three runs. Recall and F1 describe coverage of the released pooled lists under the five-record limit; they do not estimate recall over the full database. These supplementary measures are not substituted for the RSS values in the manuscript.

The scored outputs include identifiers recovered by read-only SQL replay when identifiers were missing or fewer than five were extracted from stored outputs. Historical SQL without deterministic ordering may yield order-sensitive Top-5 selections. This package preserves the selections actually used in the evaluation; it does not rerun those SQL statements, reproduce model generations, or release the underlying crop database. Vanna uses the later temperature-0.7 runs incorporated in the revised tables.
