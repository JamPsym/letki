#!/usr/bin/env python3
"""Generate Polish Chatterbox V3 audio for readable display scenes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from demo_timing import scene_timing

ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
os.environ.setdefault("HF_HOME", str(ROOT / ".tools/huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def voice_digest(config):
    settings = dict(language=config["language"], model=config.get("model", "v3"),
                    seed=config["seed"], speech=[p["speech"] for p in config["phrases"]],
                    exaggeration=0.5, cfg_weight=0.5, temperature=0.7)
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode() +
                          MODEL_REVISION.encode()).hexdigest()


def prepare(config_path=ROOT / "config/demo.json", output=None):
    import numpy as np
    import soundfile as sf

    config_path = Path(config_path)
    config = json.loads(config_path.read_text())
    output_name = config.get("output_name", "demo")
    if not output_name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid output directory name")
    output = Path(output) if output is not None else ROOT / "build" / output_name
    digest = hashlib.sha256(config_path.read_bytes() + MODEL_REVISION.encode() +
                            b"space-width-2-once").hexdigest()
    manifest_path = output / "manifest.json"
    cached = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest.get("configuration_sha256") == digest and
                all((output / item["audio"]).exists() for item in manifest["clips"])):
            return manifest
        if (manifest.get("voice_configuration_sha256") == voice_digest(config) and
                len(manifest["clips"]) == len(config["phrases"]) and
                all((output / f"phrase-{i + 1:02d}-raw.wav").exists()
                    for i in range(len(config["phrases"])))):
            cached = manifest

    voice_cache = ROOT / "build/tts-voices"
    voice_cache.mkdir(parents=True, exist_ok=True)

    def voice_key(phrase):
        settings = dict(language=config["language"], model=config.get("model", "v3"),
                        seed=config["seed"], speech=phrase["speech"],
                        exaggeration=0.5, cfg_weight=0.5, temperature=0.7)
        return hashlib.sha256(json.dumps(settings, sort_keys=True).encode() +
                              MODEL_REVISION.encode()).hexdigest()

    need_gpu = cached is None and any(not (voice_cache / (voice_key(p) + ".wav")).exists()
                                     for p in config["phrases"])
    if need_gpu:
        import torch
        from huggingface_hub import snapshot_download
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        if not torch.version.hip or not torch.cuda.is_available():
            raise RuntimeError("ROCm GPU unavailable; run scripts/setup_tts.py with GPU access")
        torch.manual_seed(config["seed"])
        torch.set_num_threads(4)
        print("Loading Chatterbox Multilingual V3 on", torch.cuda.get_device_name(0), flush=True)
        checkpoint = snapshot_download(
            repo_id="ResembleAI/chatterbox", revision=MODEL_REVISION,
            allow_patterns=["ve.pt", "s3gen.pt", "t3_mtl23ls_v3.safetensors",
                            "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json"],
        )
        model = ChatterboxMultilingualTTS.from_local(checkpoint, "cuda", t3_model="v3")
        device = torch.cuda.get_device_properties(0)
        runtime = dict(torch_version=torch.__version__, rocm_version=torch.version.hip,
                       gpu_arch=getattr(device, "gcnArchName", "unknown"))
    elif cached is not None:
        runtime = {key: cached[key] for key in ("torch_version", "rocm_version", "gpu_arch")}
    else:
        runtime = json.loads((voice_cache / "runtime.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    clips = []
    for index, phrase in enumerate(config["phrases"]):
        display = phrase["display"].strip().upper()
        if not 1 <= len(display) <= 64:
            raise ValueError("Each display phrase must contain 1..64 characters")
        started = time.monotonic()
        voice_file = voice_cache / (voice_key(phrase) + ".wav")
        if cached is None and not voice_file.exists():
            print("Generating:", phrase["speech"], flush=True)
            with torch.inference_mode():
                wav = model.generate(phrase["speech"], language_id=config["language"],
                                     exaggeration=0.5, cfg_weight=0.5, temperature=0.7)
            raw = wav.squeeze().detach().cpu().numpy().astype(np.float32)
            sample_rate = model.sr
            sf.write(output / f"phrase-{index + 1:02d}-raw.wav", raw, sample_rate)
            sf.write(voice_file, raw, sample_rate, subtype="FLOAT")
            (voice_cache / "runtime.json").write_text(json.dumps(runtime) + "\n")
            generation_seconds = time.monotonic() - started
        elif voice_file.exists():
            print("Using cached word:", phrase["speech"], flush=True)
            raw, sample_rate = sf.read(voice_file, dtype="float32")
            sf.write(output / f"phrase-{index + 1:02d}-raw.wav", raw, sample_rate)
            generation_seconds = 0
        else:
            print("Retiming cached speech:", phrase["speech"], flush=True)
            raw, sample_rate = sf.read(output / f"phrase-{index + 1:02d}-raw.wav", dtype="float32")
            generation_seconds = cached["clips"][index]["generation_seconds"]
        if len(raw) == 0 or not np.isfinite(raw).all():
            raise RuntimeError("TTS produced an empty or invalid clip")
        step_ms = config.get("scroll_step_ms", 75)
        steps, scroll_seconds, delay_seconds, scene_seconds = scene_timing(
            display, step_ms, len(raw) / sample_rate, config.get("speech_delay_pixels", 6))
        # Let the first letter enter before speaking. Never compress the voice.
        lead = np.zeros(round(delay_seconds * sample_rate), dtype=np.float32)
        fitted = np.concatenate((lead, raw))
        fitted *= config.get("gain", 0.65) / max(1.0, float(np.max(np.abs(fitted))))
        name = f"phrase-{index + 1:02d}.wav"
        sf.write(output / name, fitted, sample_rate, subtype="PCM_16")
        item = dict(phrase, display=display, audio=name, sample_rate=sample_rate,
                    samples=len(fitted), duration_seconds=len(fitted) / sample_rate,
                    step_ms=step_ms, scroll_steps=steps,
                    scroll_duration_seconds=scroll_seconds,
                    scene_duration_seconds=scene_seconds,
                    speech_delay_seconds=delay_seconds,
                    raw_duration_seconds=len(raw) / sample_rate,
                    generation_seconds=generation_seconds)
        clips.append(item)
        print(f"Saved {name}: {item['duration_seconds']:.3f}s, {step_ms} ms/pixel", flush=True)
    manifest = dict(configuration_sha256=digest, model="Chatterbox Multilingual V3",
                    voice_configuration_sha256=voice_digest(config),
                    model_revision=MODEL_REVISION, **runtime,
                    clips=clips, pause_seconds=config.get("pause_seconds", 0.4))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/demo.json")
    args = parser.parse_args()
    prepare(args.config)
