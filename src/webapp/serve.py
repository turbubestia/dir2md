from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dir2md webapp development commands.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backend", action="store_true", help="Start the FastAPI backend server.")
    group.add_argument("--frontend", action="store_true", help="Start the Vite frontend dev server.")
    group.add_argument("--build-frontend", action="store_true", help="Build the frontend website.")

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "src" / "webapp" / "frontend"

    if args.backend:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "webapp.backend.app:app",
            "--reload",
            "--port",
            "8000",
        ]
        return subprocess.run(command, cwd=repo_root).returncode

    npm = shutil.which("npm")
    if npm is None:
        print("npm was not found on PATH.", file=sys.stderr)
        return 1

    if args.frontend:
        return subprocess.run([npm, "run", "dev"], cwd=frontend_dir).returncode

    if args.build_frontend:
        return subprocess.run([npm, "run", "build"], cwd=frontend_dir).returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())