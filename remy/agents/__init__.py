"""
Multi-agent orchestration — role-scoped sub-agents:

  Orchestrator (talks to the user, top model, delegates)
  Executor     (does concrete work, cheaper model, bounded tool loop)
  Watcher      (heartbeat brain, cheapest model or coded fallback)
  Reviewer     (conservative advisory gate for risky autonomous work)

All of them reach tools through remy.agents.toolbox → the shared FastMCP
instance → the permission engine, so no agent bypasses enforcement.
"""
