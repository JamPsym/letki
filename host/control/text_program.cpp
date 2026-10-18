#include "text_program.hpp"
#include <glib.h>
#include <limits>
#include <algorithm>
#include <cstring>
#include <dlfcn.h>
#include <stdexcept>
#include <set>
extern "C" {
uint8_t font_compact_column(wchar_t, uint8_t);
uint8_t font_column(wchar_t, uint8_t);
}
namespace control {
namespace {
std::string normalize_text(const std::string &input) {
  // Explicit length rejects embedded NULs as well as invalid/overlong UTF-8.
  // GLib does Unicode case conversion without relying on the process locale.
  if (input.size() > size_t(std::numeric_limits<gssize>::max()) ||
      !g_utf8_validate(input.data(), gssize(input.size()), nullptr))
    throw std::runtime_error("Text must contain valid UTF-8 without NUL bytes.");
  using GString = std::unique_ptr<gchar, decltype(&g_free)>;
  GString normalized(g_utf8_normalize(input.data(), gssize(input.size()),
                                     G_NORMALIZE_DEFAULT_COMPOSE), g_free);
  if (!normalized)
    throw std::runtime_error("Could not normalize UTF-8 text.");
  GString upper(g_utf8_strup(normalized.get(), -1), g_free);
  GString composed(g_utf8_normalize(upper.get(), -1,
                                   G_NORMALIZE_DEFAULT_COMPOSE), g_free);
  std::string text = composed.get();
  for (char &c : text)
    if (c == '\n' || c == '\r' || c == '\t')
      c = ' ';
  bool visible = false;
  for (const char *p = text.c_str(); *p; p = g_utf8_next_char(p))
    visible |= !g_unichar_isspace(g_utf8_get_char(p));
  if (!visible)
    throw std::runtime_error("Enter a message to preview and apply.");
  return text;
}
std::string character_utf8(gunichar c) {
  char data[6];
  return std::string(data, g_unichar_to_utf8(c, data));
}
} // namespace
TextProgram compile(const std::string &input, Mode mode, unsigned speed,
                    unsigned brightness, bool loop, Style style) {
  if (speed < 10 || speed > 500 || brightness > 100)
    throw std::runtime_error(
        "Speed must be 10–500 ms/pixel; brightness must be 0–100%.");
  if (style.minimum > 100 || style.pulses < 1 || style.pulses > 6)
    throw std::runtime_error("Minimum must be 0–100%; pulses must be 1–6.");
  if (style.modulation != Modulation::Steady && style.minimum > brightness)
    throw std::runtime_error("Minimum brightness must not exceed peak brightness.");
  TextProgram out;
  out.text = normalize_text(input);
  std::vector<uint8_t> columns;
  const std::string symbols = "0123456789.,!?-:+/'";
  const uint8_t digits[][3] = {
      {31, 17, 31}, {18, 31, 16}, {29, 21, 23}, {21, 21, 31}, {7, 4, 31},
      {23, 21, 29}, {23, 21, 31}, {1, 1, 31},   {31, 21, 31}, {31, 21, 29},
      {0, 16, 0},   {0, 24, 0},   {0, 23, 0},   {1, 21, 3},   {4, 4, 4},
      {0, 10, 0},   {4, 14, 4},   {16, 14, 1},  {0, 3, 0}};
  for (const char *p = out.text.c_str(); *p; p = g_utf8_next_char(p)) {
    const gunichar c = g_utf8_get_char(p);
    if (c == ' ') {
      columns.insert(columns.end(), style.font == Font::Compact ? 2 : 4, 0);
      continue;
    }
    auto symbol = c < 128 ? symbols.find(char(c)) : std::string::npos;
    int index = symbol == std::string::npos ? -1 : int(symbol);
    std::vector<uint8_t> glyph(style.font == Font::Compact ? 3 : 8, 0);
    for (unsigned x = 0; x < glyph.size(); x++) {
      if (style.font == Font::Compact)
        glyph[x] = index >= 0 ? digits[index][x] << 1
                              : font_compact_column(wchar_t(c), x);
      else if (index < 0)
        glyph[x] = font_column(wchar_t(c), x);
      else if (x >= 1 && x <= 5) {
        // Expand the same punctuation/digit forms to five by seven pixels.
        for (unsigned y = 0; y < 7; y++)
          if (digits[index][(x - 1) * 3 / 5] & (1 << (y * 5 / 7)))
            glyph[x] |= 1 << (y + 1);
      }
    }
    if (std::none_of(glyph.begin(), glyph.end(), [](uint8_t v) { return v; }))
      throw std::runtime_error("Unsupported character: " +
                               character_utf8(c));
    if (style.font == Font::Bold) {
      // An extra column preserves right-edge Polish marks during dilation.
      glyph.push_back(0);
      for (unsigned x = glyph.size() - 1; x > 0; x--)
        glyph[x] |= glyph[x - 1];
    }
    columns.insert(columns.end(), glyph.begin(), glyph.end());
    columns.push_back(0);
  }
  out.width = unsigned(columns.size());
  if (out.width > 4096)
    throw std::runtime_error(
        "The message is too long; split it into shorter messages.");
  int x0 = 0, x1 = 0, y0 = 0, y1 = 0;
  unsigned flags = 0;
  switch (mode) {
  case Mode::Scroll:
    out.duration = (out.width + 40) * speed;
    x0 = 40;
    x1 = -int(out.width);
    flags = 1;
    break;
  case Mode::Bounce:
    out.duration =
        std::max(1000U, 2 * unsigned(std::abs(40 - int(out.width))) * speed);
    x1 = 40 - int(out.width);
    flags = 2;
    break;
  case Mode::Fall:
    out.duration = 16 * speed;
    x0 = x1 = std::max(0, (40 - int(out.width)) / 2);
    y0 = -8;
    y1 = 8;
    flags = 1;
    break;
  case Mode::Still:
    out.duration = style.modulation == Modulation::Steady ? 1000 : 4000;
    x0 = x1 = std::max(0, (40 - int(out.width)) / 2);
    break;
  }
  struct Segment {
    unsigned start, length, flags;
    int x0, y0, x1, y1;
    unsigned low, high;
  };
  std::vector<Segment> segments;
  if (style.modulation == Modulation::Steady && out.duration <= 60000) {
    segments.push_back({0, out.duration, flags, x0, y0, x1, y1,
                        brightness, brightness});
  } else {
    // 60 seconds limits a track's interpolation period, not the entire show.
    // Split at envelope corners, bounce turns and the per-track period limit,
    // sharing one bitmap. Everything still plays without PC streaming.
    const bool modulated = style.modulation != Modulation::Steady;
    const unsigned halves = modulated ? style.pulses * 2 : 1;
    std::set<unsigned> cuts{0, out.duration};
    for (unsigned i = 1; i < halves; i++)
      cuts.insert(unsigned(uint64_t(out.duration) * i / halves));
    if (mode == Mode::Bounce)
      cuts.insert(out.duration / 2);
    std::vector<unsigned> corners(cuts.begin(), cuts.end());
    for (unsigned i = 1; i < corners.size(); i++)
      for (unsigned at = corners[i - 1] + 60000; at < corners[i]; at += 60000)
        cuts.insert(at);
    auto position = [&](unsigned t, int a, int z) {
      int f = int(uint64_t(t) * 1000 / out.duration);
      if (mode == Mode::Bounce)
        f = f <= 500 ? 2 * f : 2 * (1000 - f);
      return a + (z - a) * f / 1000;
    };
    auto level = [&](unsigned t) {
      if (!modulated)
        return brightness;
      // Match the integer segment boundaries, including odd cycle lengths.
      unsigned h = std::min(halves - 1,
          unsigned((uint64_t(t + 1) * halves - 1) / out.duration));
      unsigned a = unsigned(uint64_t(out.duration) * h / halves);
      unsigned z = unsigned(uint64_t(out.duration) * (h + 1) / halves);
      if (style.modulation == Modulation::Blink)
        return (h % 2) ? brightness : style.minimum;
      unsigned fraction = (t - a) * 1000 / (z - a);
      int low = int(style.minimum), high = int(brightness);
      return unsigned(h % 2 ? high + (low - high) * int(fraction) / 1000
                            : low + (high - low) * int(fraction) / 1000);
    };
    for (auto it = cuts.begin(); std::next(it) != cuts.end(); ++it) {
      unsigned a = *it, z = *std::next(it);
      unsigned l0 = level(a);
      unsigned l1 = style.modulation == Modulation::Breathe ? level(z) : l0;
      segments.push_back({a, z - a, 1, position(a, x0, x1),
                          position(a, y0, y1), position(z, x0, x1),
                          position(z, y0, y1), l0, l1});
    }
  }
  if (segments.size() > 16)
    throw std::runtime_error("This text cycle needs more than 16 timeline segments. "
                             "Lower ms/pixel, shorten the message or reduce pulses.");
  unsigned asset = 16 + 32 * unsigned(segments.size());
  auto &b = out.bytes;
  b = {'L', 'G', 'S', '1'};
  letki::put16(b, asset + out.width);
  b.push_back(uint8_t(segments.size()));
  b.push_back(loop ? 1 : 0);
  letki::put32(b, out.duration);
  letki::put32(b, 0);
  for (auto &s : segments) {
    b.insert(b.end(), {2, 0, uint8_t(s.flags), 0});
    letki::put32(b, s.start);
    letki::put32(b, s.length);
    letki::put32(b, s.flags ? s.length : 0);
    letki::put16(b, asset);
    letki::put16(b, out.width);
    b.insert(b.end(), {8, 0});
    for (int v : {s.x0, s.y0, s.x1, s.y1})
      letki::put16(b, uint16_t(v));
    b.push_back(s.low);
    b.push_back(s.high);
  }
  b.resize(asset + out.width);
  for (unsigned x = 0; x < out.width; x++)
    for (unsigned y = 0; y < 8; y++)
      if (columns[x] & (1 << y)) {
        unsigned bit = y * out.width + x;
        b[asset + bit / 8] |= 1 << (bit % 8);
      }
  return out;
}
struct Preview::Impl {
  void *lib = nullptr, *sim = nullptr;
  void *(*create)() = nullptr;
  void (*destroy)(void *) = nullptr;
  unsigned (*source)(void *, const uint8_t *, unsigned) = nullptr;
  const uint8_t *(*render)(void *, unsigned, uint32_t) = nullptr;
  letki::Bytes data;
  ~Impl() {
    if (sim)
      destroy(sim);
    if (lib)
      dlclose(lib);
  }
};
Preview::Preview() : p(new Impl) {
  p->lib = dlopen("build/general/libletki-general.so", RTLD_NOW | RTLD_LOCAL);
  if (!p->lib)
    throw std::runtime_error(
        "Build the firmware simulator first: make control");
  p->create =
      reinterpret_cast<decltype(p->create)>(dlsym(p->lib, "lg_sim_create"));
  p->destroy =
      reinterpret_cast<decltype(p->destroy)>(dlsym(p->lib, "lg_sim_destroy"));
  p->source =
      reinterpret_cast<decltype(p->source)>(dlsym(p->lib, "lg_sim_source"));
  p->render =
      reinterpret_cast<decltype(p->render)>(dlsym(p->lib, "lg_sim_render"));
  if (!p->create || !p->destroy || !p->source || !p->render)
    throw std::runtime_error("Incompatible firmware simulator");
  p->sim = p->create();
  if (!p->sim)
    throw std::bad_alloc();
}
Preview::~Preview() = default;
void Preview::set(const TextProgram &program) {
  p->data = program.bytes;
  if (!p->source(p->sim, p->data.data(), p->data.size()))
    throw std::runtime_error("Invalid text program");
}
letki::Frame Preview::frame(uint32_t position) {
  letki::Frame f{};
  if (!p->data.empty())
    for (unsigned n = 0; n < 5; n++)
      std::memcpy(f[n].data(), p->render(p->sim, n, position), 64);
  return f;
}
} // namespace control
