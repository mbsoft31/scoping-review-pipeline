# Meta Module

The **meta** module implements statistical meta‑analysis routines and visualisation utilities.  It allows you to synthesise effect sizes from multiple studies and assess heterogeneity and publication bias.

## Analyzer

The `MetaAnalyzer` class defined in [`analyzer.py`](../../src/srp/meta/analyzer.py) provides several methods:

- `compute_pooled_effect(effect_sizes: List[EffectSize], method: str = "random") -> Dict`: Computes a pooled effect estimate using either a fixed‑effect or random‑effects model.  Weights are inversely proportional to the squared standard errors (for fixed effect) or incorporate between‑study variance (`tau²`) estimated via the DerSimonian–Laird method (for random effects).  Returns the pooled estimate, standard error, confidence interval and z‑test p‑value.
- `assess_heterogeneity(effect_sizes: List[EffectSize]) -> Dict`: Calculates Cochran’s Q statistic, the I² statistic and between‑study variance to quantify heterogeneity among studies, along with an interpretation (low, moderate, substantial, considerable).  The Q statistic tests the null hypothesis that all effects are equal.
- `publication_bias_test(effect_sizes: List[EffectSize]) -> Dict`: Performs Egger’s regression test for publication bias by regressing effect estimates on their standard errors.  Returns the intercept, p‑value and an interpretation.
- `generate_forest_plot_data(effect_sizes: List[EffectSize], pooled: Dict) -> pandas.DataFrame`: Constructs a DataFrame summarising individual effect sizes and the pooled estimate, suitable for plotting.

### EffectSize dataclass

Also in `analyzer.py`, the `EffectSize` dataclass holds per‑study effect information: `study_id`, `effect`, `se`, `ci_lower`, `ci_upper`, `weight` and optional `sample_size`.  Instances of `EffectSize` are consumed by the analyzer.

## Forest Plot

[`forest_plot.py`](../../src/srp/meta/forest_plot.py) provides a convenience function `create_forest_plot(df: pandas.DataFrame, output_path: Path) -> None` that takes the DataFrame from `generate_forest_plot_data()` and produces a forest plot using Matplotlib.  Each row displays a point estimate with its confidence interval; the pooled effect is shown as a diamond or horizontal bar.  The plot is saved to the specified file.

## CLI integration

The CLI exposes a `meta` command that accepts a CSV file of effect sizes (with columns for study ID, effect estimate and standard error), computes the pooled effect using the specified method (`fixed` or `random`) and produces a forest plot.  Example usage:

```bash
srp meta --effects-csv my_effects.csv --method random --output my_forest_plot.png
```

Effect sizes can be derived manually from extracted outcomes or using custom code outside of the pipeline.  The meta module does not perform automatic extraction of effect sizes; it focuses on the synthesis step.