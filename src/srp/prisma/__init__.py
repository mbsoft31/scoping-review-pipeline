"""Utilities for generating PRISMA flow diagrams.

This module exposes a helper to create PRISMA flow charts from the
intermediate outputs of the systematic‑review pipeline.  PRISMA
diagrams are a standard way to transparently report how many
records were identified, screened, excluded and ultimately
included in a review【225382337630412†L102-L110】.  Using this
module, users can automatically summarise their workflow and
produce a publication‑ready image.
"""

from .diagram import generate_prisma_diagram, compute_prisma_counts

__all__ = ["generate_prisma_diagram", "compute_prisma_counts"]