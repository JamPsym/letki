// Deterministic PortAudio harness: execute the production callback, decoder
// thread and ring without opening an audio device. The real DAC is tested
// apart.
#include "player.hpp"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <portaudio.h>
#include <thread>
static PaStreamCallback *callback = nullptr;
static void *context = nullptr;
static double clock_now = 0, rate = 16000;
static bool active = false;
static float peak = 0;
static void pump(unsigned frames = 512) {
  float output[4096]{};
  assert(frames <= 2048);
  PaStreamCallbackTimeInfo time{0, clock_now, clock_now + .08};
  int status = callback(nullptr, output, frames, &time, 0, context);
  for (unsigned i = 0; i < frames * 2; i++) {
    assert(std::isfinite(output[i]));
    peak = std::max(peak, std::abs(output[i]));
  }
  clock_now += frames / rate;
  if (status != paContinue)
    active = false;
  std::this_thread::sleep_for(std::chrono::milliseconds(1));
}
extern "C" {
PaError Pa_Initialize() { return paNoError; }
PaError Pa_Terminate() { return paNoError; }
const char *Pa_GetErrorText(PaError) { return "mock error"; }
PaDeviceIndex Pa_GetDefaultOutputDevice() { return 0; }
PaError Pa_OpenStream(PaStream **stream, const PaStreamParameters *,
                      const PaStreamParameters *, double sample_rate,
                      unsigned long, PaStreamFlags, PaStreamCallback *cb,
                      void *data) {
  *stream = reinterpret_cast<PaStream *>(1);
  callback = cb;
  context = data;
  rate = sample_rate;
  clock_now = 0;
  return paNoError;
}
PaError Pa_StartStream(PaStream *) {
  active = true;
  pump();
  return paNoError;
}
PaError Pa_AbortStream(PaStream *) {
  active = false;
  return paNoError;
}
PaError Pa_CloseStream(PaStream *) { return paNoError; }
PaError Pa_IsStreamActive(PaStream *) { return active; }
PaTime Pa_GetStreamTime(PaStream *) { return clock_now; }
}
int main() {
  letki::Media media("build/player/test-tone.wav");
  letki::Audio audio(media, .25, .5);
  audio.start();
  assert(audio.position() == 0);
  // Half-second pre-roll, then a quarter-second introduction: all silence.
  for (int i = 0; i < 20; i++) {
    pump();
    assert(audio.position() >= 0 && audio.position() < .25);
  }
  assert(peak == 0);
  double previous = audio.position();
  for (int i = 0; i < 35 && active; i++) {
    pump();
    double position = audio.position();
    assert(position + 1e-9 >= previous);
    previous = position;
  }
  assert(peak > .1 && peak <= .251);
  assert(audio.underruns() == 0);
  assert(!active);
  audio.stop();
  audio.start(.8);
  assert(std::abs(audio.position() - .8) < 1e-8);
  peak = 0;
  for (int i = 0; i < 40 && active; i++)
    pump();
  assert(peak > .1 && audio.underruns() == 0);
  audio.stop();
  // Starting within the last block must drain exactly once and terminate.
  audio.start(1.249);
  for (int i = 0; i < 25 && active; i++)
    pump();
  assert(!active);
  audio.stop();
  std::cout << "Native audio: production callback pre-roll, silent title, "
               "gain, sample clock, ring, seek and EOF passed.\n";
}
