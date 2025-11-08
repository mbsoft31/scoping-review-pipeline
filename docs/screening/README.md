# Screening Module

The **screening** module implements semi‑automated and interactive workflows for deciding whether papers meet inclusion criteria.  Screening is one of the most labour‑intensive stages of a systematic review, and this module provides tools to reduce that burden through semantic matching, active learning and human‑in‑the‑loop review.

## Key Concepts

- **ScreeningCriterion** (`models.py`): Represents an inclusion or exclusion criterion with a name and a list of keywords.  During screening, the paper’s title and abstract are compared against these keywords.
- **ScreeningDecision**: An enum of possible decisions (`INCLUDE`, `EXCLUDE`, `MAYBE`) assigned by the screener.
- **ScreeningMode**: Specifies how the screener should operate – `auto`, `semi_auto`, `hitl` (human in the loop) or `manual`.
- **ScreeningResult**: A Pydantic model summarising the screener’s decision for a paper, including matched criteria, confidence scores and any assigned tags.
- **DomainVocabulary**: Contains a domain name and a list of conceptual keywords used by the semantic matcher to compute relevance scores.

## Semantic Matching

The [`semantic_matcher.py`](../../src/srp/screening/semantic_matcher.py) module defines a `SemanticMatcher` class.  It uses [sentence‑transformers](https://www.sbert.net/) to embed text into a high‑dimensional vector space.  The matcher pre‑computes embeddings for the inclusion and exclusion criteria and optional domain vocabulary, and computes cosine similarities between a paper’s title/abstract and each criterion.  It can rank papers by relevance to the criteria and return similarity scores for further decision making.

## AutoScreener

Implemented in [`screener.py`](../../src/srp/screening/screener.py), `AutoScreener` applies rules to the similarity scores to produce preliminary screening decisions:

- It requires a `SemanticMatcher` instance and thresholds for auto inclusion/exclusion (`auto_threshold`) and the “maybe” category (`maybe_threshold`).
- For each paper, it computes similarity scores to inclusion and exclusion criteria.  If the highest inclusion score exceeds `auto_threshold` and also exceeds the exclusion score, the paper is automatically included.  Conversely, if the exclusion score exceeds `auto_threshold`, the paper is excluded.  Papers with scores in between are marked as `MAYBE` and can be prioritised for human review.
- The screener returns a `ScreeningResult` with the decision, matched criteria and confidence.
- In `semi_auto` and `hitl` modes, the screener uses an `HITLReviewer` to create a queue of uncertain papers for manual review.

## HITL Reviewer

[`hitl.py`](../../src/srp/screening/hitl.py) defines `HITLReviewer`, which manages the human‑in‑the‑loop process:

- It stores automatic screening results and a review queue in a local directory (`review/`).
- Reviewers can fetch batches of papers to review, confirm or override the auto decision and record notes.  The reviewer’s identity and decisions are logged.
- Statistics such as agreement rate with the auto screener and the number of remaining papers are tracked.

## Active Learning

[`active_learner.py`](../../src/srp/screening/active_learner.py) introduces `ActiveScreener`, an active learning algorithm that iteratively trains a classifier on reviewer decisions to prioritise the most uncertain papers:

1. **Feature extraction** – Uses a TF‑IDF vectoriser over titles and abstracts (1‑ to 3‑grams).
2. **Classifier** – Employs a Random Forest within a `CalibratedClassifierCV` to output calibrated probabilities.
3. **Training** – The user supplies a seed set of manually screened papers to train the initial model.
4. **Prediction** – Remaining papers are predicted as include, exclude or maybe based on probability thresholds (0.7/0.3 by default).
5. **Uncertainty sampling** – The `select_uncertain()` method picks papers with the highest entropy in the predicted probabilities for further labelling.

## API and CLI

Programmatically, you can use the screener as follows:

```python
from srp.screening.screener import AutoScreener
from srp.screening.semantic_matcher import SemanticMatcher

matcher = SemanticMatcher(model_name="all-MiniLM-L6-v2")
screener = AutoScreener(matcher, auto_threshold=0.75, maybe_threshold=0.5)
result = screener.screen_paper(paper, inclusion_criteria, exclusion_criteria)
print(result.decision, result.confidence)
```

The CLI exposes two commands:

- `srp screen`: Runs Phase 1.5 screening on Phase 1 results.  Accepts criteria and optional domain vocabulary YAML files and outputs screening results, with an optional review queue for uncertain papers.
- `srp review`: Launches an interactive reviewer loop to confirm or override the screener’s decisions and record notes.

These commands make it easy to incorporate semi‑automated screening into your systematic review workflow.