"""Bounded local Git audit; prints paths and rule names, never matched values.

Scans blobs reachable from local refs (fetch remote refs first). This is not a
replacement for a full secret scanner, visual media review or legal review.
"""

import json
import re
import subprocess
from pathlib import Path


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    patterns = {
        "groq_key": rb"gsk_[A-Za-z0-9]{30,}",
        "github_token": rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}",
        "openai_key": rb"sk-(?:proj-)?[A-Za-z0-9_-]{30,}",
        "aws_access_key": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
        "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    }
    # Compare actual local configured secrets without emitting their values.
    configured = []
    env = Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            name, sep, value = line.partition("=")
            value = value.strip().strip("\"'")
            if sep and len(value) >= 8 and any(
                marker in name.upper() for marker in ("KEY", "SECRET", "PASSWORD")
            ):
                configured.append(value.encode())
    objects = {}
    for line in git("rev-list", "--objects", "--all").decode().splitlines():
        oid, _, path = line.partition(" ")
        if path:
            objects[oid] = path
    findings = set()
    scanned = 0
    for oid, path in objects.items():
        if git("cat-file", "-t", oid).strip() != b"blob":
            continue
        scanned += 1
        blob = git("cat-file", "blob", oid)
        if path != ".env.example" and re.search(
            r"(^|/)(\.env(?:\..*)?|.*\.(?:sqlite3|db|pem|key|dump)|.*qr.*\.png)$",
            path,
            re.IGNORECASE,
        ):
            findings.add((path, "private_artifact_path"))
        for rule, pattern in patterns.items():
            if re.search(pattern, blob):
                findings.add((path, rule))
        if any(value in blob for value in configured):
            findings.add((path, "configured_secret"))
    print(json.dumps({
        "scope": "all locally reachable Git refs",
        "blobs_scanned": scanned,
        "findings": [{"path": path, "rule": rule} for path, rule in sorted(findings)],
    }, indent=2))
    return bool(findings)


if __name__ == "__main__":
    raise SystemExit(main())
