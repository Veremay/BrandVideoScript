#!/usr/bin/env python3
"""Follow Docker Compose logs and split project-tagged records into folders."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_RE = re.compile(r"(?:^|\s|\|)project_id=([A-Za-z0-9][A-Za-z0-9._-]{0,127})")
RECORD_START_RE = re.compile(r"^(?:[^|\n]+\|\s*)?\d{2}:\d{2}:\d{2}\s+\|")
STREAM_START_RE = re.compile(r"\[LLM STREAM\]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-file", required=True)
    parser.add_argument("--log-root", default="/var/log/brandvideo")
    return parser.parse_args()


def append(path: Path, line: str) -> None:
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(line)
        output.flush()


def main() -> int:
    args = parse_args()
    root = Path(args.log_root)
    main_log = root / "backend.log"
    command = [
        os.environ.get("DOCKER_BIN", "/usr/bin/docker"),
        "compose", "-p", "brandvideo", "-f", args.compose_file,
        "logs", "-f", "--no-color", "--tail=0", "backend", "nginx",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    current_project: str | None = None
    assert process.stdout is not None
    for line in process.stdout:
        append(main_log, line)
        match = PROJECT_RE.search(line)
        if match:
            current_project = match.group(1)
        elif RECORD_START_RE.search(line) or STREAM_START_RE.search(line):
            current_project = None
        if current_project:
            append(root / "projects" / current_project / "backend.log", line)
    return process.wait()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
