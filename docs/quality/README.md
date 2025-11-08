# Quality Module

The **quality** module provides tools for assessing the methodological quality and risk of bias of included studies.  Performing a risk‑of‑bias assessment is a critical step in systematic reviews【21136371304256†L35-L80】.

## Models

[`models.py`](../../src/srp/quality/models.py) defines:

- `BiasJudgment`: An enumeration of possible risk‑of‑bias judgments (`LOW`, `SOME_CONCERNS`, `HIGH`, `UNCLEAR`).
- `RiskOfBiasAssessment`: A Pydantic model summarising the result of a risk assessment.  It includes:
  - `paper_id`: Identifier of the assessed paper.
  - `tool`: Name of the tool used (e.g. RoB2, ROBINS‑I, Newcastle‑Ottawa).
  - `overall_judgment`: One of the `BiasJudgment` values.
  - `overall_confidence`: A confidence score between 0 and 1.
  - `domain_assessments`: A list of per‑domain judgments with supporting evidence.
  - Flags for whether human review is required, who reviewed it and when.

## RoBAssessor

The core class in [`rob_assessor.py`](../../src/srp/quality/rob_assessor.py) is `RoBAssessor`.  It supports multiple risk‑of‑bias tools via the `RoBTool` enumeration (e.g. `ROB2`, `ROBINS_I`, `NEWCASTLE_OTTAWA`).  The assessor loads a set of heuristically defined criteria for the selected tool and applies keyword matching to a paper’s full text or abstract:

- **Domains and criteria** – Each tool defines several domains (e.g. randomisation, blinding, incomplete data).  Each domain has associated keywords and a weight.  If many keywords are present in the text, the domain is judged `LOW` risk; fewer matches result in `SOME_CONCERNS` or `HIGH` risk.
- **Judgment aggregation** – The assessor returns a `RiskOfBiasAssessment` with per‑domain judgments, an overall judgment (the worst domain), and an average confidence score.  A paper marked `HIGH` risk or with low confidence (<0.6) triggers a `requires_human_review` flag.

### API

```python
from srp.quality.rob_assessor import RoBAssessor, RoBTool

assessor = RoBAssessor(tool=RoBTool.ROB2)
assessment = assessor.assess_paper(paper, full_text=paper.abstract)
print(assessment.overall_judgment, assessment.overall_confidence)
for domain in assessment.domain_assessments:
    print(domain)
```

## CLI integration

The CLI includes a `quality` command (added in advanced phases) that runs the RoBAssessor on extracted data and aggregates results.  Users can specify which tool to use and a threshold below which papers require human review.