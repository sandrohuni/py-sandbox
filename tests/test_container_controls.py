"""Opt-in functional verification against a real engine, with writable project scripts."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("PY_SANDBOX_TEST_ENGINE"), reason="Set PY_SANDBOX_TEST_ENGINE=docker or podman on the host"
)
def test_real_read_only_controls_writable_scripts_and_host_updates(tmp_path):
    engine = os.environ["PY_SANDBOX_TEST_ENGINE"]
    assert engine in ("docker", "podman")
    assert shutil.which(engine) and shutil.which("devcontainer"), "Install the engine and Dev Containers CLI"
    source = Path(__file__).resolve().parents[1]
    project = tmp_path / "project"
    shutil.copytree(
        source,
        project,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".uv-cache",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "runs",
            "devcontainer.json",
            "runtime.local.json",
            "sbxenv.yaml",
        ),
    )
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    output = tmp_path / "outputs"
    output.mkdir()
    policy = {"read_and_write": [".", str(output)], "read_only": [str(dataset)], "engine": engine, "memory": "4g"}
    (project / ".devcontainer/access_env.yaml").write_text(yaml.safe_dump(policy))
    cli = [sys.executable, str(project / "setup/sandbox.py")]

    def checked(arguments):
        result = subprocess.run([*cli, *arguments], text=True, capture_output=True)
        assert result.returncode == 0, result.stdout[-10000:] + result.stderr[-10000:]
        return result

    checked(["init", "--full", "control-test"])
    protected = [
        project / ".devcontainer/Dockerfile",
        project / "setup/sandbox.py",
        project / "docker/agent-box",
        project / "access_env.yaml",
        project / "init.sh",
        project / "sbxenv.yaml",
    ]
    probe = f"""from pathlib import Path
import errno
for filename in {list(map(str, protected))!r}:
    try: Path(filename).write_text("must not be written")
    except OSError as error: assert error.errno == errno.EROFS, (filename, error)
    else: raise AssertionError(filename)
for directory in {[str(project / "scripts"), str(output)]!r}:
    path=Path(directory)/"write-probe"; path.touch(); path.unlink()
try: (Path({str(dataset)!r})/"write-probe").touch()
except OSError as error: assert error.errno == errno.EROFS
else: raise AssertionError("dataset is writable")
"""
    try:
        checked(["dev", "exec", "python", "-c", probe])
        # Host edits work normally; the running guest cannot make these changes.
        (project / ".devcontainer/access_env.yaml").write_text(
            yaml.safe_dump({"read_and_write": ["."], "read_only": [], "engine": engine, "memory": "4g"})
        )
        checked(["init", "--sandbox"])
        stale = subprocess.run([*cli, "dev", "exec", "pwd"], text=True, capture_output=True)
        assert stale.returncode != 0 and "rebuild" in stale.stderr
        checked(["dev", "rebuild"])
        checked(
            [
                "dev",
                "exec",
                "python",
                "-c",
                f"from pathlib import Path; assert not Path({str(dataset)!r}).exists(); assert not Path({str(output)!r}).exists()",
            ]
        )
    finally:
        identifiers = subprocess.run(
            [engine, "ps", "-aq", "--filter", f"label=devcontainer.local_folder={project}"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.split()
        volumes = []
        if identifiers:
            containers = json.loads(
                subprocess.run([engine, "inspect", *identifiers], check=True, text=True, capture_output=True).stdout
            )
            volumes = [
                mount["Name"] for container in containers for mount in container["Mounts"] if mount["Type"] == "volume"
            ]
        checked(["dev", "down"])
        if volumes:
            subprocess.run([engine, "volume", "rm", *volumes], check=True, capture_output=True)
