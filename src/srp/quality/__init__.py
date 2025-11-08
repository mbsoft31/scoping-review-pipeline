"""Quality assessment package.

This package provides tools for assessing the methodological quality
and risk of bias of studies included in a systematic review.  The
RiskOfBiasAssessment model encapsulates structured judgments for
individual bias domains as well as an overall rating.  Assessors can
choose between different standard tools (e.g. RoB 2, ROBINS‑I,
Newcastle‑Ottawa) and optionally provide extracted data to improve
their judgments.

"""

from .models import BiasJudgment, RiskOfBiasAssessment  # noqa: F401
from .rob_assessor import RoBAssessor, RoBTool  # noqa: F401