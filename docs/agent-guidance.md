# Agent guidance

`AGENTS.md` defines project design choices and an explicit functional testing policy.
`CLAUDE.md` links to the same shared instructions.
The initializer substitutes the project overview only. AGENTS.md asks for uv,
a mathematical denotation line in module docstrings, one composition root for
configuration and I/O authority, narrow function inputs, domain types for units
and invariants, explicit failures, and library-native test assertions. It retains
a stamped design-doctrine block for compatibility with doctrine synchronization tools.
The testing policy favors a few real functional checks, restricts mocks to justified
external boundaries, and requires reporting integrations that were not verified.

This steers output toward small explicit modules, typed boundaries, fewer hidden
configuration reads, and errors instead of guessed defaults. It can also mean
more upfront design and domain types. These are instructions to a model, not
compiler guarantees or filesystem permissions. Review code and run checks.
Codex discovers AGENTS.md along the working-directory hierarchy:
https://learn.chatgpt.com/docs/agent-configuration/agents-md

`CLAUDE.md` links to AGENTS.md, keeping one source of rules for both agents.

Container mounts and runtime policies enforce isolation. No rule file prevents
an agent from writing to the writable checkout or using available network access.
Do not put secrets in any of these files. Review changes to guidance too.
