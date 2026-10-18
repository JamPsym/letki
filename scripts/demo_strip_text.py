#!/usr/bin/env python3
"""Preview strip text animation through the native renderer's API."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build/renderer/letki-renderer"
OUT = ROOT / "build/strip-text-preview"


def control(path, *command):
    result = subprocess.run([str(BIN), "--socket", str(path), "ctl", *command],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def start(path, headless=False, boards=2):
    if path.exists():
        control(path, "status")
        return None
    log = (OUT / ("record.log" if headless else "window.log")).open("ab", buffering=0)
    command = [str(BIN), "--boards", str(boards), "--manual", "--socket", str(path)]
    if headless:
        command.append("--headless")
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=log, start_new_session=True)
    log.close()
    deadline = time.monotonic() + 3
    while not path.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            process.terminate()
            process.wait(timeout=3)
            raise RuntimeError("Native renderer did not start; see build/strip-text-preview logs")
        time.sleep(.01)
    return process


def configure(path, mode, boards=2, text=None):
    control(path, "stop")
    control(path, "boards", str(boards))
    control(path, "demo", "text")
    if text is not None:
        control(path, "uart", "t " + text)
    control(path, "uart", "m " + mode)


def record(boards=2, text=None):
    from PIL import Image
    path = OUT / "record.sock"
    if path.exists():
        raise RuntimeError("A recorder already owns record.sock; do not replace it")
    process = start(path, headless=True, boards=boards)
    results = {}
    try:
        for mode in ("bounce", "scroll", "fall"):
            configure(path, mode, boards, text)
            columns=control(path,"status")["text_columns"]
            count=160 if mode=="fall" else columns if mode=="scroll" else max(1,2*max(0,columns-boards*8)+16)
            frames = []
            states = []
            for i in range(count):
                states.append(control(path, "step"))
                png = OUT / f"{mode}-{i:03d}.png"
                control(path, "snapshot", str(png))
                with Image.open(png) as image:
                    image.thumbnail((800, 500))
                    frames.append(image.convert("P", palette=Image.Palette.ADAPTIVE))
            gif = OUT / f"{mode}.gif"
            # GIF time units are 10 ms; alternating 70/80 ms preserves 75 ms mean.
            frames[0].save(gif, save_all=True, append_images=frames[1:],
                           duration=[70 if i % 2 == 0 else 80 for i in range(count)],
                           loop=0, disposal=2)
            results[mode] = {"gif": str(gif.relative_to(ROOT)), "frames": count, "states": states}
        (OUT / "recording.json").write_text(json.dumps(results, indent=2) + "\n")
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("bounce", "scroll", "fall"), default="bounce")
    parser.add_argument("--tour", action="store_true", help="Show bounce, then scroll, then return to bounce")
    parser.add_argument("--record", action="store_true", help="Export all three modes using an independent native C instance")
    parser.add_argument("--boards", type=int, default=2, choices=range(1,17))
    parser.add_argument("--text", help="Caption text (up to 64 characters)")
    args = parser.parse_args()
    if not BIN.exists():
        raise SystemExit("Run make renderer first")
    OUT.mkdir(parents=True, exist_ok=True)
    if args.record:
        record(args.boards, args.text)
        print("Recorded native C previews: build/strip-text-preview/bounce.gif, scroll.gif and fall.gif", flush=True)
        if not args.tour:
            return
    path = ROOT / "build/renderer/control.sock"
    start(path, boards=args.boards)
    configure(path, args.mode, args.boards, args.text)
    control(path, "run")
    print(f"Native {args.boards}-board {args.mode} preview running; commands use the real firmware parser", flush=True)
    if args.tour:
        time.sleep(7)
        control(path, "uart", "m scroll")
        print("Showing continuous scrolling", flush=True)
        time.sleep(5)
        control(path, "uart", "m bounce")
        print("Returned to the default bounce animation", flush=True)


if __name__ == "__main__":
    main()
