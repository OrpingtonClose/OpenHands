"""Bridge between mcp-agent's structured logging and OpenHands EventStream.

This module provides utilities to translate mcp-agent log events into
OpenHands-compatible observations so that they surface in the UI
(terminal view, chat, status bar).

For now we expose a simple ``log_bridge_message`` helper that the
AetherAgent calls at key orchestration checkpoints.  A more complete
integration can subscribe to mcp-agent's ``AsyncEventBus`` to stream
all internal events in real-time.
"""

from __future__ import annotations

from openhands.core.logger import openhands_logger as logger


def log_bridge_message(level: str, message: str) -> None:
    """Emit an OpenHands log entry from an mcp-agent event.

    Args:
        level: Log level — one of ``"debug"``, ``"info"``, ``"warning"``, ``"error"``.
        message: Human-readable description of the event.
    """
    log_fn = {
        'debug': logger.debug,
        'info': logger.info,
        'warning': logger.warning,
        'error': logger.error,
    }.get(level, logger.info)
    log_fn(f'[AetherBridge] {message}')


def bridge_plan_created(plan_description: str) -> None:
    """Log that a new plan has been created by the orchestrator."""
    log_bridge_message('info', f'Plan created: {plan_description}')


def bridge_task_started(task_name: str) -> None:
    """Log that a task has started execution."""
    log_bridge_message('info', f'Task started: {task_name}')


def bridge_task_completed(task_name: str, success: bool) -> None:
    """Log that a task has completed."""
    status = 'succeeded' if success else 'failed'
    log_bridge_message('info', f'Task {status}: {task_name}')


def bridge_policy_decision(action: str) -> None:
    """Log a policy engine decision (CONTINUE, REPLAN, STOP, etc.)."""
    log_bridge_message('info', f'Policy decision: {action}')


def bridge_budget_update(tokens_used: int, cost: float) -> None:
    """Log a budget update."""
    log_bridge_message(
        'info',
        f'Budget update — tokens: {tokens_used}, cost: ${cost:.2f}',
    )


def bridge_knowledge_extracted(key: str) -> None:
    """Log that a knowledge item was extracted."""
    log_bridge_message('debug', f'Knowledge extracted: {key}')


def bridge_synthesis_complete(summary_length: int) -> None:
    """Log that the final synthesis is ready."""
    log_bridge_message(
        'info',
        f'Final synthesis complete ({summary_length} chars)',
    )
