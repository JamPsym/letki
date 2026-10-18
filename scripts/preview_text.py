#!/usr/bin/env python3
"""Render the active firmware's text frames as a PNG strip and an animated GIF."""

import ctypes
from pathlib import Path
import re
import subprocess
import tempfile
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "firmware/v3/User"
OUTPUT = ROOT / "build/preview"
OUTPUT.mkdir(parents=True, exist_ok=True)
main = (APP / "main.c").read_text()
message = re.search(r'message\[\] = L"([^"]*)"', main)[1]
step_ms = int(re.search(r'#define SCROLL_STEP_MS (\d+)', main)[1])

with tempfile.TemporaryDirectory(prefix="letki-preview-") as temp:
    library = Path(temp) / "text.so"
    subprocess.run([
        "cc", "-shared", "-fPIC", f"-I{APP}", str(APP / "font.c"),
        str(APP / "text.c"), "-o", str(library),
    ], check=True)
    lib = ctypes.CDLL(str(library))
    lib.text_frame.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_wchar_p,
                               ctypes.c_size_t, ctypes.c_size_t]
    lib.text_frame.restype = None
    lib.text_columns.argtypes = [ctypes.c_wchar_p, ctypes.c_size_t]
    lib.text_columns.restype = ctypes.c_size_t
    total_columns = lib.text_columns(message, len(message))

    def columns(offset):
        frame = (ctypes.c_uint8 * 8)()
        lib.text_frame(frame, message, len(message), offset)
        return list(frame)

    def draw_grid(values, cell=22):
        image = Image.new("RGB", (len(values) * cell + 8, 8 * cell + 8), "#111820")
        draw = ImageDraw.Draw(image)
        for x, value in enumerate(values):
            for y in range(8):
                colour = "#ef504d" if value & (1 << y) else "#26313c"
                draw.ellipse((x * cell + 6, y * cell + 6,
                              (x + 1) * cell + 2, (y + 1) * cell + 2), fill=colour)
        return image

    frames = [draw_grid(columns(offset), cell=28)
              for offset in range(total_columns)]
    frames[0].save(OUTPUT / "text-scroll.gif", save_all=True,
                   append_images=frames[1:], duration=step_ms, loop=0)
    strip = [column for offset in range(0, total_columns, 8)
             for column in columns(offset)[:min(8, total_columns - offset)]]
    draw_grid(strip, cell=10).save(OUTPUT / "message.png")

print(f"Preview: {OUTPUT / 'text-scroll.gif'}")
print(f"Message: {OUTPUT / 'message.png'}")
