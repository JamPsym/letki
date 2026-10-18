#pragma once
#include <vector>

namespace letki {
struct BeatAnchor {
  double at = 0, beat = 0;
};

// Stateless source-audio time -> continuous beat position. Negative positions
// before the first beat are intentional, so seeking never resets the phase.
struct Rhythm {
  double bpm = 120, offset = 0;
  std::vector<BeatAnchor> anchors;
  // Call after authoring/loading. Throws std::runtime_error for invalid maps.
  void validate() const;
  double position(double seconds) const;
  // Inverse map, including negative beats and nearest-segment extrapolation.
  double time(double beat) const;
};
} // namespace letki
