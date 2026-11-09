# Work in Herdr

Keep Herdr on your host as the terminal workspace manager. Launch the agent
through the project's devcontainer wrapper in a Herdr pane:

```text
Herdr on host → .devcontainer/dev → Docker or Podman container → coding agent
```

This uses normal terminal input/output and requires no Herdr socket or host home
mount inside the container. This machine has Herdr TUI 0.7.1; its CLI differs from
the current Herdr app/core and newer TUI documentation. Manual pane commands
avoid depending on a particular version's automation API.

## First session

Start Herdr normally and open a shell pane in your project folder. If the project
is new, configure its host access and initialize it once:

```bash
cd /path/to/my-project
# Edit access_env.yaml for your host paths and chosen engine.
bash init.sh --full my-project
.devcontainer/dev info
.devcontainer/dev claude
```

The wrapper starts the container if needed and runs Claude there. In another
Herdr pane, use the same project folder for the development shell or tests:

```bash
cd /path/to/my-project
.devcontainer/dev shell
# Or run one command and return to the host shell:
.devcontainer/dev exec pytest
```

Run `.devcontainer/dev codex` in place of Claude when you want to use Codex.
Use one editing agent per checkout. For concurrent editing agents, use separate
clones and generate each clone's config with `bash init.sh --sandbox`; each gets
its own container and project-scoped credentials. This workflow is simpler than
linked Git worktrees, whose shared Git directory may lie outside the mounted
checkout and require additional access.

## Daily use

Open your Herdr project workspace and run `.devcontainer/dev claude` in a pane.
The container and agent credential volumes are reused. Herdr is the UI; the
wrapper decides where the agent executes. A host pane running plain `claude`
executes the host agent rather than the project container.

After changing access, end the attached agent session, then run on the host:

```bash
bash init.sh --sandbox
.devcontainer/dev rebuild
.devcontainer/dev claude
```

`dev down` and `dev rebuild` terminate processes in the old container. Start the
agent again afterward. Terminal I/O works through the wrapper; native Herdr
agent status tracking and automatic session resumption have not been verified
through it. Host-installed integration hooks do not automatically appear inside
the container. Do not forward Herdr's control socket to the agent container:
that would expose control of host-side panes and commands.

For sbx, launch `sbx env run sbxenv.yaml` directly in a Herdr pane. Herdr supplies
the terminal UI, while sbx supplies its separate sandbox runtime.

See [Herdr agents](https://herdr.dev/tui/docs/agents/) and
[integrations](https://herdr.dev/tui/docs/integrations/) for native agent tracking.

## Skipping Claude permission prompts

Container isolation reduces host exposure, but does not make unattended actions
risk-free. The default configuration leaves Claude's permission checks enabled.
If you deliberately choose bypass for a trusted project in a disposable clone:

```bash
.devcontainer/dev exec claude --dangerously-skip-permissions
```

This starts Claude inside the devcontainer. It does not enable a global setting.
Before an unattended session, commit and push work you want to recover, and use
`dev info` to inspect actual mounts. Give the agent write access only to folders
whose contents you are willing to let it change or delete.

The current configuration still permits:

- Changing or deleting the writable project, Git metadata, and writable output folders.
- Reading and potentially transmitting data from read-only mounts.
- Access to the agent's persistent credential directories inside the container.
- Outbound network access. `network_allow` applies to sbx policy additions, not
  Docker/Podman devcontainer egress.

A read-only mount prevents writes; it does not provide confidentiality. AGENTS.md
is guidance rather than an access-control boundary. Keep approvals enabled for
unfamiliar projects, and review access configuration on the host before applying
it. For a stronger isolation boundary, consider the separate sbx microVM workflow
and inspect its mounts and active network policy too.

Anthropic explicitly notes that a malicious project can exfiltrate accessible
data and credentials from a devcontainer when permissions are bypassed:
[Claude Code devcontainer guidance](https://code.claude.com/docs/en/devcontainer).
