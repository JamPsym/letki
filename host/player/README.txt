Letki native music engine (C++17)
================================

Build from the repository root:
    make player
    make player-test
    make player-sanitize

Linux dependencies: C/C++ compiler, make, pkg-config, PortAudio, libsndfile,
SDL2, json-c, FFmpeg libraries and psmisc/fuser. All are installed on the development machine.
Arch package names: base-devel pkgconf portaudio libsndfile sdl2 json-c ffmpeg psmisc.
No Python interpreter is used by the player. The simulator is the existing C
firmware core, loaded from build/general/libletki-general.so. Python is used only
by some CLI tests and existing asset-generation tools.

Force a PC-only five-tile preview (PC speakers + simulated UART/firmware):
    build/player/letki-player --show config/player/my-cyganie-full.json --simulate
    build/player/letki-player --show config/player/tubular-bells-full.json --simulate
    build/player/letki-player --show config/player/adagio-full.json --simulate

Use the same engine and frames on the physical chain:
    build/player/letki-player --show config/player/my-cyganie-full.json \
      --port /dev/serial/by-id/usb-wch.cn_WCH-Link_02858F0687B7-if01

At startup, the player automatically finds a WCH-Link serial adapter and verifies
all five Letki nodes. With no adapter, it clearly selects PC simulation. Use
--simulate to force PC-only playback, or --port PATH to choose an adapter. Multiple
adapters require --port; busy or incompatible adapters report an error rather
than silently playing only on the PC. Close picocom first. fuser, flock and
TIOCEXCL guard against another serial reader. Identify without playback using
--inspect (automatic) or --port PATH --inspect. After missing startup replies,
the player waits once for the10-second high-baud lease to expire and retries;
Ctrl+C cancels that wait. No SWIO, application flash, option
bytes or programmer power changes are involved. Saved programs are never
uploaded/erased by this engine; it pauses them and allocates volatile frame
slots from actual advertised free RAM. On normal exit/Ctrl+C the queue is cleared,
two LEVEL8 slots restored when space permits, and the retained program restarts
from position zero with its own loop setting and fresh I2C clocks. With stale
I2C, standalone restoration reports an error rather than claiming synchronization.
Each device high-baud idle lease falls back to 115200 after 10 seconds without
addressed traffic. Abrupt SIGKILL cannot run normal display/tty cleanup.

Recordings
----------
The default preset is my-cyganie-full: a complete18-scene arrangement using new
butterfly-like pairs, opposing claps, turning skirts, embroidered flowers and
diagonal woven patterns. The movie
is shown only on the PC. All three full demos and quiet preparation commands:
docs/music-demos.md.
The local presets reference the user-supplied media under ignored build/media/:
- My Cyganie / Ore ore — Don Vasyl, 278.338 seconds.
- Tubular Bells — Mike Oldfield, BBC live 1973, 1548.307 seconds.
- Adagio for Strings — Tiesto, 205.729 seconds.

Media files are not source assets or bundled redistributable recordings. Override
any preset with --audio /absolute/path/to/recording.flac. WAV/FLAC/MP3 and other
formats depend on the installed libsndfile; errors name the unsupported file.
The built-in bell-demo preset uses the earlier locally generated original score
and narration in build/pwm-show/audio/score.wav. Generate that optional asset via
.tools/native-tts/bin/python scripts/pwm_show_audio.py --prepare-only. This score
is distinct from Mike Oldfield's recording.

Controls and testing
--------------------
Space pauses/resumes, Left/Right seek five seconds, Home restarts, Escape quits.
V toggles the PC video panel. N or ] skips to the next instrument/effect cue.
A seek restarts the decoder and schedules a half-second silent pre-roll before
resuming. --seek SECONDS starts at an absolute show time (including introduction).
--seconds SECONDS limits wall time, useful for short hardware tests.
--headless hides the preview. --silent uses a steady clock without audio output.
Neither disables hardware discovery: use --simulate for a PC-only run.
--check and --analyze always bypass discovery and physical UART.
--fps defaults to12; allowed1..25. LEVEL8 (full0..100) is the default;
--format gray4 uses16perceptual levels and higher throughput. 230400baud defaults to the qualified R3 rate;
--baud115200 is supported but may require a lower FPS. The engine deliberately
does not enable the previously failing460800/untested921600 rates.

A full accelerated simulation does not open audio/video/serial hardware:
    build/player/letki-player --show config/player/tubular-bells-full.json --check

This renders the actual recording's features across its complete timeline and
passes every selected-format frame through the real C firmware's packet/router/node/queue
path, then compares all320 resulting pixels. --check --port is rejected. These
checks validate software, not physical optical/audio skew.

Editing a show
--------------
JSON paths are relative to the JSON file; --audio paths are relative to cwd.
name, title and artist describe the introduction. intro_seconds adds silence
before the recording starts, with a scrolling title across all five tiles.
gain0..1 scales playback. visual_offset_ms (-2000..2000) adjusts visual time
against audio for manual latency calibration; positive advances the animation.

style: music-ribbon and music-ripple preserve the first two original demo
shapes with bass-hit motion bursts and strong PWM attack/release pulses,
plus small treble highlights; piano, organ, mallets, bass-guitar, guitar, guitar-fast, guitar-duo,
mandolin, tubular-bells (instrument theatre); ribbons (music-driven full-width ribbons), bells (reactive
ripples/chimes), strings (flowing arches), bars (reactive
levels), pwm (original six-scene demo), ribbon, ripple, embers, lanterns, ladder,
daisy. The last six reuse the tested original C geometry. bells/strings/bars use
a50Hz radix-2 Hann-window FFT with24logarithmic bands, smoothed envelopes and
separate low/high spectral-flux attack events. Bass swells/brightens the ribbon,
mids bend it, and treble lights the thinner strand. This is not score transcription
or a promise of perfect beat/downbeat detection. Full-track normalization is
repeatable. Every frame is evaluated at absolute audio time, so seeks do not
require replaying past animation state. Polish compact glyphs are shared with
firmware; captions use uppercase Latin/Polish letters and spaces.

Full authored shows may set transition_seconds0..5 for smooth scene changes.
Effect cues accept level0..1, speed0.1..3, sustain0..1 and variant0..3
(horizontal/vertical mirroring bits). sustain applies to music-ribbon,
music-ripple, music-lanterns and music-daisy; it retains a visible moving body
between bass-hit pulses. label is a PC-only scene title. Captions stay separate.

Optional cues use recording-relative seconds (the intro is excluded):
    {"at":30,"duration":7,"text":"TUBULAR BELLS","effect":"daisy"}
The caption scrolls once over its interval, with dimmed background. Omit text
for an effect-only interval. Later overlapping cues take precedence for effect
selection; text cues overlay in chronological order. Cues are configurable,
not word alignment or claims about the instruments in the BBC performance.

Synchronization and resources
-----------------------------
PortAudio's outputBufferDacTime and Pa_GetStreamTime use the same audio clock.
The callback publishes sample position and presentation timestamp through
lock-free atomics. It performs no allocation, file access, UART I/O or locks.
A decoder thread supplies a65536-frame stereo ring (512KiB); long files are not
loaded into RAM. File analysis stores compact features every20ms (roughly12MB for the26-minute
BBC recording, depending on the native struct layout). Supported audio is mono/stereo,
8..192kHz, up to6hours. Playback does not time-stretch or resynthesize music.

The foreground sends future LEVEL8 or GRAY4 frames, pipelined across five addressed nodes.
Each request has CRC/COBS, cached idempotent retry IDs, bounded timeouts and a
random session. Three TIME samples/node select minimum RTT; timestamps account
for modulo32-bit device clocks. A one-second UART clock check detects substantial
offset jumps, flushes queued frames and reanchors the next ones. Shared-I2C age
is reported separately: raw frames use their own UART-derived clock mapping.
Typical lookahead is650ms, bounded by actual queue slots. If an active RAM
program leaves few slots, the player lowers FPS to retain at least250ms of
lookahead; it does not discard the program to gain RAM. Expired frames are
skipped rather than building an ever-growing backlog. No cross-tile atomic
commit or optical timing measurement is claimed. USB scheduling, asymmetric
UART delays, scan phase and audio backend timestamp accuracy remain limits.

Each run writes bounded aggregate telemetry to build/player/last-run.json, or
--report FILE: frames, skipped frames, late uploads, audio warnings, retries,
invalid replies, selected clock/mode and retention. Tests include wire golden
vectors, corruption/lost replies, clock jumps, two virtual hours/request wrap, FFT frequency separation and synthetic
bass/treble attacks, default-ribbon brightness response,
real POSIX PTY coalesced replies/exclusivity/settings restoration, production
audio callback with deterministic fake DAC, gain, pre-roll, seeks and EOF, plus
full-show C firmware/pixel checks. Physical evidence is recorded separately.

Primary API references:
https://files.portaudio.com/docs/v19-doxydocs/structPaStreamCallbackTimeInfo.html
https://portaudio.com/docs/v19-doxydocs-dev/api_overview.html
https://wiki.libsdl.org/SDL2/SDL_PollEvent

Video scenes
------------
    build/player/letki-player --show config/player/my-cyganie-video.json
    build/player/letki-player --show config/player/adagio-video.json
    build/player/letki-player --show config/player/tubular-bells-video.json

--video FILE adds or overrides the full-color movie shown on the PC above the
five-tile simulator. It follows the audio clock and supports pause/seek. Video
never supplies LED pixels, textures, shadows or brightness: UART frames depend
only on the procedural animation, music features and text cues. V hides/shows
the PC movie. There are no video-to-LED modes.

FFmpeg scales video proportionally to at most960x540 RGB with a four-frame
cache. The PC preview is capped at30fps. Short videos loop against absolute
audio time. Decoding stays outside the audio callback. --headless skips video.

Complete My Cyganie show with video on the PC only:
    build/player/letki-player --show config/player/my-cyganie-full.json

Instrument theatre prototype:
    build/player/letki-player --show config/player/tubular-theatre.json --seek1194

This starts just before the BBC recording's instrument announcements. Piano
keys, organ pipes, mallets, guitars, mandolin and hanging bells use distinct
shapes across the display with music-driven PWM. N advances to the next cue.
Announcement labels/times are a draft from local recognition, not a verified
transcription. Repeated shapes are allowed when they help the design read.

Replay the original six-scene PWM demo with its original music/narration:
    build/player/letki-player --show config/player/original-pwm.json
Add --port as above to stream the same frames to the five physical boards.
This preset omits text overlays so the original shapes remain unobstructed.

Word/caption authoring
---------------------
See docs/player-word-tools.txt for local Whisper extraction, timestamp search,
audio audition clips, SRT/CSV exports and conversion to centered/scrolling cues.
Source-audio SHA256 is checked before exporting a derived show. Recognition
confidence and review flags remain in the transcript. The BBC announcement
section and the Polish My Cyganie recording were actually processed; some
instrument names are misrecognized, so generated captions remain reviewable.

Verification record
-------------------
See docs/native-player-20261017.txt and build/player/summary.json for the final
native source fingerprint, complete recording simulations, short physical
synchronization checks, saved-program retention and validation limits.

Musical choreography clocks
---------------------------
The reusable dance-steps, dance-accordion, dance-clap and dance-weave styles
render the whole 40x8 canvas independently of the earlier PWM showcases. Broad
area-sampled shapes retain smooth 0..100 PWM edges at the default12fps. Bass and
treble attacks have source-time hold/release envelopes; quiet audio gates the
shapes down. Geometry and response are deterministic across seeking.

Optional rhythm object:
    "rhythm": {"bpm":160,"offset":0.07,
               "anchors":[{"at":0.07,"beat":0},{"at":36.07,"beat":96}]}
Times are recording-relative seconds. Without anchors, offset is beat zero.
One anchor uses bpm; multiple anchors interpolate continuous beat positions and
extrapolate the nearest segment outside their range. Time/beat must increase;
global and segment tempos must be30..300BPM. Anchors are authored pulse positions,
not automatically inferred musical downbeats.

Dance effect cues accept clock="grid" (default), "bass" or "treble". Grid uses
the shared rhythm map. Attack clocks advance smoothly after measured FFT events,
so irregular passages need no invented constant tempo. speed scales this phase;
brightness still responds independently to measured attack strength and RMS.
These clocks are evaluated at absolute audio source time, including after seeks.
My Cyganie uses measured160BPM verse pulse grids and locally tracked pulse
anchors through the slower refrains and their accelerations. Approximate short refrain captions remain editorial placements.

PC playback cadence
-------------------
The main thread draws video/preview at up to60Hz against the audio presentation
clock. One asynchronous transport job handles UART frames or clock sync, so
serial acknowledgement waits cannot stall normal movie playback. Jobs remain
serialized; pause/seek drains the current job before flushing the device queue.
Reports include preview_draws, preview_fps and preview_max_gap_ms (presentation
loop metrics, not a claim about source video FPS or optical timing).
Dance accents use a short attack hold followed by160ms bass/120ms treble decay;
a32% silhouette floor gives a stronger musical brightness range between hits.

Low-current output and reusable motifs
-------------------------------------
output_gamma (0.25..3, default1) remaps final0..100 host pixels. Values below1
lift dim levels while preserving black and full scale. My Cyganie uses0.5 for
the user's current low-current v3.1 configuration:10 ->32,25 ->50,50 ->71.
This is a host visibility adjustment, not an electrical calibration/current change.
Other shows keep their existing identity mapping.

My Cyganie v3 retains the butterfly-like dance-steps opening, claps and text;
dance-skirts and dance-flowers replace accordion scenes. The dance-accordion
renderer and config/player/my-cyganie-stepping-v2.json remain available for reuse.
Grid-clock dance scenes derive bass accent age from the
inverse Rhythm::time(beat) map, so movement and light follow the same measured
pulse even during tempo ramps. FFT energy still sets accent strength and treble
highlights. Bass/treble event clocks remain selectable for other arrangements.

Independent Adagio and Tubular arrangements
------------------------------------------
Adagio uses adagio-bows and adagio-vault for its sustained30..129s breakdown,
and adagio-shutters/adagio-prism around the beat-led sections. Its measured
source grid is141.723356BPM with beat-zero at0.192s. The breakdown's sustained
midrange drives the shapes; no artificial bass pulse is injected there.

Tubular uses bells-hammers, bells-gears, bells-weft and bells-monoliths to build
its mechanical score before the existing named instrument theatre. Current
spectral normalization keeps the quiet opening visible. The shared Media
analysis now exposes24 independent band_age/band_hit/band_count attack tracks,
with a local novelty threshold and140ms refractory time. These retain note
attacks at source-time ages for12fps playback and arbitrary seeking. They are
frequency-register features, not isolated instrument stems or a transcription.

Both shows use output_gamma0.5 for low-current visibility, PC-only video and a
title overlay starting with the recording (intro_seconds0). Previous full
arrangements remain in config/player/{adagio,tubular-bells}-arrangement-v1.json.

Sparse Tubular strings: bells-guitar, bells-bass, bells-mandolin and bells-duet
retain dark space under the low-current brightness curve. Highlights follow
register attacks; duet halves use independent frequency registers.

L'Amour Toujours: config/player/lamour-toujours-full.json (make demo-lamour-toujours).
lamour-theme samples eight half-beat upper-mid registers for a melodic contour;
lamour-wings and lamour-floor share its measured pulse. All are stateless and
seek-safe. Contour extraction is not isolated lead-note transcription. The
complete local recording is pinned by hash; video stays on the PC.

Laskowski x 2Pac: config/player/laskowski-2pac-full.json; make demo-laskowski-2pac.
The fusion-duet/ride/radio/drama/toast styles use a source-time pulse, measured
midrange levels and a silence gate. Motifs deliberately mix wedding ceremony,
West Coast imagery and exaggerated theatrical pathos. Test: test-fusion in the
normal make player-test suite. Media and full previews remain ignored.
