"""API-based LLM provider manager.

This module implements a unified interface for calling external large
language model services.  It supports multiple providers (OpenAI,
Anthropic, Groq and others) and hides the details of request
construction, prompt formatting and cost calculation.  All service
calls are asynchronous and return consistent result dictionaries
including the generated content, token usage and estimated cost.

Unlike earlier iterations, this implementation avoids a lengthy
template for the risk‑of‑bias prompt that caused syntax errors.  The
reasoning prompt builder has been simplified and resides at the end
of the class.  Additional providers (e.g., Google Gemini) can be
implemented following the same pattern.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional, List

import httpx

from ..config.settings import settings
from ..utils.logging import get_logger


logger = get_logger(__name__)


class APIModelManager:
    """Unified interface for multiple LLM API providers.

    Each call to a provider records usage statistics and estimated cost
    based on approximate per‑token pricing.  The manager can be used
    directly for tasks such as classification, extraction, reasoning
    and summarisation.  High‑level routing to different tiers of
    models is handled by :class:`~srp.llm.router.ModelRouter`.
    """

    # Approximate pricing per million tokens (USD)
    PRICING: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},  # Groq
        "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},      # Groq
    }

    def __init__(self) -> None:
        # API keys from settings
        self.openai_key = settings.openai_api_key
        self.anthropic_key = settings.anthropic_api_key
        self.groq_key = settings.groq_api_key
        self.google_key = settings.google_api_key
        self.together_key = settings.together_api_key
        # Cost and call tracking
        self.total_cost: float = 0.0
        self.calls_by_provider: Dict[str, int] = {}
        self.call_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Provider calls
    async def call_groq(
        self,
        prompt: str,
        model: str = "llama-3.1-70b-versatile",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call the Groq API for chat completion.

        Groq exposes an OpenAI‑compatible endpoint for their hosted Llama
        and Mixtral models.  Low latency makes these models suitable
        for mid‑tier tasks.
        """
        if not self.groq_key:
            raise RuntimeError("Groq API key not configured")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60.0,
            )
            data = resp.json()
        content: str = data["choices"][0]["message"]["content"]
        usage: Dict[str, int] = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        pricing = self.PRICING.get(model, {"input": 0.59, "output": 0.79})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        self._accumulate_cost("groq", model, input_tokens, output_tokens, cost)
        return {
            "content": content,
            "model": model,
            "provider": "groq",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        }

    async def call_openai(
        self,
        prompt: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Call the OpenAI chat completion API."""
        if not self.openai_key:
            raise RuntimeError("OpenAI API key not configured")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient() as client:
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            data = resp.json()
        content: str = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        pricing = self.PRICING.get(model, {"input": 0.15, "output": 0.60})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        self._accumulate_cost("openai", model, input_tokens, output_tokens, cost)
        return {
            "content": content,
            "model": model,
            "provider": "openai",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        }

    async def call_anthropic(
        self,
        prompt: str,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call the Anthropic messages API."""
        if not self.anthropic_key:
            raise RuntimeError("Anthropic API key not configured")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_prompt or "You are a systematic review expert.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            data = resp.json()
        content = data.get("content", [])
        content_text = content[0]["text"] if content else ""
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        pricing = self.PRICING.get(model, {"input": 3.00, "output": 15.00})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        self._accumulate_cost("anthropic", model, input_tokens, output_tokens, cost)
        return {
            "content": content_text,
            "model": model,
            "provider": "anthropic",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        }

    # ------------------------------------------------------------------
    # High‑level task processing
    async def process(
        self,
        task_type: str,
        input_data: Dict[str, Any],
        model_tier: Literal["mid", "frontier"] = "mid",
    ) -> Dict[str, Any]:
        """Route a task to the chosen provider and parse the response.

        Parameters
        ----------
        task_type:
            One of ``"classify"``, ``"extract"``, ``"reason"``, ``"summarize"``.
        input_data:
            Dictionary containing the input text and any criteria or
            configuration required by the task.
        model_tier:
            ``"mid"`` uses fast, less expensive models (Groq or OpenAI mini).
            ``"frontier"`` uses more capable models (Anthropic or GPT‑4o mini).

        Returns
        -------
        Dict[str, Any]
            Parsed result augmented with raw API metadata.
        """
        prompt = self._build_prompt(task_type, input_data)
        system_prompt = self._get_system_prompt(task_type)
        if model_tier == "mid":
            result = await self.call_groq(prompt, model="llama-3.1-70b-versatile", system_prompt=system_prompt)
        else:
            # Frontier tier uses stronger models depending on task
            if task_type in {"reason", "assess_quality"}:
                result = await self.call_anthropic(prompt, model="claude-3-5-sonnet-20241022", system_prompt=system_prompt)
            else:
                result = await self.call_openai(prompt, model="gpt-4o-mini", system_prompt=system_prompt, json_mode=True)
        parsed = self._parse_api_output(result["content"], task_type)
        return {**parsed, **result}

    # ------------------------------------------------------------------
    # Prompt builders
    def _build_prompt(self, task_type: str, data: Dict[str, Any]) -> str:
        if task_type == "classify":
            return self._build_classification_prompt(data)
        if task_type == "extract":
            return self._build_extraction_prompt(data)
        if task_type == "reason":
            return self._build_reasoning_prompt(data)
        if task_type == "summarize":
            return self._build_summary_prompt(data)
        raise ValueError(f"Unknown task type: {task_type}")

    def _build_classification_prompt(self, data: Dict[str, Any]) -> str:
        """Build a prompt for abstract classification.

        The prompt includes formatted inclusion/exclusion criteria and the
        paper abstract, then instructs the model to answer whether the
        paper should be included or excluded in JSON format.  This
        version is intentionally concise to avoid syntax errors.
        """
        text: str = data.get("text", "")
        criteria: Dict[str, Any] = data.get("criteria", {})
        inclusion = criteria.get("inclusion", []) or []
        exclusion = criteria.get("exclusion", []) or []
        parts: List[str] = [
            "Classify the following abstract for systematic review inclusion.",
            "",
            "INCLUSION CRITERIA:",
            self._format_criteria(inclusion),
            "",
            "EXCLUSION CRITERIA:",
            self._format_criteria(exclusion),
            "",
            "ABSTRACT:",
            text.strip(),
            "",
            "QUESTION: Should this paper be INCLUDED or EXCLUDED?",
            "Return a JSON object with keys 'decision' and 'confidence'.",
        ]
        return "\n".join(parts)

    def _build_extraction_prompt(self, data: Dict[str, Any]) -> str:
        """Build a prompt for structured data extraction."""
        text: str = data.get("text", "")
        prompt_parts: List[str] = [
            "Extract structured data from this research paper section.",
            "",
            "TEXT:",
            text[:4000],
            "",
            "EXTRACT:",
            "1. Study design (e.g., 'randomized_controlled_trial', 'cohort_study')",
            "2. Sample size (total N)",
            "3. Interventions/exposures (list with descriptions)",
            "4. Primary outcomes (list with effect sizes, CIs, p-values)",
            "5. Statistical methods used",
            "",
            "Respond with ONLY this JSON structure:",
            "{",
            "  \"sample_size\": 150,",
            "  \"study_design\": \"randomized_controlled_trial\",",
            "  \"population\": \"adults with type 2 diabetes\",",
            "  \"interventions\": [",
            "    {\"name\": \"metformin\", \"dosage\": \"500mg twice daily\", \"duration\": \"12 weeks\"}",
            "  ],",
            "  \"outcomes\": [",
            "    {",
            "      \"name\": \"HbA1c reduction\",",
            "      \"effect_size\": -0.8,",
            "      \"unit\": \"percentage points\",",
            "      \"ci_lower\": -1.2,",
            "      \"ci_upper\": -0.4,",
            "      \"p_value\": 0.001",
            "    }",
            "  ],",
            "  \"statistical_methods\": [\"t-test\", \"ANOVA\", \"intention-to-treat analysis\"]",
            "}",
            "",
            "Use null for missing information. Be precise.",
        ]
        return "\n".join(prompt_parts)

    def _build_reasoning_prompt(self, data: Dict[str, Any]) -> str:
        """Build a simplified risk‑of‑bias prompt.

        This prompt asks the model to assess study quality according to
        a specified tool (e.g., RoB 2) and a list of assessment
        questions.  The model is instructed to return a JSON object
        summarising judgments per domain along with supporting evidence
        and reasoning.
        """
        text: str = data.get("text", "")
        tool: str = data.get("tool", "rob2")
        questions: List[str] = data.get("questions", []) or []
        lines: List[str] = [
            f"Assess risk of bias using {tool.upper()}.",
            "",
            "STUDY METHODS SECTION:",
            text.strip()[:5000],
            "",
            "ASSESSMENT QUESTIONS:",
            json.dumps(questions, indent=2),
            "",
            "For each domain, provide:",
            "1. Judgment: LOW_RISK, SOME_CONCERNS, or HIGH_RISK",
            "2. Supporting evidence: Direct quotes from the methods section",
            "3. Reasoning: Explain why this judgment was made",
            "",
            "Respond with JSON containing 'overall_judgment', 'overall_confidence',",
            "and a list of 'domain_assessments' with 'domain', 'judgment', 'evidence' and 'reasoning'.",
        ]
        return "\n".join(lines)

    def _build_summary_prompt(self, data: Dict[str, Any]) -> str:
        """Build a prompt for narrative synthesis."""
        papers: List[Dict[str, Any]] = data.get("papers", [])
        focus: str = data.get("focus", "main findings")
        lines: List[str] = [
            "Synthesize findings from these research papers.",
            "",
            f"FOCUS: {focus}",
            "",
            "PAPERS:",
            self._format_papers_for_summary(papers),
            "",
            "TASK: Write a narrative synthesis (2-3 paragraphs) covering:",
            "1. Common themes and patterns",
            "2. Key findings and effect sizes",
            "3. Heterogeneity or contradictions",
            "4. Quality of evidence",
            "",
            "Write in academic style suitable for systematic review.",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helper functions
    def _format_criteria(self, criteria: List[Dict[str, Any]]) -> str:
        if not criteria:
            return "None specified"
        return "\n".join(
            [f"{i+1}. {c.get('name', 'Unnamed')}: {c.get('description', '')}" for i, c in enumerate(criteria)]
        )

    def _format_papers_for_summary(self, papers: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for i, p in enumerate(papers[:10], 1):
            lines.append(f"\n{i}. {p.get('title', 'Untitled')}")
            abstract = p.get("abstract")
            if abstract:
                lines.append(f"   {abstract[:300]}...")
        return "\n".join(lines)

    def _get_system_prompt(self, task_type: str) -> str:
        prompts = {
            "classify": "You are a systematic review expert specialising in paper screening. Always output valid JSON.",
            "extract": "You are a data extraction specialist for systematic reviews. Always output valid JSON with precise values.",
            "reason": "You are a methodologist assessing study quality. Be thorough and evidence‑based. Always output valid JSON.",
            "summarize": "You are a research synthesist writing narrative summaries for systematic reviews.",
        }
        return prompts.get(task_type, "You are a systematic review expert.")

    def _parse_api_output(self, content: str, task_type: str) -> Dict[str, Any]:
        """Parse JSON content from a provider response.

        If the provider returns Markdown‑formatted JSON (wrapped in
        triple backticks), this function strips the backticks and
        extracts the JSON object.  For summary tasks, the raw content
        is returned under the ``summary`` key.
        """
        try:
            import re
            # Remove ```json and ``` wrappers
            content_clean = re.sub(r"```.*?\n", "", content, flags=re.DOTALL)
            match = re.search(r"\{.*\}", content_clean, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            if task_type == "summarize":
                return {"summary": content.strip()}
            return {"raw_output": content, "parse_error": "No JSON found"}
        except Exception as exc:
            logger.warning(f"Failed to parse API output: {exc}")
            return {"raw_output": content, "parse_error": str(exc)}

    def _accumulate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        self.total_cost += cost
        self.calls_by_provider[provider] = self.calls_by_provider.get(provider, 0) + 1
        self.call_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        })

    # ------------------------------------------------------------------
    # Reporting
    def get_cost_summary(self) -> Dict[str, Any]:
        """Return a summary of costs and call counts."""
        total_calls = sum(self.calls_by_provider.values()) if self.calls_by_provider else 0
        return {
            "total_cost": round(self.total_cost, 4),
            "calls_by_provider": dict(self.calls_by_provider),
            "total_calls": total_calls,
            "avg_cost_per_call": round(self.total_cost / total_calls, 4) if total_calls else 0.0,
            "call_history": self.call_history[-100:],
        }

    def export_cost_report(self, output_path: Path) -> None:
        """Export call history to a CSV file for offline analysis."""
        try:
            import pandas as pd  # type: ignore
            df = pd.DataFrame(self.call_history)
            df.to_csv(output_path, index=False)
            logger.info(f"Exported cost report to {output_path}")
        except ImportError:
            logger.warning("pandas is not installed; cannot export cost report")
