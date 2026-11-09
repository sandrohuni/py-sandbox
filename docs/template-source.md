# Template source

Based on https://github.com/hydrosolutions/pyplate at `f92556680ade1790f1764ae10d334cd5576aa5ab`.

AGENTS.md extends pyplate with a functional-testing-first policy outside the
stamped doctrine block. CLAUDE.md retains its upstream link. Python metadata,
lockfile, version selection and import smoke test also originate there. The source
package is a placeholder. The initializer supports portable macOS/Linux operation, repeatable full setup,
and config-only updates. The access YAML generator and devcontainer launcher are
local additions; generated runtime configs are ignored by Git. Fleet retrofit/sync scripts are not included.
Sandbox configuration comes from agent-sandbox-kit. Ruff targets Python 3.13;
Ruff and ty explicitly exclude the workspace uv cache, including before git init.
GitHub template status is a repository setting, not a local file property.
