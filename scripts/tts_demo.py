#!/usr/bin/env python3
"""Play locally generated speech alongside readable, synchronized word scrolls."""

import argparse
import json
from pathlib import Path
import statistics
import threading
import time

from swio_link import SwioLink
from tts_generate import prepare

ROOT = Path(__file__).resolve().parents[1]


def play_clip(link, clip, audio_path, command_lead):
    import sounddevice as sd
    import soundfile as sf

    audio, rate = sf.read(audio_path, dtype="float32", always_2d=True)
    if rate != clip["sample_rate"] or len(audio) != clip["samples"]:
        raise ValueError("Audio does not match the scroll manifest")
    started, finished = threading.Event(), threading.Event()
    position = 0
    timing = {}
    warnings = []

    def callback(out, frames, clock, status):
        nonlocal position
        if status:
            warnings.append(str(status))
        out[:] = 0
        if not started.is_set():
            timing["audio_dac_monotonic"] = (time.monotonic() +
                max(0, clock.outputBufferDacTime - clock.currentTime))
            started.set()
        count = min(frames, len(audio) - position)
        out[:count] = audio[position:position + count]
        position += count
        if position >= len(audio):
            raise sd.CallbackStop

    link.set_speed(clip["step_ms"])
    link.set_text(clip["display"])
    link.arm()
    with sd.OutputStream(samplerate=rate, channels=audio.shape[1], dtype="float32",
                         blocksize=960, latency=0.1, callback=callback,
                         finished_callback=finished.set):
        if not started.wait(5):
            raise RuntimeError("Audio output did not start")
        cue = timing["audio_dac_monotonic"] - command_lead
        delay = cue - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        timing["resume_sent_monotonic"] = time.monotonic()
        marker = link.send("r")
        link.wait(marker, "paused=0")
        stop = timing["audio_dac_monotonic"] + clip["scroll_duration_seconds"] - command_lead
        delay = stop - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        link.wait(link.send("p"), "paused=1")
        if not finished.wait(clip["duration_seconds"] + 5):
            raise RuntimeError("Audio playback did not finish")
    timing.update(display=clip["display"], duration_seconds=clip["duration_seconds"],
                  step_ms=clip["step_ms"], audio_warnings=warnings,
                  scroll_duration_seconds=clip["scroll_duration_seconds"],
                  speech_delay_seconds=clip["speech_delay_seconds"],
                  estimated_command_lead_ms=command_lead * 1000)
    print(f"Played {clip['display']}: {clip['duration_seconds']:.3f}s, "
          f"{clip['step_ms']} ms/pixel", flush=True)
    return timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/demo.json")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    manifest = prepare(args.config)
    if args.prepare_only:
        print("Audio prepared in build/demo; playback and board connection skipped.")
        return
    config = json.loads(args.config.read_text())
    output = ROOT / "build" / config.get("output_name", "demo")
    report = []
    with SwioLink(output / "swio.log") as link:
        # Estimate inbound command travel from acknowledged round trips.
        samples = []
        for _ in range(5):
            start = time.monotonic()
            link.wait(link.send("s"), "speed_ms=")
            samples.append(time.monotonic() - start)
        lead = statistics.median(samples) / 2
        try:
            for clip in manifest["clips"]:
                report.append(play_clip(link, clip, output / clip["audio"], lead))
                time.sleep(manifest["pause_seconds"])
        finally:
            link.set_speed(75)
            link.set_text("ZOBACZ ADAŚ DZIAŁA")
            link.wait(link.send("0"), "paused=0")
    (output / "playback.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Demo complete. Original message and speed restored.")


if __name__ == "__main__":
    main()
