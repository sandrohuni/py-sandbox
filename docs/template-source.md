# Template structure

`py-sandbox` combines a uv Python project with shared agent guidance and generated
container access configuration.

- `AGENTS.md` defines design choices and a functional testing policy. `CLAUDE.md`
  points to those shared instructions. Initialization fills in the project overview.
- `src/mypackage/` is the placeholder package. Full initialization renames it and
  updates the project metadata and import smoke test while preserving existing work.
- `access_env.yaml` defines directory access, runtime selection, and resource limits.
  Sandbox initialization generates the per-machine devcontainer and sbx configs;
  those outputs are ignored by Git.
- `.devcontainer/dev` manages the project devcontainer. The standalone `docker/`
  launcher keeps its own `.agentbox` configuration.
- Ruff targets Python 3.13. Ruff and ty exclude the workspace uv cache.

GitHub template mode is a repository setting. Create new projects from
[sandrohuni/py-sandbox](https://github.com/sandrohuni/py-sandbox), then follow the
[setup guide](setup.md).
