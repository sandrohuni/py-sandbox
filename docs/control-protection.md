# Read-only control files

Everything stays in the project. There is no external installation, approval
store, or agent configuration-edit mode.

| Location | Inside devcontainer/sbx | On your host |
|---|---|---|
| `.devcontainer/` | Read-only | Editable |
| `setup/` | Read-only | Editable |
| `docker/` | Read-only | Editable |
| `scripts/`, source code, tests, docs, Git metadata | Writable | Editable |
| Datasets declared read-only | Read-only | Your normal host permissions |

The runtime enforces read-only directory mounts; this does not rely on AGENTS.md
or file modes. `setup/` contains the sandbox renderer, launcher logic and project
initializer. `scripts/` is reserved for normal project commands and stays writable.
The `docker/agent-box` launcher is a separate legacy option; these guarantees
apply to the configured devcontainer and sbx routes.

## Change settings yourself

Edit `.devcontainer/access_env.yaml`, `.devcontainer/Dockerfile`, or setup code
from a host terminal/editor. Then run:

```bash
bash .devcontainer/init.sh --sandbox
.devcontainer/dev rebuild
```

For sbx:

```bash
bash .devcontainer/init.sh --sandbox
sbx env plan .devcontainer/sbxenv.yaml
sbx env rm .devcontainer/sbxenv.yaml
sbx env run .devcontainer/sbxenv.yaml
```

The mounts are read-only only inside the running guest. Your host files are not
made immutable, so you can edit them normally. Regenerating overwrites generated
JSON/YAML with settings from the access file. Container filesystem-only state is
lost on recreation; mounted work and devcontainer credential volumes persist.

## Real paths and convenience links

`access_env.yaml`, `init.sh`, and generated `sbxenv.yaml` in the root are convenience
symlinks into `.devcontainer/`. Writing through a link normally reaches the
protected file, but an agent can replace a root link's directory entry because
the project root is writable. Use the actual `.devcontainer/init.sh`,
`.devcontainer/dev`, and `.devcontainer/sbxenv.yaml` paths for later launches.
The launcher reads `.devcontainer/access_env.yaml` directly.

Avoid extra mounts inside the protected directories; the generator rejects
these so a nested writable mount cannot undermine protection. The protection
layout has a version in the access fingerprint, so an older running container
must be regenerated/rebuilt rather than silently reused.

## Verification and limits

The optional real-engine test checks that protected-file writes fail, `scripts/`
remains writable, dataset writes fail, and host edits apply after regeneration
and rebuild:

```bash
PY_SANDBOX_TEST_ENGINE=docker uv run pytest tests/test_container_controls.py
```

Docker is tested here. Podman and sbx have matching configuration but require
live verification on a host where they are installed. sbx environment files and
read-only workspaces are described in the
[official environment reference](https://docs.docker.com/ai/sandboxes/configuration/environment-files).

This protects against direct writes through the configured mounts, not runtime
escapes or host execution of other agent-edited code. Project/Git files and agent
credentials remain accessible according to their mounts; outbound networking is
not restricted by default. Review project code or Git hooks before running them
on the host. Skipping agent permission checks remains a separate choice.
