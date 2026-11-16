# Explicit timepoint experiment

Run `python3 run_temporal_challenge.py` from the project root. The optional Python entry point is `medcalc.temporal_guard.execute_at_timepoint`. The app supplies the requested phase (admission or discharge), the exact note, its digest recorded when that note was selected, and the proposed calculator call. A trusted caller must bind the phase to the original request. A production EHR integration would also need to bind patient and encounter identity.

A supported export uses a standalone timepoint heading, followed by one explicitly named field and an entire quantity per line. An unrecognized heading ends the previous section. Different canonical quantities for one required field cause an abstention. Equivalent repetitions preserve the first source span. The wrapper requires all fields in one section and checks their units and domain before calculating. It records offsets into the exact note. Out-of-section quantities cannot supply missing values.

The 19 authored fixtures contain 17 distinct synthetic texts and cover BMI, mean arterial pressure, anion gap, and corrected sodium. The expected canonical quantities and numerical answers are explicit constants. Both implementations receive the same calls and notes. Scoring requires agreement on all canonical quantities and the final value. Seven fixtures have missing or conflicting evidence, so an abstention is appropriate. These related scenarios test the adapter contract. The fixture author supplied the expected values without independent clinical review.

| Outcome | Frozen source repair | Explicit timepoint guard |
|---|---:|---:|
| Correct release on 12 answerable cases | 4 | 10 |
| Nonmatching release on an answerable case | 8 | 0 |
| Abstention on an answerable case | 0 | 2 |
| Unsupported release on 7 ambiguous/missing cases | 7 | 0 |
| Appropriate abstention on an ambiguous/missing case | 0 | 7 |

Two answerable free-text controls fall outside the supported format, so the new guard withholds both. Among the previous 50 validation questions, 45 explicitly requested first admission. **Zero of these 45 notes had the required admission section.** Direct use of this guard on those notes would withhold every explicitly requested admission result. This controlled improvement applies only to appropriately structured records. It leaves the original frozen benchmark results intact.

The contained runner supplies the expected digest from each input row for reproduction. A separate regression changes the note after recording its digest. Synthetic fixtures use point-in-time section labels that may themselves be inaccurate in real data. Other forms of timing, multiple encounters, events within the same phase, incorrect source labels, narrative interpretation, and EHR transaction semantics are outside the evaluated contract.
