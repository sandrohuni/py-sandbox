# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml==6.0.2"]
# ///
"""sandbox : AccessPlan → (DevcontainerConfig, SbxConfig); CLI grants runtime authority."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROTECTED_DIRECTORIES = (".devcontainer", "setup", "docker")


@dataclass(frozen=True)
class Mount:
    path: Path
    read_only: bool


@dataclass(frozen=True)
class AccessPlan:
    engine: str
    agent: str
    mounts: tuple[Mount, ...]
    memory: str
    cpus: int
    shm_size: str
    gpu: bool
    network_allow: tuple[str, ...]
    fingerprint: str


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently changing access policy."""

    def construct_mapping(self, node: Any, deep: bool = False) -> dict:
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if any(not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("YAML keys must be unique strings")
        return super().construct_mapping(node, deep=deep)


def parse_plan(text: str, root: Path, environment: dict[str, str]) -> AccessPlan:
    raw = yaml.load(text, Loader=UniqueKeyLoader)
    if not isinstance(raw, dict):
        raise ValueError("access_env.yaml must be a mapping")
    allowed = {"read_and_write", "read_only", "engine", "agent", "memory", "cpus", "shm_size", "gpu", "network_allow"}
    unknown = raw.keys() - allowed
    if unknown:
        raise ValueError(f"Unknown access settings: {sorted(unknown)}")
    engine = raw.get("engine", "docker")
    agent = raw.get("agent", "claude")
    if engine not in ("docker", "podman") or agent not in ("claude", "codex"):
        raise ValueError("engine must be docker/podman; agent must be claude/codex")
    memory, shm = raw.get("memory", "8g"), raw.get("shm_size", "1g")
    if any(not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*[kmgKMG]", value) for value in (memory, shm)):
        raise ValueError("memory and shm_size need a positive size such as 8g or 512m")
    cpus, gpu = raw.get("cpus", 2), raw.get("gpu", False)
    if type(cpus) is not int or cpus < 0 or type(gpu) is not bool:
        raise ValueError("cpus must be a nonnegative integer; gpu must be true/false")
    hosts = raw.get("network_allow", [])
    if not isinstance(hosts, list) or any(
        not isinstance(host, str) or not re.fullmatch(r"(?:\*\.)?[a-zA-Z0-9][a-zA-Z0-9.-]*", host) for host in hosts
    ):
        raise ValueError("network_allow must be a list of hostnames (optional leading *.)")
    mounts: list[Mount] = []
    seen: set[Path] = set()
    for key in ("read_and_write", "read_only"):
        entries = raw.get(key, [])
        if not isinstance(entries, list):
            raise ValueError(f"{key} must be a list of directory paths")
        for entry in entries:
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(f"{key} entries must be nonempty directory paths")
            # Expand only host environment names; never execute shell expressions.
            expanded = re.sub(
                r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))",
                lambda match: environment[match[1] or match[2]],
                entry,
            )
            if expanded == "~" or expanded.startswith("~/"):
                expanded = environment["HOME"] + expanded[1:]
            path = Path(expanded)
            path = (root / path).resolve() if not path.is_absolute() else path.resolve()
            if any(char in str(path) for char in (",", "\n", "\r", "${")):
                raise ValueError(f"Unsupported mount path: {path}")
            if not path.is_dir():
                raise ValueError(f"Mount directory does not exist; create it first: {path}")
            if path in seen:
                raise ValueError(f"Repeated or conflicting mount: {path}")
            seen.add(path)
            mounts.append(Mount(path, key == "read_only"))
    if not any(mount.path == root and not mount.read_only for mount in mounts):
        raise ValueError('read_and_write must include "." (the project workspace)')
    for mount in mounts:
        if (
            mount.path != root
            and mount.path.is_relative_to(root)
            and mount.path.relative_to(root).parts[0] in PROTECTED_DIRECTORIES
        ):
            raise ValueError("Protected control directories cannot be additional data mounts; edit them on the host")
        if mount.read_only and root.is_relative_to(mount.path):
            raise ValueError("A read-only directory cannot contain the writable project")
        if not mount.read_only and any(
            parent.read_only and mount.path.is_relative_to(parent.path) for parent in mounts
        ):
            raise ValueError("Writable mounts inside read-only mounts are ambiguous; use disjoint paths")
    mounts.sort(key=lambda mount: (len(mount.path.parts), str(mount.path)))
    resolved_mounts = json.dumps([(str(mount.path), mount.read_only) for mount in mounts])
    fingerprint = hashlib.sha256(
        (
            "readonly-controls-v2\n" + str(root) + "\n" + text + resolved_mounts + str((root / "docker").is_dir())
        ).encode()
    ).hexdigest()
    return AccessPlan(engine, agent, tuple(mounts), memory, cpus, shm, gpu, tuple(hosts), fingerprint)


def dev_config(plan: AccessPlan, root: Path) -> dict:
    workspace = "${localWorkspaceFolder}"
    extra = []
    for mount in plan.mounts:
        if mount.path == root:
            continue
        path = str(mount.path)
        if mount.path.is_relative_to(root):
            path = f"{workspace}/{mount.path.relative_to(root)}"
        suffix = ",readonly" if mount.read_only else ""
        extra.append(f"source={path},target={path},type=bind{suffix}")
    # Apply protection mounts last, after the user's broader directory mounts.
    extra.extend(
        [
            *[
                f"source={workspace}/{name},target={workspace}/{name},type=bind,readonly"
                for name in PROTECTED_DIRECTORIES
                if name != "docker" or (root / name).is_dir()
            ],
            "source=${devcontainerId}-claude,target=/home/agent/.claude,type=volume",
            "source=${devcontainerId}-codex,target=/home/agent/.codex,type=volume",
        ]
    )
    run_args = [
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        f"--memory={plan.memory}",
        f"--shm-size={plan.shm_size}",
        f"--label=agent-sandbox.access-hash={plan.fingerprint}",
    ]
    if plan.cpus:
        run_args.append(f"--cpus={plan.cpus}")
    if plan.gpu:
        run_args.extend(["--gpus=all"] if plan.engine == "docker" else ["--device=nvidia.com/gpu=all"])
    return {
        "name": "Python agent sandbox",
        "build": {"dockerfile": "Dockerfile"},
        "workspaceMount": f"source={workspace},target={workspace},type=bind",
        "workspaceFolder": workspace,
        "mounts": extra,
        "runArgs": run_args,
        "containerUser": "agent",
        "remoteUser": "agent",
        "updateRemoteUserUID": True,
        "remoteEnv": {"PATH": "${containerWorkspaceFolder}/.venv/bin:${containerEnv:PATH}"},
        "postCreateCommand": "uv sync",
    }


def sbx_config(plan: AccessPlan, root: Path) -> dict:
    config: dict = {
        "schemaVersion": "1",
        "agent": "${{ env.args.agent }}",
        "args": {"agent": {"default": plan.agent, "enum": ["claude", "codex"]}},
        "workspace": {"path": str(root), "clone": False},
        "sandboxOptions": {"memory": plan.memory, "cpus": plan.cpus, "gpu": plan.gpu, "writableEnvFiles": False},
    }
    extra = [{"path": str(mount.path), "readOnly": mount.read_only} for mount in plan.mounts if mount.path != root]
    extra.extend(
        {"path": str(root / name), "readOnly": True}
        for name in PROTECTED_DIRECTORIES
        if name != "docker" or (root / name).is_dir()
    )
    config["additionalWorkspaces"] = extra
    if plan.network_allow:
        hosts = ",".join(plan.network_allow)
        config["lifecycle"] = {
            "postCreate": [
                {
                    "name": "Allow configured network hosts",
                    "command": f'sbx policy allow network --sandbox "$SBX_SANDBOX_NAME" "{hosts}"',
                }
            ]
        }
    return config


def generate(root: Path, plan: AccessPlan) -> None:
    output = {
        root / ".devcontainer/devcontainer.json": json.dumps(dev_config(plan, root), indent=2) + "\n",
        root / ".devcontainer/sbxenv.yaml": "# Generated by init.sh from access_env.yaml; do not edit.\n"
        + yaml.safe_dump(sbx_config(plan, root), sort_keys=False),
    }
    for path, text in output.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text)
        temporary.replace(path)
    alias = root / "sbxenv.yaml"
    if not alias.exists() and not alias.is_symlink():
        alias.symlink_to(".devcontainer/sbxenv.yaml")
    print("Generated .devcontainer/devcontainer.json and .devcontainer/sbxenv.yaml")
    print(
        "Apply to an existing runtime: .devcontainer/dev rebuild; or sbx env rm .devcontainer/sbxenv.yaml, then sbx env run .devcontainer/sbxenv.yaml"
    )


def container_ids(engine: str, root: Path) -> list[str]:
    result = subprocess.run(
        [engine, "ps", "--all", "--quiet", "--filter", f"label=devcontainer.local_folder={root}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.split()


def inspect(engine: str, identifiers: list[str]) -> list[dict]:
    if not identifiers:
        return []
    result = subprocess.run([engine, "inspect", *identifiers], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def require_tool(tool: str) -> None:
    if shutil.which(tool) is None:
        raise ValueError(f"Missing host tool: {tool}. See README.md for installation.")


def dev(root: Path, action: str, command: list[str], plan: AccessPlan | None) -> int:
    # Down uses the last-started engine, even after editing or breaking the access file.
    runtime_file = root / ".devcontainer/runtime.local.json"
    runtime = json.loads(runtime_file.read_text()) if runtime_file.exists() else {}
    if action == "down":
        if runtime:
            engine = runtime["engine"]
        else:
            raw = yaml.load((root / ".devcontainer/access_env.yaml").read_text(), Loader=UniqueKeyLoader)
            if not isinstance(raw, dict):
                raise ValueError("No saved runtime; access_env.yaml must specify the engine to stop")
            engine = raw.get("engine", "docker")
        if engine not in ("docker", "podman"):
            raise ValueError("Invalid saved runtime engine")
        require_tool(engine)
        identifiers = container_ids(engine, root)
        if identifiers:
            subprocess.run([engine, "rm", "--force", *identifiers], check=True)
        runtime_file.unlink(missing_ok=True)
        print(f"Removed {len(identifiers)} project container(s); credential volumes retained.")
        return 0
    assert plan is not None
    engine = plan.engine
    if action == "info":
        print(f"Engine: {engine}\nWorkspace: {root}\nConfigured directory mounts:")
        for mount in plan.mounts:
            print(f"  {'ro' if mount.read_only else 'rw'}  {mount.path}")
        controls = ", ".join(f"{name}/" for name in PROTECTED_DIRECTORIES if name != "docker" or (root / name).is_dir())
        print(f"  ro  {controls} (control files; scripts/ stays writable)")
        print("Credential volumes: scoped by devcontainer ID; persistent across rebuilds/down")
        active_engine = runtime.get("engine", engine)
        if shutil.which(active_engine) is None:
            print(f"Actual mounts unavailable: {active_engine} is not installed")
            return 0
        print(f"Inspecting project containers on: {active_engine}")
        for container in inspect(active_engine, container_ids(active_engine, root)):
            print(f"Container: {container['Id']} ({container['State']['Status']})")
            for mount in container["Mounts"]:
                print(f"  {'rw' if mount['RW'] else 'ro'}  {mount['Source']} -> {mount['Destination']}")
        return 0
    require_tool(engine)
    require_tool("devcontainer")
    config_path = root / ".devcontainer/devcontainer.json"
    if not config_path.exists():
        raise ValueError("Run bash init.sh --sandbox first")
    generated = json.loads(config_path.read_text())
    label = f"--label=agent-sandbox.access-hash={plan.fingerprint}"
    if label not in generated.get("runArgs", []):
        raise ValueError("Access settings changed. Run bash init.sh --sandbox, then .devcontainer/dev rebuild")
    if runtime.get("engine", engine) != engine:
        raise ValueError("Engine changed: run .devcontainer/dev down first to remove the old engine's container")
    if action != "rebuild":
        for container in inspect(engine, container_ids(engine, root)):
            if container["Config"]["Labels"].get("agent-sandbox.access-hash") != plan.fingerprint:
                raise ValueError("Running container has older access settings. Run .devcontainer/dev rebuild")
    options = ["--workspace-folder", str(root), "--docker-path", engine]
    up = ["devcontainer", "up", *options]
    if action == "rebuild":
        up.append("--remove-existing-container")
    subprocess.run(up, cwd=root, check=True)
    runtime_file.write_text(json.dumps({"engine": engine}) + "\n")
    if action == "rebuild":
        return 0
    commands = {"claude": ["claude"], "codex": ["codex"], "shell": ["bash"]}
    # uv makes `exec pytest` use project dependencies, without requiring a shell activation.
    run = ["uv", "run", "--", *command] if action == "exec" else commands[action]
    return subprocess.call(["devcontainer", "exec", *options, "--", *run], cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate access configs or manage a project devcontainer")
    sub = parser.add_subparsers(dest="operation", required=True)
    init = sub.add_parser("init")
    mode = init.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true")
    mode.add_argument("--sandbox", action="store_true")
    init.add_argument("name", nargs="?")
    runtime = sub.add_parser("dev")
    runtime.add_argument("action", choices=["claude", "codex", "shell", "exec", "info", "rebuild", "down"])
    runtime.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.operation == "dev" and args.action == "down":
        # Avoid depending on paths that may have been removed since the last launch.
        return dev(root, "down", [], None)
    plan = parse_plan((root / ".devcontainer/access_env.yaml").read_text(), root, dict(os.environ))
    if args.operation == "dev":
        if (args.action == "exec" and not args.command) or (args.action != "exec" and args.command):
            parser.error("exec requires a command; other actions accept no extra arguments")
        return dev(root, args.action, args.command, plan)
    if args.sandbox and args.name:
        parser.error("--sandbox accepts no project name and never changes project metadata")
    if not args.sandbox:
        # The project initializer is independently testable and preserves existing source files.
        subprocess.run(
            [sys.executable, str(root / "setup/init_project.py"), *([args.name] if args.name else [])], check=True
        )
    generate(root, plan)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, yaml.YAMLError) as error:
        print(f"sandbox: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        raise SystemExit(error.returncode) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None
