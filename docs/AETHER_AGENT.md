# AetherAgent — Multi-Agent Orchestration for OpenHands

AetherAgent is an OpenHands agent plugin that replaces the single-agent
CodeAct loop with **mcp-agent's DeepOrchestrator** — a production-ready,
adaptive workflow engine that plans, executes, verifies, replans, and
synthesises results across multiple specialised sub-agents.

---

## What it is

| Aspect | CodeActAgent | AetherAgent |
|--------|-------------|-------------|
| Architecture | Single agent, single LLM | Multi-agent orchestrator |
| Planning | Implicit (LLM decides) | Explicit (DeepOrchestrator plans) |
| Execution | Sequential tool calls | Parallel + dependency-aware |
| Error handling | Retry via prompt | Policy engine (CONTINUE / REPLAN / STOP) |
| Knowledge | None | In-memory extraction & retrieval |
| Budget control | Token limit only | Tokens + cost + time limits |
| Self-review | None | Optional EvaluatorOptimizer critic |

Under the hood, AetherAgent:

1. Boots an **MCPApp** configured with three MCP servers (filesystem,
   bash, fetch).
2. Defines three **AgentSpec**s — *coder*, *researcher*, *tester* — each
   with access to the relevant servers.
3. Creates a **DeepOrchestrator** that drives the full
   plan → execute → verify → replan → synthesise loop.
4. Returns the final synthesis as an OpenHands `MessageAction`.

---

## How to use

### 1. Select the agent

In the OpenHands UI, open the agent dropdown and choose **AetherAgent**.

### 2. Configure (optional)

Add an `[agent.AetherAgent]` section to your `config.toml`:

```toml
[agent.AetherAgent]
# extended config keys are passed to the orchestrator
[agent.AetherAgent.extended]
provider = "anthropic"             # LLM provider
model = "claude-sonnet-4-20250514"          # Model to use
max_iterations = 20                # Max orchestration iterations
max_tokens = 100000                # Token budget
max_cost = 5.0                     # Dollar budget
enable_parallel = true             # Parallel task execution
enable_critic = false              # Self-review loop
```

### 3. Run

Type your task in the chat box. AetherAgent will:

- Create a strategic plan
- Spin up specialised agents per task
- Execute tasks (in parallel when possible)
- Retry failures with exponential back-off
- Replan if the policy engine decides to
- Produce a final synthesised result

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   OpenHands UI                      │
│  (chat, terminal, file browser, status bar)         │
└──────────────────────┬──────────────────────────────┘
                       │  step()
┌──────────────────────▼──────────────────────────────┐
│                  AetherAgent                        │
│  (openhands/agenthub/aether_agent/agent.py)         │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │              MCPApp (mcp-agent)                │  │
│  │                                               │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │         DeepOrchestrator                │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌─────────┐ │  │  │
│  │  │  │ Planner  │ │ Executor │ │Synthesis│ │  │  │
│  │  │  └──────────┘ └──────────┘ └─────────┘ │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌─────────┐ │  │  │
│  │  │  │ Policy   │ │ Budget   │ │Knowledge│ │  │  │
│  │  │  └──────────┘ └──────────┘ └─────────┘ │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  │                                               │  │
│  │  Agent Specs:                                 │  │
│  │  • coder     → [filesystem, bash]             │  │
│  │  • researcher → [fetch]                       │  │
│  │  • tester    → [filesystem, bash]             │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Optional: EvaluatorOptimizerLLM (critic wrapper)   │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │filesystem│  │   bash   │  │  fetch   │
  │MCP server│  │MCP server│  │MCP server│
  └──────────┘  └──────────┘  └──────────┘
```

---

## MCP Servers

| Server | Source | Purpose |
|--------|--------|---------|
| `filesystem` | `@modelcontextprotocol/server-filesystem` | Read/write files in `/workspace` |
| `bash` | `openhands.agenthub.aether_agent.mcp_servers.bash_server` | Execute shell commands |
| `fetch` | `mcp-server-fetch` | HTTP GET/POST for documentation |

---

## Configuration Reference

All configuration is passed via the `[agent.AetherAgent.extended]`
section in `config.toml`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | `str` | `"anthropic"` | LLM provider (`anthropic`, `openai`, etc.) |
| `model` | `str` | `"claude-sonnet-4-20250514"` | Model identifier |
| `max_iterations` | `int` | `20` | Maximum orchestration loop iterations |
| `max_tokens` | `int` | `100000` | Token budget for the entire run |
| `max_cost` | `float` | `5.0` | Dollar budget for the entire run |
| `enable_parallel` | `bool` | `true` | Allow parallel task execution |
| `enable_critic` | `bool` | `false` | Wrap orchestrator in evaluator-optimizer |

---

## Critic Mode

When `enable_critic = true`, the DeepOrchestrator is wrapped in
mcp-agent's `EvaluatorOptimizerLLM`.  This creates a refinement loop:

1. The orchestrator produces a result.
2. An evaluator agent reviews it for correctness, security, and test
   coverage.
3. If the rating is below GOOD, the orchestrator refines and
   resubmits (up to 2 times by default).

This works because every mcp-agent workflow is an `AugmentedLLM` —
they compose seamlessly.

---

## Design Decisions

- **mcp-agent is a pip dependency, not vendored** — get upstream
  improvements automatically.
- **3 MCP servers only** (filesystem, bash, fetch) — covers 90% of
  coding tasks; add more later.
- **No LangGraph** — DeepOrchestrator already handles the full
  orchestration loop.
- **No vector database** — WorkspaceMemory handles in-memory knowledge;
  add Qdrant later if needed.
- **The bash MCP server is the only new server code** — everything else
  uses existing community MCP servers.
- **AetherAgent is a standard OpenHands agent plugin** — users switch
  between CodeActAgent and AetherAgent from the UI dropdown.
