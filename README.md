# py-sandbox

A uv Python project template with shared agent instructions and your choice of devcontainer or Docker Sandbox.

## Get the template

Install/authenticate [GitHub CLI](https://cli.github.com/), then create a project
from [sandrohuni/py-sandbox](https://github.com/sandrohuni/py-sandbox):

```bash
gh auth login
gh repo create my-project --template sandrohuni/py-sandbox --clone --private
cd my-project
# Edit access_env.yaml for your host paths and engine.
bash init.sh --full my-project
.devcontainer/dev claude
```

`bash init.sh my-project` is also supported as shorthand for `--full my-project`.
See the [installation guide](docs/setup.md) for the tools required on your host
and step-by-step Docker, Podman, and sbx setup.

## First setup

Start with the [installation guide](docs/setup.md) if your container tools are not installed.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on the host.
For devcontainers, install Docker or Podman 5+ and the Dev Containers CLI:

```bash
npm install -g @devcontainers/cli
cd my-project
# Edit access_env.yaml: engine, writable paths, read-only paths, resources.
bash init.sh --full my-project
```

`--full [project-name]` initializes `src/<package>/`, `scripts/`, `tests/`, and
`docs/adr/`; updates the package name, smoke test and project overview; and generates
both sandbox configs. Omit the name to use the folder name on first setup. It can
be repeated for the same project without overwriting existing source code. The
older `bash init.sh my-project` spelling also works.
Dependencies are installed **inside the devcontainer** automatically on first start.
The host needs uv for the launcher, not the project's Python dependencies.

## Start a devcontainer

Run these on the host, from your project root:

```bash
cd my-project
.devcontainer/dev claude       # start container if needed, run Claude Code
.devcontainer/dev codex        # same for Codex
.devcontainer/dev shell        # bash inside the sandbox
.devcontainer/dev exec pytest  # any command; uses the project's uv environment
.devcontainer/dev info         # show engine, configured paths, and actual container mounts
.devcontainer/dev rebuild      # recreate after Dockerfile/devcontainer.json changes
.devcontainer/dev down         # stop and remove this project's container
```

`exec` forwards arguments literally: `.devcontainer/dev exec pytest -k 'my test'`.
For shell expressions, use `.devcontainer/dev exec bash -lc 'command1 && command2'`.
Agent logins persist in project-scoped volumes across rebuilds and `down`.
`rebuild` uses the build cache and reruns the dependency installation hook.
Changes stored only in the container's filesystem are lost on rebuild/down; project
bind mounts and credential volumes remain.

For Podman, set `engine: podman` in `access_env.yaml`, then regenerate the configs.
On macOS start its VM first (`podman machine start`; initialize one if needed).
For VS Code also set `"dev.containers.dockerPath": "podman"` in your user settings.
Use **Dev Containers: Reopen in Container** to work in the editor.
Before switching engines on an existing project, run `.devcontainer/dev down` with the old engine.
Podman is mostly CLI compatible; GPU, UID and SELinux behavior remain host-specific.

## Work in Herdr

Keep Herdr on the host. In a project pane run `.devcontainer/dev claude` or
`.devcontainer/dev codex`; use another pane for `.devcontainer/dev shell` or tests.
The wrapper runs the agent inside the container while Herdr remains your UI.
Native agent tracking/resume through the wrapper has not been verified.

See the [Herdr workflow and permission guidance](docs/herdr.md), including the
opt-in bypass command and the isolation limits of the current configuration.

## Start Docker Sandboxes (sbx)

Install [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) separately.
The `engine` setting selects the devcontainer backend; sbx uses its own microVM
runtime and does not run on Podman.

```bash
sbx login                                  # once per machine
cd my-project
sbx env plan sbxenv.yaml                    # inspect generated access settings
sbx env run sbxenv.yaml                     # start/attach to default agent
sbx env run sbxenv.yaml --env-arg agent=codex
```

The default sbx agent is selected by `agent` in `access_env.yaml`. Use separate
sandbox names if keeping both agents' environments: add `--name my-project-codex`
consistently to plan/run/rm commands. Each sbx agent image supplies its own tools;
if uv is absent, install it **inside that sandbox**, then run `uv sync` there.
The devcontainer Dockerfile is not used by sbx.

## Change access later

`access_env.yaml` is the source for both generated configs:

```yaml
read_and_write:
  - .                         # required writable project
  - ../shared-code
read_only:
  - $HOME/datasets/my-data
engine: docker                # or podman, for devcontainers
agent: claude                 # default sbx agent
memory: 8g
cpus: 2                       # 0 = runtime default
shm_size: 1g                  # devcontainer only
gpu: false                    # requires host GPU support when enabled
network_allow: []             # sbx host allowlist additions only
```

All listed directories must already exist. Relative paths resolve from the
project root; `~` and host environment variables are expanded without shell
execution. Nested read-only datasets inside the writable project are supported.
Conflicting or missing paths fail before configs are written.

After adding or removing paths, run on the **host**:

```bash
bash init.sh --sandbox         # regenerate configs only; preserve package/code/docs
.devcontainer/dev info
.devcontainer/dev rebuild      # apply mounts to a devcontainer
```

For an existing sbx environment, apply the regenerated config with:

```bash
sbx env plan sbxenv.yaml
sbx env rm sbxenv.yaml         # removes sandbox state; keep work in mounted paths
sbx env run sbxenv.yaml
```

Regeneration does not change a running environment. The dev wrapper refuses to
reuse a container with an older access policy until you rebuild it. Review config
changes before regenerating on the host. Generated `.devcontainer/devcontainer.json`
and `sbxenv.yaml` are ignored by Git because they can contain machine-specific paths.
Edit `access_env.yaml` for mounts/resources and `.devcontainer/Dockerfile` for tools.
Manual JSON edits survive `dev rebuild` but are replaced by the next `init.sh` generation.
The standalone `docker/agent-box` option still uses its own `.agentbox` rules.

## Structure and checks

```text
src/<package>/      installable Python code
scripts/            initialization and sandbox CLI
tests/              tests
docs/adr/           architecture decisions
AGENTS.md           shared coding instructions
CLAUDE.md           points Claude to AGENTS.md
access_env.yaml     source access policy and resource settings
.devcontainer/      Dockerfile, dev launcher, generated devcontainer.json
docker/             optional standalone agent-box
sbxenv.yaml         generated Docker Sandboxes environment
```

```bash
.devcontainer/dev exec pytest
.devcontainer/dev exec ruff format --check
.devcontainer/dev exec ruff check
.devcontainer/dev exec ty check
```

See [installation and host setup](docs/setup.md), [environment details](docs/environments.md), [agent guidance](docs/agent-guidance.md),
and [template structure](docs/template-source.md).
