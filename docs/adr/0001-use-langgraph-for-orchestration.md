# ADR 0001: Use LangGraph for Spot Bid Workflow Orchestration

## Status
Accepted

## Context
Spot bid execution requires stateful, branching workflows with retries, event callbacks, and concurrency across many loads.

## Decision
Use LangGraph as the orchestration layer for workflow state transitions.

## Consequences
- Pros:
- Explicit state graph for maintainability.
- Better fit for multi-step async workflows.
- Easier to test node-level transitions.
- Cons:
- Additional abstraction to learn.
- Needs clear contracts between graph nodes and external services.

## Follow-Up
- Define graph states and transition guards in implementation doc.
- Add tests for idempotency and duplicate trigger events.
