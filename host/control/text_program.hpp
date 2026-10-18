#pragma once
#include "player.hpp"
#include <string>
namespace control {
enum class Mode { Scroll, Bounce, Fall, Still };
enum class Font { Compact, Large, Bold };
enum class Modulation { Steady, Breathe, Blink };
struct Style {
  Font font = Font::Compact;
  Modulation modulation = Modulation::Steady;
  unsigned minimum = 5, pulses = 2;
};
struct TextProgram {
  letki::Bytes bytes;
  unsigned width = 0, duration = 0;
  std::string text;
};
TextProgram compile(const std::string &, Mode, unsigned speed, unsigned brightness,
                    bool loop = true, Style style = {});
// Uses the exact C firmware interpreter, with host-owned draft assets.
class Preview {
  struct Impl;
  std::unique_ptr<Impl> p;

public:
  Preview();
  ~Preview();
  void set(const TextProgram &);
  letki::Frame frame(uint32_t position);
};
} // namespace control
