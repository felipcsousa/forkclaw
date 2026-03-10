from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    workspace_root = Path(__file__).resolve().parents[2]
    backend_root = workspace_root / "apps" / "backend"
    desktop_root = workspace_root / "apps" / "desktop" / "src-tauri"
    staging_root = workspace_root / ".build" / "nanobot-sidecar"
    dist_dir = staging_root / "dist"
    work_dir = staging_root / "work"
    spec_dir = staging_root / "spec"
    resources_dir = desktop_root / ".sidecar" / "backend"

    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    executable_name = "nanobot-agent-backend.exe" if sys.platform == "win32" else "nanobot-agent-backend"

    command = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "nanobot-agent-backend",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--paths",
        str(backend_root),
        "--collect-data",
        "litellm",
        "--add-data",
        f"{backend_root / 'alembic'}{os.pathsep}alembic",
        "--add-data",
        f"{backend_root / 'alembic.ini'}{os.pathsep}.",
        str(backend_root / "app" / "entrypoints" / "sidecar.py"),
    ]
    subprocess.run(command, cwd=backend_root, check=True)

    built_executable = dist_dir / executable_name
    if not built_executable.exists():
        msg = f"Expected sidecar binary was not created: {built_executable}"
        raise FileNotFoundError(msg)

    target_executable = resources_dir / executable_name
    if target_executable.exists():
        target_executable.unlink()
    shutil.copy2(built_executable, target_executable)
    target_executable.chmod(0o755)
    print(f"Built backend sidecar at {built_executable}")
    print(f"Staged backend sidecar at {target_executable}")


if __name__ == "__main__":
    main()
