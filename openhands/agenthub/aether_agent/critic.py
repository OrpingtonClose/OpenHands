"""Optional critic wrapper for the DeepOrchestrator.

When ``enable_critic = true`` in the agent configuration, the
``AetherAgent`` wraps the ``DeepOrchestrator`` in mcp-agent's
``EvaluatorOptimizerLLM``.  This adds a refinement loop that
evaluates the orchestrator's output for correctness, security,
and test coverage, and requests improvements until the result
meets a minimum quality bar.

This works because every mcp-agent workflow is an ``AugmentedLLM`` —
they compose seamlessly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_agent.core.context import Context
    from mcp_agent.workflows.deep_orchestrator.orchestrator import DeepOrchestrator
    from mcp_agent.workflows.evaluator_optimizer.evaluator_optimizer import (
        EvaluatorOptimizerLLM,
    )


def wrap_with_critic(
    orchestrator: 'DeepOrchestrator',
    provider: str = 'anthropic',
    model: str | None = None,
    context: 'Context | None' = None,
    min_rating: int = 2,
    max_refinements: int = 2,
) -> 'EvaluatorOptimizerLLM':
    """Wrap a DeepOrchestrator with an evaluator-optimizer refinement loop.

    Args:
        orchestrator: The ``DeepOrchestrator`` instance to wrap.
        provider: LLM provider for the evaluator (e.g. ``"anthropic"``).
        model: Model identifier for the evaluator.
        context: mcp-agent application context.
        min_rating: Minimum acceptable ``QualityRating`` value
            (0=POOR, 1=FAIR, 2=GOOD, 3=EXCELLENT).
        max_refinements: Maximum number of refinement iterations.

    Returns:
        An ``EvaluatorOptimizerLLM`` that uses the orchestrator as the
        optimizer and a code-review evaluator for quality gating.
    """
    from mcp_agent.workflows.factory import create_evaluator_optimizer_llm

    evaluator_instruction = (
        'Review the code changes for correctness, security, and test '
        'coverage. Rate EXCELLENT only if no improvements are needed.'
    )

    return create_evaluator_optimizer_llm(
        optimizer=orchestrator,
        evaluator=evaluator_instruction,
        min_rating=min_rating,
        max_refinements=max_refinements,
        provider=provider,
        model=model,
        context=context,
    )
