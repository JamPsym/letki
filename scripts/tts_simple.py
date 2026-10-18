#!/usr/bin/env python3
"""A short, repeatable voice/display test with just two tempo settings."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from speech_timing import slow_speech
from swio_link import SwioLink
from tts_generate import MODEL_REVISION
from tts_live import load_model, ticker_columns

ROOT = Path(__file__).resolve().parents[1]


def main():
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/short-demo.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if not 0.5 <= config["speech_rate"] <= 1.25:
        parser.error("Speech rate must be 0.5..1.25")
    if not 30 <= config["pixel_ms"] <= 120:
        parser.error("Caption interval must be 30..120 ms")
    if not 1 <= len(config["display"]) <= 24:
        parser.error("Use a short display text of 1..24 characters")

    output = ROOT / "build/short-demo"
    output.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((config["speech"] + MODEL_REVISION).encode()).hexdigest()[:16]
    voice_path = output / f"voice-{key}.wav"
    if not voice_path.exists():
        import torch
        print("Preparing one short natural phrase; future tempo changes reuse it.", flush=True)
        model = load_model()
        torch.manual_seed(42)
        with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            wav = model.generate(config["speech"], language_id="pl",
                                 exaggeration=0.5, cfg_weight=0.5, temperature=0.7)
        raw = wav.squeeze().float().cpu().numpy()
        sf.write(voice_path, raw, model.sr, subtype="FLOAT")
        del model
        torch.cuda.empty_cache()

    raw, rate = sf.read(voice_path, dtype="float32")
    audio = slow_speech(raw, config["speech_rate"]).astype(np.float32)
    audio *= config["gain"] / max(1.0, float(np.max(np.abs(audio))))
    if not np.isfinite(audio).all():
        raise RuntimeError("Invalid audio")
    columns = ticker_columns(config["display"])
    print(f"{config['speech']} | voice {config['speech_rate']:.0%}, "
          f"captions {config['pixel_ms']} ms/pixel", flush=True)

    with SwioLink(output / "swio.log") as link:
        try:
            link.set_frame([0] * 8)
            sd.play(audio, rate, blocksize=960, latency=.1)
            start = time.monotonic()
            for index in range(len(columns) - 7):
                delay = start + index * config["pixel_ms"] / 1000 - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                link.set_frame(columns[index:index + 8])
            sd.wait()
        finally:
            sd.stop()
            link.set_text("ZOBACZ ADAŚ DZIAŁA")
            link.wait(link.send("0"), "paused=0")
    report = dict(config, audio_seconds=len(audio)/rate, frames=len(columns)-7,
                  caption_seconds=(len(columns)-8)*config["pixel_ms"]/1000)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print("Short test complete. Change config/short-demo.json and run again.")


if __name__ == "__main__":
    main()
