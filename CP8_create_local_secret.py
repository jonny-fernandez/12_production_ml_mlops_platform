r"""CP8: create/check a private local Docker API key without printing it.

Run from the Project 12 root:
    .\.venv\Scripts\python.exe .\CP8_create_local_secret.py

Uses only Python's standard library. Never uploads, logs, or displays the key.
"""
from __future__ import annotations

import re
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SECRET_PATH = ROOT / ".secrets" / "api_key.txt"


def main() -> None:
    if Path.cwd().resolve() != ROOT:
        raise SystemExit("Run this script from the Project 12 root directory.")

    for filename in (".gitignore", ".dockerignore", "docker-compose.yml"):
        if not (ROOT / filename).is_file():
            raise SystemExit(f"Missing CP8 configuration file: {filename}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    if not re.search(r"(?m)^/\.secrets/\s*$", gitignore):
        raise SystemExit(".gitignore does not protect /.secrets/; refusing to create key")
    if not re.search(r"(?m)^\.secrets/\s*$", dockerignore):
        raise SystemExit(".dockerignore does not protect .secrets/; refusing to create key")

    SECRET_PATH.parent.mkdir(exist_ok=True)
    created = False
    try:
        # Exclusive create: existing secrets are never overwritten or rotated silently.
        with SECRET_PATH.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(secrets.token_urlsafe(48))
        created = True
    except FileExistsError:
        pass

    if not SECRET_PATH.is_file() or SECRET_PATH.is_symlink():
        raise SystemExit("Unsafe secret file: expected a regular non-symlink file")
    key = SECRET_PATH.read_text(encoding="utf-8").rstrip("\r\n")
    if not (32 <= len(key) <= 256) or any(c.isspace() for c in key):
        raise SystemExit("Existing local key is invalid; stop and inspect privately")

    print("CP8 LOCAL DOCKER SECRET CHECK")
    print("Secret status:", "CREATED" if created else "REUSED (NOT OVERWRITTEN)")
    print("Key format: valid (key not shown)")
    print("Git ignore protection: PASS")
    print("Docker build ignore protection: PASS")
    print("RESULT: CP8 LOCAL SECRET READY")
    # The file is still locally stored in plaintext. It is intended only for
    # this loopback-bound Docker demonstration, not a cloud production secret.


if __name__ == "__main__":
    main()
