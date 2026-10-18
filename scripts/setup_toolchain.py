#!/usr/bin/env python3
"""Install the pinned Linux MRS toolchain mirror inside this checkout."""

from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".tools/mrs-1.90"
REPO = "https://github.com/ToolchainRepository/MRS_Toolchain_Linux_x64_V1.90.git"
REVISION = "90064ec81d15b9d42fcc3dc11cd6bf204774ca1c"


def run(*args):
    return subprocess.run(args, check=True, text=True)


if not DEST.exists():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    run("git", "init", str(DEST))
    run("git", "-C", str(DEST), "remote", "add", "origin", REPO)
    run("git", "-C", str(DEST), "fetch", "--depth=1", "origin", REVISION)
    run("git", "-C", str(DEST), "checkout", "--detach", "FETCH_HEAD")

revision = subprocess.check_output(
    ["git", "-C", str(DEST), "rev-parse", "HEAD"], text=True
).strip()
if revision != REVISION:
    raise SystemExit(f"Unexpected toolchain revision in {DEST}: {revision}")

# This mirror lacks executable bits, including GCC's internal assembler.
for path in (DEST / "RISC-V_Embedded_GCC").rglob("*"):
    if path.is_file():
        with path.open("rb") as stream:
            is_elf = stream.read(4) == b"\x7fELF"
        if is_elf:
            path.chmod(path.stat().st_mode | stat.S_IXUSR)

run(str(DEST / "RISC-V_Embedded_GCC/bin/riscv-none-embed-gcc"), "--version")
print("Toolchain ready. Run make doctor, then make all-variants.")
