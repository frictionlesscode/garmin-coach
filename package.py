#!/usr/bin/env python
"""Package SKILL.md into an installable .skill bundle, validating it first.

A .skill file is a zip containing `<name>/SKILL.md`, where `<name>` matches the frontmatter
`name` field.

Validation exists because the constraints are enforced at *upload* time, where the error
arrives with no context and after a round trip. This catches a too-long description or a
malformed `name` locally instead.

    python package.py                 # writes ./garmin-coach.skill
    python package.py --out DIR       # writes DIR/garmin-coach.skill
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

MAX_DESCRIPTION = 1024
MAX_NAME = 64
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

HERE = Path(__file__).resolve().parent


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        raise SystemExit("error: SKILL.md must open with a --- frontmatter block")
    end = text.find("\n---", 3)
    if end == -1:
        raise SystemExit("error: unterminated frontmatter block")
    block = text[3:end]

    fields: dict[str, str] = {}
    current: str | None = None
    for line in block.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            current = m.group(1)
            fields[current] = m.group(2).strip()
        elif current:  # folded continuation line
            fields[current] += " " + line.strip()
    return fields


def validate(fields: dict[str, str]) -> str:
    problems: list[str] = []

    name = fields.get("name", "")
    if not name:
        problems.append("'name' is missing")
    elif len(name) > MAX_NAME:
        problems.append(f"'name' is {len(name)} chars (max {MAX_NAME})")
    elif not NAME_PATTERN.match(name):
        problems.append(f"'name' must be lowercase-kebab-case; got {name!r}")

    description = fields.get("description", "")
    if not description:
        problems.append("'description' is missing")
    elif len(description) > MAX_DESCRIPTION:
        over = len(description) - MAX_DESCRIPTION
        problems.append(
            f"'description' is {len(description)} chars, {over} over the "
            f"{MAX_DESCRIPTION} limit"
        )

    if problems:
        raise SystemExit("error: " + "\n       ".join(problems))

    print(f"  name:        {name}")
    print(f"  description: {len(description)}/{MAX_DESCRIPTION} chars "
          f"({MAX_DESCRIPTION - len(description)} to spare)")
    return name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="package", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=str(HERE), help="output directory (default: repo root)")
    args = p.parse_args(argv)

    source = HERE / "SKILL.md"
    if not source.exists():
        raise SystemExit(f"error: {source} not found")

    text = source.read_text(encoding="utf-8")
    print(f"validating {source.name} ({len(text.encode('utf-8'))} bytes)")
    name = validate(parse_frontmatter(text))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / f"{name}.skill"

    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{name}/SKILL.md", text)

    # read back rather than trusting the write -- cheap, and catches a corrupt archive
    with zipfile.ZipFile(bundle) as z:
        if z.testzip() is not None:
            raise SystemExit(f"error: {bundle} failed its integrity check")
        names = z.namelist()
        if names != [f"{name}/SKILL.md"]:
            raise SystemExit(f"error: unexpected archive contents: {names}")
        if z.read(f"{name}/SKILL.md").decode("utf-8") != text:
            raise SystemExit("error: archived content does not match source")

    print(f"\nwrote {bundle} ({bundle.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
