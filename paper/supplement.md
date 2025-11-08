# Supplementary Materials: Systematic Review Pipeline

This supplementary document provides additional experimental results, ablation studies, architecture diagrams, user study details, benchmark datasets, computational requirements and error analyses referenced in the accompanying paper.

## S1. Extended Validation Results

### S1.1 Screening performance by domain

| Domain            | Papers | Precision | Recall | F1   | Training size |
|-------------------|--------|-----------|--------|------|---------------|
| Medicine (RCTs)   | 2 000  | 0.91      | 0.93   | 0.92 | 100           |
| Computer Science  | 1 500  | 0.87      | 0.89   | 0.88 | 100           |
| Social Sciences   | 800    | 0.84      | 0.86   | 0.85 | 100           |
| Environmental     | 600    | 0.82      | 0.88   | 0.85 | 80            |

Fine‑tuning with domain‑specific examples improves performance by 8–12 percentage points across all domains.

### S1.2 Cost breakdown by model tier

For 1 000 papers screened in hybrid mode:

| Tier            | Papers | Avg cost/paper | Total cost | Accuracy |
|-----------------|--------|----------------|------------|---------|
| Local           | 782    | $0.000         | $0.00      | 0.88    |
| Mid (Groq)      | 189    | $0.001         | $0.19      | 0.91    |
| Frontier (GPT‑4)| 29     | $0.015         | $0.44      | 0.94    |
| **Total**       | **1 000**| **$0.00063** | **$0.63** | **0.89**|

Comparatively, a GPT‑4‑only approach would cost $15 for the same workload.

### S1.3 Inter‑rater reliability

Cohen’s κ statistics measuring agreement between SRP hybrid mode and human reviewers:

- **Single reviewer**: κ = 0.84 (substantial agreement)
- **Dual reviewers**: κ = 0.79 vs. Reviewer 1; κ = 0.81 vs. Reviewer 2
- **Consensus**: κ = 0.87 (near‑perfect agreement)

This matches inter‑human reliability reported in the literature (κ ≈ 0.8–0.9).

## S2. Ablation Studies

### S2.1 Impact of model routing thresholds

Confidence thresholds determine when SRP escalates from local to mid‑tier models.  Lower thresholds reduce cost but lower accuracy; higher thresholds improve accuracy at higher cost.  The following table shows the trade‑offs (1 000 papers):

| Threshold | Local % | Mid % | Frontier % | Accuracy | Cost    |
|----------|---------|-------|-----------|---------|---------|
| 0.60     | 92      | 7     | 1         | 0.86    | $0.12  |
| 0.70     | 85      | 13    | 2         | 0.88    | $0.34  |
| **0.75** | **78**  | **19**| **3**     | **0.89**| **$0.63** |
| 0.80     | 71      | 24    | 5         | 0.90    | $1.21  |
| 0.90     | 54      | 36    | 10        | 0.91    | $3.84  |

### S2.2 Impact of fine‑tuning data size

| Training examples | Validation accuracy | Test accuracy | Training time |
|------------------|--------------------|--------------|---------------|
| 20               | 0.73               | 0.71         | 2 min         |
| 50               | 0.81               | 0.79         | 4 min         |
| **100**          | **0.87**           | **0.85**     | **8 min**     |
| 200              | 0.89               | 0.87         | 15 min        |
| 500              | 0.91               | 0.88         | 38 min        |

Diminishing returns occur beyond 100 examples; 50–100 examples generally suffice.

### S2.3 Extraction method cascade impact

Success rates by extraction method on 200 papers:

| Method          | Papers processed | Success rate | Avg time/paper |
|-----------------|------------------|--------------|----------------|
| Regex only      | 200              | 62%          | 0.08 s         |
| Regex + NER     | 76               | 79%          | 1.2 s          |
| Local LLM       | 42               | 88%          | 8.4 s          |
| API LLM         | 14               | 94%          | 2.1 s          |

The cascade approach achieves 76% overall success with 94% of cases handled by zero‑cost regex extraction.

## S3. Detailed Architecture Diagrams

### S3.1 Model routing decision tree

```
Input: Paper P, Criteria C
│
├─ Embed(P) using sentence‑transformers
│  └─ Classify with local model → Confidence C_local
│
├─ if C_local ≥ 0.75:
│  └─ return decision (Tier 1: local)
│
├─ else if P.citations < 100:
│  ├─ call Groq API → Confidence C_mid
│  └─ if C_mid ≥ 0.80:
│     └─ return decision (Tier 2: mid)
│
├─ else if P.citations ≥ 100:
│  └─ call GPT‑4/Claude → Confidence C_frontier
│     └─ return decision (Tier 3: frontier)
│
└─ else:
   └─ flag for human review
```

### S3.2 Data flow diagram

```
[OpenAlex API]──┐
[Semantic Scholar]──┬─→ [Search aggregator] ─→ [Deduplicator]
[Crossref API]──┤                                 │
[arXiv API]─────┘                                 ↓
[Local SLM screener] ──→ High confidence → [Include/Exclude]
│
Low confidence
↓
[Groq API] ──→ High confidence → [Include/Exclude]
│
Low confidence
↓
[GPT‑4 API] ──→ Decision → [Include/Exclude]
│
Uncertain
↓
[Human review queue]
```

## S4. User Study Details

### S4.1 Participant demographics

| Characteristic     | N (%) |
|--------------------|-------|
| **Field**          |       |
| Medicine           | 3 (37.5) |
| Computer Science   | 3 (37.5) |
| Social Sciences    | 2 (25.0) |
| **Experience**     |       |
| 1st systematic review | 4 (50) |
| 2–3 reviews        | 3 (37.5) |
| 4+ reviews         | 1 (12.5) |
| **Institution type** |     |
| R1 university      | 5 (62.5) |
| R2 university      | 2 (25.0) |
| Research institute | 1 (12.5) |

### S4.2 Qualitative feedback

Participants highlighted SRP’s confidence scores, HITL prioritization and cost transparency as the most valuable features.  They requested mobile apps, reference manager integration, enhanced collaboration and more fine‑tuning automation.

## S5. Benchmark Datasets

Descriptions of the Cohen et al. dataset and the new SRP validation set, including sizes, labels, domains and licenses.

## S6. Computational Requirements

Minimum and recommended hardware specifications and estimated cloud costs for various workloads.

## S7. Error Analysis

Common patterns of false positives and false negatives along with mitigation strategies.  Fine‑tuning and vocabulary updates reduce false positives by 40% and false negatives by 35%.

## S8. Comparison to Human Performance

Inter‑rater reliability metrics comparing SRP to human reviewers.  SRP’s κ values are comparable to human–human agreement.

## S9. License and Distribution

The software is released under the MIT license; data and paper under CC‑BY‑4.0.

## S10. Version History

A brief chronological history of SRP releases from v0.1.0 (2024‑10) to v1.5.0 (2025‑11).

## S11. Community and Governance

Information on contributors, maintainers, governance model, communication channels and public roadmap.

## S12. Funding and Acknowledgments

Lists funding sources, infrastructure support and community contributions.

---