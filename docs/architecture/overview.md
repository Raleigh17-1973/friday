# Friday Architecture Overview

Friday uses a manager-led architecture with five layers:

1. Conversation layer: single user interface and synthesized responses.
2. Orchestration layer: planning, specialist selection, critique, synthesis, approval decisions.
3. Specialist layer: schema-constrained internal experts.
4. Memory/learning layer: working, conversation, semantic, episodic, procedural memory.
5. Governance layer: auth, policy, approvals, injection defense, audit, eval gates.

This repository implements Phase 1 with production-oriented contracts and Phase 2/3 scaffolding.
