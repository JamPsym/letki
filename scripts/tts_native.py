#!/usr/bin/env python3
"""Short Polish demo with model-native tempo control; no audio stretching."""

import argparse
import json
import os
import subprocess
import threading
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".tools/native-huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from swio_link import SwioLink
from tts_live import ticker_columns


def main():
    import numpy as np
    import onnxruntime as ort
    ort.disable_telemetry_events()
    import sounddevice as sd
    import soundfile as sf
    from supertonic import TTS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/native-demo.json")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if not .6 <= config["native_speed"] <= 2:
        parser.error("This demo allows native speed 0.6..2.0")
    if not 30 <= config["pixel_ms"] <= 120:
        parser.error("Caption interval must be 30..120 ms")
    if not 1 <= len(config["display"]) <= 64:
        parser.error("Caption must contain 1..64 characters")

    output = ROOT / "build/native-demo"
    output.mkdir(parents=True, exist_ok=True)
    tts = TTS(model="supertonic-3", model_dir=ROOT / ".tools/supertonic3",
              auto_download=True, intra_op_num_threads=4, inter_op_num_threads=1)
    style = tts.get_voice_style(voice_name=config["voice"])
    # SDK 1.3.1 conservatively guards speed at 0.7. The acoustic model divides
    # predicted duration by speed before decoding, so this local demo permits
    # a small extension to 0.6. Downloaded package files remain untouched.
    if config["native_speed"] < .7:
        import supertonic.core
        supertonic.core.MIN_SPEED = .6
    measurements = []
    for label, speed in [("normal", 1.05), ("slow", config["native_speed"])]:
        np.random.seed(42)
        start = time.monotonic()
        wave, duration = tts.synthesize(config["speech"], voice_style=style,
                                       lang="pl", total_steps=8, speed=speed)
        wave = np.asarray(wave, dtype=np.float32).reshape(-1)
        wave *= config["gain"] / max(1.0, float(np.max(np.abs(wave))))
        sf.write(output / f"{label}.wav", wave, tts.sample_rate)
        measurements.append(dict(label=label, native_speed=speed,
                                 audio_seconds=len(wave)/tts.sample_rate,
                                 generation_seconds=time.monotonic()-start))
        print(f"Supertonic Polish {label}: {measurements[-1]['audio_seconds']:.2f}s; "
              f"native speed={speed}", flush=True)
    (output / "report.json").write_text(json.dumps(dict(model="supertonic-3", backend="CPU",
        text=config["speech"], voice=config["voice"], native_duration_control=True,
        postprocessing_time_stretch=False, measurements=measurements),
        ensure_ascii=False, indent=2)+"\n")
    if args.prepare_only:
        return

    audio, rate = sf.read(output / "slow.wav", dtype="float32")
    columns = ticker_columns(config["display"])
    boundaries = []
    if config.get("sync_after"):
        align_python = ROOT / ".tools/align-venv/bin/python"
        if not align_python.exists():
            align_python = ROOT / ".tools/tts-venv/bin/python"
        if not align_python.exists():
            raise RuntimeError("Run python3 scripts/setup_native_tts.py for local alignment")
        with (output / "alignment.log").open("w") as log:
            subprocess.run([str(align_python),
                str(ROOT/"scripts/align_native.py"), "--config", str(args.config),
                "--audio", str(output/"slow.wav"), "--output", str(output/"anchors.json")],
                stdout=log, stderr=subprocess.STDOUT, check=True)
        boundaries = json.loads((output / "anchors.json").read_text())["boundaries"]
    state = dict(position=0, boundary=0, caption=0, pause_frames=0, audio_warnings=[])
    started, done = threading.Event(), threading.Event()

    def callback(out, frames, clock, status):
        out[:] = 0
        if status:
            state["audio_warnings"].append(str(status))
        if not started.is_set():
            state["start"] = time.monotonic()+max(0,clock.outputBufferDacTime-clock.currentTime)
            started.set()
        written = 0
        while written < frames:
            if state["boundary"] < len(boundaries):
                stop = boundaries[state["boundary"]]
                if state["position"] >= stop["audio_sample"]:
                    if state["caption"] < stop["caption_column"]:
                        state["pause_frames"] += frames-written
                        return
                    state["boundary"] += 1
                    continue
                remaining = stop["audio_sample"]-state["position"]
            else:
                remaining = len(audio)-state["position"]
            if remaining <= 0:
                raise sd.CallbackStop
            count = min(frames-written,remaining)
            out[written:written+count,0] = audio[state["position"]:state["position"]+count]
            state["position"] += count
            written += count

    with SwioLink(output / "swio.log") as link:
        try:
            link.set_frame([0] * 8)
            with sd.OutputStream(samplerate=rate, channels=1, dtype="float32",
                                 blocksize=960, latency=.1, callback=callback,
                                 finished_callback=done.set):
                if not started.wait(5):
                    raise RuntimeError("Audio failed to start")
                for index in range(len(columns)-7):
                    delay = state["start"] + index * config["pixel_ms"]/1000 - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    link.set_frame(columns[index:index+8])
                    state["caption"] = index
                if not done.wait(timeout=30):
                    raise TimeoutError("Anchored audio did not finish")
        finally:
            sd.stop()
            link.set_text("ZOBACZ ADAŚ DZIAŁA")
            link.wait(link.send("0"), "paused=0")
    (output / "playback.json").write_text(json.dumps(dict(config=config,
        audio_seconds=len(audio)/rate, inserted_pause_seconds=state["pause_frames"]/rate,
        audio_warnings=state["audio_warnings"], boundaries=boundaries),
        ensure_ascii=False, indent=2)+"\n")
    print("Native slow-speech test complete; selected synchronization points applied.")


if __name__ == "__main__":
    main()
