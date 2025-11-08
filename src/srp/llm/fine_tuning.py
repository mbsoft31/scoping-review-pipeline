"""Fine‑tuning utilities for systematic review models.

This module provides lightweight scaffolding to prepare training data
from human‑reviewed screening results and to fine‑tune a classifier
using parameter‑efficient methods such as LoRA.  The heavy lifting
required for fine‑tuning (data loading, training loops, etc.) is
encapsulated behind simple methods.  In environments without GPUs or
large memory, these methods behave as stubs, logging a warning and
returning the base model path unchanged.

Usage Example::

    pipeline = FineTuningPipeline(
        base_model="allenai/scibert_scivocab_uncased",
        output_dir=Path("models/fine_tuned"),
    )
    train_papers, train_labels = pipeline.prepare_training_data(results, papers)
    model_path = pipeline.fine_tune_with_lora(train_papers, train_labels)
    inference_path = pipeline.export_for_inference(model_path, quantize=True)

Note that the actual fine‑tuning is not performed in this stub to
avoid heavy computation during testing.  To enable real training, you
can install ``transformers``, ``peft`` and ``bitsandbytes`` and
replace the stub implementation with the full LoRA training loop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.models import Paper
from ..screening.models import ScreeningResult, ScreeningDecision
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScreeningDataset:
    """A lightweight dataset for screening fine‑tuning.

    When fine‑tuning is enabled, this class wraps a list of papers and
    corresponding labels and exposes them via ``__len__`` and
    ``__getitem__``.  During inference in this stub, it simply stores
    the data and makes it available for the trainer when implemented.
    """

    papers: List[Paper]
    labels: List[int]
    tokenizer: Any
    max_length: int = 512

    def __len__(self) -> int:
        return len(self.papers)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        # Combine the title and abstract
        paper = self.papers[idx]
        label = self.labels[idx]
        text = f"{paper.title}\n\n{paper.abstract or ''}"
        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        # Flatten the tensors
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": label,
        }


class FineTuningPipeline:
    """Pipeline to fine‑tune a text classifier for screening.

    This class wraps the steps required to prepare training data from
    screening results, perform parameter‑efficient fine‑tuning, and
    export the resulting model for inference.  In this simplified
    implementation, the fine‑tuning steps are no‑ops and simply log
    progress messages.  The returned model path will be the base
    model's path inside ``output_dir``.
    """

    def __init__(self, base_model: str = "allenai/scibert_scivocab_uncased", output_dir: Optional[Path] = None) -> None:
        self.base_model = base_model
        self.output_dir = output_dir or Path("models") / "fine_tuned"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def prepare_training_data(
        self,
        screening_results: List[ScreeningResult],
        papers: List[Paper],
    ) -> Tuple[List[Paper], List[int]]:
        """Prepare training examples from human‑reviewed screening results.

        This method pairs each reviewed paper with a binary label (1 for
        inclusion, 0 for exclusion) and filters out papers without
        explicit decisions.
        """
        paper_map = {p.paper_id: p for p in papers}
        training_papers: List[Paper] = []
        training_labels: List[int] = []
        for result in screening_results:
            if result.reviewed_by is None:
                # Skip results without human review
                continue
            paper = paper_map.get(result.paper_id)
            if not paper:
                continue
            # Determine label: include=1, exclude=0
            decision = result.human_override or result.decision
            if decision == ScreeningDecision.INCLUDE:
                training_papers.append(paper)
                training_labels.append(1)
            elif decision == ScreeningDecision.EXCLUDE:
                training_papers.append(paper)
                training_labels.append(0)
        logger.info(f"Prepared {len(training_papers)} training examples")
        return training_papers, training_labels

    def fine_tune_with_lora(
        self,
        train_papers: List[Paper],
        train_labels: List[int],
        val_papers: Optional[List[Paper]] = None,
        val_labels: Optional[List[int]] = None,
        num_epochs: int = 3,
        learning_rate: float = 2e-4,
        batch_size: int = 8,
        lora_r: int = 16,
        lora_alpha: int = 32,
    ) -> Path:
        """Perform LoRA fine‑tuning of the base model.

        In this stub, no actual training is performed.  A directory is
        created in ``self.output_dir`` and a metadata file is saved to
        document the intended training parameters.  The returned path
        points to the created directory.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        model_path = self.output_dir / f"{Path(self.base_model).name}_lora_{timestamp}"
        model_path.mkdir(parents=True, exist_ok=True)
        # Save metadata
        metadata = {
            "base_model": self.base_model,
            "training_size": len(train_papers),
            "validation_size": len(val_papers) if val_papers else 0,
            "num_epochs": num_epochs,
            "learning_rate": learning_rate,
            "lora_r": lora_r,
            "lora_alpha": lora_alpha,
            "created_at": timestamp,
            "note": "This is a stub; no training was performed.",
        }
        (model_path / "metadata.json").write_text(json.dumps(metadata, indent=2))
        logger.warning("Fine‑tuning is not implemented in this environment; returning stub model path")
        return model_path

    def export_for_inference(self, model_path: Path, quantize: bool = True) -> Path:
        """Export a fine‑tuned model for inference.

        This stub simply returns the provided ``model_path``.  In a
        full implementation, this would convert the model into a
        quantized or otherwise optimised format for CPU inference.
        """
        logger.info(f"Exporting model {model_path} for inference (stub)")
        return model_path