#include "controller.hpp"
#include <glib.h>
#include <chrono>
#include <thread>
#include <cassert>
#include <iostream>
#include <numeric>
#include <stdexcept>
extern "C" {
#include "font.h"
}
using namespace letki;
using namespace control;
namespace {
struct Spy : Transport {
  std::unique_ptr<Transport> inner = simulation();
  unsigned writes = 0, replacements = 0, mutations = 0;
  bool simulated() const override { return true; }
  void rate(unsigned n) override { inner->rate(n); }
  void advance(uint64_t n) override { inner->advance(n); }
  Frame pixels() override { return inner->pixels(); }
  std::vector<Bytes> exchange(const std::vector<Bytes> &messages,
                              int timeout) override {
    for (auto &wire : messages) {
      auto m = decode(wire);
      if (m.op >= 4)
        mutations++;
      if (m.op == 4) {
        assert(m.data[0] == 0);
        writes++;
        replacements += m.data[1];
      }
    }
    return inner->exchange(messages, timeout);
  }
};
template <class F> void throws(F f) {
  bool failed = false;
  try {
    f();
  } catch (const std::exception &) {
    failed = true;
  }
  assert(failed);
}
Bytes read(Chain &c, unsigned n) {
  c.inspect();
  Bytes p;
  for (unsigned at = 0; at < c.info[n].length; at += 47) {
    Bytes b;
    put16(b, at);
    b.push_back(std::min(47U, c.info[n].length - at));
    auto chunk = c.request(n, 17, b);
    p.insert(p.end(), chunk.begin(), chunk.end());
  }
  return p;
}
} // namespace
int main() {
  Preview preview;
  for (auto mode : {Mode::Scroll, Mode::Bounce, Mode::Fall, Mode::Still}) {
    auto p =
        compile("Zażółć gęślą jaźń 0123!?", mode, 50, 73);
    assert(p.text == "ZAŻÓŁĆ GĘŚLĄ JAŹŃ 0123!?");
    assert(p.bytes.size() == 48 + p.width);
    preview.set(p);
    unsigned lit = 0;
    for (unsigned t = 0; t < p.duration; t += 25) {
      auto f = preview.frame(t);
      for (auto &tile : f)
        for (auto v : tile) {
          assert(v == 0 || v == 73);
          lit += v;
        }
    }
    assert(lit > 0);
  }
  throws([] { compile("", Mode::Scroll, 75, 100); });
  throws([] { compile("🙂", Mode::Scroll, 75, 100); });
  throws([] { compile("Hello", Mode::Scroll, 0, 100); });
  for (const auto &bad : {std::string("\xc0\xaf", 2), // Overlong encoding.
                          std::string("\xed\xa0\x80", 3), // Surrogate.
                          std::string("\xf4\x90\x80\x80", 4), // Above Unicode range.
                          std::string("\xe2\x82", 2), // Truncated sequence.
                          std::string("A\0B", 3), std::string("\x80", 1)})
    throws([&] { compile(bad, Mode::Still, 75, 100); });
  throws([] { compile(" \t\n\r", Mode::Still, 75, 100); });
  throws([] { compile("\u2003", Mode::Still, 75, 100); });
  assert(compile("Straße", Mode::Still, 75, 100).text == "STRASSE");
  assert(compile("A\r\nB\tC", Mode::Still, 75, 100).text == "A  B C");
  throws([] { compile(std::string(300, 'A'), Mode::Bounce, 500, 100, true,
                       {Font::Bold, Modulation::Steady, 5, 1}); });
  auto peak = [](const Frame &f) {
    unsigned v = 0;
    for (auto &tile : f)
      for (auto p : tile)
        v = std::max(v, unsigned(p));
    return v;
  };
  for (auto font : {Font::Compact, Font::Large, Font::Bold}) {
    for (auto mod : {Modulation::Breathe, Modulation::Blink}) {
      auto p = compile("ĄĆĘŁŃÓŚŹŻ 0123!?", Mode::Still,
                       50, 95, true, {font, mod, 5, 2});
      preview.set(p);
      for (unsigned t : {0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000}) {
        unsigned phase = t % 2000;
        unsigned expected = mod == Modulation::Blink ? (phase < 1000 ? 5 : 95)
                            : phase == 0 ? 5 : phase == 1000 ? 95 : 50;
        assert(peak(preview.frame(t)) == expected);
      }
      for (auto mode : {Mode::Scroll, Mode::Bounce, Mode::Fall}) {
        p = compile("ŁÓDŹ 42", mode, 47, 100, true,
                    {font, mod, 0, 6});
        preview.set(p); // Actual firmware validation, including track bounds.
        assert(p.bytes[6] <= 16);
        unsigned lit = 0;
        for (unsigned t = 0; t < p.duration; t += 20)
          lit += peak(preview.frame(t));
        assert(lit);
        for (unsigned i = 1; i < p.bytes[6]; i++) {
          unsigned a = 16 + (i - 1) * 32, b = a + 32;
          assert(get32(p.bytes, a + 4) + get32(p.bytes, a + 8) ==
                 get32(p.bytes, b + 4));
          assert(get16(p.bytes, a + 26) == get16(p.bytes, b + 22));
          assert(get16(p.bytes, a + 28) == get16(p.bytes, b + 24));
          if (mod == Modulation::Breathe)
            assert(p.bytes[a + 31] == p.bytes[b + 30]);
        }
      }
    }
  }
  // All eight original rows/Polish marks survive; bold grows to the right.
  auto large = compile("B", Mode::Still, 75, 100, true,
                       {Font::Large, Modulation::Steady, 5, 2});
  preview.set(large);
  auto regular = preview.frame(0);
  for (unsigned y = 0; y < 8; y++)
    assert(regular[2][y * 8] == 100); // Original B's full-height left stem.
  for (char32_t ch : std::u32string(U"ĄĆĘŁŃÓŚŹŻ")) {
    for (auto font : {Font::Large, Font::Bold}) {
      char encoded[6];
      std::string character(encoded, g_unichar_to_utf8(ch, encoded));
      auto p = compile(character, Mode::Still, 75, 100, true,
                       {font, Modulation::Steady, 5, 2});
      unsigned asset = get16(p.bytes, 32);
      for (unsigned x = 0; x < p.width - 1; x++) {
        uint8_t expected = font_column(wchar_t(ch), x);
        if (font == Font::Bold && x)
          expected |= font_column(wchar_t(ch), x - 1);
        unsigned actual = 0;
        for (unsigned y = 0; y < 8; y++) {
          unsigned bit = y * p.width + x;
          if (p.bytes[asset + bit / 8] & (1 << (bit % 8)))
            actual |= 1 << y;
        }
        assert(actual == expected);
      }
    }
  }
  auto once = compile("HELLO", Mode::Still, 75, 90, false,
                      {Font::Large, Modulation::Breathe, 0, 1});
  preview.set(once);
  assert(peak(preview.frame(2000)) == 90);
  assert(peak(preview.frame(5000)) <= 1); // End holds; it never starts another pulse.
  auto decomposed = compile("Z\u0307", Mode::Still, 75, 100);
  assert(decomposed.bytes == compile("Ż", Mode::Still, 75, 100).bytes);
  throws([] { compile("A", Mode::Still, 75, 30, true,
                       {Font::Large, Modulation::Breathe, 50, 2}); });
  auto spy = std::make_unique<Spy>();
  auto *wire = spy.get();
  Chain c(std::move(spy));
  // Regression: 54 characters in Bold at 92 ms/pixel fitted RAM but the old
  // compiler rejected this 82-second bounce as if the track limit were global.
  for (auto mod : {Modulation::Steady, Modulation::Breathe, Modulation::Blink}) {
    auto longCycle = compile(std::string(45, 'W') + std::string(9, ' '), Mode::Bounce,
                             92, 97, true, {Font::Bold, mod, 5, 1});
    assert(longCycle.width == 486 && longCycle.duration == 82064);
    assert(longCycle.bytes.size() == 566);
    assert(longCycle.bytes[6] == 2);
    upload_ram(c, longCycle);
    for (unsigned n = 0; n < 5; n++)
      assert(read(c, n) == longCycle.bytes);
    preview.set(longCycle);
    Preview expected;
    for (unsigned t : {20, 41032, 59980, 60000, 60020, 82044, 82064, 102064}) {
      // This includes the firmware's 60s clock-anchor normalization and wrap
      // to the beginning of another complete text cycle.
      expected.set(longCycle);
      auto reference = expected.frame(t % longCycle.duration);
      assert(preview.frame(t) == reference);
    }
    for (unsigned i = 0; i < longCycle.bytes[6]; i++)
      assert(get32(longCycle.bytes, 16 + i * 32 + 12) <= 60000);
  }
  auto slowScroll = compile(std::string(140, 'A'), Mode::Scroll, 500, 100);
  assert(slowScroll.duration == 300000 && slowScroll.bytes[6] == 5);
  assert(slowScroll.bytes.size() == 736); // Full five-minute cycle still fits RAM.
  upload_ram(c, slowScroll);
  for (unsigned n = 0; n < 5; n++)
    assert(read(c, n) == slowScroll.bytes);
  auto beforeWrites = wire->writes;
  auto p = compile("CZEŚĆ ADAŚ", Mode::Bounce, 50, 90,
                    true, {Font::Bold, Modulation::Breathe, 5, 3});
  upload_ram(c, p);
  assert(wire->writes == beforeWrites + 5);
  for (unsigned n = 0; n < 5; n++)
    assert(read(c, n) == p.bytes);
  preview.set(p);
  auto now = monotonic_ms() + 700;
  auto actual = c.pixels(now);
  for (unsigned n = 0; n < 5; n++) {
    auto t = c.request(n, 3);
    assert(actual[n] == preview.frame(get32(t, 4))[n]);
  }
  c.all(9);
  c.inspect();
  for (auto &i : c.info)
    assert(i.raw[20] & 1);
  control::play(c, false);
  c.all(12, {0});
  c.inspect();
  for (auto &i : c.info)
    assert(i.raw[32] == 0);
  // A stream preserves the saved RAM program and leaves its final frame lit.
  begin_stream(c);
  assert(!c.resume_on_close && c.format == 1 && c.slots >= 2 && c.baud == 230400);
  Frame frame{};
  for (unsigned n = 0; n < 5; n++)
    for (unsigned pixel = 0; pixel < 64; pixel++)
      frame[n][pixel] = (pixel * 3 + n * 17) % 101;
  auto deadline = monotonic_ms() + 120;
  c.frame(frame, deadline);
  uint64_t simulationDue = deadline;
  for (const auto &clock : c.clocks)
    simulationDue = std::max(simulationDue, uint64_t(deadline + clock.offset));
  auto streamed = c.pixels(simulationDue + 1);
  for (unsigned n = 0; n < 5; n++) {
    assert(read(c, n) == p.bytes);
    for (unsigned pixel = 0; pixel < 64; pixel++) {
      unsigned quantized = (frame[n][pixel] * 15 + 50) / 100;
      assert(streamed[n][pixel] == quantized * 100 / 15);
    }
  }
  end_stream(c);
  assert(!c.resume_on_close && c.baud == 115200 &&
         c.pixels(simulationDue + 1000) == streamed);
  control::play(c, true);
  auto longText = compile(std::string(170, 'W'), Mode::Scroll, 10, 100);
  upload_ram(c, longText);
  auto replacement = compile(std::string(170, 'B'), Mode::Scroll, 10, 40);
  upload_ram(c, replacement);
  assert(wire->replacements >= 5);
  for (unsigned n = 0; n < 5; n++)
    assert(read(c, n) == replacement.bytes);
  c.inspect();
  auto mutations = wire->mutations;
  throws([&] { begin_stream(c); });
  assert(wire->mutations == mutations); // Refuse before pause/flush/queue changes.
  for (unsigned n = 0; n < 5; n++)
    assert(read(c, n) == replacement.bytes);
  auto oversized = compile(std::string(190, 'C'), Mode::Scroll, 10, 100);
  auto writes = wire->writes;
  throws([&] { upload_ram(c, oversized); });
  assert(wire->writes == writes);
  for (unsigned n = 0; n < 5; n++)
    assert(read(c, n) == replacement.bytes);
  // Controller's worker serializes stream commands and never restores a show
  // implicitly when it is destroyed. It must initialize its chain before start.
  {
    Controller controller;
    auto wait = [&] {
      const auto until = monotonic_ms() + 5000;
      while (controller.snapshot().busy && monotonic_ms() < until)
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
      assert(!controller.snapshot().busy);
      return controller.snapshot();
    };
    assert(controller.submit(Action::Connect, {}, {}, true));
    assert(wait().connected);
    assert(!controller.submitFrame(frame));
    assert(controller.submit(Action::Apply, p));
    assert(wait().applied == 1);
    assert(controller.submit(Action::StreamBegin));
    assert(wait().streaming);
    auto beforeFrames = controller.snapshot().streamed;
    throws([&] { controller.submitFrame(frame, monotonic_ms() - 1); });
    throws([&] { controller.submitFrame(frame, monotonic_ms() + 2000); });
    assert(controller.snapshot().connected && controller.snapshot().streaming);
    assert(controller.snapshot().streamed == beforeFrames);
    assert(controller.submitFrame(frame));
    assert(wait().streamed == 1);
    auto expectedFrame = frame;
    for (auto &tile : expectedFrame)
      for (auto &value : tile)
        value = ((value * 15 + 50) / 100) * 100 / 15;
    // Ending immediately after queue acknowledgement must drain its deadline;
    // otherwise a one-frame client could flush its sole frame before display.
    assert(controller.submit(Action::StreamEnd));
    assert(!wait().streaming);
    assert(controller.snapshot().pixels == expectedFrame);
    assert(controller.submit(Action::Resume));
    assert(wait().connected);
    Frame bad{};
    bad[4][63] = 101;
    throws([&] { controller.submitFrame(bad); });
    assert(controller.submit(Action::Apply, oversized));
    assert(!wait().error.empty());
    assert(controller.submit(Action::Connect, {}, {}, true));
    assert(wait().connected && controller.snapshot().error.empty());
    assert(controller.submit(Action::Disconnect));
    assert(!wait().connected);
  }
  std::cout << "Control: UTF-8 validation, three fonts, Polish text/motion, standalone breathe/blink, real-C preview, "
               "RAM-only upload/readback, safe staging/replacement, "
               "pause/resume, GRAY4 streams and capacity rejection passed.\n";
}
