"""LLM/SLM integration layer for the systematic review pipeline.

This package provides building blocks for integrating local and API‑based
language models into the pipeline.  It exposes a unified router for task
routing, managers for local and remote models, and a fine‑tuning
pipeline for adapting classifiers to domain‑specific screening tasks.

The public API exports the following classes:

* ``ModelRouter`` – orchestrates routing between local, mid‑tier and
  frontier models based on task complexity, confidence thresholds and
  cost budgets.
* ``LocalModelManager`` – manages on‑disk caches of sentence
  transformers, classification models, generative models and NER models.
  It handles loading, inference and metrics for local models.
* ``APIModelManager`` – wraps calls to third‑party LLM providers such
  as OpenAI, Anthropic, Groq, Google and Together AI.  It also tracks
  token usage and costs.
* ``FineTuningPipeline`` – provides utilities for parameter‑efficient
  fine‑tuning of sequence classification models on screening decisions.

These components are imported into the top‑level namespace for
convenience.
"""

"""Public API for the ``srp.llm`` package.

This package exposes the primary classes used for language model
integration: ``ModelRouter`` for routing tasks between local and API
models, ``LocalModelManager`` and ``APIModelManager`` for handling
specific model backends, and ``FineTuningPipeline`` for training
custom classifiers.  See the documentation in each module for details.
"""

from .router import ModelRouter  # noqa: F401
from .local_models import LocalModelManager  # noqa: F401
from .api_models import APIModelManager  # noqa: F401
from .fine_tuning import FineTuningPipeline  # noqa: F401

__all__ = [
    "ModelRouter",
    "LocalModelManager",
    "APIModelManager",
    "FineTuningPipeline",
]

__all__ = [
    "ModelRouter",
    "LocalModelManager",
    "APIModelManager",
    "FineTuningPipeline",
]