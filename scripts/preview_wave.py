#!/usr/bin/env python3
"""Preview the actual standalone wave generator without connecting hardware."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'firmware/visual-demo/User'
OUTPUT = ROOT / 'build/preview'
OUTPUT.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='letki-wave-') as temp:
    library = Path(temp) / 'wave.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-I' + str(APP), str(APP / 'wave.c'), '-o', str(library)], check=True)
    lib = ctypes.CDLL(str(library))
    lib.wave_frame.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
    lib.wave_frame.restype = None
    frames = []
    for phase in range(32):
        levels = (ctypes.c_uint8 * 64)()
        lib.wave_frame(levels, phase)
        image = Image.new('RGB', (264, 264), '#10141a')
        draw = ImageDraw.Draw(image)
        for x in range(8):
            for y in range(8):
                level = levels[x*8+y]/100
                colour = (int(255*level), int(130*level), int(15*level))
                draw.ellipse((x*32+7,y*32+7,x*32+31,y*32+31), fill=colour)
        frames.append(image)
    frames[0].save(OUTPUT/'radial-wave.gif', save_all=True, append_images=frames[1:], duration=45, loop=0)
    frames[4].save(OUTPUT/'radial-wave.png')
print(OUTPUT/'radial-wave.gif')
