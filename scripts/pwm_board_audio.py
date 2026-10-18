#!/usr/bin/env python3
"""Play the narrated PWM score with the physical five-tile chain over UART."""
import argparse
import glob
import json
from pathlib import Path
import subprocess
import threading
import time
from pwm_show_audio import OUT, prepare
from uart_link import UartLink


def phase_at(sample, rate):
    return (sample * 25 // rate) % 960


def connect(port):
    # An existing terminal would consume acknowledgements. Do not close it.
    busy = subprocess.run(['fuser', str(Path(port).resolve())], capture_output=True)
    if busy.returncode == 0:
        raise RuntimeError('Close picocom/other serial readers first (Ctrl+A, Ctrl+X in picocom).')
    link = UartLink(port, OUT/'board-uart.log')
    try:
        link.wait(link.send('k 0'), 'OK tick 0', 3)
        return link
    except Exception:
        link.close()
        raise


def play(port, loop=False):
    import sounddevice as sd
    import soundfile as sf
    prepare()  # Complete synthesis before touching hardware.
    audio, rate = sf.read(OUT/'score.wav', dtype='float32', always_2d=True)
    state = {'position': 0, 'dac_start': None, 'warnings': []}
    started = threading.Event(); done = threading.Event(); checks = []
    link = connect(port)
    def callback(out, frames, clock, status):
        out.fill(0)
        if status: state['warnings'].append(str(status))
        if state['dac_start'] is None:
            state['dac_start'] = float(clock.outputBufferDacTime); started.set()
        written = 0
        while written < frames:
            index = state['position'] % len(audio) if loop else state['position']
            count = min(frames-written, len(audio)-index)
            if count <= 0: raise sd.CallbackStop
            out[written:written+count] = audio[index:index+count]
            state['position'] += count; written += count
    try:
        link.set_brightness(100)
        print('Playing music + narration on the five physical tiles. Ctrl+C stops.', flush=True)
        with sd.OutputStream(samplerate=rate, channels=2, dtype='float32', blocksize=512,
                             latency=.08, callback=callback, finished_callback=done.set) as stream:
            if not started.wait(5): raise RuntimeError('Audio did not start')
            previous = None
            # Some backends signal completion before the last buffered audio
            # reaches the DAC. Continue driving the final presentation ticks.
            while not done.is_set() or (not loop and
                    stream.time < state['dac_start'] + len(audio)/rate):
                sample = round(max(0, stream.time-state['dac_start'])*rate)
                if not loop: sample = min(sample, len(audio)-1)
                tick = phase_at(sample, rate)
                if tick != previous:
                    before = stream.time
                    reply = link.wait(link.send(f'k {tick}'), f'OK tick {tick}', 2)
                    if reply != f'OK tick {tick}': raise RuntimeError('Incorrect phase acknowledgement')
                    checks.append({'sample': sample, 'tick': tick,
                                   'ack_seconds': stream.time-before})
                    previous = tick
                time.sleep(.003)
    finally:
        try:
            link.wait(link.send('m auto'), 'OK mode updated', 2)
            link.wait(link.send('r'), 'speed_ms=', 2)
        finally:
            link.close()
            (OUT/'board-playback.json').write_text(json.dumps({
                'checks': checks, 'audio_warnings': state['warnings'],
                'status_lines': [line for line in link.lines if line.startswith('speed_ms=')],
                'synchronization': 'DAC presentation clock -> UART tick -> four CRC acknowledgements',
                'optical_timing_measured': False,
            }, indent=2)+'\n')
    print('Playback finished; tiles resumed their standalone automatic show.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port')
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--general', action='store_true', help='Use the new general firmware after full-chain migration')
    parser.add_argument('--format',choices=('mono1','gray4','level8'),default='gray4')
    parser.add_argument('--baud', type=int, choices=(115200,230400,460800,921600), default=115200)
    args = parser.parse_args()
    if args.baud!=115200 and not args.general:parser.error('--baud requires --general')
    ports = glob.glob('/dev/serial/by-id/*WCH-Link*')
    port = args.port or (ports[0] if len(ports)==1 else None)
    if not port: parser.error('Specify --port /dev/ttyACM0 (or its /dev/serial/by-id path)')
    try:
        if args.general:
            from general_link import Driver, Serial
            from letki_general import stream
            prepare()
            with Driver(Serial(port)) as driver:
                if args.baud!=115200:driver.set_baud(args.baud)
                stream(driver,dict(source='pwm-show',duration_ms=38400),audio=OUT/'score.wav',loop=args.loop,fmt=args.format)
        else: play(port,args.loop)
    except KeyboardInterrupt: print('\nStopped.')
    except (RuntimeError, OSError, TimeoutError) as error: parser.exit(1, str(error)+'\n')

if __name__ == '__main__': main()
