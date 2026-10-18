#!/usr/bin/env python3
"""Estimate selected word boundaries in the local native-speed recording."""

import argparse
import hashlib
import json
from pathlib import Path

from tts_paced import align_phrase_ends, words
from tts_live import ticker_text

ROOT = Path(__file__).resolve().parents[1]


def main():
    import numpy as np
    import soundfile as sf
    import torch
    import whisper

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    settings = {key: config[key] for key in ("speech", "display", "sync_after")}
    digest = hashlib.sha256(args.audio.read_bytes()+
                            json.dumps(settings, sort_keys=True).encode()).hexdigest()
    if args.output.exists() and json.loads(args.output.read_text()).get("sha256") == digest:
        return
    tokens = config["speech"].split()
    normalized = [words(token)[0] for token in tokens]
    groups, previous = [], 0
    for anchor in config["sync_after"]:
        index = normalized.index(words(anchor)[0], previous)
        groups.append(" ".join(tokens[previous:index+1]))
        previous = index+1
    if previous < len(tokens):
        groups.append(" ".join(tokens[previous:]))
    torch.set_num_threads(4)
    model = whisper.load_model("base", device="cpu", download_root=str(ROOT/".tools/whisper"))
    result = model.transcribe(str(args.audio), language="pl", word_timestamps=True,
                              fp16=False, verbose=False, initial_prompt=config["speech"])
    recognized = [w for segment in result["segments"] for w in segment.get("words",[])]
    audio, rate = sf.read(args.audio, dtype="float32")
    ends, ratio = align_phrase_ends(groups, recognized, len(audio)/rate)
    cursor, last_audio = 8, 0
    boundaries = []
    for index, (group, end) in enumerate(zip(groups, ends)):
        if index:
            cursor += 2
        caption = ticker_text(group)
        cursor += sum(2 if c == " " else 4 for c in caption)
        point = round(end*rate)
        if index < len(groups)-1:
            window = round(.01*rate)
            low = max(last_audio+window, point-round(.06*rate))
            high = min(len(audio)-window, point+round(.18*rate))
            point = min(range(low,high,window),
                        key=lambda p:float(np.mean(audio[p:p+window]**2)), default=point)
        point = max(last_audio, min(len(audio), point))
        boundaries.append(dict(audio_sample=point, caption_column=cursor, text=caption))
        last_audio = point
    args.output.write_text(json.dumps(dict(sha256=digest, match_ratio=ratio,
        boundaries=boundaries), ensure_ascii=False, indent=2)+"\n")


if __name__ == "__main__":
    main()
