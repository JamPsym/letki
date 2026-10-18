# Complete music demos

The finished cue sheets cover the exact local recordings, opening titles,
scene transitions and a final fade to black. Audio and normal full-color video
come from the PC. The five LED tiles receive procedural animation and occasional
short text cues; video never supplies their pixels.

| Demo | Recording | With introduction | Scenes | Direction |
| --- | ---: | ---: | ---: | --- |
| My Cyganie / Don Vasyl — Ore ore | 4:38.338 | 4:38.338 | 18 | Butterfly-like pairs, opposing claps, turning skirts, embroidered flowers, woven patterns and refrain text |
| Tubular Bells / Mike Oldfield — BBC 1973 | 25:48.307 | 25:48.307 | 33 | Pitched hammers, toothed mechanisms, orthogonal tracks and suspended bars, then the announced instruments |
| Adagio for Strings / Tiësto | 3:25.729 | 3:25.729 | 14 | Pulse gates and angular facets; bowed strings and suspended arches during the breakdown; release at129seconds |
| L’Amour Toujours / Gigi D’Agostino | 4:02.493 | 4:02.493 | 15 | Recurring melodic contour, paired wings and six alternating dance-floor chevrons |

| Laskowski × 2Pac / Nospe Epson | 5:06.393 | 5:06.393 | 17 | Solemn duet, lowrider with wedding cake, bow-tied boombox, monumental tear and ceremonial toast |

The cue sheets are `config/player/my-cyganie-full.json`,
`config/player/tubular-bells-full.json`, `config/player/adagio-full.json` and
`config/player/lamour-toujours-full.json`, plus `config/player/laskowski-2pac-full.json`.
`config/player/demos.json` binds their durations and recording identities.
The earlier experimental presets remain available.

## Launch later

These commands play music. They were not run during the quiet preparation.
They automatically connect to the WCH-Link chain when present, or use the PC
simulator when no adapter is found. Normal video and audio play on the PC:

```sh
make demo-my-cyganie
make demo-tubular-bells
make demo-adagio
make demo-lamour-toujours
make demo-laskowski-2pac
```

To select a particular adapter, close picocom and add the port:

```sh
make demo-my-cyganie PORT=/dev/ttyACM0
```

The same `PORT` option works for all five targets. No firmware flash is needed.
For PC-only playback even with the chain plugged in, use:

```sh
build/player/letki-player --show config/player/my-cyganie-full.json --simulate
```

Discovery verifies all five nodes before starting. Multiple adapters require an
explicit port; busy/nonresponsive devices report an error. One automatic startup
retry handles an interrupted session's10-second high-baud lease. Offline
`demos-check`/`demos-prepare` always bypass this discovery.
The default `make player-run` now selects the complete My Cyganie demo.
Space pauses, Left/Right seek five seconds, N skips to the next scene, Home
restarts, V toggles the PC movie panel, and Escape quits. Normal exit restores
the retained standalone show. Full driver/clock/retention limits are in
[the player guide](../host/player/README.txt).

## Quiet preparation and previews

```sh
make demos-check       # native five-node simulation, frame exports, contact sheets
make demos-prepare     # also encode complete, silent video/simulator previews
```

Both commands stay offline: no PortAudio playback, live window or physical UART.
They analyze files and run the actual C firmware packet/queue/render simulation.
The preview MP4 files have no audio stream and are not opened automatically.

Generated artifacts are under `build/player/complete-demos/`. Each demo has:

- `silent-preview.mp4`: normal PC video above the exact LED frames, covering the whole show.
- `timeline.png`: two source-time samples from every scene.
- `frames.bin`: every native 0–100% PWM frame, exported at 12 fps.
- `simulation.json`: the result of comparing every frame with all five C firmware nodes.
- `preparation.json`: recording/binary/cue hashes, full coverage checks and artifact paths.

The combined report is `build/player/complete-demos/summary.json`.
Preparations are cached against exact binary, cue, audio and video hashes.
Native `--check --frames FILE` is the underlying export command; `--frames`
requires `--check` and cannot be combined with a physical port.

## Musical choices and limits

My Cyganie uses five whole-canvas dance renderers: butterfly-like pairs,
opposing claps, turning skirts, embroidered flowers and interlocking textile
patterns. Area-sampled edges and separate bass/treble envelopes produce smooth
PWM. A show-specific brightness curve lifts low levels for the user's current
low-current v3.1 setup. Source-time pulse anchors follow the fast verses and
slower, accelerating refrains. Movement and bass accents share this timing map.
The reusable rhythm map, grid/bass/treble clocks and output curve are documented
in the player guide. The previous arrangement and spring/accordion renderer stay
available alongside the original PWM showcases.

Adagio's low-frequency energy falls substantially after its opening and returns
near 129 seconds; its cue sheet follows that contrast. Tubular Bells uses a longer
artistic arc before its instrument theatre. The spoken-announcement times and
short My Cyganie refrain cues use the existing local recognition draft. They
are approximate editorial placements, not a verified score or exact lyric
transcription; no new vocals are synthesized and music is not time-stretched.

Instrument scenes normalize against the current spectral peak with a noise floor,
so quiet piano notes remain distinct from idle keys instead of disappearing under
the later full-track peak. A quiet-note frequency-position regression covers this.

The native tests cover cue parameter bounds, exact crossfade blending, whole-canvas
mirroring, PC-only labels, FFT/pulse response, offline frame export and the
existing wire/audio/video paths. Full preparation checks require continuous scene
coverage, exact recording identities/durations, 0–100 pixel bounds, no unintended
blackout longer than five seconds, full firmware pixel comparisons, and a silent
preview with the correct complete duration. Optical timing, audible alignment
and aesthetic response on the physical chain were deliberately not tested during
this quiet preparation.

## Prepared evidence

The complete run compares **24,726 frames** with the real five-node C firmware.
All three timelines and silent previews were inspected offline. Native tests,
nine CLI tests, four word-tool tests and ASan/UBSan passed after the final rendering
changes. The authored timelines contain 18, 33 and 14 scenes respectively.
`build/player/complete-demos/completion-audit.json` binds the exact binary, source,
recordings, cue sheets, frame exports, silent videos and simulation reports.
Its adjacent `source.tar.gz` preserves the prepared source without bundling music.

Silent previews, for opening later:

- [My Cyganie](../build/player/complete-demos/my-cyganie/silent-preview.mp4)
- [Tubular Bells](../build/player/complete-demos/tubular-bells/silent-preview.mp4)
- [Adagio](../build/player/complete-demos/adagio/silent-preview.mp4)

The later automatic-connection repair is verified separately in
`build/player/auto-connect-tests.log`, `auto-connect-live-inspect.log` and
`auto-connect-recovery.json`. The original preparation audit remains a snapshot
of the rendered show sources; the connection repair does not change their
animation or music timelines.

## My Cyganie rework

The current `my-cyganie-full.json` is version2, titled “Stepping together”. Its
18 scenes cover the full recording. It uses only `dance-*` geometry, with PC-only
video and the existing short refrain captions. Local analysis evidence is in
`build/my-cyganie-rework/analysis-report.txt`; the earlier complete-demo audit
above describes the prior arrangement. Fresh frame comparisons and previews use
the same `prepare_demo_previews.py --only my-cyganie` workflow and output folder.

Rework validation: all3437 frames passed the full five-node firmware simulation;
the54-second live PC preview delivered649 frames with zero skips/late uploads/
audio warnings. A65-second physical service-launched run delivered780 frames at
12fps with zero skips/late uploads/audio warnings and37 recovered ACK retries.
All five boards had zero added UART errors/drops/late frames; the service
reconnected at115200 and their102-byte RAM program lengths were unchanged.
No firmware/options were written. Optical/audio alignment was not instrumentally
measured. Player tests and dance ASan/UBSan passed; complete Tubular Bells and
Adagio frame exports match their earlier exports byte-for-byte. Evidence and
source hashes: `build/my-cyganie-rework/completion-audit.json`.

Video smoothness follow-up: UART uploads/clock-sync now run as a single serialized
asynchronous job, independent of the PC draw loop. A30-second physical run
measured60.9 preview draws/s with an18ms maximum gap; the360 LED frames remained
at12fps with zero skips/late uploads/audio warnings and17 recovered ACK retries.
All five node error/drop/late counters were unchanged. These are UI cadence
measurements, not source-video FPS or measured optical synchronization.
Dance brightness accents now decay faster and have a32% silhouette floor;
synthetic tests require fresh-hit light to exceed twice the settled frame.
Evidence: `build/my-cyganie-rework/video-playback.json` and `video-tests.log`.

## Low-current v3.1 arrangement

User feedback selected the butterfly-like opening, claps and refrain text.
The active My Cyganie cue sheet now replaces the spring/accordion with turning
skirts and embroidered flowers. The accordion renderer and the previous
`config/player/my-cyganie-stepping-v2.json` preset remain reusable.

The user reports low PWM levels are hard to see on the current low-currentv3.1
configuration. A show-specific output_gamma0.5 lifts these levels, preserving
black and full scale. This does not alter firmware or current limits. The user subsequently confirmed
improved visibility; the two other active shows now use the same output curve.

Refrains initially slow, then accelerate: local pulse intervals evolve from
roughly0.7s toward0.4s, and the final passage reaches about0.34s. The former bass
event counter could follow extra notes instead of the musical pulse. The new
piecewise source-time anchors drive both movement and bass light accents;
measured bass energy controls strength. Anchors were fitted to the recording,
not manually verified as musical downbeats. Strong spectral peaks agree within
20ms median/40ms90th-percentile in the analysis; this supports timing but is not
an optical or perceptual synchronization measurement. Candidate evidence:
`build/my-cyganie-rework/slow-pulse-candidates.json` and `slow-pulse-notes.txt`.

The user confirmed both visibility and slower-section synchronization improved.
My Cyganie's title now overlays the first8seconds of the actual song/video;
intro_seconds is0, removing the silent lead-in. Its total duration is4:38.338.
The older preserved preset retains its original introduction.

## Independent Tubular Bells and Adagio arrangements

Both active cue sheets now use their own motif families, with full source-time
coverage, output_gamma0.5 and title/video/audio starting together. Earlier
arrangements remain as separate presets, and their renderers are still usable.
Tubular retains the spoken instrument captions and theatre at1188.9seconds
onward. The earlier recognition timings remain approximate editorial placements.
New register-specific note attacks drive its mechanical motifs; no single
constant beat grid is imposed on the live performance.

Adagio's jointly fitted pulse grid spans its opening and return after129seconds.
From30 to129seconds, bows and architectural arches follow sustained midrange
energy instead of pulsing to an absent kick. Evidence for these choices is in
`build/song-rework/analysis-report.txt` and `section-evidence.json`.

Tubular's new string instruments use sparse outlines, dark sound holes and
separated strings, with per-register highlights. The two guitar halves respond
independently. Old theatre renderers remain available in the v1 preset. The
recording's near-silent tail is explicitly black from1539seconds; preview
validation exempts declared zero-level scenes, not an arbitrary trailing window.

Validation for this revision: `make player-test` and four preview-blackout tests
passed. Complete five-node C-firmware simulations covered18580Tubular frames
and2469Adagio frames, with rendered scene contact sheets and full silent videos
under `build/player/complete-demos/`. The longest undeclared dark runs were
1.583s and0.083s respectively. The existing My Cyganie full frame export was
byte-identical after the shared per-register analysis addition. Unit checks
cover silence, dynamics, source-time seeking and independent register responses.

Bounded physical playback covered Tubular0–18s and1260–1278s plus
Adagio120–145s:732frames, zero late/skipped frames, zero audio warnings,
about59.7–60.2preview draws/s, and maximum draw gaps18–20ms. Transport
reported11/6/16retries respectively; no invalid replies or increases in any
board's error/drop/late counters. All five102-byte RAM programs remained
loaded and the service connection was restored. Reports and before/after
status are in `build/song-rework/`. Full-length physical playback and optical
synchronization measurement were not performed. No firmware was flashed.

## L’Amour Toujours — together in light (2026-10-18)

Source: Gigi D’Agostino’s official video, YouTube `w15oWDh02K4`, downloaded
with the existing yt-dlp Python archive. Local video/audio stay ignored under
`build/media/lamour-toujours/`; the cue sheet pins the decoded FLAC hash and
native 242.493-second duration. The title starts with audio/video.

Three new reusable renderers in `host/player/lamour.cpp` focus on the theme and
beat. `lamour-theme` shows eight recent half-beat upper-mid register samples,
with a four-beat row of footlights. This is an approximate spectral contour,
not a separated melody or note transcription. `lamour-wings` opens two large
paired shapes; `lamour-floor` alternates six chevrons across the complete chain.
Measured bass energy controls the pulse strength, preserving the softer intro
and break. A 139.06 BPM fit with 0.3035-second offset follows the strong pulses;
section-wise phase estimates over32–232seconds differ by roughly3ms. This is
analysis evidence, not an optical timing measurement or confirmed bar alignment.

The full simulation covers2910frames and15scenes; contact sheet and silent
preview are in `build/player/complete-demos/lamour-toujours/`. Native player,
preview-blackout and isolated Unix-socket service tests passed. The socket tests
require execution outside the restricted sandbox; no physical UART is used.
No firmware changes or flashes are needed. Launch with `make demo-lamour-toujours`
or select L’Amour Toujours in Studio’s music/video list after the broker refresh.

The previous My Cyganie full export remained byte-identical. This new show has
not yet been physically played. At handoff, the existing Adagio player was left
open; the rebuilt broker catalog becomes active after `systemctl --user restart
letkid.service` once that playback is closed. Studio refreshes the catalog itself.

GUI catalog correction: the original Studio still hard-coded three music rows,
so restarting the broker alone did not expose the fourth show. Studio now builds
rows and playback IDs dynamically from `music_catalog`, including updated
recording descriptions. The rebuilt app was opened on Demo and all four entries,
including L’Amour Toujours with its enabled Play button, were visually verified.


## Laskowski × 2Pac — wielkie pojednanie (2026-10-18)

The user requested the absurd fusion of styles with theatrical pathos. The
Nospe Epson mashup (`LaXazWRppwI`) joins Janusz Laskowski’s “Świat nie wierzy
łzom” and 2Pac’s “Baby Don’t Cry”. Its accompanying video stays on the PC.
The tile show is an editorial comic interpretation, not a literal reconstruction
of the video: a solemn duet exchanging hats, a lowrider towing a wedding cake,
a boombox wearing a bow tie, a monumental tear between curtains/spotlights,
and a ceremonial toast. Short location/title/punchline captions leave most of
the timeline to the silhouettes. New styles are reusable `fusion-*` renderers.

Measured pulse fit is91.44BPM with0.2768s offset. Twenty-second phase estimates
range0.2619–0.2968s across the active recording; these support a stable beat grid,
not verified bars or optical synchronization. Beat accents and movement use the
source-time grid; FFT mids and audio RMS modulate brightness/visibility. The
cue sheet uses the low-current output_gamma0.5 profile. Native duration and audio
hash are pinned; the long near-silent video tail has an explicit blackout from294s.
Evidence and analysis are under `build/fusion-demo/`; media remain ignored.

Full validation passed:3677frames against the actual five-node C firmware
simulation,17continuous scenes,0..100PWM and at most1s of undeclared darkness.
Native player tests include the five fusion motifs, silence, beat contrast,
seek determinism and hat exchange. All13isolated service tests passed, including
the five-entry catalog. The complete contact sheet was visually inspected.
No physical playback/optical validation is claimed. The running Tubular Bells
session was preserved; activate the rebuilt catalog by restarting letkid after
closing the player. The existing dynamic Studio list will pick it up automatically.
