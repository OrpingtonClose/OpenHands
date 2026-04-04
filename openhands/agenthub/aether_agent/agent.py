"""AetherAgent — Multi-agent orchestrator powered by mcp-agent's DeepOrchestrator.

This agent integrates mcp-agent's adaptive orchestration into OpenHands,
enabling plan→execute→verify→replan→synthesize workflows with specialised
sub-agents that have access to filesystem, bash, and fetch MCP servers.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
from typing import TYPE_CHECKING

from openhands.controller.agent import Agent
from openhands.core.config import AgentConfig
from openhands.core.logger import openhands_logger as logger
from openhands.events.action import AgentFinishAction, MessageAction
from openhands.events.event import EventSource
from openhands.llm.llm_registry import LLMRegistry

if TYPE_CHECKING:
    from openhands.controller.state.state import State
    from openhands.events.action import Action


# Path to the mcp-agent config file shipped alongside this agent.
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'mcp_agent.config.yaml')


class AetherAgent(Agent):
    """Multi-agent orchestrator backed by mcp-agent's DeepOrchestrator.

    On the **first** call to ``step()`` the agent boots an ``MCPApp``,
    creates agent specs (coder, researcher, tester), builds the
    ``DeepOrchestrator``, and runs the full orchestration loop.  The
    result is returned as a ``MessageAction`` so the OpenHands UI can
    display it.

    Subsequent calls simply return ``AgentFinishAction`` because the
    orchestrator has already completed the task.
    """

    VERSION = '0.1'

    def __init__(
        self,
        config: AgentConfig,
        llm_registry: LLMRegistry,
    ) -> None:
        super().__init__(config, llm_registry)
        self._orchestrator_result: str | None = None

    # ------------------------------------------------------------------
    # OpenHands agent interface
    # ------------------------------------------------------------------

    def step(self, state: 'State') -> 'Action':
        """Synchronous entry-point required by OpenHands.

        We need to run async code (mcp-agent is fully async), so we
        bridge via ``asyncio.get_event_loop().run_until_complete``.
        """
        if self._orchestrator_result is not None:
            return AgentFinishAction(
                outputs={},
                thought='Orchestration already completed.',
            )

        # Extract the user's task from the conversation history.
        user_task = self._extract_user_task(state)
        if not user_task:
            return AgentFinishAction(
                outputs={},
                thought='No user task found in the conversation.',
            )

        logger.info(f'[AetherAgent] Starting orchestration for: {user_task[:120]}…')

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside an event loop (always true in OpenHands).
                # Run the async orchestrator in a dedicated thread that
                # creates its own event loop via asyncio.run().
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self._run_orchestrator(user_task))
                    self._orchestrator_result = future.result()
            else:
                self._orchestrator_result = loop.run_until_complete(
                    self._run_orchestrator(user_task)
                )
        except RuntimeError:
            # No running loop — just run directly.
            self._orchestrator_result = asyncio.run(self._run_orchestrator(user_task))

        msg = MessageAction(content=self._orchestrator_result or '')
        msg._source = EventSource.AGENT  # type: ignore[attr-defined]
        return msg

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_user_task(state: 'State') -> str:
        """Pull the first user message from the event history."""
        for event in state.history:
            if isinstance(event, MessageAction) and event.source == 'user':
                return event.content
        return ''

    async def _run_orchestrator(self, user_task: str) -> str:
        """Boot mcp-agent and run the DeepOrchestrator end-to-end."""
        from mcp_agent.agents.agent_spec import AgentSpec
        from mcp_agent.app import MCPApp
        from mcp_agent.workflows.deep_orchestrator.config import (
            DeepOrchestratorConfig,
        )
        from mcp_agent.workflows.factory import create_deep_orchestrator

        from openhands.agenthub.aether_agent.event_bridge import log_bridge_message

        # Read configuration values from the AgentConfig extended section.
        # ExtendedConfig is a Pydantic RootModel[dict] — access the
        # underlying dict via .root to use .get() safely.
        raw_ext = getattr(self.config, 'extended', None)
        _ext: dict = raw_ext.root if raw_ext else {}
        provider = _ext.get('provider', 'anthropic')
        model = _ext.get('model', 'claude-sonnet-4-20250514')
        max_iterations = int(_ext.get('max_iterations', 20))
        max_tokens = int(_ext.get('max_tokens', 100000))
        max_cost = float(_ext.get('max_cost', 5.0))
        enable_parallel = bool(_ext.get('enable_parallel', True))
        enable_critic = bool(_ext.get('enable_critic', False))

        log_bridge_message('info', 'Initialising MCPApp…')

        app = MCPApp(name='aether', settings=_CONFIG_PATH)

        async with app.run() as running_app:
            context = running_app.context

            # Define agent specifications
            agent_specs = [
                AgentSpec(
                    name='coder',
                    instruction=(
                        'You are an expert software engineer. Use the filesystem '
                        'and bash tools to read, write, and test code.'
                    ),
                    server_names=['filesystem', 'bash'],
                ),
                AgentSpec(
                    name='researcher',
                    instruction=(
                        'You search documentation and fetch web resources to '
                        'gather information needed for the task.'
                    ),
                    server_names=['fetch'],
                ),
                AgentSpec(
                    name='tester',
                    instruction=(
                        'You run tests, analyse failures, and fix issues. '
                        'Use the filesystem and bash tools.'
                    ),
                    server_names=['filesystem', 'bash'],
                ),
            ]

            config = DeepOrchestratorConfig.from_simple(
                name='AetherOrchestrator',
                max_iterations=max_iterations,
                max_tokens=max_tokens,
                max_cost=max_cost,
                enable_parallel=enable_parallel,
            )

            log_bridge_message('info', 'Creating DeepOrchestrator…')

            orchestrator = create_deep_orchestrator(
                available_agents=agent_specs,
                config=config,
                provider=provider,
                model=model,
                context=context,
            )

            # Optionally wrap with EvaluatorOptimizerLLM
            target = orchestrator
            if enable_critic:
                from openhands.agenthub.aether_agent.critic import (
                    wrap_with_critic,
                )

                target = wrap_with_critic(
                    orchestrator=orchestrator,
                    provider=provider,
                    context=context,
                )
                log_bridge_message('info', 'Critic wrapper enabled.')

            log_bridge_message('info', 'Running orchestration…')
            result = await target.generate_str(user_task)
            log_bridge_message('info', 'Orchestration complete.')
            return result
