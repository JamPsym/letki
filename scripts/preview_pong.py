#!/usr/bin/env python3
"""Preview the real two-board ball renderer without hardware access."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'firmware/pingpong-demo/User'
OUT = ROOT / 'build/preview'
OUT.mkdir(parents=True, exist_ok=True)

class State(ctypes.Structure):
    _fields_ = [('last_ms', ctypes.c_uint32), ('accepted', ctypes.c_uint32),
                ('failed', ctypes.c_uint32), ('phase', ctypes.c_uint16),
                ('seen', ctypes.c_bool), ('fault', ctypes.c_bool),
                ('paused', ctypes.c_bool)]

with tempfile.TemporaryDirectory(prefix='letki-pong-') as temp:
    libpath = Path(temp) / 'pong.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-I'+str(APP), str(APP/'pong.c'),
                    '-o', str(libpath)], check=True)
    lib = ctypes.CDLL(str(libpath))
    lib.pong_accept.argtypes = [ctypes.POINTER(State), ctypes.c_uint16, ctypes.c_uint32]
    lib.pong_accept.restype = ctypes.c_bool
    lib.pong_frame.argtypes = [ctypes.POINTER(State), ctypes.c_uint, ctypes.c_uint32,
                              ctypes.POINTER(ctypes.c_uint8)]
    lib.pong_frame.restype = ctypes.c_bool
    states = [State(), State()]
    frames = []
    for phase in range(210):
        image = Image.new('RGB', (400, 208), '#10141a')
        draw = ImageDraw.Draw(image)
        draw.line((200, 0, 200, 208), fill='#606978', width=2)
        for tile, state in enumerate(states):
            assert lib.pong_accept(ctypes.byref(state), phase, phase*100)
            pixels = (ctypes.c_uint8*8)()
            assert lib.pong_frame(ctypes.byref(state), tile, phase*100, pixels)
            for x in range(8):
                for y in range(8):
                    px = tile*200 + x*24 + 8
                    py = y*24 + 8
                    colour = '#ff8c1a' if pixels[x] & (1 << y) else '#242930'
                    draw.ellipse((px, py, px+16, py+16), fill=colour)
        frames.append(image)
    frames[0].save(OUT/'pingpong.gif', save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    frames[8].save(OUT/'pingpong.png')
print(OUT/'pingpong.gif')
