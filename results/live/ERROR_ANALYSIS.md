# Development error analysis

These examples were inspected after Qwen's schema-constrained run. They are
diagnostic examples, not an independent test set or clinical harm adjudication.

## A syntactically valid but numerically wrong call

In `train-2397`, the input note gives height 170 cm and weight 57 kg. Qwen emitted
height **170 m**, while quoting the exact source text `170 cm`. The schema gate
accepted the numeric value and string unit; the unit-aware gate accepted `m` as
a valid height unit. The literal-quote gate found both the quote and number and
also passed. The deterministic calculator returned:

```text
Emitted call:    57 / 170^2 = 0.001972318339100346
Source units:   57 / 1.70^2 = 19.72318339100346
```

The emitted result is 10,000 times too small. Unit normalization alone cannot
detect a model that changes the unit label without changing the value. A
source-bound value/unit pair is required. This is a numerical failure; this
experiment does not establish a clinical injury or fatality.

## Quote matching also rejects useful outputs

For Qwen, L2 released 42 benchmark-matching answers and 6 nonmatching answers.
The literal gate then blocked 24 of those matching answers and 4 nonmatching
answers. It still released 2 nonmatching answers. This is a poor utility tradeoff
for this prototype and needs improvement before it can support the paper's
enforcement claims.

## Reference-data discrepancy

Training row 4318 stores platelets as 213,000,000 per liter. Its original case
report gives 213 × 10^9/L, a factor of 1,000 higher. With age 42 and admission
AST/ALT 117/186, source-based FIB-4 is 1.69160545, versus the benchmark's
1691.60545. Qwen also selected later AST/ALT, giving 1.32089984; correcting the
platelet reference alone would not make that model output correct for admission.

Primary source: [Wickramasinghe et al., 2020, case report](https://link.springer.com/article/10.1186/s13256-020-02428-3).
Source article CC BY 4.0; this paragraph paraphrases its numeric observations.
Full flag: `reference_quality_flags.json`. Primary scores retain the original
case and reference. Independent review and versioned label corrections are
needed before a confirmatory study.

The earlier 200/200 arithmetic reconstruction only established agreement with
the supplied annotations. It did not validate those annotations against their
original sources. No blanket claim of clinically correct reference data follows
from that arithmetic check.
