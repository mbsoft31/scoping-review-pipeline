"""Local model management for LLM and SLM usage.

This module provides a unified manager for loading and using a variety
of local models, including sentence transformers for embeddings,
SciBERT/PubMedBERT for classification, quantized large language models
via llama‑cpp for text generation, and spaCy models for biomedical
named‑entity recognition.  It also tracks inference statistics.

The manager lazily loads models when first used to conserve memory.  It
supports optional loading of fine‑tuned classification weights and
handles device selection automatically based on available hardware.

Note: Heavy dependencies such as ``torch``, ``sentence_transformers`` and
``llama_cpp`` are imported within methods to avoid import overhead
during CLI startup.  Some functions will raise an exception if the
required packages are not installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a local model.

    Attributes:
        name: Human‑readable name for the model.
        model_path: Filesystem path or Hugging Face model identifier.
        model_type: One of ``embedding``, ``classification``, ``generative``
            or ``ner``.
        device: Device string (e.g., ``cpu``, ``cuda``, ``mps``).
        quantized: Whether the model is quantized (for generative models).
        context_length: Maximum context length supported.
        batch_size: Batch size used for embedding generation.
    """

    name: str
    model_path: str
    model_type: str
    device: str = "cpu"
    quantized: bool = False
    context_length: int = 512
    batch_size: int = 32


class LocalModelManager:
    """Unified manager for local models.

    This class hides the details of loading and using various types of
    models.  It keeps track of loaded models in an internal registry
    keyed by model type (e.g., ``embedding``, ``classifier``,
    ``generative``, ``ner``) and records simple inference statistics for
    performance monitoring.  Devices are auto‑detected at construction.
    """

    def __init__(self, model_dir: Optional[Path] = None, device: Optional[str] = None) -> None:
        # Determine model cache directory
        self.model_dir = model_dir or Path.home() / ".cache" / "srp_models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Determine default device
        if device is None:
            try:
                import torch  # type: ignore

                if torch.cuda.is_available():
                    device = "cuda"
                elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            except Exception:
                device = "cpu"
        self.device: str = device
        logger.info(f"LocalModelManager using device: {self.device}")

        self.models: Dict[str, Any] = {}
        self.inference_count: int = 0
        self.total_inference_time: float = 0.0

    # ---------------------------------------------------------------------
    # Embedding model
    def load_embedding_model(self, model_name: str = "sentence-transformers/all-mpnet-base-v2") -> Any:
        """Load a sentence transformer for embeddings.

        Args:
            model_name: Hugging Face model name.

        Returns:
            SentenceTransformer instance.
        """
        if "embedding" in self.models:
            return self.models["embedding"]
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is required for embedding generation") from exc
        logger.info(f"Loading embedding model: {model_name}")
        model = SentenceTransformer(model_name, device=self.device)
        self.models["embedding"] = model
        return model

    # ---------------------------------------------------------------------
    # Classification model
    def load_classifier_model(
        self,
        model_name: str = "allenai/scibert_scivocab_uncased",
        num_labels: int = 2,
        fine_tuned_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Load a sequence classification model.

        If a fine‑tuned model directory is provided, it will be loaded
        instead of the base model.  The tokenizer is always loaded from
        ``model_name``.

        Args:
            model_name: Base model name.
            num_labels: Number of classification labels.
            fine_tuned_path: Path to fine‑tuned weights.

        Returns:
            Dict with keys ``model`` and ``tokenizer``.
        """
        if "classifier" in self.models:
            return self.models["classifier"]
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore
        except ImportError as exc:
            raise RuntimeError("transformers is required for classification models") from exc
        logger.info(f"Loading classifier: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if fine_tuned_path and fine_tuned_path.exists():
            logger.info(f"Loading fine‑tuned weights from {fine_tuned_path}")
            model = AutoModelForSequenceClassification.from_pretrained(str(fine_tuned_path), num_labels=num_labels)
        else:
            model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_labels)
        # Move to device
        try:
            import torch  # type: ignore
            model.to(self.device)
            model.eval()
        except Exception:
            pass
        self.models["classifier"] = {"model": model, "tokenizer": tokenizer}
        return self.models["classifier"]

    # ---------------------------------------------------------------------
    # Generative model
    def load_generative_model(self, model_path: Optional[Path] = None, quantized: bool = True) -> Dict[str, Any]:
        """Load a local generative model for text generation.

        If ``quantized`` is True, the model will be loaded via
        `llama-cpp-python` as a quantized GGUF file.  Otherwise, a
        full‑precision Transformers model will be loaded from
        ``mistralai/Mistral-7B-Instruct-v0.2``.
        """
        if "generative" in self.models:
            return self.models["generative"]
        if not quantized:
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
                import torch  # type: ignore
            except ImportError as exc:
                raise RuntimeError("transformers is required for generative models") from exc
            model_name = "mistralai/Mistral-7B-Instruct-v0.2"
            logger.info(f"Loading generative model: {model_name}")
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=dtype, device_map="auto" if self.device == "cuda" else None)
            self.models["generative"] = {
                "model": model,
                "tokenizer": tokenizer,
                "type": "transformers",
            }
        else:
            # Use llama-cpp for quantized inference
            try:
                from llama_cpp import Llama  # type: ignore
            except ImportError as exc:
                raise RuntimeError("llama-cpp-python is required for quantized LLM inference") from exc
            if model_path is None:
                model_path = self.model_dir / "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
            if not model_path.exists():
                raise FileNotFoundError(f"Quantized model not found at {model_path}. Please download it using scripts/download_models.sh")
            logger.info(f"Loading quantized generative model: {model_path.name}")
            # Determine GPU layers for partial offload if running on GPU
            n_gpu_layers = 0
            try:
                import torch  # type: ignore
                if self.device != "cpu":
                    # Rough heuristic: use half of the layers on GPU
                    n_gpu_layers = 35
            except Exception:
                n_gpu_layers = 0
            model = Llama(
                model_path=str(model_path),
                n_ctx=4096,
                n_threads=4,
                n_gpu_layers=n_gpu_layers,
                verbose=False,
            )
            self.models["generative"] = {
                "model": model,
                "type": "llama_cpp",
            }
        return self.models["generative"]

    # ---------------------------------------------------------------------
    # Named‑entity recognition model
    def load_ner_model(self, model_name: str = "en_core_sci_lg") -> Any:
        """Load spaCy NER model for biomedical text.

        Args:
            model_name: spaCy model name.  If the model is not installed,
                it will be downloaded automatically.

        Returns:
            Loaded spaCy ``Language`` object.
        """
        if "ner" in self.models:
            return self.models["ner"]
        try:
            import spacy  # type: ignore
        except ImportError as exc:
            raise RuntimeError("spaCy is required for NER models") from exc
        try:
            nlp = spacy.load(model_name)
        except OSError:
            logger.info(f"Downloading spaCy model {model_name}...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", model_name], check=True)
            nlp = spacy.load(model_name)
        self.models["ner"] = nlp
        return nlp

    # ---------------------------------------------------------------------
    # Embedding inference
    async def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of input strings.
            batch_size: Batch size for inference.

        Returns:
            NumPy array of embeddings.
        """
        import time
        start = time.time()
        model = self.load_embedding_model()
        embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True)
        elapsed = time.time() - start
        self.inference_count += len(texts)
        self.total_inference_time += elapsed
        logger.debug(f"Embedded {len(texts)} texts in {elapsed:.2f}s")
        return embeddings

    # ---------------------------------------------------------------------
    # Classification inference
    async def classify_text(
        self,
        text: str,
        labels: List[str] = ["include", "exclude"],
        fine_tuned_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Classify a single text with a local classifier.

        Args:
            text: The text to classify.
            labels: List of label names corresponding to the classifier
                outputs (default: ``include``, ``exclude``).
            fine_tuned_path: Optional path to a fine‑tuned classifier.

        Returns:
            Dictionary with prediction, confidence, all scores and
            inference time.
        """
        import time
        start = time.time()
        classifier = self.load_classifier_model(num_labels=len(labels), fine_tuned_path=fine_tuned_path)
        tokenizer = classifier["tokenizer"]
        model = classifier["model"]
        # Tokenize and move to device
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        try:
            import torch  # type: ignore
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)[0]
                pred_idx = torch.argmax(probs).item()
                confidence = probs[pred_idx].item()
                scores = {label: float(probs[i]) for i, label in enumerate(labels)}
        except Exception:
            # Fallback if torch not available or model not loaded correctly
            pred_idx = 0
            confidence = 0.5
            scores = {label: 0.5 for label in labels}
        elapsed = time.time() - start
        self.inference_count += 1
        self.total_inference_time += elapsed
        return {
            "prediction": labels[pred_idx],
            "confidence": float(confidence),
            "all_scores": scores,
            "inference_time": elapsed,
        }

    # ---------------------------------------------------------------------
    # Generative inference
    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate text from a prompt using a local generative model.

        Args:
            prompt: The input prompt.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature.
            stop_sequences: Optional list of stop sequences for generation.

        Returns:
            Dictionary with generated text and timing metadata.
        """
        import time
        start = time.time()
        gen_model = self.load_generative_model(quantized=True)
        if gen_model["type"] == "llama_cpp":
            output = gen_model["model"](
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.95,
                stop=stop_sequences or ["</s>", "\n\n\n"],
                echo=False,
            )
            generated_text = output["choices"][0]["text"]
        else:
            from transformers import AutoTokenizer  # type: ignore
            tokenizer = gen_model["tokenizer"]
            model = gen_model["model"]
            import torch  # type: ignore
            inputs = tokenizer(prompt, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_p=0.95,
                )
            text_out = tokenizer.decode(outputs[0], skip_special_tokens=True)
            generated_text = text_out[len(prompt):].strip()
        elapsed = time.time() - start
        self.inference_count += 1
        self.total_inference_time += elapsed
        return {
            "generated_text": generated_text,
            "inference_time": elapsed,
            "tokens_per_second": max_tokens / elapsed if elapsed > 0 else 0,
        }

    # ---------------------------------------------------------------------
    # Named entity extraction
    async def extract_entities(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Extract named entities from text using spaCy.

        Args:
            text: Input text.
            entity_types: Optional list of entity labels to include.

        Returns:
            List of extracted entities with text, label and character offsets.
        """
        import time
        start = time.time()
        nlp = self.load_ner_model()
        doc = nlp(text)
        entities = []
        for ent in doc.ents:
            if entity_types is None or ent.label_ in entity_types:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                })
        elapsed = time.time() - start
        self.inference_count += 1
        self.total_inference_time += elapsed
        return entities

    # ---------------------------------------------------------------------
    # Statistics and cleanup
    def get_stats(self) -> Dict[str, Any]:
        """Return inference statistics and loaded models."""
        return {
            "total_inferences": self.inference_count,
            "total_time_seconds": self.total_inference_time,
            "avg_time_per_inference": self.total_inference_time / self.inference_count if self.inference_count > 0 else 0.0,
            "loaded_models": list(self.models.keys()),
            "device": self.device,
        }

    def unload_models(self) -> None:
        """Unload all models and free GPU memory if possible."""
        self.models.clear()
        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        logger.info("Unloaded all local models")