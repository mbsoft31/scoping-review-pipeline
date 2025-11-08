"""Model routing infrastructure for LLM/SLM usage.

This module defines a simple ``ModelRouter`` that can choose between a local
model and an API‑based model depending on task complexity and the
confidence of the local model.  It also keeps track of basic cost
statistics.  The router works with ``LocalModelManager`` and
``APIModelManager`` from the ``srp.llm`` package.  The goal is to
minimise API calls (which incur cost and latency) by handling the
majority of work locally and only escalating to remote models when
necessary.

The implementation here is intentionally lightweight.  It does not
implement every nuance from the design document but provides a
foundation that can be extended.  Tasks are identified by a
``task_type`` string (e.g. ``"classify"``, ``"extract"``) and a
dictionary of ``input_data``.  The router first tries to process the
task using the local model.  If that fails or returns a confidence
below the configured threshold, the router will call the API model.  A
``TaskComplexity`` enumeration is provided to help callers describe
the difficulty of the task, though in this simplified implementation it
is not used for routing decisions.
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Dict, Optional

from .local_models import LocalModelManager
from .api_models import APIModelManager
from ..utils.logging import get_logger


logger = get_logger(__name__)


class ModelTier(Enum):
    """Enumeration describing the tier of model used for a task."""

    LOCAL = "local"
    MID = "mid"
    FRONTIER = "frontier"


class TaskComplexity(Enum):
    """Describe the complexity of the task for routing purposes."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class ModelRouter:
    """Route tasks to the appropriate model tier.

    The router first attempts to execute tasks using a local model.  If
    the local model returns a result with a ``confidence`` score greater
    than or equal to ``local_threshold``, the router returns that result.
    Otherwise, it will attempt to use the API model.  The router
    maintains counters for how many times each tier was used and the
    cumulative cost spent on API calls.
    """

    def __init__(
        self,
        local_manager: Optional[LocalModelManager] = None,
        api_manager: Optional[APIModelManager] = None,
        local_threshold: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> None:
        """Create a new ``ModelRouter``.

        Parameters
        ----------
        local_manager:
            Instance of ``LocalModelManager`` to handle local tasks.  If
            ``None``, a default ``LocalModelManager`` will be created.
        api_manager:
            Instance of ``APIModelManager`` to handle API calls.  If
            ``None``, a default ``APIModelManager`` will be created.  API
            keys must be configured via environment variables for
            this manager to function.
        local_threshold:
            Minimum confidence required to accept a local result.  If the
            confidence from the local model is below this threshold the
            router will attempt to call the API model.  If ``None``,
            ``settings.llm_local_threshold`` is used.
        mode:
            LLM usage mode: ``'local'``, ``'hybrid'`` or ``'api_only'``.  If
            ``None``, ``settings.llm_mode`` will be used.  ``local`` forces
            local-only inference, ``api_only`` bypasses local models
            entirely, and ``hybrid`` uses the confidence threshold to
            decide when to call the API.
        """
        from ..config.settings import settings  # local import to avoid circular

        self.local_manager = local_manager or LocalModelManager()
        self.api_manager = api_manager or APIModelManager()
        # Determine local threshold and mode from settings if not provided
        self.local_threshold = local_threshold if local_threshold is not None else settings.llm_local_threshold
        self.mode = mode or settings.llm_mode
        # Cost budget per paper; if exceeded we will stop API calls
        self.cost_budget_per_paper = settings.llm_cost_budget_per_paper
        # Track cumulative cost for the session
        self.total_cost: float = 0.0
        # Track calls per tier
        self.calls_by_tier: Dict[ModelTier, int] = {
            ModelTier.LOCAL: 0,
            ModelTier.MID: 0,
            ModelTier.FRONTIER: 0,
        }

    async def route_task(
        self,
        task_type: str,
        input_data: Dict[str, Any],
        *,
        complexity: TaskComplexity = TaskComplexity.SIMPLE,
        is_critical: bool = False,
    ) -> Dict[str, Any]:
        """Route a task to the appropriate model tier.

        The router first invokes a local model.  If the local model
        returns a confidence greater than or equal to ``local_threshold``,
        that result is returned with ``tier_used`` set to "local" and
        zero cost.  Otherwise, the router chooses between the mid and
        frontier API tiers depending on the task complexity or explicit
        request.  Critical tasks skip local processing entirely and
        immediately call the API.  When the API is invoked, the cost
        and tier used are recorded.

        Parameters
        ----------
        task_type:
            The type of task (e.g. ``"classify"``, ``"extract"``, ``"reason"``).
        input_data:
            A dictionary containing whatever inputs the model needs.
        complexity:
            A hint about the complexity of the task.  ``SIMPLE`` tasks
            generally use mid‑tier models; ``COMPLEX`` tasks may use
            frontier models.  ``MODERATE`` tasks can fall back to
            frontier models depending on confidence.
        is_critical:
            Whether this task should bypass local processing and use the
            API directly.

        Returns
        -------
        Dict[str, Any]
            The result of the model call.  The result dictionary will
            include ``tier_used`` and ``cost`` keys.
        """
        # Determine routing based on global mode
        # If critical, always call API (respecting budget)
        if is_critical:
            logger.debug("Critical task; using API directly")
            return await self._call_api(task_type, input_data, complexity=complexity)

        # Local‑only mode: always use local model and never call API
        if self.mode == "local":
            try:
                local_res = await self.local_manager.process(task_type, input_data)
            except Exception as exc:
                logger.warning(f"Local model failed for task {task_type}: {exc}")
                # Return empty result with failure flag
                return {"tier_used": ModelTier.LOCAL.value, "cost": 0.0, "error": str(exc)}
            self.calls_by_tier[ModelTier.LOCAL] += 1
            local_res["tier_used"] = ModelTier.LOCAL.value
            local_res["cost"] = 0.0
            return local_res

        # API‑only mode: bypass local processing
        if self.mode == "api_only":
            return await self._call_api(task_type, input_data, complexity=complexity)

        # Hybrid mode: attempt local, fallback to API based on confidence and budget
        # Attempt local processing
        try:
            local_res = await self.local_manager.process(task_type, input_data)
            self.calls_by_tier[ModelTier.LOCAL] += 1
            conf = float(local_res.get("confidence", 0.0))
            if conf >= self.local_threshold:
                local_res["tier_used"] = ModelTier.LOCAL.value
                local_res["cost"] = 0.0
                return local_res
        except Exception as exc:
            logger.warning(f"Local model failed for task {task_type}: {exc}")

        # Check cost budget: if exceeded, skip API and return local result
        if self.total_cost >= self.cost_budget_per_paper:
            logger.debug("Cost budget exceeded; returning local result despite low confidence")
            # Return local result (or a placeholder if local failed)
            fallback = locals().get("local_res", {}) or {}
            fallback.setdefault("confidence", 0.0)
            fallback["tier_used"] = ModelTier.LOCAL.value
            fallback["cost"] = 0.0
            fallback["fallback_used"] = True
            return fallback

        # Decide which API tier to use based on complexity and task type
        use_frontier = False
        # Consider the complexity hint
        if complexity == TaskComplexity.COMPLEX:
            use_frontier = True
        # Certain task types inherently require more reasoning power
        if task_type in {"reason", "summarize"}:
            use_frontier = True
        # Call API with selected tier
        api_res = await self._call_api(task_type, input_data, use_frontier=use_frontier)
        return api_res

    async def _call_api(
        self,
        task_type: str,
        input_data: Dict[str, Any],
        *,
        use_frontier: bool = False,
        complexity: Optional[TaskComplexity] = None,
    ) -> Dict[str, Any]:
        """Call the API model for a task.

        This helper delegates to ``APIModelManager.process`` and
        updates cost tracking.  It chooses between the mid and frontier
        model tiers based on ``use_frontier``.  Errors from the API are
        propagated.

        Parameters
        ----------
        task_type:
            The task type (e.g. 'classify', 'extract').
        input_data:
            Input data for the model.
        use_frontier:
            Whether to use the frontier tier; if False, the mid tier is used.
        complexity:
            Optional complexity hint (unused here but may influence
            provider selection in future).

        Returns
        -------
        Dict[str, Any]
            API response augmented with cost and tier information.
        """
        # Determine model_tier parameter for APIModelManager
        # If cost budget is already exceeded, skip API and return a placeholder
        if self.total_cost >= self.cost_budget_per_paper:
            # return an empty response to indicate skip
            logger.debug("Skipping API call due to cost budget limit")
            return {"tier_used": ModelTier.LOCAL.value, "cost": 0.0, "skipped": True}
        model_tier = "frontier" if use_frontier else "mid"
        api_res = await self.api_manager.process(task_type, input_data, model_tier=model_tier)  # type: ignore[arg-type]
        cost = float(api_res.get("cost", 0.0))
        self.total_cost += cost
        tier_enum = ModelTier.FRONTIER if use_frontier else ModelTier.MID
        self.calls_by_tier[tier_enum] += 1
        api_res["tier_used"] = tier_enum.value
        return api_res

    def get_routing_stats(self) -> Dict[str, Any]:
        """Return statistics about routing decisions and costs."""
        total_calls = sum(self.calls_by_tier.values())
        local_calls = self.calls_by_tier[ModelTier.LOCAL]
        local_success_rate = (
            local_calls / total_calls
            if total_calls > 0
            else 0.0
        )
        return {
            "calls_by_tier": {tier.value: count for tier, count in self.calls_by_tier.items()},
            "total_cost": self.total_cost,
            "cost_budget_per_paper": self.cost_budget_per_paper,
            "total_calls": total_calls,
            "local_success_rate": local_success_rate,
        }