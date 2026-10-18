#!/usr/bin/env python3
"""Install Polish GPU TTS in repo-local environments without system changes."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
BOOTSTRAP = TOOLS / "tts-bootstrap"
ENVIRONMENT = TOOLS / "tts-venv"
env = os.environ.copy()
env.update(UV_CACHE_DIR=str(TOOLS / "uv-cache"),
           UV_PYTHON_INSTALL_DIR=str(TOOLS / "python"))


def run(*command):
    subprocess.run(command, cwd=ROOT, env=env, check=True)


if not (BOOTSTRAP / "bin/uv").exists():
    run(sys.executable, "-m", "venv", str(BOOTSTRAP))
    run(str(BOOTSTRAP / "bin/python"), "-m", "pip", "install",
        "--cache-dir", str(TOOLS / "pip-cache"), "uv==0.12.24")
uv = str(BOOTSTRAP / "bin/uv")
if not (ENVIRONMENT / "bin/python").exists():
    run(uv, "--system-certs", "python", "install", "3.11.17")
    run(uv, "venv", "--python", "3.11.17", str(ENVIRONMENT))
python = str(ENVIRONMENT / "bin/python")
run(uv, "--system-certs", "pip", "install", "--python", python,
    "--index-url", "https://download.pytorch.org/whl/rocm7.1",
    "torch==2.10.0", "torchaudio==2.10.0")
run(uv, "--system-certs", "pip", "install", "--python", python,
    "--index-url", "https://pypi.org/simple",
    "--extra-index-url", "https://download.pytorch.org/whl/rocm7.1",
    "--index-strategy", "unsafe-best-match",
    "--overrides", "config/tts-overrides.txt", "-r", "config/tts-requirements.txt")
run(python, "-c", "import torch; assert torch.version.hip and torch.cuda.is_available(); "
    "print('GPU:', torch.cuda.get_device_name(0)); "
    "x=torch.randn(256,256,device='cuda'); print('GPU check:', (x@x).mean().item())")
print("TTS environment ready. Use .tools/tts-venv/bin/python scripts/tts_demo.py")
