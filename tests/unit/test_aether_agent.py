"""Unit tests for the AetherAgent plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.agenthub.aether_agent.agent import AetherAgent
from openhands.agenthub.aether_agent.critic import wrap_with_critic
from openhands.agenthub.aether_agent.event_bridge import (
    bridge_budget_update,
    bridge_plan_created,
    bridge_policy_decision,
    bridge_synthesis_complete,
    bridge_task_completed,
    bridge_task_started,
    log_bridge_message,
)
from openhands.core.config import AgentConfig
from openhands.events.action import AgentFinishAction, MessageAction

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent_config() -> AgentConfig:
    """Minimal AgentConfig for testing."""
    return AgentConfig()


@pytest.fixture()
def llm_registry() -> MagicMock:
    """Mock LLMRegistry."""
    registry = MagicMock()
    registry.get_llm_from_agent_config.return_value = MagicMock()
    return registry


@pytest.fixture()
def aether_agent(agent_config: AgentConfig, llm_registry: MagicMock) -> AetherAgent:
    """Create an AetherAgent instance for testing."""
    return AetherAgent(config=agent_config, llm_registry=llm_registry)


# ---------------------------------------------------------------------------
# Agent initialisation
# ---------------------------------------------------------------------------


class TestAetherAgentInit:
    """Tests for AetherAgent construction."""

    def test_agent_creates_successfully(self, aether_agent: AetherAgent) -> None:
        assert aether_agent is not None
        assert aether_agent.VERSION == '0.1'

    def test_orchestrator_result_initially_none(
        self, aether_agent: AetherAgent
    ) -> None:
        assert aether_agent._orchestrator_result is None

    def test_agent_registered_in_registry(self) -> None:
        from openhands.controller.agent import Agent

        assert 'AetherAgent' in Agent.list_agents()


# ---------------------------------------------------------------------------
# step() behaviour
# ---------------------------------------------------------------------------


class TestAetherAgentStep:
    """Tests for the step() method."""

    def test_finish_when_no_user_task(self, aether_agent: AetherAgent) -> None:
        state = MagicMock()
        state.history = []
        action = aether_agent.step(state)
        assert isinstance(action, AgentFinishAction)

    def test_finish_when_already_completed(self, aether_agent: AetherAgent) -> None:
        aether_agent._orchestrator_result = 'done'
        state = MagicMock()
        action = aether_agent.step(state)
        assert isinstance(action, AgentFinishAction)
        assert action.thought == 'Orchestration already completed.'

    @patch(
        'openhands.agenthub.aether_agent.agent.AetherAgent._run_orchestrator',
        new_callable=AsyncMock,
    )
    def test_step_returns_message_action(
        self,
        mock_run: AsyncMock,
        aether_agent: AetherAgent,
    ) -> None:
        mock_run.return_value = 'Here is the result.'

        user_msg = MessageAction(content='Create a hello world script')
        user_msg._source = 'user'  # type: ignore[attr-defined]

        state = MagicMock()
        state.history = [user_msg]

        action = aether_agent.step(state)
        assert isinstance(action, MessageAction)
        assert action.content == 'Here is the result.'


# ---------------------------------------------------------------------------
# _extract_user_task
# ---------------------------------------------------------------------------


class TestExtractUserTask:
    """Tests for extracting the user task from state."""

    def test_extracts_first_user_message(self) -> None:
        msg = MessageAction(content='Fix the bug')
        msg._source = 'user'  # type: ignore[attr-defined]
        state = MagicMock()
        state.history = [msg]
        assert AetherAgent._extract_user_task(state) == 'Fix the bug'

    def test_returns_empty_when_no_user_message(self) -> None:
        state = MagicMock()
        state.history = []
        assert AetherAgent._extract_user_task(state) == ''


# ---------------------------------------------------------------------------
# Agent specs helper check
# ---------------------------------------------------------------------------


class TestAgentSpecs:
    """Verify that the agent specs match the expected server names."""

    def test_agent_spec_creation(self) -> None:
        from mcp_agent.agents.agent_spec import AgentSpec

        coder = AgentSpec(
            name='coder',
            instruction='Write code.',
            server_names=['filesystem', 'bash'],
        )
        assert coder.name == 'coder'
        assert 'filesystem' in coder.server_names
        assert 'bash' in coder.server_names

    def test_researcher_spec(self) -> None:
        from mcp_agent.agents.agent_spec import AgentSpec

        researcher = AgentSpec(
            name='researcher',
            instruction='Research.',
            server_names=['fetch'],
        )
        assert researcher.server_names == ['fetch']


# ---------------------------------------------------------------------------
# DeepOrchestratorConfig propagation
# ---------------------------------------------------------------------------


class TestConfigPropagation:
    """Verify that config values propagate to DeepOrchestratorConfig."""

    def test_from_simple_defaults(self) -> None:
        from mcp_agent.workflows.deep_orchestrator.config import (
            DeepOrchestratorConfig,
        )

        config = DeepOrchestratorConfig.from_simple()
        assert config.execution.max_iterations == 20
        assert config.budget.max_tokens == 100000
        assert config.execution.enable_parallel is True

    def test_from_simple_custom(self) -> None:
        from mcp_agent.workflows.deep_orchestrator.config import (
            DeepOrchestratorConfig,
        )

        config = DeepOrchestratorConfig.from_simple(
            max_iterations=10,
            max_tokens=50000,
            max_cost=3.0,
            enable_parallel=False,
        )
        assert config.execution.max_iterations == 10
        assert config.budget.max_tokens == 50000
        assert config.budget.max_cost == 3.0
        assert config.execution.enable_parallel is False


# ---------------------------------------------------------------------------
# Event bridge
# ---------------------------------------------------------------------------


class TestEventBridge:
    """Tests for the event bridge helper functions."""

    def test_log_bridge_message(self, caplog: pytest.LogCaptureFixture) -> None:
        # Should not raise regardless of level.
        log_bridge_message('info', 'hello')
        log_bridge_message('debug', 'debug msg')
        log_bridge_message('warning', 'warn msg')
        log_bridge_message('error', 'err msg')
        log_bridge_message('unknown_level', 'fallback')

    def test_bridge_plan_created(self) -> None:
        bridge_plan_created('Plan A')

    def test_bridge_task_started(self) -> None:
        bridge_task_started('compile')

    def test_bridge_task_completed(self) -> None:
        bridge_task_completed('compile', success=True)
        bridge_task_completed('lint', success=False)

    def test_bridge_policy_decision(self) -> None:
        bridge_policy_decision('CONTINUE')

    def test_bridge_budget_update(self) -> None:
        bridge_budget_update(tokens_used=5000, cost=0.15)

    def test_bridge_synthesis_complete(self) -> None:
        bridge_synthesis_complete(summary_length=1234)


# ---------------------------------------------------------------------------
# Critic wrapper
# ---------------------------------------------------------------------------


class TestCriticWrapper:
    """Tests for the optional critic wrapper."""

    @patch('openhands.agenthub.aether_agent.critic.create_evaluator_optimizer_llm')
    def test_wrap_with_critic_calls_factory(self, mock_factory: MagicMock) -> None:
        mock_orchestrator = MagicMock()
        mock_factory.return_value = MagicMock()
        result = wrap_with_critic(
            orchestrator=mock_orchestrator,
            provider='anthropic',
            context=None,
        )
        mock_factory.assert_called_once()
        assert result is mock_factory.return_value
