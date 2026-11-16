"""Create the short engineering evidence report from complete packaged outputs."""
import json
from pathlib import Path

from summarize_official_policies import SMALL, LARGE

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
MODELS = {SMALL[0]: "Qwen2.5-1.5B", SMALL[1]: "SmolLM2-1.7B", LARGE: "Qwen2.5-7B"}
METHODS = {"baseline":"Unit and domain checks", "source_repair":"Original source repair",
           "note_only":"Named measurements, without a model", "combined":"Combined candidate",
           "reviewed":"Combined candidate plus local context checks"}


def read(path):
    return json.loads(path.read_text())


def table(reports, view):
    lines = ["| Model | Method | All cases | Within benchmark interval | Nonmatching release | No answer |",
             "|---|---|---:|---:|---:|---:|"]
    for model, report in reports.items():
        for key, label in METHODS.items():
            result = report[view][key]
            lines.append(f"| {MODELS[model]} | {label} | {result['cases']} | {result['matched']} ({result['agreement']:.1%}) | "
                         f"{result['nonmatching']} | {result['unanswered']} |")
    return lines


def main():
    reports = {m:read(RESULTS/"final_evaluation"/m/"report.json") for m in MODELS}
    for m, r in reports.items():
        if r["all"]["baseline"]["cases"] != (44 if m == LARGE else 124):
            raise ValueError("Final evidence requires all registered cases")
    lines = ["# MedCalc-Enforce v0.4 experiment results","",
             "Two open-weight models executed the planner and extraction tasks on all 124 eligible distinct official test cases. A third, larger model ran on the same first 44 cases. That makes 292 model-case attempts on 124 underlying sources. An outcome matches when it uses the requested calculator and falls within the original answer interval. Every abstention, workflow failure and nonmatching release remains in the denominator. The original development figures from v0.3 are recorded separately in the historical report.","",
             "## All evaluated cases by model",""] + table(reports,"all")
    lines += ["","The first official cohort was capped at five examples per calculator. The extension included all 80 remaining eligible distinct sources. It was locked before the first model’s official summary was scored. The larger model comparison was added separately. Its cohort was limited to the first 44. All models use the same underlying formulas. The global note-only row is deterministic and repeats across models evaluated on the same cases.","",
              "The combined candidate was frozen before official scoring. The additional context checks were developed from synthetic CLI review examples and locked while the first model was running, before the reviewer examined official results. Treat this reviewed row as a secondary analysis. Neither published benchmark answers nor scores enter runtime decisions.","",
              "## Paired comparisons and input agreement","",
              "| Model | Context-checked candidate gained / lost matches vs baseline | Paired exact p | All released inputs agree with annotations | Answer matches despite a discrepant input |",
              "|---|---:|---:|---:|---:|"]
    for m, report in reports.items():
        r=report["all"]["reviewed"]
        lines.append(f"| {MODELS[m]} | {r['paired_gains']} / {r['paired_losses']} | {r['paired_exact_p_unadjusted']:.4g} | "
                     f"{r['field_checks'].get('all_annotated_inputs_matched',0)}/{r['matched']+r['nonmatching']} | "
                     f"{len(r['case_ids'].get('answer_in_tolerance_despite_field_disagreement', []))} |")
    lines += ["","P values are exploratory and unadjusted for multiple methods and endpoints. Conditional field agreement is assessed against the benchmark entities with numeric relative tolerance 1e-5. Exact agreement on the reference quantity is more demanding than the benchmark answer interval. Confidence intervals, case IDs, calculator breakdowns and transition counts are included in each model report.","",
              "## Initial cohort for an equal comparison of model sizes",""] + table(reports,"first")
    lines += ["","## Notes with extracted clinical narrative","",
              "All 124 questions repeat normalized question templates in the benchmark training data. Twenty QTc notes also match a training-note template after replacing numbers. None of the remaining 104 extracted notes reached 0.70 Jaccard similarity using number-masked token five-grams against the pinned training and one-shot notes. Exact normalized-note and source-key overlap is zero under the declared rule. This sensitivity analysis changes the mix of calculators because it removes the QTc family. It does not test generalization to novel requests or model pretraining exposure.",""] + table(reports, "extracted_source_notes")
    lines += ["","## What each code change contributes","",
              "The baseline executes the model-proposed quantities with unit conversion and arithmetic checks. The original repair rebinds those proposals to quantities in the note. The combined version uses question-based calculator selection and falls back to a complete set of unique, explicitly named measurements if the model call is missing or unsupported. The secondary guard additionally checks for explicit subject, measurement-status, time and output-statistic conflicts. A note-only comparator measures what the same templated questions and named fields allow without model inference.","",
              "All policies remain subject to source parsing errors and missing context. The engineering review documents cases that passed substring verification despite using a relative’s weight or a target weight. The local guard fixed the explicit examples and still failed two fresh probes in which another sentence supplied the subject or time. A locally supported value can still be a wrong-time or wrong-person value.","",
              "The equal-coverage analysis ranks baseline releases by the proportion of individually supported source quotes and integrates tie breaking. It also reports uniform thinning, per-calculator quotas, and answers released on identical cases. The comparisons are retrospective diagnostics. Detailed model-by-model results and uncertainty are in [the paired ablation report](results/official_ablations/REPORT.md).","",
              "## Temporal and commit-time experiments","",
              "In 19 authored temporal scenarios, the structured-section guard matched 10 of 12 answerable requests, withheld the other two, and abstained on all seven ambiguous or incomplete requests. The comparisons used four calculators and 17 distinct texts. The earlier narrative validation set contained zero compatible sectioned notes among 45 explicitly requesting first-admission measurements. The temporal guard is a separate structured-input policy with a narrower contract.","",
              "In 216 controlled two-connection SQLite trials, the read-then-write baseline published 36 superseded revisions in its 108 trials. Twelve of those had an outdated numerical value. The atomic publication check published zero superseded revisions in 108 trials. It withheld 24 otherwise numerically valid answers after an irrelevant addendum or an edit that restored the original value. These schedules test the local publication invariant and its coverage cost. They do not measure production incidence. The reference experiment used BMI. The integrated checked store also has regression coverage for an edit between staging and publication.","",
              "## Arithmetic and source integrity","",
              "A Decimal implementation reconstructed all 124 reference answers from 303 annotated fields within 0.1%. Four osmolality rationales repeat the BUN value in the displayed glucose term despite a matching reference answer. One annotated blood-pressure unit is absent directly after the pressure pair. The original registry rejects one unusual count-volume spelling. All labels were preserved; the separate offline field-level audit supports the reported input comparisons.","",
              "## Scope and remaining evidence","",
              "Nine calculator families survived the full training and one-shot source exclusion. Anion gap had no eligible independent official cases under these rules. The Q4_K_M weights and decoding configuration are pinned. Replicates on the same notes with multiple models remain paired measurements. Accuracy on these notes does not establish patient outcomes, clinical validation, hospital deployment or end-to-end correctness under distributed EHR updates.","",
              "A transfer audit considered MedCalc-Pro Simple. All 200 records spanning the supported families shared sources with the existing evaluation or development data. The audit therefore produced no independent external estimate. The published framework comparison is documented in [the methods comparison](results/code_review/RELATED_METHODS.md) with its actual execution scope.","",
              "The next substantive validation would be blinded review of variable identity, units, timepoint and appropriateness on independent notes with new question wording. Each reviewer should see the source and requested computation before seeing system output. The public score set can support retrospective error analysis; it has now been evaluated.","",
              "## Reproduce","",
              "Run `python3 verify_release.py` from the unpacked project to verify checksums and reproduce the main decisions and totals from retained model generations. See [the protocol](OFFICIAL_PROTOCOL.md) for fresh inference commands. [The per-case artifacts](results/final_evaluation/) retain nonmatching answer IDs, reasons for abstention, evidence spans, repaired values and per-model diagnostics.",""]
    latency = read(RESULTS/"runtime_latency/summary.json")
    rows = ["", "## Measured local execution time", "",
            "| Method | Timed attempts | Median milliseconds | 95th percentile milliseconds |",
            "|---|---:|---:|---:|"]
    for method, values in latency["timing_ms"].items():
        rows.append(f"| {method} | {values['observations']} | {values['median']:.3f} | {values['p95']:.3f} |")
    rows.extend(["", "Fifty earlier cases were timed three times each in shuffled order. Timing includes abstentions, excludes model generation and was measured on a shared CPU. Publication includes local durable SQLite operations. Latencies describe this run only.", ""])
    insertion = lines.index("## Reproduce")
    lines[insertion:insertion] = rows
    (ROOT/"RESULTS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
