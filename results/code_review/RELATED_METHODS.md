# Published-method comparison

Zhao et al. describe MedCalc-Pro's retrieval, selection, extraction, structured parameter checks, evidence audit and execution. The authors already investigated tool-call reliability, evidence checks and error propagation in medical calculation. Describe that overlap when positioning this contribution. The narrow comparison here tests which numerical results different policies return from the same generated proposals. [Paper, §3.3 and Table 3](https://aclanthology.org/2026.findings-emnlp.1512.pdf)

The executable comparison replays the **authors' first-pass structured validator and their scoring functions** at commit 751a514644d22bc6f7066087205fbbb61b7b40f5. The wrapper translates local field names to the corresponding registry field names and passes the recorded values, units and quotes. It invokes the unmodified upstream methods, including their native scoring precision. It performs no source repair, conversion or substitution before calling those methods. Every source, configuration and formula used has a pinned SHA-256 digest in upstream_hashes.json. Third-party code remains in its upstream repository. [Upstream implementation](https://github.com/easymoney7774/MedCalc-Pro/blob/751a514644d22bc6f7066087205fbbb61b7b40f5/core/Execution.py)

| Stage | Treatment of the archived call |
|---|---|
| Retrieval and tool selection | All policies receive the same model's archived selection as an input. The local reviewed policy may independently resolve the task from the question and return a fallback calculation. |
| Parameter extraction | The first-pass component receives the original generated values, units and evidence, translated into the upstream slot names. A missing call stays unanswered. |
| Structured validation | Executes upstream _validate_parameters using the published calculator schemas. The wrapper records an unanswered case if the published validator requests a new model-based unit conversion. |
| Evidence audit, re-extraction and retries | The authors' _reflect_parameters and _extract_parameters issue new model prompts. The archived planner and one extractor response do not contain their answers. These stages cannot be reconstructed by pure replay, so a numerical result for the full agent remains unmeasured. |
| Numerical calculation | Executes upstream _execute_score_code with the upstream validator's flattened parameters, matching the data handoff in its run method. A result must select the benchmark tool and land within the original interval to match. |
| Temporal controls and atomic publication | Separate experiments in this package. They are outside this upstream component replay. |

The mapping covers nine of the project's ten formula definitions. The pinned registry includes the Schwartz long-QT score, which is a different task from the Bazett QTc equation, and does not supply the required Bazett-only entry point. The original 44-case primary panel contained five Bazett questions and zero eligible anion-gap cases. Thus the comparison contains all 39 questions for eight represented formulas. All methods share those cases. Missing calls, incorrect selections and cases requiring extra conversion requests remain in the denominator. The published component comparison was added after primary registration, independently of the locked evaluations. [Pinned calculator registry](https://github.com/easymoney7774/MedCalc-Pro/blob/751a514644d22bc6f7066087205fbbb61b7b40f5/data/scales_registry.json)

| Primary model and method | Matches | Disagrees | Unanswered |
|---|---:|---:|---:|
| qwen2.5_1.5b · published first pass | 25 | 5 | 9 |
| qwen2.5_1.5b · unit domain | 28 | 7 | 4 |
| qwen2.5_1.5b · reviewed | 31 | 2 | 6 |
| smollm2_1.7b · published first pass | 22 | 8 | 9 |
| smollm2_1.7b · unit domain | 22 | 15 | 2 |
| smollm2_1.7b · reviewed | 29 | 1 | 9 |

For qwen2.5_1.5b, both the upstream component and reviewed policy returned a number on 26 cases. Their matching counts on those identical cases were 21 and 24, respectively. The upstream component requested model-based conversion on 6 cases. For smollm2_1.7b, both the upstream component and reviewed policy returned a number on 24 cases. Their matching counts on those identical cases were 18 and 24, respectively. The upstream component requested model-based conversion on 9 cases.
 
The comparison answers a component-level question conditional on these cached proposals. The full published system can obtain other selections, extractions, conversions and re-audits. The two panels of 39 model workflows reuse the same 39 questions.

Run the comparison against a local checkout of the pinned MedCalc-Pro commit with the Python standard library:

```bash
python3 results/code_review/compare_published_component.py --upstream /path/to/MedCalc-Pro --model qwen2.5_1.5b_q4km
python3 results/code_review/compare_published_component.py --upstream /path/to/MedCalc-Pro --model smollm2_1.7b_q4km
```

The project's stored per-case outputs are published_component_primary_*.json. They identify every original row and the reason when an upstream conversion generation would have been needed. The separate AgentSpec work by Wang et al. supplies a language for event-triggered predicates and actions. A new clinical rule library would define the operative decisions in an adaptation, so no AgentSpec accuracy is attributed to the current replay. [AgentSpec paper](https://arxiv.org/abs/2503.18666) · [AgentSpec implementation](https://github.com/haoyuwang99/AgentSpec/blob/master/README.md)
