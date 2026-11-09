# Choose an environment

For required host software and installation steps, see [setup.md](setup.md).

The [project README](../README.md) is the command reference for initialization,
`access_env.yaml`, the `.devcontainer/dev` wrapper, Docker/Podman, and sbx.
Generate both configs on the host with `bash init.sh --full <project-name>`;
use `bash init.sh --sandbox` for later access changes. Dependencies sync inside
the devcontainer on creation. The wrapper requires host uv and the Dev Containers CLI.

`--sandbox` updates only the two generated runtime configs. It does not install
project dependencies, launch containers, or change package metadata. Running
containers need recreation before new mounts take effect.

The devcontainer is a non-root Linux container with capability dropping and
no-new-privileges. Docker Sandboxes supplies a separate microVM environment.
Podman is supported through Dev Containers' Docker-compatible CLI interface;
it is not a backend for sbx. References:

- https://code.visualstudio.com/remote/advancedcontainers/docker-options
- https://docs.docker.com/ai/sandboxes/configuration/environment-files

## Optional standalone agent-box

Docker on macOS:

```bash
docker build -t agent-box:latest docker
./docker/agent-box
./docker/agent-box codex
./docker/agent-box -- bash
```

On Linux, build with your host IDs for writable bind mounts:

```bash
docker build --build-arg AGENT_UID="$(id -u)" --build-arg AGENT_GID="$(id -g)" -t agent-box:latest docker
```

Podman (default image user is 1000; launcher uses keep-id mapping):

```bash
podman build -t agent-box:latest docker
CONTAINER_ENGINE=podman ./docker/agent-box
```

The standalone launcher persists its home in `agent-box-home`. Use
`AGENT_HOME_VOLUME=project-name-agent-home` for separate credentials by project.
Devcontainer credentials use volumes scoped by devcontainer ID. Rebuilding images
does not clear these volumes. Authenticate inside the chosen environment; host
agent credentials are not copied into it.

## Mounts and limits

The checkout is writable. No dataset, GPU, host home, SSH directory, or engine
socket is mounted by default. Containers drop Linux capabilities and set
no-new-privileges. These containers still have outbound network access. A
container is not a microVM; running as non-root reduces authority but does not
make kernel isolation absolute. VS Code may forward credentials through its
integration: disable forwarding in your editor if you need that isolation.

Extra datasets: add paths under `read_only` in `access_env.yaml`, regenerate on the
host, then rebuild/recreate the chosen environment. The standalone agent-box
continues using `.agentbox.local` independently of this generator.
The devcontainer config directory and access source file are mounted read-only;
the checkout remains writable, so parent-directory replacement is still possible.
Keep sensitive host launch logic outside the checkout for stronger protection.
sbx protects the generated root environment file, but not the source access YAML.
Review source access changes before invoking initialization on the host.
`network_allow` adds sbx allow rules; it does not itself select a deny-by-default
sbx policy and does not restrict devcontainer networking.

Agent permission defaults remain enabled. The Dockerfiles do not force Codex
into full access or automatically skip Claude permissions. If an inner sandbox
cannot run in your container, inspect the error and choose permissions explicitly
for that session after reviewing the outer isolation.

GPU passthrough is optional and host-specific. Configure it only after a CPU
launch works; CUDA requires an appropriate Linux driver/runtime setup. Python
package dependencies are managed by uv and declared in pyproject.toml.
