# Polish voice and display demo

The active demo uses Supertonic 3 with native speaking-rate control. It synthesizes the full phrase with natural intonation, scrolls compact text at a fixed readable speed, and lets audio wait at selected word boundaries. It does not stretch the completed waveform.

## Run the current demo

```sh
.tools/native-tts/bin/python scripts/tts_native.py
```

Edit `config/native-demo.json` to change the phrase and these settings:

| Setting | Current value | Effect |
| --- | --- | --- |
| `speech` | No zobacz, Adaś, jak fajnie jest bez baby. | Text sent to the Polish TTS model |
| `display` | Uppercase version without punctuation | Text scrolled on the matrix |
| `voice` | `M1` | Built-in voice style |
| `native_speed` | `0.65` | Lower means slower speech during synthesis |
| `pixel_ms` | `55` | Higher means slower captions |
| `sync_after` | `ADAŚ`, `JEST`, `BABY` | Audio may wait here until the caption passes |
| `gain` | `0.65` | Playback gain |

The compact font is three pixels wide with a blank column between letters. Polish marks occupy the extra rows, and spaces are two pixels wide. The host streams complete eight-column frames through SWIO; the MCU keeps its independent 125 Hz scan. Captions never reset at individual words.

The synchronization points use local Whisper word-time estimates, moved toward nearby quiet intervals. Playback inserts silence at those points without changing the samples, pitch or intonation within each fragment. This is approximate synchronization, intended for readability on the 8×8 display. Close other probe sessions before running the demo. After playback, the original firmware message is restored.

## Install the active environment

```sh
python3 scripts/setup_native_tts.py
```

This creates `.tools/native-tts/` with Python 3.11.17, Supertonic 1.3.1 and audio libraries. It runs on CPU and does not change the existing ROCm environment. First use downloads public model assets into `.tools/supertonic3/`; synthesis is local. Selected-point alignment reuses the existing Whisper environment, or the installer creates a smaller `.tools/align-venv/` with CPU Torch on a fresh checkout.

[Supertonic 3](https://huggingface.co/Supertone/supertonic-3) supports Polish and local ONNX inference. Its [SDK](https://github.com/supertone-oss-archive/supertonic-py) exposes native `speed` control. The SDK normally guards speed at 0.7; this demo locally relaxes that validation to 0.6 so the requested 0.65 value can be tested. The acoustic model still adjusts predicted duration before waveform decoding. Downloaded package files are unchanged. Use values at or above 0.7 to stay within the standard SDK range.

To generate samples without audio playback or a board connection:

```sh
.tools/native-tts/bin/python scripts/tts_native.py --prepare-only
```

Samples, native-rate measurements, selected boundaries and playback reports are ignored artifacts in `build/native-demo/`. Changing only `pixel_ms` reuses the word-boundary estimate when the recording is unchanged.

## Earlier experiments

Chatterbox Multilingual V3 ran successfully on the Radeon `gfx1201` GPU through ROCm, but its fast speech and post-processing slowdown did not suit this demo. Its isolated environment remains under `.tools/tts-venv/`.

`tts_demo.py` preserves the earlier word scenes, `tts_live.py` the sentence-buffered RAM stream, `tts_paced.py` the prepared narration with phrase pauses, and `tts_simple.py` the stretched short sample. They are comparison experiments, not the active workflow. The user preferred Supertonic's native slow speech; use `tts_native.py` for further iterations.

## Physical five-tile music and narration

Close picocom first (Ctrl+A, then Ctrl+X). From the repository root:

```sh
.tools/native-tts/bin/python scripts/pwm_board_audio.py
```

Add `--loop` to repeat, or `--port /dev/ttyACM0` to select the UART explicitly.
Ctrl+C stops playback and resumes the standalone automatic show. Keep PC UART
connected through the existing head-to-four-receivers chain; SWIO is not needed
for playback. The launcher refuses a port already used by another process.
Audio is synthesized/cached before the UART is opened, with no waveform time
stretching. The head needs the audio-phase update; existing PWM receivers work
unchanged. Music and speech come from the PC speakers.

The PortAudio DAC presentation clock determines the 0..959 animation tick at
25 ticks/second. UART `k TICK` selects automatic scene geometry at that absolute
tick, holds native advancement, and replies `OK tick TICK` after all four
receivers CRC-acknowledge the phase. The host skips elapsed ticks rather than
queuing delayed frames. This prevents accumulated clock drift; bus, serial,
scan and operating-system latency remain. No optical timing measurement is
claimed. Logs: `build/pwm-show/audio/board-{uart.log,playback.json}`.


Final physical audio run passed: all 960 ticks acknowledged; no audio warnings,
UART errors unchanged at 2 and drops at 0. Phase ACK mean 16.06 ms,
max 24.22 ms. User confirmed scene alignment. Tiles returned
to standalone automatic show; serial released. Evidence:
`build/board-readback/pwm-audio-20261016/summary.json`.
