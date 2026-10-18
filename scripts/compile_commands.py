#!/usr/bin/env python3
"""Generate a compile database for the selected firmware using Make's flags."""

import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--compiler", required=True)
parser.add_argument("--flags", required=True)
parser.add_argument("sources", nargs="+")
args = parser.parse_args()
compiler = shutil.which(args.compiler)
if compiler is None:
    parser.error(f"compiler not found: {args.compiler}; see docs/arch-setup.md")
root = Path.cwd()
# Embed the compiler's include directories so clangd needs no query-driver
# permission and does not pass its Clang-only target option to WCH GCC.
probe = subprocess.run(
    [compiler, "-E", "-v", "-x", "c", "-"],
    input="", text=True, capture_output=True, check=True,
)
system_flags = []
in_includes = False
for line in probe.stderr.splitlines():
    if line == "#include <...> search starts here:":
        in_includes = True
    elif line == "End of search list.":
        in_includes = False
    elif in_includes and Path(line.strip()).is_dir():
        system_flags.extend(["-isystem", str(Path(line.strip()).resolve())])
entries = [
    {
        "directory": str(root),
        "file": str((root / source).resolve()),
        "arguments": [compiler, *shlex.split(args.flags), *system_flags, "-c", source],
    }
    for source in args.sources
]
(root / "compile_commands.json").write_text(json.dumps(entries, indent=2) + "\n")
print(f"Wrote compile_commands.json for {len(entries)} C files")
