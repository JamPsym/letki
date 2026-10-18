#!/usr/bin/env python3
"""Verify and render complete music demos offline. Never plays audio or opens UART."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'build/player/letki-player'
OUT = ROOT / 'build/player/complete-demos'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def probe(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                        '-of', 'json', str(path)], check=True, capture_output=True, text=True)
    return json.loads(p.stdout)


def pixels(path):
    with path.open('rb') as f:
        header = f.readline().decode('ascii').split()
        if header[:4] != ['LETKI-FRAMES', '1', '40', '8'] or len(header) != 6:
            raise ValueError('Invalid native frame export')
        fps, start = float(header[4]), float(header[5])
        data = np.frombuffer(f.read(), dtype=np.uint8)
    if len(data) % 320 or not len(data) or data.max() > 100:
        raise ValueError('Invalid PWM pixels')
    return fps, start, data.reshape(-1, 5, 8, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 40)


def colored(frames):
    v = np.sqrt(frames.astype(np.float32) / 100)[..., None]
    return (np.array([30, 21, 13]) + v * np.array([225, 138, 36])).astype(np.uint8)


def sheet(show, frames, fps, out):
    scenes = [c for c in show['cues'] if c.get('effect')]
    width, row = 1000, 94
    result = Image.new('RGB', (width, 48 + row * len(scenes)), '#0a0d14')
    draw = ImageDraw.Draw(result)
    draw.text((12, 10), show['name'], fill='#ffffff')
    draw.text((12, 27), 'Full timeline; two source-time samples per scene. Video stays on the PC.', fill='#bbbbbb')
    times = []
    for i, c in enumerate(scenes):
        y = 48 + i * row
        draw.text((8, y), f"{c['at']:7.2f}s  {c['label']}", fill='#eeeeee')
        draw.text((8, y+17), f"{c['effect']}  level={c['level']}  speed={c['speed']}", fill='#999999')
        for j, fraction in enumerate((.22, .68)):
            t = show['intro_seconds'] + c['at'] + c['duration'] * fraction
            index = min(len(frames)-1, round(t*fps))
            image = Image.fromarray(colored(frames[index])).resize((400, 80), Image.Resampling.NEAREST)
            result.paste(image, (190+j*405, y+4))
            times.append(t)
    result.save(out)
    return times


def longest_unintended_blackout(show, total, fps):
    dark = np.asarray(total) == 0
    intro = show.get('intro_seconds', 0)
    dark[:math.ceil(intro * fps)] = False
    # A declared zero-level scene may cover a long silent tail. Other dark
    # passages still count, including darkness before the intended blackout.
    for cue in show['cues']:
        if cue.get('effect') and cue.get('level', 1) == 0:
            begin = max(0, math.ceil((intro + cue['at']) * fps - 1e-7))
            end = max(begin, math.ceil((intro + cue['at'] + cue['duration']) * fps - 1e-7))
            dark[begin:end] = False
    longest = current = 0
    for value in dark:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest / fps


def run_demo(entry, video):
    source = ROOT / entry['show']
    show = json.loads(source.read_text())
    audio = (source.parent / show['audio']).resolve()
    movie = (source.parent / show['video']).resolve()
    if digest(audio) != show['recording']['sha256']:
        raise ValueError(f"Recording identity changed: {audio}")
    duration = entry['recording_seconds']
    if abs(duration-show['recording']['duration_seconds']) > 1e-6:
        raise ValueError('Manifest duration differs from authored recording')
    scenes = [c for c in show['cues'] if c.get('effect')]
    cursor = 0
    for c in scenes:
        if abs(c['at']-cursor) > 1e-6:
            raise ValueError(f"Gap/overlap at {cursor}: {c['at']}")
        cursor += c['duration']
    if abs(cursor-duration) > 1e-6 or show['video_target'] != 'PC only':
        raise ValueError('Incomplete timeline or incorrect video destination')
    folder = OUT / entry['id']
    folder.mkdir(parents=True, exist_ok=True)
    fingerprint = dict(binary=digest(BINARY), show=digest(source), audio=digest(audio), video=digest(movie),
                       preparer=digest(__file__), manifest=digest(ROOT/'config/player/demos.json'))
    stamp = folder/'preparation.json'
    previous = json.loads(stamp.read_text()) if stamp.exists() else {}
    raw, report = folder/'frames.bin', folder/'simulation.json'
    same = previous.get('fingerprint') == fingerprint and previous.get('complete')
    cached_frames = (same and raw.exists() and report.exists() and
                     digest(raw) == previous.get('frame_export_sha256') and
                     digest(report) == previous.get('simulation_report_sha256'))
    if not cached_frames:
        with (folder/'simulation.log').open('w') as log:
            subprocess.run([str(BINARY), '--show', str(source), '--check', '--frames', str(raw),
                            '--report', str(report)], cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT)
    fps, start, frames = pixels(raw)
    if start != 0 or len(frames) != math.ceil(entry['total_seconds']*fps):
        raise ValueError('Full recording/introduction coverage was not exported')
    result = json.loads(report.read_text())
    if result['status'] != 'checked' or result['hardware'] or result['video_on_leds']:
        raise ValueError('Offline native firmware verification failed')
    if abs(result['elapsed_seconds']-entry['total_seconds']) > 1e-6:
        raise ValueError('Native audio duration differs from cue sheet')
    contacts = folder/'timeline.png'
    sheet(show, frames, fps, contacts)
    rgb = folder/'leds.rgb'
    rgb.write_bytes(colored(frames).tobytes())
    preview = folder/'silent-preview.mp4'
    cached_video = same and preview.exists() and digest(preview) == previous.get('silent_preview_sha256')
    if video and not cached_video:
        intro = show['intro_seconds']
        filters = (f'[0:v]scale=960:540:force_original_aspect_ratio=decrease,'
                   f'pad=960:540:(ow-iw)/2:(oh-ih)/2:color=0x0a0d14,'
                   f'fps={fps},tpad=start_mode=clone:start_duration={intro}:stop_mode=clone:stop_duration=2[top];'
                   '[1:v]scale=800:160:flags=neighbor,drawgrid=w=20:h=20:t=2:c=0x0a0d14,'
                   'pad=960:210:80:25:color=0x0a0d14[leds];'
                   '[top][leds]vstack=inputs=2[out]')
        command = ['ffmpeg', '-v', 'error', '-y', '-i', str(movie), '-f', 'rawvideo',
                   '-pixel_format', 'rgb24', '-video_size', '40x8', '-framerate', str(fps), '-i', str(rgb),
                   '-filter_complex', filters, '-map', '[out]', '-an', '-t', str(entry['total_seconds']),
                   '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '27', '-pix_fmt', 'yuv420p',
                   '-threads', '2', '-movflags', '+faststart', str(preview)]
        with (folder/'render.log').open('w') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    if video:
        info = probe(preview)
        if any(s['codec_type']=='audio' for s in info['streams']):
            raise ValueError('Preview unexpectedly contains audio')
        if abs(float(info['format']['duration'])-entry['total_seconds']) > 1/fps+.02:
            raise ValueError('Preview does not cover the complete demo')
    total = frames.sum(axis=(1,2))
    longest = longest_unintended_blackout(show, total, fps)
    if longest > 5:
        raise ValueError(f'Unintended blackout exceeds5s: {longest}')
    output = dict(id=entry['id'],fingerprint=fingerprint,complete=True,offline_only=True,
                  audio_played=False,physical_display_opened=False,frames=len(frames),fps=fps,
                  total_seconds=entry['total_seconds'],scenes=len(scenes),
                  longest_internal_blackout_seconds=longest,pwm_min=int(frames.min()),pwm_max=int(frames.max()),
                  frame_export_sha256=digest(raw),simulation_report_sha256=digest(report),
                  silent_preview_sha256=digest(preview) if video else None,
                  contact_sheet=str(contacts.relative_to(ROOT)),
                  silent_preview=str(preview.relative_to(ROOT)) if video else None,
                  simulation_report=str(report.relative_to(ROOT)))
    stamp.write_text(json.dumps(output,indent=2)+'\n')
    print(f"{entry['id']}: {len(frames)} frames, {len(scenes)} scenes, full timeline verified",flush=True)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--only',choices=[d['id'] for d in json.loads((ROOT/'config/player/demos.json').read_text())['demos']])
    p.add_argument('--no-video',action='store_true',help='Generate checks/contacts only, without silent MP4')
    args=p.parse_args()
    manifest=json.loads((ROOT/'config/player/demos.json').read_text())
    OUT.mkdir(parents=True,exist_ok=True)
    results=[run_demo(d,not args.no_video) for d in manifest['demos'] if not args.only or d['id']==args.only]
    (OUT/('summary-'+args.only+'.json' if args.only else 'summary.json')).write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as e:
        sys.exit(str(e))
