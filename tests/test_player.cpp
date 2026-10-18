#include "player.hpp"
#include "lamour.hpp"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <pty.h>
#include <set>
#include <sndfile.h>
#include <stdexcept>
#include <termios.h>
#include <thread>
#include <unistd.h>
using namespace letki;
namespace {
struct Faults : Transport {
  std::unique_ptr<Transport> inner = simulation();
  unsigned drops = 0;
  bool drop = false, corrupt = false, persistent_write = false;
  int jump = 0;
  bool simulated() const override { return true; }
  void rate(unsigned b) override { inner->rate(b); }
  void advance(uint64_t t) override { inner->advance(t); }
  Frame pixels() override { return inner->pixels(); }
  std::vector<Bytes> exchange(const std::vector<Bytes> &qs,
                              int timeout) override {
    for (auto &wire : qs) {
      auto op = decode(wire).op;
      if (op >= 4 && op <= 6)
        persistent_write = true;
    }
    auto replies = inner->exchange(qs, timeout);
    if (drop) {
      drop = false;
      drops++;
      return {};
    }
    if (corrupt && !replies.empty()) {
      corrupt = false;
      replies[0][4] ^= 128;
    }
    if (jump)
      for (auto &wire : replies) {
        auto m = decode(wire);
        if (m.op == (3 | 128) && m.data.size() == 11) {
          uint32_t t = get32(m.data, 1) + jump;
          for (unsigned i = 0; i < 4; i++)
            m.data[1 + i] = uint8_t(t >> (8 * i));
          wire = encode(m);
        }
      }
    return replies;
  }
};
void throws(const std::function<void()> &f) {
  bool threw = false;
  try {
    f();
  } catch (const std::exception &) {
    threw = true;
  }
  assert(threw);
}
void write_show(const std::string &text) {
  std::ofstream("build/player/test-show.json") << text;
}
} // namespace
int main() {
  write_show(R"({"name":"dance","style":"dance-steps","rhythm":{"bpm":160,"anchors":[{"at":1,"beat":0},{"at":4,"beat":8}]},"cues":[{"effect":"dance-clap","clock":"bass"}]})");
  auto dance_show = Show::load("build/player/test-show.json");
  assert(dance_show.rhythm.position(2.5) == 4);
  assert(dance_show.cues.front().clock == "bass");
  for (const auto *invalid : {
      R"({"name":"bad","rhythm":{"anchors":[{"at":2,"beat":0},{"at":1,"beat":2}]}})",
      R"({"name":"bad","rhythm":{"anchors":[{"at":0}]}})",
      R"({"name":"bad","rhythm":{"bpm":0}})",
      R"({"name":"bad","cues":[{"clock":"unknown"}]})"}) {
    write_show(invalid);
    throws([] { Show::load("build/player/test-show.json"); });
  }

  // Discover only matching adapters, ignore stale/unrelated links, collapse
  // aliases of one device, and require explicit selection for multiple devices.
  char directory[] = "/tmp/letki-discovery-XXXXXX";
  assert(mkdtemp(directory));
  auto fixture = std::filesystem::path(directory);
  assert(discover_serial((fixture / "missing").string()).empty());
  std::ofstream(fixture / "tty-one") << "fixture";
  std::ofstream(fixture / "tty-two") << "fixture";
  std::filesystem::create_symlink(fixture / "tty-one",
                                  fixture / "usb-unrelated");
  std::filesystem::create_symlink(fixture / "gone",
                                  fixture / "usb-WCH-Link-stale");
  assert(discover_serial(directory).empty());
  std::filesystem::create_symlink(fixture / "tty-one",
                                  fixture / "usb-WCH-Link-one");
  assert(discover_serial(directory) == (fixture / "usb-WCH-Link-one").string());
  std::filesystem::create_symlink(fixture / "tty-one",
                                  fixture / "usb-WCH-Link-alias");
  assert(discover_serial(directory) ==
         (fixture / "usb-WCH-Link-alias").string());
  std::filesystem::create_symlink(fixture / "tty-two",
                                  fixture / "usb-WCH-Link-two");
  throws([&] { discover_serial(directory); });
  std::filesystem::remove_all(fixture);
  Message q{3, 1, 0x1234, 0x5678, {0, 255}};
  Bytes golden{9, 1, 1, 3, 0x34, 0x12, 0x78, 0x56, 2, 4, 255, 0x3c, 0x99, 0};
  assert(encode(q) == golden);
  auto r = decode(golden);
  assert(r.data == q.data && r.request == q.request);
  for (unsigned n = 0; n <= 48; n++) {
    q.data.resize(n);
    for (unsigned i = 0; i < n; i++)
      q.data[i] = uint8_t(i % 4 ? i : 0);
    assert(decode(encode(q)).data == q.data);
  }
  golden[3] ^= 1;
  throws([&] { decode(golden); });
  throws([&] { decode({0}); });
  auto transport = std::make_unique<Faults>();
  auto f = transport.get();
  Chain chain(std::move(transport));
  f->drop = true;
  auto s = chain.request(0, 2);
  assert(s.size() == 47 && chain.retries == 1 && f->drops == 1);
  f->corrupt = true;
  chain.request(0, 2);
  assert(chain.invalid == 1 && chain.retries == 2);
  f->jump = 500;
  assert(chain.sync());
  f->jump = 0;
  assert(chain.sync());
  chain.prepare();
  assert(chain.slots >= 2);
  Frame frame;
  for (unsigned t = 0; t < 5; t++)
    for (unsigned p = 0; p < 64; p++)
      frame[t][p] = (p + t * 7) % 101;
  uint64_t when = monotonic_ms() + 1000;
  chain.frame(frame, when);
  auto actual = chain.pixels(when);
  for (unsigned t = 0; t < 5; t++)
    for (unsigned p = 0; p < 64; p++)
      assert(actual[t][p] == ((frame[t][p] * 15 + 50) / 100) * 100 / 15);
  // Two-hour virtual show, including request/generation wrap, uses real node
  // queues.
  for (unsigned i = 0; i < 72000; i++) {
    when += 100;
    chain.frame(frame, when);
    chain.pixels(when);
  }
  assert(chain.frames == 72001);
  assert(!f->persistent_write);
  chain.format = 2;
  chain.prepare();
  chain.sync();
  when = monotonic_ms() + 1000;
  for (unsigned t = 0; t < 5; t++)
    for (unsigned p = 0; p < 64; p++)
      frame[t][p] = (p + t * 17) % 101;
  chain.frame(frame, when);
  uint64_t local_when = when;
  for (auto c : chain.clocks)
    local_when = std::max(local_when, uint64_t(when + c.offset));
  assert(chain.pixels(local_when) == frame);
  assert(!f->persistent_write);

  // Real POSIX tty path: coalesced replies, bounds, tty restoration and
  // exclusivity.
  int master, slave;
  char name[128];
  assert(openpty(&master, &slave, name, nullptr, nullptr) == 0);
  termios before, after;
  assert(tcgetattr(slave, &before) == 0);
  throws([&] { serial(name); });
  close(slave);
  auto tty = serial(name);
  throws([&] { serial(name); });
  std::thread peer([&] {
    uint8_t b[128];
    ssize_t count = read(master, b, sizeof b);
    assert(count > 0);
    Bytes replies(81, 0x55);
    replies.back() = 0;
    for (unsigned i = 0; i < 5; i++) {
      Message m{uint8_t(i), uint8_t(2 | 128), 111, 22, {0}};
      m.data.resize(48);
      auto wire = encode(m);
      replies.insert(replies.end(), wire.begin(), wire.end());
    }
    assert(write(master, replies.data(), replies.size()) ==
           ssize_t(replies.size()));
  });
  std::vector<Bytes> queries;
  for (unsigned i = 0; i < 5; i++)
    queries.push_back(encode({uint8_t(i), 2, 111, 22, {}}));
  auto replies = tty->exchange(queries, 1000);
  peer.join();
  assert(replies.size() == 5);
  tty.reset();
  slave = open(name, O_RDWR | O_NOCTTY);
  assert(slave >= 0);
  assert(tcgetattr(slave, &after) == 0);
  assert(before.c_iflag == after.c_iflag && before.c_oflag == after.c_oflag &&
         before.c_lflag == after.c_lflag && before.c_cflag == after.c_cflag);
  close(master);
  close(slave);
  SF_INFO info{};
  info.samplerate = 16000;
  info.channels = 1;
  info.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;
  SNDFILE *out = sf_open("build/player/test-tone.wav", SFM_WRITE, &info);
  assert(out);
  std::vector<float> samples(16000);
  for (unsigned i = 0; i < samples.size(); i++)
    samples[i] = float(.5 * std::sin(i * 2 * 3.141592653589793 * 440 / 16000));
  assert(sf_writef_float(out, samples.data(), samples.size()) == 16000);
  sf_close(out);
  Media media("build/player/test-tone.wav");
  assert(media.frames == 16000 && media.features.size() == 50);
  assert(media.feature(.5).rms > .8 && media.feature(-1).rms == 0 &&
         media.feature(2).rms == 0);
  info.frames = 0;
  out = sf_open("build/player/test-bands.wav", SFM_WRITE, &info);
  assert(out);
  samples.resize(32000);
  for (unsigned i = 0; i < samples.size(); i++)
    samples[i] = float(.4 * std::sin(i * 2 * 3.141592653589793 *
                                     (i < 16000 ? 110 : 4000) / 16000));
  assert(sf_writef_float(out, samples.data(), samples.size()) == 32000);
  sf_close(out);
  Media separate("build/player/test-bands.wav");
  auto bass = separate.feature(.5), treble = separate.feature(1.5);
  auto peak_band = [](const Feature &f, unsigned a, unsigned b) {
    return *std::max_element(f.bands.begin() + a, f.bands.begin() + b);
  };
  assert(peak_band(bass, 0, 6) > .8 && peak_band(treble, 0, 6) < .1);
  assert(peak_band(treble, 17, 24) > .8 && peak_band(bass, 17, 24) < .1);
  info.frames = 0;
  out = sf_open("build/player/test-events.wav", SFM_WRITE, &info);
  assert(out);
  samples.resize(35200);
  for (unsigned i = 0; i < samples.size(); i++) {
    double t = i / 16000., v = .025 * std::sin(2 * 3.141592653589793 * 440 * t);
    for (double at : {.4, .9, 1.4})
      if (t >= at && t < at + .2) {
        double dt = t - at;
        v += .7 * std::sin(2 * 3.141592653589793 * 80 * dt) *
             std::exp(-dt / .045) * std::min(1., dt / .004);
      }
    for (double at : {.65, 1.15, 1.65})
      if (t >= at && t < at + .12) {
        double dt = t - at;
        v += .4 * std::sin(2 * 3.141592653589793 * 4000 * dt) *
             std::exp(-dt / .025) * std::min(1., dt / .003);
      }
    samples[i] = float(v);
  }
  assert(sf_writef_float(out, samples.data(), samples.size()) == 35200);
  sf_close(out);
  Media events("build/player/test-events.wav");
  auto hit_near = [&](double at, bool high) {
    for (size_t i = 1; i < events.features.size(); i++) {
      auto &a = events.features[i - 1];
      auto &b = events.features[i];
      if ((high ? b.treble_count != a.treble_count
                : b.bass_count != a.bass_count) &&
          std::abs(i * .02 - at) < .08)
        return true;
    }
    return false;
  };
  for (double at : {.4, .9, 1.4})
    assert(hit_near(at, false));
  for (double at : {.65, 1.15, 1.65})
    assert(hit_near(at, true));
  auto register_hit_near = [&](double at, unsigned begin, unsigned end) {
    for (size_t i = 1; i < events.features.size(); ++i)
      if (std::abs(i * .02 - at) < .08)
        for (unsigned b = begin; b < end; ++b)
          if (events.features[i].band_count[b] > events.features[i - 1].band_count[b])
            return true;
    return false;
  };
  for (double at : {.4, .9, 1.4}) assert(register_hit_near(at, 0, 7));
  for (double at : {.65, 1.15, 1.65}) assert(register_hit_near(at, 17, 24));
  for (size_t i = 1; i < events.features.size(); ++i)
    for (unsigned b = 0; b < 24; ++b) {
      const auto &before = events.features[i-1], &after = events.features[i];
      assert(after.band_count[b] >= before.band_count[b]);
      assert(after.band_hit[b] >= 0 && after.band_hit[b] <= 1);
      if (after.band_count[b] && after.band_count[b] == before.band_count[b])
        assert(after.band_age[b] > before.band_age[b]);
    }
  Show musical;
  musical.name = "test";
  musical.style = "ribbons";
  musical.intro = 0;
  auto total_level = [](const Frame &f) {
    unsigned total = 0;
    for (auto &tile : f)
      for (auto p : tile)
        total += p;
    return total;
  };
  assert(total_level(render(musical, events, .44)) >
         total_level(render(musical, events, .3)) * 1.5);
  for (const auto &style : {"music-ribbon", "music-ripple"}) {
    auto reactive = musical;
    reactive.style = style;
    auto quiet = render(reactive, events, .3);
    auto attack = render(reactive, events, .44);
    assert(total_level(attack) > total_level(quiet) * 1.5);
    assert(attack[0] != attack[1]);
    for (auto &tile : attack)
      for (auto p : tile)
        assert(p <= 100);
  }
  auto spectrum = media.feature(.5);
  auto dominant =
      unsigned(std::max_element(spectrum.bands.begin(), spectrum.bands.end()) -
               spectrum.bands.begin());
  assert(dominant >= 8 && dominant <= 10);
  assert(spectrum.bands[0] < .1 && spectrum.bands[23] < .1);
  Show weird;
  weird.name = "test";
  weird.intro = 0;
  weird.style = "weird";
  auto shader_media = media;
  shader_media.frames *= 10;
  auto warped = render(weird, shader_media, .5);
  assert(warped[0] != warped[1] && warped[1] != warped[4]);
  std::set<unsigned> levels;
  for (auto &tile : warped)
    for (auto p : tile)
      levels.insert(p);
  assert(levels.size() > 12);
  Feature instrument;
  instrument.rms = .7;
  instrument.mids = .5;
  instrument.treble = .6;
  instrument.bass_hit = 1;
  instrument.treble_hit = 1;
  instrument.bass_age = .05;
  instrument.treble_age = .08;
  instrument.bass_count = 8;
  instrument.treble_count = 11;
  for (unsigned b = 0; b < 24; b++)
    instrument.bands[b] = float((b % 7) + 1) / 7;
  std::vector<Frame> scenes;
  for (const auto &style :
       {"piano", "organ", "mallets", "bass-guitar", "guitar", "guitar-fast",
        "guitar-duo", "mandolin", "tubular-bells"}) {
    auto frame = theatre(instrument, 3.17, style);
    unsigned sum = 0;
    for (auto &tile : frame)
      for (auto p : tile) {
        assert(p <= 100);
        sum += p;
      }
    assert(sum > 0);
    scenes.push_back(frame);
  }
  assert(scenes[0] != scenes[1] && scenes[1] != scenes[2] &&
         scenes[2] != scenes[8]);
  Feature quiet_note;
  quiet_note.rms = .04;
  quiet_note.bands[3] = .03;
  auto low_key = theatre(quiet_note, 1, "piano");
  quiet_note.bands[3] = 0;
  quiet_note.bands[15] = .03;
  auto high_key = theatre(quiet_note, 1, "piano");
  auto column_level = [](const Frame &frame, unsigned x) {
    unsigned total = 0;
    for (unsigned y = 0; y < 8; y++)
      total += frame[x / 8][y * 8 + x % 8];
    return total;
  };
  assert(column_level(low_key, 2) > column_level(high_key, 2) * 2);
  assert(column_level(high_key, 26) > column_level(low_key, 26) * 2);
  Show with_movie = musical;
  with_movie.video = "PC-only-file.mp4";
  assert(render(with_movie, events, .44) == render(musical, events, .44));
  // Crossfades blend the actual previous/current scenes at the same audio
  // instant. Labels are PC-only, and variation mirrors the complete canvas.
  auto constant = media;
  constant.frames = constant.rate * 10;
  constant.features.assign(500, instrument);
  Show base;
  base.name = "transition";
  base.intro = 0;
  base.style = "ribbon";
  auto linear = render(base, constant, 3);
  Show lifted = base;
  lifted.output_gamma = .5;
  auto visible = render(lifted, constant, 3);
  for (unsigned tile = 0; tile < 5; ++tile)
    for (unsigned px = 0; px < 64; ++px) {
      assert(visible[tile][px] == std::lround(10 * std::sqrt(linear[tile][px])));
      assert((visible[tile][px] == 0) == (linear[tile][px] == 0));
    }
  assert(render(lifted, constant, 10) == Frame{});
  Show pulse_show;
  pulse_show.name = "pulse clock";
  pulse_show.intro = 0;
  pulse_show.style = "dance-clap";
  auto extra_attacks = constant;
  for (auto &feature : extra_attacks.features) {
    feature.bass_count += 100;
    feature.bass_age = 0;
  }
  assert(render(pulse_show, constant, 3.25) == render(pulse_show, extra_attacks, 3.25));
  Show blended = base;
  blended.transition = 1;
  Cue next;
  next.at = 2;
  next.duration = 6;
  next.effect = "ripple";
  next.label = "next scene";
  next.level = .5;
  blended.cues.push_back(next);
  assert(render(blended, constant, 2) == render(base, constant, 2));
  Show target = base;
  target.style = "ripple";
  auto from = render(base, constant, 2.5);
  auto to = render(target, constant, 2.5);
  auto half = render(blended, constant, 2.5);
  for (unsigned tile = 0; tile < 5; tile++)
    for (unsigned p = 0; p < 64; p++)
      assert(half[tile][p] ==
             std::lround((from[tile][p] + std::lround(to[tile][p] * .5)) * .5));
  assert(caption(blended, 3) == "next scene");
  auto straight = render(blended, constant, 4);
  blended.cues[0].variant = 3;
  auto mirror = render(blended, constant, 4);
  for (unsigned y = 0; y < 8; y++)
    for (unsigned x = 0; x < 40; x++)
      assert(mirror[x / 8][y * 8 + x % 8] ==
             straight[(39 - x) / 8][(7 - y) * 8 + (39 - x) % 8]);
  for (auto style : {"music-lanterns", "music-daisy"}) {
    base.style = style;
    auto f = render(base, constant, 3);
    assert(total_level(f) > 0);
    for (auto &tile : f)
      for (auto p : tile)
        assert(p <= 100);
  }
  // New song motifs are seek-safe, silent with no signal, and follow both
  // primary pulse and the melody register rather than an unrelated animation.
  auto song = constant;
  for (auto &a : song.features) {
    a.rms = .5; a.bass = .6; a.mids = .5;
    a.bands.fill(.08); a.bands[9] = .8;
  }
  Rhythm song_rhythm; song_rhythm.bpm = 120;
  std::set<Frame> song_shapes;
  for (auto style : {"lamour-theme", "lamour-wings", "lamour-floor"}) {
    auto hit = lamour(song, song_rhythm, 4, style);
    assert(hit == lamour(song, song_rhythm, 4, style));
    assert(total_level(hit) > total_level(lamour(song, song_rhythm, 4.4, style)) * 1.25);
    assert(lamour(song, song_rhythm, -1, style) == Frame{});
    assert(lamour(song, song_rhythm, 10, style) == Frame{});
    assert(hit[0] != hit[1] || hit[1] != hit[2]);
    song_shapes.insert(hit);
    for (const auto &tile : hit) for (auto v : tile) assert(v <= 100);
  }
  assert(song_shapes.size() == 3);
  auto lower = lamour(song, song_rhythm, 4, "lamour-theme");
  for (auto &a : song.features) { a.bands[9] = .08; a.bands[14] = .8; }
  assert(lower != lamour(song, song_rhythm, 4, "lamour-theme"));
  for (auto &a : song.features) a = {};
  for (auto style : {"lamour-theme", "lamour-wings", "lamour-floor"})
    assert(lamour(song, song_rhythm, 4, style) == Frame{});
  for (auto invalid : {R"({"name":"bad","output_gamma":0})", R"({"name":"bad","output_gamma":4})", R"({"name":"bad","transition_seconds":6})",
                       R"({"name":"bad","cues":[{"level":2}]})",
                       R"({"name":"bad","cues":[{"speed":0}]})",
                       R"({"name":"bad","cues":[{"sustain":-1}]})",
                       R"({"name":"bad","cues":[{"variant":1.5}]})"}) {
    write_show(invalid);
    throws([&] { Show::load("build/player/test-show.json"); });
  }
  write_show(
      R"({"name":"test","title":"Zażółć gęślą jaźń","intro_seconds":2,"cues":[{"at":0.2,"duration":0.5,"text":"HELLO","effect":"strings"}]})");
  auto show = Show::load("build/player/test-show.json");
  assert(caption(show, 0) == show.title && caption(show, 2.3) == "HELLO");
  assert(render(show, media, -1) == Frame{});
  assert(render(show, media, 1) != Frame{});
  assert(render(show, media, 2.3) == render(show, media, 2.3));
  write_show(R"({"name":"bad","gain":2})");
  throws([&] { Show::load("build/player/test-show.json"); });
  write_show(R"({"name":"bad","style":"typo"})");
  throws([&] { Show::load("build/player/test-show.json"); });
  throws([&] { Media("/nonexistent"); });
  std::cout << "Native player: wire vectors, CRC rejection, cached retries, "
               "clock jumps, 2-hour queue/wrap, POSIX tty, analysis, text and "
               "cue tests passed.\n";
}
