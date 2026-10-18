#!/usr/bin/env python3
"""Prepared natural narration, paced by readable captions and phrase pauses."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import queue
import re
import threading
import time
import unicodedata

from swio_link import SwioLink
from tts_generate import MODEL_REVISION
from tts_live import load_model, narration_chunks, produce, ticker_columns, ticker_text

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/paced"


def phrases(source):
    lines = [line for line in source.splitlines() if line.strip()]
    if len(lines) == 15:
        groups = [(0,1), (1,3), (3,6), (6,8), (8,10), (10,11), (11,13), (13,14), (14,15)]
        return ["\n".join(lines[a:b]) for a,b in groups]
    return lines


def spoken(source):
    return " ".join(narration_chunks(source))


def words(text):
    text = unicodedata.normalize("NFD", text.lower().replace("ł", "l"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", text)


def align_phrase_ends(groups, recognized, duration):
    expected = [word for group in groups for word in words(spoken(group))]
    observed, ends = [], []
    for word in recognized:
        normalized = words(word["word"])
        observed.extend(normalized)
        ends.extend([word["end"]] * len(normalized))
    matcher = difflib.SequenceMatcher(None, expected, observed, autojunk=False)
    matched = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            matched[block.a + offset] = ends[block.b + offset]
    result, count, previous = [], 0, 0
    for group in groups:
        count += len(words(spoken(group)))
        index = count - 1
        if index in matched:
            end = matched[index]
        else:
            before = max((i for i in matched if i < index), default=-1)
            after = min((i for i in matched if i > index), default=len(expected))
            left = matched.get(before, 0)
            right = matched.get(after, duration)
            end = left + (right-left) * (index-before) / max(1,after-before)
        end = max(previous, min(duration, end))
        result.append(end)
        previous = end
    result[-1] = duration
    return result, len(matched)/max(1,len(expected))


def prepare(source):
    import numpy as np
    import soundfile as sf
    import torch

    OUTPUT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.encode() + MODEL_REVISION.encode() + b"paced-v1").hexdigest()
    info_path, wav_path = OUTPUT / "narration.json", OUTPUT / "narration.wav"
    if info_path.exists() and wav_path.exists():
        info = json.loads(info_path.read_text())
        if info.get("source_sha256") == digest:
            audio, rate = sf.read(wav_path, dtype="float32")
            return audio, rate, info

    print("Preparing natural narration once; no per-word synthesis or time stretching.", flush=True)
    model = load_model()
    chunks = narration_chunks(source)
    q = queue.Queue(maxsize=len(chunks)+1)
    timings, cancel = [], threading.Event()
    producer = threading.Thread(target=produce,
        args=(model,chunks,q,cancel,timings,"bf16",1.0), daemon=True)
    producer.start()
    audio_parts = []
    while True:
        item = q.get(timeout=180)
        if item is None:
            break
        if isinstance(item,Exception):
            raise item
        audio_parts.append(item)
    producer.join()
    rate = model.sr
    audio = np.concatenate(audio_parts)
    sf.write(wav_path,audio,rate,subtype="PCM_16")
    del model
    torch.cuda.empty_cache()

    # Word times are estimated locally, only to choose phrase-boundary pauses.
    import librosa
    import whisper
    print("Locating natural phrase boundaries locally.", flush=True)
    recognizer = whisper.load_model("base", device="cpu", download_root=str(ROOT/".tools/whisper"))
    result = recognizer.transcribe(librosa.resample(audio, orig_sr=rate, target_sr=16000),
        language="pl", word_timestamps=True, fp16=False, verbose=False,
        initial_prompt=spoken(source), condition_on_previous_text=False)
    recognized = [word for segment in result["segments"] for word in segment.get("words",[])]
    groups = phrases(source)
    ends, ratio = align_phrase_ends(groups,recognized,len(audio)/rate)
    cursor, previous_audio = 8, 0
    boundaries = []
    for index,(group,end) in enumerate(zip(groups,ends)):
        if index:
            cursor += 2
        caption = ticker_text(group)
        cursor += sum(2 if c==" " else 4 for c in caption)
        position = min(len(audio), round(end*rate))
        if index < len(groups)-1:
            # Move the approximate word end to a nearby quiet 10 ms interval.
            window = max(1,round(rate*.01))
            low = max(previous_audio+window,position-round(rate*.08))
            high = min(len(audio)-window,position+round(rate*.2))
            candidates = range(low,high,window)
            position = min(candidates,key=lambda p:float(np.mean(audio[p:p+window]**2)),default=position)
        position = max(previous_audio,position)
        boundaries.append(dict(audio_sample=position,caption_column=cursor,text=caption))
        previous_audio=position
    info = dict(source_sha256=digest,sample_rate=rate,audio_seconds=len(audio)/rate,
                alignment_match_ratio=ratio,boundaries=boundaries,timings=timings)
    info_path.write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n")
    (OUTPUT/"alignment.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(f"Prepared {info['audio_seconds']:.1f}s natural speech and {len(boundaries)} phrase pauses.")
    return audio,rate,info


def main():
    import sounddevice as sd

    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=ROOT/"config/pasta-wycieczkowiec.txt")
    parser.add_argument("--pixel-ms",type=int,default=55)
    parser.add_argument("--prepare-only",action="store_true")
    args=parser.parse_args()
    if not 30 <= args.pixel_ms <= 120:
        parser.error("Readable caption interval must be 30..120 ms")
    source=args.source.read_text()
    audio,rate,info=prepare(source)
    if args.prepare_only:
        return
    columns=ticker_columns(source)
    started,done=threading.Event(),threading.Event()
    state=dict(position=0,boundary=0,caption=0,pause_blocks=0,audio_warnings=[])
    boundaries=info["boundaries"]

    def callback(out,frames,clock,status):
        out[:]=0
        if status:
            state["audio_warnings"].append(str(status))
        if not started.is_set():
            state["start"]=time.monotonic()+max(0,clock.outputBufferDacTime-clock.currentTime)
            started.set()
        written=0
        while written<frames:
            if state["boundary"]<len(boundaries):
                stop=boundaries[state["boundary"]]
                if state["position"]>=stop["audio_sample"]:
                    if state["caption"]<stop["caption_column"]:
                        state["pause_blocks"]+=1
                        return
                    state["boundary"]+=1
                    continue
                remaining=stop["audio_sample"]-state["position"]
            else:
                remaining=len(audio)-state["position"]
            if remaining<=0:
                raise sd.CallbackStop
            count=min(frames-written,remaining)
            out[written:written+count,0]=audio[state["position"]:state["position"]+count]
            state["position"]+=count
            written+=count

    with SwioLink(OUTPUT/"swio.log") as link:
        try:
            link.set_frame([0]*8)
            with sd.OutputStream(samplerate=rate,channels=1,dtype="float32",
                                 blocksize=960,latency=.1,callback=callback,
                                 finished_callback=done.set):
                if not started.wait(5):
                    raise RuntimeError("Audio failed to start")
                for index in range(len(columns)-7):
                    target=state["start"]+index*args.pixel_ms/1000
                    delay=target-time.monotonic()
                    if delay>0:
                        time.sleep(delay)
                    link.set_frame(columns[index:index+8])
                    state["caption"]=index
                if not done.wait(timeout=30):
                    raise TimeoutError("Paced narration did not finish")
        finally:
            link.set_text("ZOBACZ ADAŚ DZIAŁA")
            link.wait(link.send("0"),"paused=0")
    report=dict(pixel_ms=args.pixel_ms,frames=len(columns)-7,
                natural_audio_seconds=info["audio_seconds"],
                inserted_pause_seconds=state["pause_blocks"]*960/rate,
                audio_warnings=state["audio_warnings"])
    (OUTPUT/"playback.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Paced demo complete: fixed caption speed, original speech intonation preserved.")


if __name__=="__main__":
    main()
