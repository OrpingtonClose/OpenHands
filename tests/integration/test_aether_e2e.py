"""Integration tests for the AetherAgent end-to-end workflow.

These tests verify the full orchestration path by mocking external
LLM calls while keeping the internal mcp-agent plumbing live.  They
are deliberately lightweight — a full sandbox test requires a running
OpenHands instance and is out of scope for CI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.agenthub.aether_agent.agent import AetherAgent
from openhands.core.config import AgentConfig
from openhands.events.action import MessageAction


@pytest.fixture()
def agent() -> AetherAgent:
    """Create an AetherAgent with a mocked LLM registry."""
    config = AgentConfig()
    registry = MagicMock()
    registry.get_llm_from_agent_config.return_value = MagicMock()
    return AetherAgent(config=config, llm_registry=registry)


class TestAetherE2E:
    """End-to-end integration tests."""

    @patch(
        'openhands.agenthub.aether_agent.agent.AetherAgent._run_orchestrator',
        new_callable=AsyncMock,
    )
    def test_simple_task_returns_result(
        self,
        mock_orchestrator: AsyncMock,
        agent: AetherAgent,
    ) -> None:
        """Send a simple task and verify we get a MessageAction back."""
        mock_orchestrator.return_value = 'Created hello.py that prints "Hello, World!"'

        user_msg = MessageAction(content='Create a Python file that prints hello world')
        user_msg._source = 'user'  # type: ignore[attr-defined]

        state = MagicMock()
        state.history = [user_msg]

        action = agent.step(state)

        assert isinstance(action, MessageAction)
        assert 'hello' in action.content.lower()
        mock_orchestrator.assert_called_once()

    @patch(
        'openhands.agenthub.aether_agent.agent.AetherAgent._run_orchestrator',
        new_callable=AsyncMock,
    )
    def test_orchestrator_called_with_user_task(
        self,
        mock_orchestrator: AsyncMock,
        agent: AetherAgent,
    ) -> None:
        """Verify the orchestrator receives the correct user task."""
        mock_orchestrator.return_value = 'Done.'

        task_text = 'Refactor the database module'
        user_msg = MessageAction(content=task_text)
        user_msg._source = 'user'  # type: ignore[attr-defined]

        state = MagicMock()
        state.history = [user_msg]

        agent.step(state)
        mock_orchestrator.assert_called_once_with(task_text)

    @patch(
        'openhands.agenthub.aether_agent.agent.AetherAgent._run_orchestrator',
        new_callable=AsyncMock,
    )
    def test_second_step_returns_finish(
        self,
        mock_orchestrator: AsyncMock,
        agent: AetherAgent,
    ) -> None:
        """After orchestration, subsequent steps should return AgentFinishAction."""
        from openhands.events.action import AgentFinishAction

        mock_orchestrator.return_value = 'Done.'

        user_msg = MessageAction(content='Do something')
        user_msg._source = 'user'  # type: ignore[attr-defined]

        state = MagicMock()
        state.history = [user_msg]

        first = agent.step(state)
        assert isinstance(first, MessageAction)

        second = agent.step(state)
        assert isinstance(second, AgentFinishAction)
