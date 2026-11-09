"""initialize : ProjectName × TemplateCheckout → InitializedCheckout (preserves project work)."""

import keyword
import re
import sys
import tomllib
from pathlib import Path


def main() -> None:
    if len(sys.argv) > 2:
        raise SystemExit("Usage: bash init.sh --full [project-name]")
    root = Path(__file__).resolve().parents[1]
    metadata = root / "pyproject.toml"
    current_name = tomllib.loads(metadata.read_text())["project"]["name"]
    name = sys.argv[1] if len(sys.argv) == 2 else (root.name if current_name == "mypackage" else current_name)
    package = name.replace("-", "_")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name) or keyword.iskeyword(package) or name == "mypackage":
        raise SystemExit("Use a lowercase Python-compatible name other than mypackage, optionally with hyphens.")
    if current_name not in ("mypackage", name):
        raise SystemExit(f"Already initialized as {current_name}; refusing to rename existing project work.")
    source = root / "src/mypackage"
    destination = root / "src" / package
    if source.exists() and destination.exists():
        raise SystemExit("Both placeholder and destination packages exist; no changes made.")
    if source.exists():
        source.rename(destination)
    destination.mkdir(parents=True, exist_ok=True)
    initializer = destination / "__init__.py"
    if not initializer.exists():
        initializer.write_text('"""Project package."""\n')
    for directory in ("scripts", "tests", "docs/adr"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "docs/adr/.gitkeep").touch(exist_ok=True)
    for filename in ("pyproject.toml", "uv.lock"):
        path = root / filename
        path.write_text(path.read_text().replace('name = "mypackage"', f'name = "{name}"'))
    smoke = root / "tests/test_smoke.py"
    if not smoke.exists():
        smoke.write_text(f"import {package}\n\ndef test_package_imports() -> None:\n    assert {package} is not None\n")
    elif current_name == "mypackage":
        smoke.write_text(smoke.read_text().replace("mypackage", package))
    agents = root / "AGENTS.md"
    agents.write_text(agents.read_text().replace("SHORT PROJECT DESCRIPTION", name))
    readme = root / "README.md"
    readme_text = readme.read_text()
    if current_name == "mypackage":
        for title in ("# Python sandbox project\n", "# py-sandbox\n"):
            if readme_text.startswith(title):
                readme_text = f"# {name}\n" + readme_text[len(title) :]
                break
    readme.write_text(readme_text)
    print(f"Initialized {name} (import {package}). Dependencies sync inside the devcontainer on first start.")


if __name__ == "__main__":
    main()
