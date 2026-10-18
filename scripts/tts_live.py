#!/usr/bin/env python3
"""Natural Polish speech in RAM, with a continuously scrolled live LED ticker."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

from swio_link import SwioLink
from tts_generate import MODEL_REVISION
from speech_timing import slow_speech

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = "ABCDEFGHIJKLMNOPQRSTUVWXYZĄĆĘŁŃÓŚŹŻ "


def narration_chunks(source):
    sentences = []
    for line in source.splitlines():
        text = line.strip().lstrip("-> ").strip()
        if not text:
            continue
        text = text.replace("oshit.png", "o shit, kropka pe en gie")
        text = text.replace("(", ", ").replace(")", "")
        text = text[0].upper() + text[1:]
        if text[-1] not in ".!?":
            text += "."
        sentences.append(text)
    chunks, current = [], []
    for sentence in sentences:
        current.append(sentence)
        if len(" ".join(current)) >= 120:
            chunks.append(" ".join(current))
            current = []
    if current:
        if chunks and len(" ".join(current)) < 60:
            chunks[-1] += " " + " ".join(current)
        else:
            chunks.append(" ".join(current))
    return chunks


def ticker_text(source):
    text = " ".join(line.lstrip("-> ").strip() for line in source.splitlines())
    return " ".join("".join(c if c in SUPPORTED else " " for c in text.upper()).split())


def ticker_columns(source):
    directory = ROOT / "build/tools"
    directory.mkdir(parents=True, exist_ok=True)
    library = directory / "compact-font.so"
    source_file = ROOT / "firmware/v3/User/font_compact.c"
    header = source_file.parent / "font.h"
    if not library.exists() or max(source_file.stat().st_mtime, header.stat().st_mtime) > library.stat().st_mtime:
        subprocess.run(["cc", "-shared", "-fPIC", "-O2", str(source_file), "-o", str(library)], check=True)
    font = ctypes.CDLL(str(library)).font_compact_column
    font.argtypes = [ctypes.c_wchar, ctypes.c_uint8]
    font.restype = ctypes.c_uint8
    text = ticker_text(source)
    columns = [0] * 8
    for char in text:
        columns.extend([0, 0] if char == " " else [font(char, i) for i in range(3)] + [0])
    columns.extend([0] * 8)
    return columns


def load_model():
    import torch
    from huggingface_hub import snapshot_download
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    if not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError("ROCm GPU unavailable")
    torch.set_num_threads(4)
    checkpoint = snapshot_download(
        repo_id="ResembleAI/chatterbox", revision=MODEL_REVISION, local_files_only=True,
        allow_patterns=["ve.pt", "s3gen.pt", "t3_mtl23ls_v3.safetensors",
                        "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json"],
    )
    return ChatterboxMultilingualTTS.from_local(checkpoint, "cuda", t3_model="v3")


def produce(model, chunks, audio_queue, cancel, timings, precision, speech_rate):
    import numpy as np
    import torch
    try:
        for index, text in enumerate(chunks):
            if cancel.is_set():
                break
            started = time.monotonic()
            torch.manual_seed(42 + index)
            dtype = torch.bfloat16 if precision == "bf16" else torch.float16
            with torch.inference_mode(), torch.autocast(
                    device_type="cuda", dtype=dtype, enabled=precision != "fp32"):
                wav = model.generate(text, language_id="pl", exaggeration=0.5,
                                     cfg_weight=0.5, temperature=0.7)
            audio = wav.squeeze().float().cpu().numpy().astype(np.float32)
            if not len(audio) or not np.isfinite(audio).all():
                raise RuntimeError("Invalid generated audio")
            audio = slow_speech(audio, speech_rate).astype(np.float32)
            audio *= 0.65 / max(1.0, float(np.max(np.abs(audio))))
            duration = len(audio) / model.sr
            timings.append(dict(chunk=index, text=text, audio_seconds=duration,
                                generation_seconds=time.monotonic() - started))
            print(f"Speech chunk {index + 1}/{len(chunks)}: {duration:.2f}s audio, "
                  f"{timings[-1]['generation_seconds']:.2f}s generation", flush=True)
            while not cancel.is_set():
                try:
                    audio_queue.put(audio, timeout=.2)
                    break
                except queue.Full:
                    pass
    except Exception as error:
        audio_queue.put(error)
    finally:
        if not cancel.is_set():
            audio_queue.put(None)


def main():
    import numpy as np
    import sounddevice as sd

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "config/pasta-wycieczkowiec.txt")
    parser.add_argument("--text")
    parser.add_argument("--pixel-ms", type=int)
    parser.add_argument("--precision", choices=["fp32", "fp16", "bf16"], default="bf16")
    parser.add_argument("--speech-rate", type=float, default=0.85,
                        help="Speech speed, 0.5..1.25; 0.85 means 15%% slower with unchanged pitch")
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()
    if args.pixel_ms is not None and not 20 <= args.pixel_ms <= 100:
        parser.error("Pixel interval must be 20..100 ms")
    if not 0.5 <= args.speech_rate <= 1.25:
        parser.error("Speech rate must be 0.5..1.25")
    source = args.text if args.text is not None else args.source.read_text()
    chunks = narration_chunks(source)
    if not chunks:
        parser.error("No text to narrate")
    print("Loading local Polish TTS; audio stays in RAM.", flush=True)
    model = load_model()
    audio_queue = queue.Queue(maxsize=max(3, len(chunks)) if args.benchmark else 3)
    cancel = threading.Event()
    timings = []
    producer = threading.Thread(target=produce,
        args=(model, chunks, audio_queue, cancel, timings, args.precision, args.speech_rate), daemon=True)
    producer.start()
    # Buffer two sentence groups; later groups are generated during playback.
    buffered = []
    for _ in range(min(2, len(chunks))):
        item = audio_queue.get(timeout=180)
        if isinstance(item, Exception):
            raise item
        if item is not None:
            buffered.append(item)
    if args.benchmark:
        producer.join(timeout=180)
        if producer.is_alive():
            raise TimeoutError("TTS benchmark timed out")
        print(json.dumps(timings, ensure_ascii=False, indent=2))
        return

    output = ROOT / "build/live"
    output.mkdir(parents=True, exist_ok=True)
    columns = ticker_columns(source)
    known_characters = sum(len(t["text"]) for t in timings[:len(buffered)])
    known_audio = sum(t["audio_seconds"] for t in timings[:len(buffered)])
    estimate = known_audio * sum(len(text) for text in chunks) / max(1, known_characters)
    pixel_ms = args.pixel_ms or max(20, min(40, round(estimate * 1000 / (len(columns) - 7))))
    print(f"Continuous ticker: {pixel_ms} ms/pixel, compact font, no word resets.", flush=True)
    current, position = buffered.pop(0), 0
    done, started = threading.Event(), threading.Event()
    state = dict(starved_blocks=0, audio_warnings=[], ended=False)

    def callback(out, frames, clock, status):
        nonlocal current, position
        out[:] = 0
        if status:
            state["audio_warnings"].append(str(status))
        if not started.is_set():
            state["start"] = time.monotonic() + max(0, clock.outputBufferDacTime - clock.currentTime)
            started.set()
        written = 0
        while written < frames:
            if position >= len(current):
                try:
                    item = buffered.pop(0) if buffered else audio_queue.get_nowait()
                except queue.Empty:
                    state["starved_blocks"] += 1
                    return
                if item is None:
                    state["ended"] = True
                    raise sd.CallbackStop
                if isinstance(item, Exception):
                    state["error"] = str(item)
                    raise sd.CallbackStop
                current, position = item, 0
            count = min(frames - written, len(current) - position)
            out[written:written + count, 0] = current[position:position + count]
            position += count
            written += count

    frame_latencies = []
    try:
        with SwioLink(output / "swio.log") as link:
            try:
                link.set_frame([0] * 8)
                with sd.OutputStream(samplerate=model.sr, channels=1, dtype="float32",
                                     blocksize=960, latency=.1, callback=callback,
                                     finished_callback=done.set):
                    if not started.wait(5):
                        raise RuntimeError("Audio failed to start")
                    for index in range(len(columns) - 7):
                        target = state["start"] + index * pixel_ms / 1000
                        delay = target - time.monotonic()
                        if delay > 0:
                            time.sleep(delay)
                        before = time.monotonic()
                        link.set_frame(columns[index:index + 8])
                        frame_latencies.append(time.monotonic() - before)
                    if not done.wait(timeout=120):
                        raise TimeoutError("Narration did not finish")
                    if state.get("error"):
                        raise RuntimeError(state["error"])
            finally:
                link.set_text("ZOBACZ ADAŚ DZIAŁA")
                link.wait(link.send("0"), "paused=0")
    finally:
        cancel.set()
        producer.join(timeout=5)
    report = dict(timings=timings, audio=state, pixel_ms=pixel_ms, speech_rate=args.speech_rate,
                  frames=len(frame_latencies), frame_latency_max_ms=max(frame_latencies, default=0)*1000)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Live demo complete: {len(frame_latencies)} frames, "
          f"{state['starved_blocks']} audio starvation blocks. Original display restored.")


if __name__ == "__main__":
    main()
