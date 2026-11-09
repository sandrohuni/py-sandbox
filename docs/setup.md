# Install and start your sandbox environment

This guide covers macOS and Linux hosts. Run host commands in your normal
terminal. Choose one runtime; installing all three is optional.

| Option | Install on the host | Environment provided |
|---|---|---|
| Docker devcontainer | Git, uv, Docker Desktop or Docker Engine, Dev Containers CLI | Project container built from `.devcontainer/Dockerfile` |
| Podman devcontainer | Git, uv, Podman 5+, Dev Containers CLI | Same project Dockerfile, using Podman |
| Docker Sandboxes | Git, uv, sbx, supported virtualization | Separate microVM with an sbx agent image |

For macOS, start with Docker for this template: startup, read-only mounts, access
removal, and rebuild were verified against Docker. Podman remains an alternative;
VS Code describes it as mostly CLI compatible and does not officially support
alternative engines. See [runtime compatibility](https://code.visualstudio.com/remote/advancedcontainers/docker-options).

GitHub CLI is useful for creating a project from the template. VS Code and its
Dev Containers extension are optional. The wrapper scripts use Bash. The
project's Python, Node, uv, Claude Code, and Codex are installed in the
devcontainer image; you do not need host agent installations for that route.

## 1. Install common tools

On macOS, install [Homebrew](https://brew.sh/) if you want to use these commands:

```bash
brew install git gh uv
```

On Linux install Git with your distribution's package manager, and use the
[GitHub CLI installation instructions](https://github.com/cli/cli#installation).
Install uv using its [official installer](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal if the installer updated your PATH, then check:

```bash
git --version
gh --version
uv --version
```

uv obtains the requested Python runtime for the host initialization scripts.
It also installs their isolated YAML dependency; this is separate from the
project environment installed in the devcontainer.

## 2. Install the Dev Containers CLI (Docker/Podman routes)

Use the [official standalone installer](https://github.com/devcontainers/cli#install-script)
on macOS or Linux. It includes a Node runtime, so host Node/npm is optional:

```bash
curl -fsSL https://raw.githubusercontent.com/devcontainers/cli/main/scripts/install.sh | sh
export PATH="$HOME/.devcontainers/bin:$PATH"
devcontainer --version
```

Add that PATH export to your shell startup file to keep it in new terminals.
Alternatively, with Node/npm and the required native build tools already installed:

```bash
npm install -g @devcontainers/cli
devcontainer --version
```

See the [CLI prerequisites](https://code.visualstudio.com/docs/devcontainers/devcontainer-cli)
for host Python and C/C++ build requirements of the npm route. You can skip
this section when using only sbx.

## 3A. Docker devcontainer

On macOS install [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/)
for your processor and start the application. On Linux follow the
[Docker Engine installation guide](https://docs.docker.com/engine/install/)
for your distribution, including its daemon and user-access setup.
The launcher must be able to run Docker from your normal user account.

Verify the engine, not just the client executable:

```bash
docker version
docker info
docker run --rm hello-world
```

Then create a project as described in section 4, keep `engine: docker` in
`access_env.yaml`, and run:

```bash
bash init.sh --full my-project
.devcontainer/dev shell
```

Inside the shell, `python --version` and `uv run pytest` should work. Exit the
shell to return to the host; the container stays running for your next session.

## 3B. Podman devcontainer

Install Podman 5+ using the [official installation guide](https://podman.io/docs/installation).
On macOS, Podman recommends its installer; Homebrew is an alternative whose
packaging is maintained by the community. Create a VM once, then start it:

```bash
podman machine init --cpus 4 --memory 10240
podman machine start
podman info
```

If a machine already exists, use `podman machine list` and start that machine
instead of initializing another one. Give the VM enough memory for the
`memory` limit in `access_env.yaml` plus overhead, or lower that limit.

Linux runs Podman containers natively and normally needs no Podman machine.
For example, on Ubuntu install the distribution package with
`sudo apt-get install podman`, then verify that it is version 5 or newer;
use the official guide if your distribution ships an older release.

```bash
podman --version
podman info
podman run --rm docker.io/library/hello-world
```

After creating the project in section 4, set `engine: podman` in
`access_env.yaml`, then run:

```bash
bash init.sh --full my-project
.devcontainer/dev shell
```

The wrapper passes `--docker-path podman` to the Dev Containers CLI. For VS Code,
install the Dev Containers extension and add this to your **user settings**:

```json
{ "dev.containers.dockerPath": "podman" }
```

Microsoft describes Podman as mostly Docker-CLI compatible, with alternative
engines not officially supported. See its
[Podman guidance](https://code.visualstudio.com/remote/advancedcontainers/docker-options#_podman).
On macOS, bind-mounted paths must be shared into the Podman VM. On Linux,
permission errors may require checking rootless UID mapping or SELinux labels.

## 3C. Docker Sandboxes (sbx)

Install sbx separately. It does not require Docker Desktop or Docker Engine,
and it does not use Podman. Current local-runtime prerequisites include Apple
silicon with macOS 14+, or Ubuntu 24.04+ with KVM access. Check the
[official sbx installation guide](https://docs.docker.com/ai/sandboxes/install/)
for your platform and current support.

On a supported Mac:

```bash
brew trust docker/tap
brew install docker/tap/sbx
sbx --version
sbx login
```

On Ubuntu use the guide's **Install SBX only** instructions if you do not want
Docker Engine. Ensure virtualization is enabled and your user has access to KVM;
the installer guide explains the `kvm` group setup. Restart your login session
after changing group membership.

After creating your project in section 4:

```bash
bash init.sh --full my-project
sbx env plan sbxenv.yaml
sbx env run sbxenv.yaml                     # default agent from access_env.yaml
# Alternatively, use a separate environment for Codex:
sbx env run sbxenv.yaml --name my-project-codex --env-arg agent=codex
```

Use the same `--name` for later plan, run, and rm commands for that environment.
The sbx image is independent of the Dockerfile. Inside the sandbox check
`uv --version`; if absent, install uv there with the official installer above,
then open a new shell or add its install directory to PATH. Run `uv sync` and
`uv run pytest` inside the sandbox.

`sbx env` is experimental; inspect the plan against your installed CLI version.
`network_allow` in the access YAML adds host allow rules; choose and inspect
sbx's network policy separately if you need a restricted network. It does not
restrict Docker/Podman devcontainer networking. See the
[environment-file reference](https://docs.docker.com/ai/sandboxes/configuration/environment-files).

## 4. Get a project and configure host access

Use the template once per new project:

```bash
gh auth login
gh repo create my-project --template sandrohuni/py-sandbox --clone --private
cd my-project
```

Before running `bash init.sh --full my-project`, edit `access_env.yaml`.
Keep `.` under `read_and_write`, add existing dataset directories under
`read_only`, and select your engine and resource limits. Relative paths resolve
from the project root; `$HOME` and `~` refer to your host account.

For an existing clone of this repository, work from its root; no separate kit
export step is needed. Full initialization renames the placeholder Python
package, so use a fresh template-generated repository for each project.

The [README command reference](../README.md#start-a-devcontainer) covers agents,
shells, arbitrary commands, info, rebuild, and down. Log in to your chosen agent
inside its environment; credential volumes persist across devcontainer rebuilds.

For daily work in Herdr, see the [Herdr workflow](herdr.md).

## 5. Update access and verify it

After changing paths or resource settings, run on the host:

```bash
bash init.sh --sandbox
.devcontainer/dev info
.devcontainer/dev rebuild
```

For sbx, review `sbx env plan sbxenv.yaml`, then remove/recreate that environment
with `sbx env rm sbxenv.yaml` and `sbx env run sbxenv.yaml`. Sandbox-only state is
removed; keep work you need in mounted project/output paths.

Use `dev info` to compare configured paths with actual container mounts. Verify
read-only access using a disposable dataset copy: a write there must fail while
writes to the project/output directories succeed. No host home, SSH directory,
engine socket, dataset, or GPU is mounted by default. See
[environment limits](environments.md#mounts-and-limits) for details.

If an inner agent sandbox fails, inspect the error and outer isolation before
changing that session's permissions. The images preserve agent permission defaults.
For GPU work, first get a CPU launch working, then follow your GPU/runtime vendor's
instructions; this template does not install host GPU drivers.
