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
    dist_dir = backend_root / "dist" / "sidecar"
    build_dir = backend_root / "build" / "sidecar"
    resources_dir = desktop_root / "resources" / "backend"

    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    executable_name = "nanobot-agent-backend.exe" if sys.platform == "win32" else "nanobot-agent-backend"
    data_separator = os.pathsep

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
        str(build_dir),
        "--specpath",
        str(build_dir),
        "--paths",
        str(backend_root),
        "--collect-data",
        "litellm",
        "--add-data",
        f"{backend_root / 'alembic'}{data_separator}alembic",
        "--add-data",
        f"{backend_root / 'alembic.ini'}{data_separator}.",
        str(backend_root / "app" / "entrypoints" / "sidecar.py"),
    ]
    subprocess.run(command, cwd=backend_root, check=True)

    built_executable = dist_dir / executable_name
    if not built_executable.exists():
        msg = f"Expected sidecar binary was not created: {built_executable}"
        raise FileNotFoundError(msg)

    target_executable = resources_dir / executable_name
    shutil.copy2(built_executable, target_executable)
    target_executable.chmod(0o755)
    print(f"Copied backend sidecar to {target_executable}")


if __name__ == "__main__":
    main()
