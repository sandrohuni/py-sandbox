"""Sandbox access boundaries and host CLI lifecycle contracts."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "setup/sandbox.py"
spec = importlib.util.spec_from_file_location("sandbox", SCRIPT)
assert spec is not None and spec.loader is not None
sandbox = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sandbox
spec.loader.exec_module(sandbox)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project with spaces"
    (root / "setup").mkdir(parents=True)
    (root / ".devcontainer").mkdir()
    shutil.copy2(SCRIPT, root / "setup/sandbox.py")
    shutil.copy2(SCRIPT.with_name("init_project.py"), root / "setup/init_project.py")
    (root / ".devcontainer/access_env.yaml").write_text("read_and_write: [.]\nread_only: []\nengine: docker\n")
    return root


def generate(root):
    plan = sandbox.parse_plan((root / ".devcontainer/access_env.yaml").read_text(), root, dict(os.environ))
    sandbox.generate(root, plan)
    return plan


def cli(root, *arguments, env=None):
    return subprocess.run(
        [sys.executable, str(root / "setup/sandbox.py"), *arguments],
        cwd=root.parent,
        env=env,
        text=True,
        capture_output=True,
    )


def test_both_backends_preserve_read_only_overlays_and_paths(project, tmp_path):
    data = project / "data with spaces"
    data.mkdir()
    output = tmp_path / "external output"
    output.mkdir()
    text = yaml.safe_dump({"read_and_write": [".", str(output)], "read_only": ["./data with spaces"]})
    plan = sandbox.parse_plan(text, project, {})
    dev = sandbox.dev_config(plan, project)
    sbx = sandbox.sbx_config(plan, project)
    assert any("data with spaces" in mount and mount.endswith(",readonly") for mount in dev["mounts"])
    assert {"path": str(data), "readOnly": True} in sbx["additionalWorkspaces"]
    assert {"path": str(output), "readOnly": False} in sbx["additionalWorkspaces"]
    assert dev["workspaceFolder"] == "${localWorkspaceFolder}"
    for name in (".devcontainer", "setup", "docker"):
        assert any(f"/{name},type=bind,readonly" in mount for mount in dev["mounts"])
        assert {"path": str(project / name), "readOnly": True} in sbx["additionalWorkspaces"]
    assert not any("/scripts," in mount for mount in dev["mounts"])


@pytest.mark.parametrize(
    "text",
    [
        "read_and_write: [.]\nread_only: [.]",
        "read_and_write: [.]\nread_only: [missing]",
        "read_and_write: [.]\nread_only: [.]\nread_only: []",
        "read_and_write: .",
        "read_and_write: [.]\nunknown: true",
        "read_and_write: [.]\ngpu: yesplease",
        "read_and_write: [.]\ncpus: true",
        'read_and_write: [.]\nnetwork_allow: ["example.com; touch /tmp/pwned"]',
        "read_and_write: [.]\nengine: unknown",
        "read_and_write: [.]\nread_only: [$MISSING/data]",
    ],
)
def test_invalid_policy_fails_before_generation(project, text):
    (project / ".devcontainer/access_env.yaml").write_text(text)
    result = cli(project, "init", "--sandbox")
    assert result.returncode != 0
    assert not (project / ".devcontainer/devcontainer.json").exists()
    assert not (project / "sbxenv.yaml").exists()


def test_sandbox_mode_preserves_project_files_and_removes_old_mounts(project, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    metadata = project / "pyproject.toml"
    metadata.write_text("# user metadata\n")
    (project / ".devcontainer/access_env.yaml").write_text(
        yaml.safe_dump({"read_and_write": ["."], "read_only": [str(data)]})
    )
    assert cli(project, "init", "--sandbox").returncode == 0
    assert str(data) in (project / "sbxenv.yaml").read_text()
    (project / ".devcontainer/access_env.yaml").write_text("read_and_write: [.]\nread_only: []\n")
    assert cli(project, "init", "--sandbox").returncode == 0
    assert str(data) not in (project / "sbxenv.yaml").read_text()
    assert str(data) not in (project / ".devcontainer/devcontainer.json").read_text()
    assert metadata.read_text() == "# user metadata\n"


@pytest.mark.parametrize("title", ["# Python sandbox project", "# py-sandbox"])
def test_full_init_is_repeatable_without_overwriting_code(project, title):
    (project / "pyproject.toml").write_text('[project]\nname = "mypackage"\n')
    (project / "uv.lock").write_text('name = "mypackage"\n')
    (project / "AGENTS.md").write_text("SHORT PROJECT DESCRIPTION\n")
    (project / "README.md").write_text(title + "\n")
    result = cli(project, "init", "--full", "hydro-model")
    assert result.returncode == 0, result.stderr
    package = project / "src/hydro_model/__init__.py"
    assert package.exists()
    assert (project / "README.md").read_text() == "# hydro-model\n"
    package.write_text('"""User work."""\n')
    assert cli(project, "init", "--full").returncode == 0
    assert package.read_text() == '"""User work."""\n'
    assert (project / "docs/adr").is_dir()
    assert (project / "tests/test_smoke.py").exists()
    assert cli(project, "init", "--full", "different-project").returncode != 0


@pytest.fixture
def fake_tools(project, tmp_path):
    """External CLI doubles keep contract tests portable; real mounts require runtime verification."""
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "commands.jsonl"
    program = f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps([name, *sys.argv[1:]]) + "\\n")
if sys.argv[1] == "ps":
    print("container-a" if os.environ.get("HAS_CONTAINER") else "")
elif sys.argv[1] == "inspect":
    print(json.dumps([{{"Id": "container-a", "Config": {{"Labels": {{"agent-sandbox.access-hash": os.environ.get("ACTIVE_HASH", "old")}}}}, "State": {{"Status": "running"}}, "Mounts": [{{"Source": "/data", "Destination": "/data", "RW": False}}]}}]))
elif name == "devcontainer" and sys.argv[1] == "exec":
    sys.exit(int(os.environ.get("EXEC_EXIT", "0")))
"""
    for name in ("docker", "podman", "devcontainer"):
        executable = tools / name
        executable.write_text(program)
        executable.chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"], COMMAND_LOG=str(log))
    return env, log


@pytest.mark.parametrize("engine", ["docker", "podman"])
def test_exec_starts_correct_backend_and_preserves_arguments_and_exit_status(project, fake_tools, engine):
    env, log = fake_tools
    (project / ".devcontainer/access_env.yaml").write_text(f"read_and_write: [.]\nengine: {engine}\n")
    generate(project)
    result = cli(project, "dev", "exec", "pytest", "-k", "a or b", env=dict(env, EXEC_EXIT="7"))
    assert result.returncode == 7
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    up = next(command for command in commands if command[:2] == ["devcontainer", "up"])
    assert up[-2:] == ["--docker-path", engine]
    execution = commands[-1]
    assert execution[-7:] == ["--", "uv", "run", "--", "pytest", "-k", "a or b"]


def test_stale_policy_requires_regeneration_then_runtime_rebuild(project, fake_tools):
    env, log = fake_tools
    generate(project)
    with (project / ".devcontainer/access_env.yaml").open("a") as policy:
        policy.write("memory: 4g\n")
    result = cli(project, "dev", "shell", env=env)
    assert result.returncode != 0 and "--sandbox" in result.stderr
    generate(project)
    result = cli(project, "dev", "shell", env=dict(env, HAS_CONTAINER="1"))
    assert result.returncode != 0 and "older access" in result.stderr
    assert '"up"' not in log.read_text()
    result = cli(project, "dev", "rebuild", env=dict(env, HAS_CONTAINER="1"))
    assert result.returncode == 0, result.stderr
    assert "--remove-existing-container" in log.read_text()


def test_info_inspects_actual_mounts_without_starting_and_down_ignores_broken_yaml(project, fake_tools):
    env, log = fake_tools
    generate(project)
    result = cli(project, "dev", "info", env=dict(env, HAS_CONTAINER="1"))
    assert result.returncode == 0, result.stderr
    assert "ro  /data -> /data" in result.stdout
    assert '"up"' not in log.read_text()
    (project / ".devcontainer/runtime.local.json").write_text('{"engine":"podman"}')
    (project / ".devcontainer/access_env.yaml").write_text("broken: [")
    result = cli(project, "dev", "down", env=dict(env, HAS_CONTAINER="1"))
    assert result.returncode == 0, result.stderr
    assert '["podman", "rm", "--force", "container-a"]' in log.read_text()


def test_environment_path_changes_invalidate_generated_policy(project, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    text = "read_and_write: [.]\nread_only: [$DATA_ROOT]\n"
    one = sandbox.parse_plan(text, project, {"DATA_ROOT": str(first)})
    two = sandbox.parse_plan(text, project, {"DATA_ROOT": str(second)})
    assert one.fingerprint != two.fingerprint


def test_down_before_first_start_uses_selected_engine(project, fake_tools):
    env, log = fake_tools
    (project / ".devcontainer/access_env.yaml").write_text("engine: podman\nread_and_write: [missing]\n")
    result = cli(project, "dev", "down", env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(log.read_text().splitlines()[0])[0] == "podman"
