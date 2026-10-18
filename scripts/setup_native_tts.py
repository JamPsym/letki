#!/usr/bin/env python3
"""Install the current CPU TTS demo in its own repo-local environment."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / ".tools/tts-bootstrap"
TARGET = ROOT / ".tools/native-tts"
env = os.environ.copy()
env.update(UV_CACHE_DIR=str(ROOT / ".tools/uv-cache"),
           UV_PYTHON_INSTALL_DIR=str(ROOT / ".tools/python"))


def run(*command):
    subprocess.run(command, cwd=ROOT, env=env, check=True)


if not (BOOTSTRAP / "bin/uv").exists():
    run(sys.executable, "-m", "venv", str(BOOTSTRAP))
    run(str(BOOTSTRAP / "bin/python"), "-m", "pip", "install", "uv==0.12.24",
        "--cache-dir", str(ROOT / ".tools/pip-cache"))
uv = str(BOOTSTRAP / "bin/uv")
if not (TARGET / "bin/python").exists():
    run(uv, "--system-certs", "python", "install", "3.11.17")
    run(uv, "venv", "--python", "3.11.17", str(TARGET))
run(uv, "--system-certs", "pip", "install", "--python", str(TARGET / "bin/python"),
    "--index-url", "https://pypi.org/simple", "-r", "config/native-tts-requirements.txt")

# Reuse the earlier alignment environment when present. A fresh checkout can
# use CPU Torch for Whisper without downloading the large ROCm TTS runtime.
legacy = ROOT / ".tools/tts-venv/bin/python"
has_alignment = legacy.exists() and subprocess.run(
    [str(legacy), "-c", "import importlib.util; "
     "assert importlib.util.find_spec('whisper') and importlib.util.find_spec('soundfile')"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
).returncode == 0
if not has_alignment:
    align = ROOT / ".tools/align-venv"
    if not (align / "bin/python").exists():
        run(uv, "--system-certs", "python", "install", "3.11.17")
        run(uv, "venv", "--python", "3.11.17", str(align))
    python = str(align / "bin/python")
    run(uv, "--system-certs", "pip", "install", "--python", python,
        "--index-url", "https://download.pytorch.org/whl/cpu", "torch==2.10.0")
    run(uv, "--system-certs", "pip", "install", "--python", python,
        "--index-url", "https://pypi.org/simple", "numpy", "numba", "soundfile",
        "tiktoken", "tqdm", "more-itertools")
    # CPU alignment does not need Whisper's optional CUDA Triton dependency.
    run(uv, "--system-certs", "pip", "install", "--python", python,
        "--index-url", "https://pypi.org/simple", "--no-deps", "openai-whisper==20250625")
print("Native TTS ready. Run .tools/native-tts/bin/python scripts/tts_native.py")
