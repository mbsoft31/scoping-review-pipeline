"""Meta‑analysis utilities.

This package contains classes and functions to perform quantitative
meta‑analysis on effect sizes extracted from primary studies.  It
supports fixed and random effects models, heterogeneity testing,
publication bias assessment and generation of forest plot data.

"""

from .analyzer import MetaAnalyzer, EffectSize  # noqa: F401
from .forest_plot import create_forest_plot  # noqa: F401